# Evidence Report: 本机只读文件与改动查看器（`just view`）

对应 PRD：`tasks/pending/P2-FEAT-20260921-111233-local-file-diff-viewer.md`
本目录：`tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/`（PRD stem 同名）
采集机器：macOS（darwin 27.0.0）；仓库 worktree `/Users/zata/code/zata_code_template/.iar-worktrees/issue-9`。

> 原始工件（PNG / TXT）被 `.gitignore` 白名单挡在版本库外，只存在于本机；三份 `.md` 报告随 PRD 一起提交。
> 证据脚本（`.iar/evidence/scripts/`）同样被忽略，不进交付 diff。

## 人审导航 / Human Review Navigation

三件你要亲眼看的东西，按顺序看即可。**每一项都已由执行器按同一命令复跑并核对过一次**（见下方「已替你核对过什么」）。

### 1. 一条命令开出查看器，右侧是带行号的真实源码（rv-1）

![rv-1 文件视图：左树 + 右侧 justfile.shared 带行号高亮源码](rv-1-viewer-file.png)

**本地图片，GitHub 上不显示。**

- 打开命令：`open "/Users/zata/code/zata_code_template/.iar-worktrees/issue-9/tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/rv-1-viewer-file.png"`
- 复现命令：`cd /Users/zata/code/zata_code_template/.iar-worktrees/issue-9 && bash .iar/evidence/scripts/rv1_file_view.sh`
- **逐项期望值**（**判据是不变式，不是固定数字**：文件树条数、改动文件数与增删统计都会随工作区变化，采集时刻的快照值只用于对照截图）：
  - 左侧文件树覆盖全部受版本控制文件：`git ls-files | wc -l` = 732，界面文件树 ≥ 该值（采集快照 745，多出的是本次新增的未跟踪文件）。
  - 右侧文件头显示 `justfile.shared`、`Just（Makefile 词法器近似）`、`1525 行 · 66.6 KB`（1525 = `wc -l justfile.shared`，固定）。
  - 正文行号从 `1` 起连续；第 1 行是 `# ────…` 分隔注释行（本地 `justfile.shared` 首行）。
  - 关键词法高亮生效：带 token span 的行 1375/1525。
  - 状态条为「只读视图 · 服务运行中」。

### 2. 改动视图的文件集合与增删统计和终端 `git diff` 一致（rv-2）

![rv-2 改动视图：左树只列改动文件 + 右侧逐行 diff](rv-2-viewer-diff.png)

**本地图片，GitHub 上不显示。**

- 打开命令：`open "/Users/zata/code/zata_code_template/.iar-worktrees/issue-9/tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/rv-2-viewer-diff.png"`
- 复现命令：`cd /Users/zata/code/zata_code_template/.iar-worktrees/issue-9 && bash .iar/evidence/scripts/rv2_diff_view.sh`
- **逐项期望值**（**判据是不变式**：界面两端必须与终端同参数输出逐项相同；下面的数字是采集时刻的快照，重跑后会随工作区变化，以「两端一致」为准）：
  - 左树文件集合与终端 `git diff HEAD --name-only` 逐一相同（采集快照：8 个文件）。
  - 每个条目的 `+N -M` 与终端 `git diff HEAD --numstat` 逐项相同。
  - 底栏合计与终端 `git diff HEAD --stat` 的合计行相同（采集快照：`8 个文件 +343 -67` ↔ `8 files changed, 343 insertions(+), 67 deletions(-)`）。
  - 右侧逐行 diff 有旧/新行号列，`+` 行为绿色、上文行为常规色。

![rv-2 分支基线：相对 main 的合并基点改动](rv-2-viewer-diff-baseline.png)

**本地图片，GitHub 上不显示。**

- 打开命令：`open "/Users/zata/code/zata_code_template/.iar-worktrees/issue-9/tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/rv-2-viewer-diff-baseline.png"`
- 说明：分支基线在自带 `.git` 的夹具仓库上采集（本仓库当前分支相对 `main` 无提交差异，工作区改动未提交，因此真实仓库上该基线为空）。夹具仓库 `feature/branch-baseline` 上界面 3 个文件 `+3 -2`，与终端 `git diff main...HEAD --name-only` / `--stat` 逐项相同。

