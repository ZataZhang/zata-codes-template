# Verifier Report: PRD 执行锁与看板运行态

- 审查对象：PRD `tasks/pending/P2-FEAT-20260915-112126-prd-execution-lock.md`、证据包 `tasks/evidence/P2-FEAT-20260915-112126-prd-execution-lock/`、实现代码（`scripts/shared/just/prd_lock.py`、`prd_status.py`、`justfile.shared`、`scripts/shared/worktree/create.sh`、`executor_prompt.txt`、`hooks/shared/check_prd_lock_conflict.py`、`.pre-commit-config.yaml`、`tests/guards/shared/test_prd_lock.py`、补全脚本、文档）
- 审查时间：2026-09-15；审查人：独立 verifier（未参与实现）
- 方法：日志核对 + 关键结论亲自重跑 + 对抗性代码审查 + 自建 fixture 压测竞态

## 独立重跑结果（不只信日志）

| 验证项 | 命令 | 结果 |
|---|---|---|
| rv-1 单测 | `uv run pytest tests/guards/shared/test_prd_lock.py -q` | ✅ 11 passed |
| 守卫全量回归 | `uv run pytest tests/guards/ -q` | ✅ 168 passed |
| rv-2 核心断言（自建 fixture `/tmp/verifier-prd-lock-rv2`，git init + 真实 justfile + symlink scripts/hooks + 两个真实 linked worktree） | 两 worktree 并发 `just prd start` | ✅ 恰一次退出 0、一次退出 1；拒绝输出含持锁者 tool/branch/worktree/开始时间/最后心跳 |
| 过期接管 | backdate 心跳 2h 后再次 `just prd start` | ✅ 退出 0，`active.lock.<ts>.stale` 留档存在 |
| 看板运行态（真实仓库） | `just prd status pending` | ✅ ACTIVITY 列出现 `RUNNING kimi 27m @main`（本 PRD 的活锁） |
| 锁不进 git | `git check-ignore -v .../active.lock` | ✅ 命中 `.gitignore:69:tasks/evidence/**` |
| 证据包密钥扫描 | `./scripts/shared/just/scan_evidence_secrets.sh <证据目录>` | ✅ 无命中，退出 0 |
| 钩子恒退出 0 | 无参数 / 无 `--warn-only` / 触及他人新鲜锁 三种路径直跑钩子 | ✅ 全部退出 0；第三种路径输出 `[WARNING]` 且含持锁者信息 |
| 纯标准库 | `grep '^import \|^from '` 两个新脚本 | ✅ 仅标准库（外加同目录 `prd_lock` 自引用） |
| rv-6 文档断言 | rg tooling.md / AGENTS.md / 两个补全脚本 / executor_prompt.txt | ✅ 全部命中；`<PRD_FILE>` 替换在 `justfile.shared:647` |

fixture 用完已清理（`git worktree remove` + `rm -rf /tmp/verifier-prd-lock-rv2`），未动任何 git 变更命令。

## Findings

### BLOCKER

**B-1：过期锁接管路径不是原子的，并发接管会双方成功（实测 5/10 轮双成功），互斥在 stale 场景失效。**

`prd_lock.py` `claim_lock()`（scripts/shared/just/prd_lock.py:322-330）的接管路径是 check-then-act：读锁 → `is_lock_stale` → `os.rename` 留档 → `_write_lock_file(exclusive=False)`（`os.replace` 无条件覆盖）。没有任何排他 guard：

- 两个进程可同时通过 stale 判定；
- 后一个 `os.rename(lock_path, archive)` 甚至可能把**前者刚写入的新锁**当成旧锁归档掉（留档文件名只有秒级精度，同秒还互相覆盖）；
- 随后两个 `os.replace` 都成功，两个会话都拿到退出 0、都认为自己持有锁。

独立复现（自建 fixture，预置同一把 backdate 2h 的过期锁，wt-b 与主仓库并发 claim，10 轮）：**第 1/2/5/7/9 轮双方退出码均为 0**。这直接违反 PRD Measurable Objective"对同一 PRD 并发执行两次开工命令：恰好一次成功、一次被拒绝"——该目标并未把过期锁场景排除在外；Risk Register 也把"claim 原子性与接管语义"列为 R2（失败=重复开工防护失效）。现实触发场景并不罕见：原会话死亡（锁过期）后，用户把同一 PRD 交给两个 agent、或自己重试时另一个 agent 也在重试。

