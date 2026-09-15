# Verification Plan: PRD 执行锁与看板运行态

对应 PRD：`tasks/pending/P2-FEAT-20260915-112126-prd-execution-lock.md`
本文件把 §9 Acceptance Checklist 每条验收项映射到具体可执行命令；证据按 rv-id 命名落在本目录。

## 验收项 → 命令映射

### Human-Confirmed / R2

- **新鲜锁策略 + 并发开工唯一成功（rv-2）**
  - 负控（实现前红跑）：fixture 仓库内 `just prd start tasks/pending/<fixture>.md`，子命令不存在 → usage 退出 1，存 `rv-2.red.log`；另在 rv-2 场景脚本内用 tests 侧替身（去掉 O_EXCL 的 `"w"` 写入）演示并发双成功，同存 `rv-2.red.log`。
  - 正跑：fixture 仓库内对同一 PRD 从主仓库与另一 worktree 并发执行 `just prd start` → 恰一次退出 0、一次退出 1 且输出持锁者 ai_tool/branch/心跳时间；backdate 心跳后再次执行 → 退出 0 且出现 `active.lock.<ts>.stale` 留档。存 `rv-2.log`。

### Architecture Acceptance

- **锁唯一事实源在主仓库（rv-1）**：`uv run pytest tests/guards/shared/test_prd_lock.py -v`，其中 worktree 用例断言锁落主仓库 `tasks/evidence/<stem>/active.lock` 且 worktree 内同名路径不存在。存 `rv-1.log`。
- **锁文件不进 git**：真实仓库内 `git check-ignore tasks/evidence/P2-FEAT-20260915-112126-prd-execution-lock/active.lock` 命中 + `git status --porcelain tasks/evidence/` 不出现锁文件。存 `rv-2.log` 附加段。
- **未新增第三方依赖**：`rg -n "^import|^from" scripts/shared/just/prd_lock.py hooks/shared/check_prd_lock_conflict.py` 仅标准库。存 `rv-6.log` 附加段。

### Behavior Acceptance

- **三个子命令可用 + usage 更新（rv-2）**：`just prd start / heartbeat / release` 在 fixture 仓库逐个实测；`just prd badsub` 打印新 usage。存 `rv-2.log`。
- **看板三种标注（rv-3）**：fixture 仓库 `just prd status pending` 分别构造 RUNNING（真实 claim，含 --tool/--branch）/ STALE（backdate 心跳）/ ⚡（无锁 + touch PRD 文件）三种状态并截图文本输出。存 `rv-3.log`。
- **implement 中止（rv-4）**：fixture 仓库预置他人新鲜锁后 `just implement tasks/pending/<fixture>.md claude` → 退出非零、输出持锁者信息、worktree 目录未创建。只测拒绝路径，不启动真实 AI。存 `rv-4.log`。
- **worktree 拒绝（rv-7）**：fixture 仓库预置他人新鲜锁后 `just worktree <匹配分支名>` → 退出非零、输出持锁者信息、目标目录未落地。只测拒绝路径（claim 失败发生在建库/建目录之前）。存 `rv-7.log`。
- **提交钩子警告但退出 0（rv-5）**：fixture 仓库预置他人新鲜锁 + staged 变更触及该 PRD 的 `tasks/pending` 路径，直接运行 `uv run python hooks/shared/check_prd_lock_conflict.py <staged-files>` → stdout 含警告、退出 0。存 `rv-5.log`。

### Documentation Acceptance

- **文档与补全搜索断言（rv-6）**：`rg -n 'prd (start|heartbeat|release)' docs/ai-standards/tooling.md AGENTS.md scripts/shared/just/worktree_completion.bash scripts/shared/just/worktree_completion.zsh` 每处命中。存 `rv-6.log`。
- **executor_prompt 第 0 步**：`rg -n 'just prd start|just prd heartbeat' scripts/shared/just/executor_prompt.txt` 命中；`<PRD_FILE>` 占位符替换在 rv-4 的 implement 前置 claim 拒绝输出中间接覆盖，另以 `rg -n 'PRD_FILE' justfile.shared scripts/shared/just/executor_prompt.txt` 断言。存 `rv-6.log`。

### Validation Acceptance

- **真实入口验证**：rv-2 至 rv-5、rv-7 均为真实 `just` / 钩子命令日志（fixture 仓库 = 真实 git 仓库 + 真实 justfile import 链），非仅单元测试。
- **单元测试全绿（rv-1）**：`uv run pytest tests/guards/shared/test_prd_lock.py -v`。实现前先跑一次红（模块不存在，collection 失败）存 `rv-1.red.log`。
- **证据包落位**：本目录，按 rv-id 命名。

### Delivery Readiness

- `uv run pytest tests/guards/ -x -q` 无回归（存 `guards-regression.log`）；`just lint` 无新增告警。
- 密钥扫描：`./scripts/shared/just/scan_evidence_secrets.sh tasks/evidence/P2-FEAT-20260915-112126-prd-execution-lock`（存 `secrets-scan.log`）。

## Fixture 仓库约定

所有 rv-2/3/4/5/7 在 `/tmp/prd-lock-fixture/repo` 执行：`git init` + 拷贝真实 `justfile`、`justfile.shared`、`hooks/`、`scripts/`（symlink 到本仓库，保证跑的是实现本体）+ `tasks/pending/P2-FEAT-20260915-112126-prd-execution-lock.md` 的 fixture 副本。rv-4/rv-7 只测拒绝路径，不在 fixture 内启动 AI 或建 PostgreSQL。