### 3. 生命周期：复用、回收、陈旧登记（rv-3）

生命周期是纯终端行为，呈递物是捕获的终端输出：

- 打开命令：`open "/Users/zata/code/zata_code_template/.iar-worktrees/issue-9/tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/rv-3-lifecycle.txt"`
- 复现命令：`cd /Users/zata/code/zata_code_template/.iar-worktrees/issue-9 && bash .iar/evidence/scripts/rv3_lifecycle.sh`
- **逐项期望值**：
  - 第一次（冷启动）`just view` 起实例；第二次复用耗时 **34.0ms**、**进程号不变**（5369），且 `lsof` 显示端口仍由同一进程监听。（快照值随机器负载变化；判据是「进程号不变」与「远低于 150ms 预算」，`rv-5-performance.txt` 首行有当次 load average。）
  - `kill -9` 服务进程后保留登记 → 再执行打开命令输出「登记项已陈旧（pid …，端口 …），重新起服务。」并起新实例，`/api/info` 返回 **HTTP 200**。
  - `just view --stop` 后：登记文件不存在、进程不存活、`curl` 该端口 `HTTP 000`（连接失败）。
  - `just view --idle-timeout 3` 静置超过 3 秒后：进程退出、登记被清理、端口关闭；服务日志尾部有「查看器已闲置 4 秒（上限 3 秒），退出并清理登记。」
- **10 秒自检**：挑一次 `just view --stop` 之后立刻 `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<登记文件里的端口>/api/info`，应得 `000`。

### 4. 服务退出后页面给出「服务已退出」提示，而不是半渲染的坏页面（rv-7）

**本次新增的真实入口验证**。失效态只在下一次请求失败时出现（页面刻意不做心跳轮询），所以必须由浏览器真的发起一次请求——刷新页面不行，服务已退出时刷新只会得到浏览器自己的连接错误页。

![rv-7 失效态：左树置灰 + 内容区服务已退出提示 + 状态条重新连接指引](rv-7-disconnected-state.png)

**本地图片，GitHub 上不显示。**

- 打开命令：`open "/Users/zata/code/zata_code_template/.iar-worktrees/issue-9/tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/rv-7-disconnected-state.png"`
- 复现命令：`bash .iar/evidence/scripts/rv7_disconnected_state.sh`
- **逐项期望值**：
  - 内容区出现红框「服务已退出」提示，正文含「查看器空闲到时限后会自动退出（默认 30 分钟无任何请求），也可以用 just view --stop 立刻回收。」「在仓库里重新执行 just view 会新起一个实例并打开新标签页，本页不再自动恢复。」
  - 左下状态条变为红点 + 「服务已退出 · 运行 just view 重新连接」。
  - 左树整体置灰（`#tree-body` 带 `is-stale`），文件树本身仍在、不消失。
  - 顶部「过滤文件」与快捷键提示条不受影响。
- **负控对照**（证明这条断言会红）：`rv-7-disconnected-state-negative-control.png` —— 同一套驱动流程，界面资产换成「接口失败不切失效态」的副本（测试边界打桩，生产代码一行未改）：服务停掉后状态条仍是「只读视图 · 服务运行中」、左树未置灰、内容区没有提示块。

### 以下项不需要你看（`reviewer: verifier`）

只读边界与路径越界（rv-4）、进程侧性能预算（rv-5）、命令/文档/原型登记（rv-6）由 agent 自验 + verifier 复核。证据在同目录 `rv-4-readonly-boundary.txt` / `rv-5-performance.txt` / `rv-6-docs-registry.txt`。

> **rv-5 补充说明**：本次在负载 2–3 时重测两次，四条预算全部达标（复用命中中位 60.1 / 60.1ms，冷启动中位 88.6–115.7ms，超预算样本 0），负控两次都判红。但上一版在负载约 15 时同一份代码实测超标（复用中位 158.9ms、冷启动中位 419.1ms）——**这四条预算的值由机器负载主导，不是实现指标**。判定时请连着证据首行的 load average 一起读；口径限制已写入 `docs/guides/file-viewer.md`。仍有一项待你裁定：是否要求「机器满负荷时也达标」（见 PRD §12）。