修复方向（供参考，非处方）：留档后用**排他**创建写新锁（`_write_lock_file(exclusive=True)`），`FileExistsError` 时回退重新读锁重新判定（retry 循环）；或在判定+接管全程加 per-PRD 的 flock sentinel。注意现有单测只覆盖"无锁并发"（`test_concurrent_claim_from_two_worktrees_exactly_one_wins`），没有覆盖"过期锁并发接管"，修复时应补该用例。

### NON-BLOCKING

- **N-1：D-10 移交规则可被任意 worktree 用于"顺走"主仓库持有的新鲜锁。** 实测：主仓库 claim（tool=A）后数秒内，从任一连结 worktree claim → 退出 0，锁被移交。这意味着"新鲜锁硬拒绝"对 `worktree=""` 的锁不成立——包括人在主仓库 ad-hoc `just prd start` 持有的锁，以及 `just implement` 领锁到 executor 自检之间的窗口期。这是 D-10 明文记录的设计取舍（移交无法区分合法 executor 与其他会话），但对抗面比 PRD 行文暗示的更宽，建议后续评估加宽限条件（如仅在锁龄很新且 ai_tool 匹配时移交）。
- **N-2：移交不更新 `branch` 展示字段。** 移交只改 `worktree` / `heartbeat_at`（及可选 `ai_tool`），`branch` 仍为主仓库领锁时的值。实测移交后锁内 `worktree=../wt-a` 而 `branch=main`，看板会显示 `RUNNING <tool> @main` 而持有者其实在 worktree——展示层误导，不影响互斥。
- **N-3：`_write_lock_file` 的临时文件 `active.lock.tmp.<pid>` 在进程被杀于 write 与 link/replace 之间时会残留**（已被 gitignore 覆盖，无害但会累积；stale 留档名秒级精度，同秒双接管时 `os.rename` 会静默覆盖其中一个留档——留档仅作排查用途，影响小）。
- **N-4：naive/aware datetime 混用未防护。** 手写锁（或旧格式锁）若 `heartbeat_at` 为不带时区的 ISO 串，`is_lock_stale` 的 `now - heartbeat` 会抛未捕获的 `TypeError` 使 claim 以 traceback 崩溃而非按过期处理；`prd_status.py:455` 对 `started_at` 同理。自家写入端恒输出带时区时间，仅影响手工构造的锁。
- **N-5：`prd_status.py` 弱信号探测用 worktree 本地 `evidence_root`，锁查询用主仓库根。** 在 linked worktree 内跑看板时，`⚡` 弱信号扫的是 worktree 自己（通常不存在）的 `tasks/evidence`，与锁视图来源不一致；另外 `.stale` 留档与证据文件都计入 mtime 弱信号，刚释放/刚接管的 PRD 会短暂显示 `⚡`——作为"近期有活动"信号可接受，但值得知晓。
- **N-6：`executor_prompt.txt` 基线对齐项形式上未闭环。** §9 Delivery Readiness 要求与 ai-self-verify PRD 对齐 `executor_prompt.txt` 基线；该 P1 PRD 目前仍在 `tasks/pending/`（双方均未落地），当前文本冲突尚未实际发生，但验收项的"已合并先落地者文本"严格说无法判定。建议归档前在 PRD 里注明此项为"对方未落地，无需对齐"。

### SECURITY

无。证据包密钥扫描复跑无命中；锁 JSON 只含 pid/hostname/路径/时间/自报工具名，无凭据。

## §9 Acceptance Checklist 逐条核对

