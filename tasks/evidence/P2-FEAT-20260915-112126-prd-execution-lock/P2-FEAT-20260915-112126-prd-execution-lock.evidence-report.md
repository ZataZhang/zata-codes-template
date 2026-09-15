# Evidence Report: PRD 执行锁与看板运行态

对应 PRD：`tasks/pending/P2-FEAT-20260915-112126-prd-execution-lock.md`
执行时间：2026-09-15。所有真实入口验证在 `/tmp/prd-lock-fixture/` 下的全新 git fixture 仓库完成（真实 `justfile` + symlink 到本仓库的 `justfile.shared` / `scripts` / `hooks`，即跑的是实现本体）；rv-4/rv-7 只测拒绝路径，未启动真实 AI、未建 PostgreSQL。

## 实现期 PRD 修订（先于实现完成，已落 PRD 正文 §6 与 Decision Log）

- **D-09（两轮迭代）**：过期判定最终为**只看心跳**（30 分钟）。PRD 原文的"持锁 pid 已死即可接管"在 CLI/agent 场景不成立：锁脚本命令结束即退出，且 agent 工具调用给每条命令开新会话（首轮改为记录会话首领 pid 后，真实仓库 dogfood 实测领锁数分钟看板即显示 STALE——会话首领随那条工具调用消亡）。"pid 已死"恒真会让互斥完全失效，故 pid/hostname 保留在锁 JSON 仅供排查展示，不参与判定。
- **D-10**：新增开工移交规则——主仓库持有的锁被同仓库 linked worktree 的 claim 移交（刷新心跳 + 更新 worktree 字段）。否则 `just implement`（主仓库领锁）之后 executor 在 worktree 的第 0 步自检必然撞自己入口的锁，FR-4 与 FR-6 自相矛盾。
- 锁写入改为"临时文件 + `os.link`（排他）/ `os.replace`（刷新）"整内容原子写入，消除排他创建后、JSON 写完前读者读到空文件误判过期的竞态（并发测试红跑实证）。

## 第 2 轮修复（verifier 第 1 轮 REJECT 之后）

- **B-1（BLOCKER）过期锁接管原子化**：原 takeover 是 check-then-act（判过期 → rename 留档 → 无条件 `os.replace` 覆盖），verifier 实测 10 轮并发接管 5 轮双成功。修复为两段式：rename 留档（文件名带时间戳 + pid）后**排他创建**新锁；rename 后逐字节核对归档内容，若抢到的是别人刚写入的新锁则立即放回并重新判定；整体包在 5 次有界重试循环内。任何并发组合下恰一方成功。决策记录见 PRD D-11。
  - 红跑证据：`rv-1.round2.red.log`——新增并发接管用例在未修复实现上 5 次连跑中第 4 次失败（双成功，不稳定复现）；移交 branch 断言与损坏时间戳用例确定性失败。
  - 绿跑证据：`rv-1.log`（13 项全绿，已重收于最终实现）；并发接管用例修复后连跑 8 次（每次 10 轮竞态，共 80 轮）全部恰好一方成功；fixture 真实入口并发接管压测 15 轮不变量全过（恰一个退出 0、恰一个 .stale 留档、最终锁为胜方新鲜锁）。
  - `rv-2.log` 已用最终实现重收，新增场景 A2：wt-a 的过期锁由 wt-b / wt-c 两个第三方 worktree 并发接管 → B=0（留档 + 接管）C=1（看到持锁者信息）。
- **N-2**：D-10 移交分支同步把 `branch` 更新为当前 worktree 实际分支（`test_main_repo_lock_is_adopted_by_linked_worktree_claim` 断言 `branch == "wt-adopt"`）。
- **N-3**：`_write_lock_file` 的临时文件清理由 try/finally 保证（首轮已实现，本轮核对保留）；`.stale` 留档名加入 pid（`active.lock.<时间戳>.<pid>.stale`）避免同秒覆盖。
- **N-4**：新增 `parse_lock_timestamp()`——无法解析 / 非字符串 / naive 时间戳一律返回 None，`is_lock_stale` 按"不可信即过期"处理不抛异常；`prd_status.py` 的时长渲染复用同一解析。`test_unparseable_or_naive_heartbeat_treated_as_stale` 覆盖（`"not-a-timestamp"` 与 `"2026-09-15 10:00:00"` 两种损坏形态）。