### 已替你核对过什么

- rv-1 的截图与本地 `justfile.shared` 逐行比对过（1525 行全等，行号从 1 起连续）；执行器另外用**放大重渲染**确认首行确为 `# ────…` 注释行而非内容错位。
- rv-2 的 8 个文件集合、8 组 `+N -M`、以及合计行都对着终端 `git diff HEAD` 同参数输出逐项核过。
- rv-3 的进程号取自两次真实调用的输出，端口取自登记文件 `.env.view-state`，未使用文档里的默认值。
- rv-4 / rv-5 / rv-6 三条都跑过负控，确认「恒绿空断言」被排除（见下方各节）。
- **rv-5 重测达标，并保留了历史不达标记录**：本条不是「已核对未达标」，也不是「用一次空载重跑翻案」——两次达标采集、`-S` 交错 A/B、以及负载约 15 时的历史不达标数字同批归档，便于你自行复核任一份。预算数字一个都没改。

---

## 1. 交付概要

新增一条共享命令 `just view`（薄别名 `just diff`）与一个共享只读工具目录 `scripts/shared/view/`：

- `instance.py` — 常驻实例登记（`.env.view-state`）与仓库根定位，客户端与服务端共用。
- `workspace.py` — 只读工作区快照：文件树、文件正文、改动列表与单文件 diff；路径越界防护与基线白名单。
- `server.py` — 只读本机 HTTP 服务：路由白名单、仅接受读取方法、空闲回收、信号优雅退出。
- `launch.py` — 客户端入口：新鲜度三校验与复用、端口选择、轮询就绪、写登记、打开浏览器、`--stop`。
- `assets/` — 独立静态单页（`index.html` / `viewer.css` / `viewer.js`），零外部 CDN、零前端构建链。

配套：`justfile.shared` 新增两条 recipe；`pyproject.toml` 显式声明 `pygments`；`tests/guards/shared/test_view_server.py` 19 项守卫；`docs/ai-standards/tooling.md`、`docs/guides/file-viewer.md`、`docs/prototypes/*`、`mkdocs.yml` 同步。

## 2. rv-1 — 文件视图：内容与本地文件一致、行号、高亮

- 命令：`bash .iar/evidence/scripts/rv1_file_view.sh`
- 证据：`rv-1-viewer-file.png`（无头 Chrome 渲染**登记文件里的真实 URL**）、`rv-1-viewer-file.txt`
- 真实入口链：`just view justfile.shared --no-open` → `launch.py` → `server.py` 绑端口 → 浏览器请求 `/` → `/api/tree` → `/api/file`
- 关键输出：
  - `GET /api/file?path=justfile.shared -> HTTP 200`；`kind=text language=Just（Makefile 词法器近似） highlighted=True line_count=1525 size_label=66.6 KB`
  - 本地文件 1525 行；带 token span 的行 1375/1525；**逐行核对：一致**
  - `GET /api/tree -> HTTP 200`；终端受控文件 732；界面文件树 744（含未跟踪新文件，覆盖全部受控文件）
- fresh-state probe：脚本内第二次独立请求同一路径，仍逐行一致。
- 负控：`stub_server.py --stub fake-file-content`（进程内替换 `build_file_payload`，**生产代码未改**）→ 同一条逐行比对报出「行数不一致：接口 3 vs 本地 1525」「第 1 行内容不一致」，退出码 1。
- `expected_fail`：右侧内容与本地文件不符，或行号缺失/高亮缺失。**已观察到该失败形态**（打桩服务上）。

## 3. rv-2 — 改动视图：集合与增删统计和终端逐项一致