| 验收项 | 证据 | 判定 |
|---|---|---|
| 新鲜锁策略（拒绝+接管留档） | rv-2.log + 本人独立重跑 | ✅ 有真实入口证据 |
| R2 并发唯一成功 | rv-2.log + 红跑（rv-2.red.log、去 O_EXCL 替身双成功）+ 本人重跑 | ⚠️ 无锁并发成立，但**过期锁并发接管双成功**（B-1） |
| 锁唯一事实源在主仓库 | rv-1 用例断言 + 本人重跑 | ✅ |
| 锁文件不进 git | 本人重跑 check-ignore 命中 | ✅ |
| 未新增第三方依赖 | 本人 grep | ✅ |
| 三子命令可用 + usage | rv-2.log 场景 C | ✅ |
| 看板三标注 | rv-3.log（RUNNING/STALE/⚡ 同屏）+ 真实仓库 RUNNING 实测 | ✅ |
| implement 新鲜锁中止不建 worktree | rv-4.log（真实 recipe，退出 1，无 repo-worktrees 目录） | ✅（只测拒绝路径，符合验证计划声明） |
| worktree 匹配分支名拒绝创建 | rv-7.log | ✅（同上） |
| 提交钩子警告但退出 0 | rv-5.log + 本人三路径重跑 | ✅ |
| 文档/补全断言 | 本人 rg 重跑全部命中 | ✅ |
| executor_prompt 第 0 步 + `<PRD_FILE>` | executor_prompt.txt:5 + justfile.shared:647 | ✅ |
| 真实入口验证非仅单测 | rv-2~rv-5、rv-7 均为真实 just/钩子命令日志；本人独立 fixture 复核 | ✅ |
| `test_prd_lock.py` 全绿 | 本人重跑 11 passed | ✅ |
| 证据包按 rv-id 命名落位 | 目录核对 | ✅ |
| 无遗留临时兼容层 / lint 无回归 | 证据报告已披露 check-guard-test-modification 需人工 `GUARD_UPDATE_ACK=1`（新增守卫测试属预期动作，留待提交时确认）；guards 168 passed 本人重跑 | ✅（披露充分） |

证据可信度说明：fixture 通过 symlink 复用本仓库 `scripts/`、`hooks/` 与 `justfile.shared`，被测的是实现本体；本人在独立目录重建了同类 fixture 复核 rv-2 核心断言，结果一致。rv-4/rv-7 只测拒绝路径已在验证计划中预先声明（claim 失败发生在建库/建目录之前，无副作用），不构成偷降保真度。

## 结论

B-1 是 PRD 并发防护核心（R2）上的实证互斥失效，必须修复并重跑（含补充"过期锁并发接管"用例）；其余为 NON-BLOCKING 记录项，不阻断。

VERDICT: REJECT

---

# 第 2 轮复审（2026-09-15，针对 B-1 / N-2 / N-3 / N-4 修复）

## 独立重跑结果

| 验证项 | 命令 / 方法 | 结果 |
|---|---|---|
| rv-1 单测 | `uv run pytest tests/guards/shared/test_prd_lock.py -q` 连跑 5 次 | ✅ 13 passed × 5，稳定 |
| 新增并发接管用例稳定性 | `test_concurrent_stale_takeover_exactly_one_wins` 单跑 10 次 | ✅ 10/10 passed（每次内含 10 轮竞态，共 100 轮） |
| 守卫全量回归 | `uv run pytest tests/guards/ -q` | ✅ 170 passed |
| **B-1 复现场景（自建 fixture `/tmp/verifier-prd-lock-r2`，独立重建）** | 每轮重置一把 `wt-old` 持有的过期锁并清空留档，wt-a / wt-b 经真实 `just prd start` 并发接管，连跑 20 轮 | ✅ 20/20 轮恰一方退出 0、另一方退出 1；每轮 `.stale` 留档恰好 1 份；最终锁为胜方新鲜锁、字段完整 |
| N-2 移交更新 branch | 主仓库 `--tool entry-tool` 领锁（branch=main）→ wt-b 自检移交 | ✅ 退出 0，锁内 `worktree=../wt-b`、`branch` 由 `main` 更新为 `wt-b`；顺带验证：wt-a 持有的新鲜锁在主仓库再 claim 仍被硬拒绝（互斥未因修复变松） |
| N-4 naive/损坏时间戳 | 手写 `heartbeat_at="2026-09-15 10:00:00"`（naive）后 claim | ✅ 按过期接管退出 0，无 traceback；`prd_status.py:453` 的时长渲染也已改走 `parse_lock_timestamp` |
| N-3 留档名 / 临时文件 | 20 轮竞态后检查证据目录 | ✅ 留档名带 pid（`active.lock.<ts>.<pid>.stale`），无 `.tmp.` 残留 |
| 红跑负控真实性 | 审 `rv-1.round2.red.log` | ✅ 移交 branch 断言与 naive 时间戳用例在未修复实现上确定性失败；并发接管用例 5 连跑中第 4 次失败（不稳定复现，见 N-2.2） |
| rv-2.log 重收 | 审场景 A2（wt-b / wt-c 并发接管过期锁） | ✅ B=0（留档+接管）、C=1（见持锁者信息），与本人 fixture 结果一致 |
| 密钥扫描（含第 2 轮新日志） | `scan_evidence_secrets.sh` | ✅ 无命中 |
| PRD / 证据报告同步 | 审 PRD §7 D-11 段与 evidence-report"第 2 轮修复"段 | ✅ 与代码实现一致，无夸大 |