## 证据清单

### rv-1 — 锁脚本基础语义单元测试（含 worktree 落主仓库断言）

- 命令：`uv run pytest tests/guards/shared/test_prd_lock.py -v`
- 证据：`rv-1.log`（第 2 轮修复后重收，13 项全绿）；`rv-1.red.log`（第 1 轮实现前红跑：`ModuleNotFoundError: No module named 'prd_lock'`）；`rv-1.round2.red.log`（第 2 轮修复前红跑：并发接管双成功不稳定复现 + 移交 branch / 损坏时间戳确定性失败）
- 覆盖：claim 元数据齐全、同归属幂等且不被 create.sh 兜底覆盖工具名、5 轮双 worktree 并发恰一个成功、新鲜锁拒绝含持锁者信息、心跳过期接管留档、**pid 死亡不构成过期**（反向语义锁定，D-09）、**worktree 内 claim 落主仓库且 worktree 内无同名锁**（Architecture Acceptance 第一条）、主仓库锁被 worktree 移交、心跳/释放/强制释放语义、`inspect_prd_lock` 三态。
- 对应验收：rv-1；§9 "锁唯一事实源在主仓库"。

### rv-2 — 并发开工唯一成功 + 过期接管（真实 `just prd start`）

- 命令：`bash /tmp/prd-lock-fixture/rv2_scenario.sh`（内部为真实 `just prd start/heartbeat/release`）
- 证据：`rv-2.log`
  - 场景 A：两个不同 worktree 并发 `just prd start` → A 退出 0、B 退出 1，B 的输出含持锁者 ai_tool（kimi）/ branch（wt-a）/ worktree / 开始时间 / 最后心跳与显式释放提示；锁原文在主仓库，两个 worktree 内无锁文件。
  - 场景 B：心跳 backdate 2 小时后再 `just prd start` → 退出 0，输出"旧锁已过期"告示，`active.lock.20260915-173432.stale` 留档存在。
  - 场景 C：`just prd heartbeat` / `release` 退出 0；`just prd badsub` 退出 1 且 usage 含三个新子命令。
  - 负控替身：去掉排他创建的 `"w"` 写入两进程双成功，演示互斥的来源。
- 证据：`rv-2.red.log`（实现前 `just prd start ... --tool kimi` 红跑：recipe 不存在，退出 1）。
- 证据：`rv-2-real-repo.log`（真实仓库 dogfood：`just prd start` 领取本 PRD 锁成功；`git check-ignore -v` 命中 `.gitignore:69:tasks/evidence/**`；`git status --porcelain tasks/evidence/` 不含锁文件）。
- 对应验收：§9 Human-Confirmed 新鲜锁策略、R2 并发唯一成功、三个子命令可用、锁文件不进 git。

### rv-3 — 看板运行态三标注（真实 `just prd status pending`）

- 命令：`bash /tmp/prd-lock-fixture/rv3_scenario.sh`
- 证据：`rv-3.log`——同一次看板输出同时出现：
  - `RUNNING kimi 0m @prd-execution-lock`（真实 claim，含 `--tool/--branch`）
  - `STALE 2026-09-15T07:35:17...`（真实 claim 后 backdate 心跳）
  - `⚡ active 0m ago`（无锁但 PRD 文件刚改动）
- 对应验收：§9 "看板运行态三种标注实测各出现一次"。

### rv-4 — `just implement` 新鲜锁中止（真实 recipe，只测拒绝路径）

- 命令：`bash /tmp/prd-lock-fixture/rv4_scenario.sh`（预置他人新鲜锁后 `just implement tasks/pending/....md claude`）
- 证据：`rv-4.log`——输出持锁者信息 + "未创建 worktree、未启动 executor"，recipe 退出 1；`repo-worktrees` 目录不存在；`git worktree list` 仅主仓库。
- 对应验收：§9 "just implement 在新鲜锁下中止且不建 worktree"。