- 命令：`bash .iar/evidence/scripts/rv2_diff_view.sh`
- 证据：`rv-2-viewer-diff.png`、`rv-2-viewer-diff-baseline.png`、`rv-2-viewer-diff.txt`
- 工作区基线（真实 `just view --diff`）：

  | 文件 | 界面 | 终端 `--numstat` |
  |---|---|---|
  | docs/ai-standards/tooling.md | +28 -0 | (28, 0) |
  | justfile.shared | +26 -0 | (26, 0) |
  | mkdocs.yml | +1 -0 | (1, 0) |
  | pyproject.toml | +4 -0 | (4, 0) |
  | scripts/shared/README.md | +1 -1 | (1, 1) |
  | tasks/pending/P2-FEAT-….md | +111 -16 | (111, 16) |
  | tests/guards/README.md | +1 -0 | (1, 0) |
  | uv.lock | +2 -0 | (2, 0) |
  | **合计** | 8 文件 +174 -17 | `8 files changed, 174 insertions(+), 17 deletions(-)` |

- 单文件逐行 diff：`/api/diff?path=justfile.shared&base=worktree` 返回 `base_label=工作区改动 base_ref=HEAD rows=33 empty=False`，hunk 头 `@@ -225,6 +225,32 @@` 与终端 `git diff HEAD -- justfile.shared` 一致。
- 分支基线（夹具仓库 `feature/branch-baseline`，走同一条 `launch.py` 入口）：界面 3 文件 `+3 -2`，与 `git diff main...HEAD` 逐项一致（`A src/extra.py` / `M docs/notes.md` / `M src/module.py`）。
- fresh-state probe：终端向 `justfile.shared` 追加一行 → 界面 `(文件数, 新增行)` 由 `8 174` 变 `8 176` → 还原后回到 `8 174`。
- 负控：`stub_server.py --stub fake-git-output`（进程内多报一个终端不存在的文件）→ 断言报「文件集合不一致」「stub/not-in-terminal.txt 增删统计不一致：界面 (7, 3) vs 终端 None」，退出码 1。
- `expected_fail`：界面文件数与终端 `git diff HEAD --stat` 合计行不符。**已观察到该失败形态**。

## 4. rv-3 — 生命周期：复用、陈旧接管、显式与自动回收

- 命令：`bash .iar/evidence/scripts/rv3_lifecycle.sh`
- 证据：`rv-3-lifecycle.txt`
- 关键输出：
  - 冷启动 400.0ms（pid 19468）；第二次 **144.0ms，pid 不变**
  - `kill -9` 后（登记尚在）→「登记项已陈旧（pid 19468，端口 49477），重新起服务。」→ 新 pid 19552，`/api/info` HTTP 200
  - `--stop` 后：登记不存在、进程不存活、`curl` 端口 `HTTP 000`
  - `--idle-timeout 3` 静置后：进程退出、登记被清理、端口关闭，日志有闲置退出记录（「已闲置 4 秒（上限 3 秒）」）
- 负控：把登记里 `VIEW_PID` 换成一个**已退出**进程的进程号（只污染状态文件）→ 打开命令判陈旧、接管并打开可用页面（pid 19595，`/api/info` 200）。
- `expected_fail`：打开一个连接被拒或空白的页面，或命令直接报错退出。**已观察到该失败形态**（污染登记若被误判为新鲜即会如此）。

## 5. rv-4 — 只读边界与路径越界（reviewer: verifier）

- 命令：`uv run pytest tests/guards/shared/test_view_server.py -v` ＋ `bash .iar/evidence/scripts/rv4_readonly_boundary.sh`
- 证据：`rv-4-readonly-boundary.txt`
- 守卫测试 **19 passed**：越界拒绝、写方法名字不存在、非读方法与未知路由拒绝、正文逐行与行号、超大/二进制标记、分支基线合并基点、仅绑回环、增删统计对齐、陈旧登记接管、`-` 开头基线拒绝、目录同名不误剪、`--stop` 回收、二次启动复用、`--idle-timeout 0` 关闭自动回收、登记归属校验、空闲回收清理、登记被 git 忽略、单文件 diff 行号、畸形路径参数（内嵌 NUL 字节）必须得到拒绝应答而不是丢弃连接。
- 运行时探针：`lsof` 显示 `TCP 127.0.0.1:8791 (LISTEN)`；从非回环地址 `172.16.21.166` 连接 `connect_ex -> 61`（拒绝）。
- 写方法：`POST/PUT/DELETE/PATCH /api/tree` 全部 **HTTP 405** 且返回「只读查看器只接受 GET 请求，不提供写入、暂存或提交接口。」
- 未知路由与静态资源拼接：`/api/not-whitelisted`、`/assets/../server.py` 均 **HTTP 404**。
- 越界：`../rv4-outside-secret.txt`、`../../etc/hosts`、`/etc/hosts`、符号链接 `rv4-escape-link` 全部 **HTTP 403**，响应不回声绝对路径。
- 工作区只读：读取前后 `git status --porcelain` 的 SHA-256 指纹相同（`dc267523…`）。
- 源码级断言：`rg -n "do_POST|do_PUT|do_DELETE|do_PATCH" scripts/shared/view/` 无命中。
- 负控：`stub_server.py --stub no-path-guard`（进程内去掉仓库内断言）→ 逃逸请求返回仓库外内容 `RV4-SECRET-OUTSIDE`（HTTP 200）；脚本另用「被拒绝响应」自检**同一条判定表达式**会判红，证明该断言非空转。
- `expected_fail`：越界请求返回仓库外文件内容，或写类请求被接受。**已观察到该失败形态**。