fixture 用完已清理，未动 git 变更命令。

## 修复代码审查（claim_lock 重试链）

两段式接管 + 5 次有界重试在所有**两方**并发组合下已闭合：

- 双方同时接管同一过期锁：rename 败者 `OSError` → 重试 → 读到胜方新鲜锁 → 按他人新鲜锁拒绝；胜方逐字节核对归档内容后排他创建。✅（本人 20 轮实测）
- 接管 vs 第三者新鲜 claim 抢窗：排他创建恰一方成功；接管方 link 失败后重读到新鲜锁即拒绝。✅
- 重试耗尽（5 次未收敛）：退出 1 并明确提示"未收敛，请稍后重试"，不声称持锁。✅ 行为合理。

## 第 2 轮 Findings

### BLOCKER

无。

### NON-BLOCKING

- **N-2.1（残余理论竞态，第 1 轮 N 类延续）："放回"操作用的是覆盖式 `os.rename`（prd_lock.py:396-399）。** 内容核对不符时把归档放回 `lock_path`，若在此微秒级窗口内第三者已用排他 `os.link` 创建了新锁，POSIX rename 会**静默覆盖**它——第三者以为自己持锁而文件已是别人的锁。触发需三方对齐：原持锁方在判定与 rename 之间刷新心跳（造成内容不符）+ 第三者在放回窗口内排他创建成功，无法用黑箱压测复现（本轮 20 轮 + 实现方 80 轮均未触达该路径）。建议后续把放回改为 `os.link`（目标已存在则保留归档作排查留档）。鉴于窗口量级与三方前提，不阻断。
- **N-2.2：新增并发接管用例对旧 bug 的检出率约 1/5**（红跑日志实证：5 连跑仅第 4 次失败）。竞态检测用例天然时序敏感，作为回归网偏弱；本轮本人用 CLI 级 20 轮压测弥补了强度。后续若再动接管逻辑，建议在测试内加大并发轮次或加注入点。
- **N-2.3（cosmetic）：`tests/guards/shared/test_prd_lock.py:429` 有一行游离的 docstring 字符串**（"看板查询接口……"误置在 `test_unparseable_or_naive_heartbeat_treated_as_stale` 体内），无行为影响，顺手清理即可。
- 第 1 轮 N-1（D-10 移交可被任意 worktree 用于顺走主仓库新鲜锁）、N-5（弱信号 evidence 路径来源不一致）、N-6（executor_prompt 基线对齐项待注明）维持原判，均为设计取舍或披露项，不阻断。

### SECURITY

无。第 2 轮新增日志复扫无密钥泄漏。

## 第 2 轮结论

第 1 轮唯一 BLOCKER（B-1）已修复并经本人独立 fixture 20 轮并发压测验证闭合；N-2/N-3/N-4 修复逐条核实属实；新增红跑负控真实（未修复实现上确定性/不稳定地红）。残余问题均为 NON-BLOCKING 记录项。

VERDICT: PASS