### rv-5 — warn-only 提交钩子（真实钩子 + 真实 staged 变更）

- 命令：`bash /tmp/prd-lock-fixture/rv5_scenario.sh`（真实 `git add` 构造 staged 变更，`uv run --no-project python hooks/shared/check_prd_lock_conflict.py --warn-only <staged-files>`）
- 证据：`rv-5.log`——stdout 含 `[WARNING] ... 该 PRD 正被其他会话执行：工具 claude、分支 other-session-branch ...`，退出码 0；不相关文件对照无警告退出 0。
- 对应验收：§9 "提交钩子警告但退出 0"。

### rv-7 — `just worktree` 匹配分支名 + 他人新鲜锁拒绝创建（只测拒绝路径）

- 命令：`bash /tmp/prd-lock-fixture/rv7_scenario.sh`（预置他人新鲜锁后 `just worktree P2-FEAT-20260915-112126-prd-execution-lock`）
- 证据：`rv-7.log`——输出"分支名匹配 pending PRD，先领取执行锁"→ 持锁者信息 → "拒绝创建 worktree"，退出 1；`repo-worktrees` 目录不存在。
- 对应验收：§9 "just worktree 在分支名匹配 + 他人新鲜锁下拒绝创建且不落地目录"。领锁路径（同归属幂等）由 rv-1 单元测试覆盖，避免真实建库副作用。

### rv-6 — 文档 / 补全 / 提示词文本断言

- 命令与证据：`rv-6.log`
  - `rg 'prd (start|heartbeat|release)'` 在 `docs/ai-standards/tooling.md`、`AGENTS.md`、两个补全脚本均命中（bash 补全的命中形式为 `"status start heartbeat release"` 单词表，见下）。
  - `executor_prompt.txt` 第 0 步含 `just prd start <PRD_FILE>` 自检与逐步 `just prd heartbeat` 约定；`<PRD_FILE>` 占位符替换在 `justfile.shared:647`。
  - `rg '^import |^from '`：`prd_lock.py` 与 `check_prd_lock_conflict.py` 仅标准库（外加同目录 `prd_lock` 自引用）。
- 对应验收：§9 Documentation Acceptance 全部。

### 其他门禁

- `secrets-scan.log`：`scan_evidence_secrets.sh` 无命中（证据包最终态复扫）。
- `guards-regression.log`：`uv run pytest tests/guards/ -x -q` → 168 passed，无回归。
- `full-suite.log`：`uv run pytest tests/ -q --no-header -p no:cacheprovider`（`just test` 本地档的 pytest 本体）→ 210 passed，无回归。
- `uv run mkdocs build --strict` 通过（文档改动未破站点构建）。
- `SKIP=check-test-flag just lint --full`（pre-commit 全量）：ruff / ruff-format / check-max-file-lines / **check-prd-lock-conflict（新钩子，Passed）** 等全部通过；唯一失败项是 `check-guard-test-modification`——它是提交期确认门：检测到 `tests/guards/` 下有改动（本任务**新增**守卫测试 `test_prd_lock.py`，归位符合 `tests/guards/shared/` 约定）时要求人提交时显式 `GUARD_UPDATE_ACK=1`。本次执行被明令禁止 `git add` / `git commit`，故该门留待人工提交时确认；同理 `just lint`（staged 档）因 `.pre-commit-config.yaml` 的修改处于 unstaged 状态被 pre-commit 自身拒绝（"configuration is unstaged"），非代码问题。

## 已知限制与说明

- fixture 仓库通过 symlink 复用本仓库 `scripts/` 与 `hooks/`，保证被测的是实现本体；`justfile` 为拷贝（内容一致）。
- rv-4/rv-7 只测拒绝路径（claim 失败发生在建 worktree/建库之前，无副作用）；成功路径的领锁语义由 rv-1 单元测试覆盖。
- 本 PRD 的执行锁目前在真实仓库中由本次会话持有（`just prd start --tool kimi` 已领，见 `rv-2-real-repo.log`），看板实测显示 `RUNNING kimi 19m @main`；会话结束后心跳停更，30 分钟后锁自然转为 STALE，作为看板清理信号。