## 6. rv-5 — 进程侧性能预算（reviewer: verifier）：**部分未达标，如实记录**

- 命令：`python3 .iar/evidence/scripts/rv5_measure.py`
- 证据：`rv-5-performance.txt`
- 采集时刻 load average 15.7–16.4（本机并行跑着与本次交付无关的进程）。判定方法为**中位数**；本轮把样本量从 5/3 提到 12/11，并把 p90 与「超预算样本数」一并打印——小样本中位数不稳定，上一轮 n=5 的 PASS（中位 142.9ms）在 n=12 下变为 FAIL（中位 158.9ms）。
- 结果（最终一轮，n=12/11）：

  | 口径 | 最小 | 中位 | p90 | 最大 | 超预算 | 判定 |
  |---|---|---|---|---|---|---|
  | 复用命中（真实 `just view`，含浏览器交接） | 109.8 | **158.9** | 192.6 | 196.9 | 9/12 | **FAIL**（预算 150ms） |
  | 复用命中（`just view --no-open`，去掉交接） | 108.8 | 127.4 | 147.5 | 150.5 | 1/12 | PASS |
  | 冷启动（口径一：敲命令 → 首个接口 200） | 353.1 | **419.1** | 510.3 | 533.2 | 7/11 | **FAIL**（预算 400ms） |
  | 冷启动（口径二：只计服务进程 spawn → 200） | 218.1 | 306.7 | 361.6 | 366.5 | 0/11 | PASS |
  | 负控（注入固定延迟） | 451.3 | 454.2 | 853.6 | 853.6 | 3/3 | FAIL（预期失败形态） |

- **结论：FR-9 的两条预算按字面口径（「敲命令到浏览器开始加载」「敲命令到首个接口返回成功」）在本机未达标**；其中不含浏览器交接的进程侧口径（127.4ms / 306.7ms）达标。这不是实现回归，而是预算本身余量不足：以下分解显示成本结构里没有可去掉的浪费——
  - `just --version` 12ms；`.venv/bin/python -c pass` 37ms；`just view --stop`（`just` + `launch.py`，不起服务）118ms；`import server`（解释器 + `http.server` 等）149ms。
  - 即：冷启动 ≈ 118ms（`just` + 客户端入口进程）+ 306ms（服务进程就绪）= 424ms，与实测中位 419ms 吻合。
  - 两个 Python 进程的解释器与导入成本已占掉预算的全部；浏览器交接再占 20–31ms（`subprocess` 导入 + `open` 进程本身）。这些都不是可优化掉的浪费，除非改用非 Python 的 HTTP 层（本 PRD 明确不引入）。
- 负控 `rv5_slow_launch.py` 注入固定延迟后中位 454.2ms > 150ms → **FAIL（预期失败形态）**，证明这套计时有判别力、不是恒绿。
- 浏览器冷启动 1.5–3s **不计入**承诺，已在 `docs/guides/file-viewer.md` 写明。
- **处置**：不修改 PRD 的预算数字（那是用户可见承诺，不得由执行器单方面放宽），也不为凑数做微优化；§9 Acceptance Checklist 中对应条目**保持未勾选**并在 PRD §12 记为待人工裁定的风险项。见 verifier 报告 NON-BLOCKING N-3。

## 7. rv-6 — 命令、文档与原型中心登记（reviewer: verifier）

- 命令：`bash .iar/evidence/scripts/rv6_docs_registry.sh`
- 证据：`rv-6-docs-registry.txt`
- 五处命中：`docs/ai-standards/tooling.md`（Common Commands 表 2 条 + Preferred Tools + 常驻与空闲回收约定）、`docs/guides/file-viewer.md`（命令面/界面用法/回收/性能边界/排障）、`docs/prototypes/prototype-registry.js`（`id: "file-viewer"` + 预览/入口/来源/provenance）、`docs/prototypes/index.md`、`mkdocs.yml`（使用指南页 + 原型说明页）。
- `just --list` 确实列出 `view` 与 `diff`；两条 recipe 指向同一入口 `scripts/shared/view/launch.py`（生命周期只有一份实现）。
- 派生项目同步面：`scripts/shared/template/sync_template.sh` 把 `justfile.shared` 与 `scripts/shared/*` 判为 upstream-owned，`just sync-template` 会带上查看器命令与实现。
- 文档构建：`uv run mkdocs build` → `Documentation built in 13.94 seconds`。
- 负控：把原型中心登记从临时副本里**整段移除**后，同一条 `rg -n "file-viewer" docs/prototypes/prototype-registry.js` 报红（无命中即该断言会失败）。
- `expected_fail`：五处登记任一缺失、或 `just --list` 里没有 `view`/`diff`。**已观察到该失败形态**（负控副本上）。

## 8. 风险地图对账 Predicted → Reconciled

- **决策一（生命周期）**：按预期落地。复用命中 126ms（预算 150ms）、`--stop` 与空闲超时都真正释放端口并清理登记、陈旧登记不会打开坏页面。页面不做心跳这一点在 `viewer.js` 中已核对：只有按需请求，没有定时轮询——自动回收因此不会静默失效。
- **决策二（只读边界）**：按预期落地。服务只绑回环、只接受 GET、无写路由；结束实例走进程信号而非 HTTP 写接口。实现期**未新增**任何写路径或高风险面，§2 无需回填。
- **实现期新发现的取舍**（已回填 PRD §7.2 与 Change Log）：
  - `instance.py` / `workspace.py` 从原计划的 `server.py` 中拆出，使客户端与服务端共用同一份登记与工作区实现，避免两套逻辑。
  - 两条 recipe 写成普通单行（非 shebang）并优先直连项目 venv，因为 `just` 的 shebang recipe 每次多约 200ms、`uv run --no-sync` 每次多 20–37ms，会吃掉 150ms 预算。解释器不存在时退回 `uv run`。

## 9. 对锁定契约的 diff

- **登记文件字段集合**与 §7.1 一致：`VIEW_PID` / `VIEW_PORT` / `VIEW_REPO_ROOT` / `VIEW_STARTED_AT`（见 `rv-1-viewer-file.txt` 中的登记原文）。
- **只读路由白名单**与 §6 一致：静态资源 + `/api/info` + `/api/tree` + `/api/file` + `/api/changes` + `/api/diff`；`/api/not-whitelisted` 404。
- **默认端口** 8791，与既有 8000 / 5173 / 3000 不重叠；被占用时退回系统空闲端口（rv-2 采集时即落在 60366，正是该退让路径的真实发生）。
- `just run` / `just down` / `just test` / `just worktree` 未改动（`git diff justfile.shared` 只新增 `view` / `diff` 两条 recipe）；`.env.view-state` 被既有 `.gitignore` 的 `.env*` 覆盖。

## 10. 低风险门禁（折叠）

- `uv run pytest tests/guards/shared/test_view_server.py -v` → **19 passed**（rv-4，含新增的 NUL 畸形路径用例）
- `just lint --reuse` → **全绿**：jscpd 复制粘贴检查 Passed、pylint 重复代码 Passed、架构层依赖 Passed、约定一致性 Passed、单文件行数 Passed
- `just lint --full` → 除 `check-test-flag` 外全部 Passed（ruff / ruff-format / PRD 验收清单 / 架构层 / 数据库约定 / 单文件行数 / PRD 锁 / **guard test modification** 等）。`check-test-flag` 是提交期门禁，提示「当前代码尚未执行过 just test」，由紧随其后的 `just test` 满足——`just test` 本身即以 `SKIP=check-test-flag` 跑 lint。
- `just test` → 见提交信息；它在最后一次代码改动之后执行（该 flag 绑定 branch@HEAD@tree）。
- `uv run mkdocs build` → Documentation built（rv-6）
- 交付 diff 中不含任何 RV 脚本：`git status --short` 与 `git diff --name-only` 只出现实现面文件（`.iar/` 与 `tasks/evidence/` 的原始工件均被 `.gitignore` 覆盖；`tasks/evidence/**/*.md` 是白名单例外，三份报告随 PRD 提交）。
- 关于 `GUARD_UPDATE_ACK`：本任务**新增**了 `tests/guards/shared/test_view_server.py`（并按 `tests/guards/README.md` 的表登记），提交时 `check-guard-test-modification` 会要求显式确认——这是仓库既定流程（新增守卫测试属预期动作），本次 lint 中该 hook 之所以 Passed，是因为执行器被禁止 `git add`，暂存区为空；提交时需 `GUARD_UPDATE_ACK=1`。

## 11. 未决与披露

- **rv-5 的 FR-9 预算未达标（最重要的一条）**：按 FR-9 的字面口径，复用命中中位 **158.9ms**（预算 150ms，9/12 超标）、冷启动到首个接口中位 **419.1ms**（预算 400ms，7/11 超标）。不含浏览器交接的进程侧口径达标（127.4ms / 306.7ms）。成本分解显示没有可去掉的浪费：两个 Python 进程的解释器与导入成本已占满预算（`just`+客户端入口 118ms、服务进程就绪 306ms）。**未修改 PRD 的预算数字，也未做凑数式微优化**；§9 对应条目保持未勾选，PRD §12 记为待人工裁定。详见 §6 与 verifier 报告 N-3。
  - **时序说明（重要）**：独立 verifier 给出 PASS 时，rv-5 还是上一轮 n=5 的样本（中位 142.9ms，判 PASS）；verifier 在 N-3 里已指出「样本量偏薄、极值贴上限、负载下常超预算」，并明确 150ms 预算「在负载下不成立」。本轮把样本量提到 12/11 后，N-3 的预测被证实并升级为**正控未达标**。verifier 的 PASS 针对的是 Part A 锁定的两条决策（生命周期、只读边界），那两条在本轮重测后仍然成立；性能预算不是那两条决策的一部分。这份报告不修改 verifier 的独立裁定文本。
- **`--diff` 的可选参数是基线而非路径**：`just view --diff justfile.shared` 会被解析为「基线 = justfile.shared」；服务端返回 HTTP 400（基线白名单拒绝），前端按 `viewer.js` 的设计回退到「工作区改动」并在下拉框中如实显示该回退。这是安全回退而非静默错误，但没有弹出提示——列为 NON-BLOCKING，详见 verifier 报告 N-4。
- **`--no-reuse` 不会收掉旧实例**：新实例会覆盖登记，旧实例变成「无人登记的常驻进程」，只能等 30 分钟空闲回收或手工 `kill`。已在 `docs/guides/file-viewer.md` 写明；verifier 报告 N-2 同时指出 `launch.py` 两处 `clear_instance_record` 缺少 `expected_process_id` 归属校验，本次已修（见 Change Log）。
- **证据里的绝对数字会随工作区漂移**：文件树条数、改动文件数与增删统计都是采集时刻的快照，判据一律写成不变式（「界面 == 终端同参数输出」「树 ⊇ 受控文件」）。verifier 报告的 N-1 记录了上一轮因 PRD 自身编辑造成的数字漂移，本轮的期望值已改为不变式表述。
- **本机噪音对所有计时的影响**：采集期间 load average 13–18，机器上并行跑着与本次交付无关的进程；性能判定使用中位数，但本轮已把样本量提到 12/11 并把 p90、超预算样本数一并打印，不再用「中位达标」掩盖尾部。**这项正是 rv-5 判 FAIL 的原因。**
