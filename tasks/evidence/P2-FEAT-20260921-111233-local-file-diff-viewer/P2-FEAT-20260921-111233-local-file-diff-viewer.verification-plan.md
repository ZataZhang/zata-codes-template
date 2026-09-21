# Verification Plan: 本机只读文件与改动查看器（`just view`）

对应 PRD：`tasks/pending/P2-FEAT-20260921-111233-local-file-diff-viewer.md`
本文件把 §9 Acceptance Checklist 每条验收项映射到具体可执行命令；证据按 rv-id 命名落在本目录。

## 采集环境与纪律

- 采集机器：macOS（darwin），仓库 worktree `/Users/zata/code/zata_code_template/.iar-worktrees/issue-9`。
- 端口与进程号一律**从真实输出或登记文件 `.env.view-state` 取**，不硬编码进证据；文档与 PRD 中的 8791 只是默认值。
- 每条 oracle 起停自己的实例，跑前先 `just view --stop` + 清登记，保证起于确定状态。
- 截图用 Playwright 缓存的 Chrome for Testing 无头模式渲染**真实入口 URL**；不用复刻图、不用原型截图。
- 负控一律在**测试边界**起打桩进程（`.iar/evidence/scripts/stub_server.py` 进程内替换模块属性），**绝不**往 `src/` 或 `scripts/shared/` 加故障开关。
- 证据脚本全部位于 `.iar/evidence/scripts/`（被 `.gitignore` 覆盖），不进交付 diff。

## 验收项 → 命令映射

### Human-Confirmed / R3 / R2（人审呈递项）

- **rv-1 一条命令开出查看器读源码**
  - 正跑：`bash .iar/evidence/scripts/rv1_file_view.sh` → `just view justfile.shared --no-open` 起实例 → 无头 Chrome 渲染登记文件里的 URL → 截图 `rv-1-viewer-file.png` → `check_viewer_content.py file` 逐行比对接口与本地文件。
  - fresh-state probe：脚本内第二次独立请求同一路径，逐行核对仍一致。
  - 负控：`stub_server.py --stub fake-file-content`（进程内把 `build_file_payload` 换成固定假数据）→ 同一条逐行比对必须判红（退出码非 0）。
- **rv-2 改动视图与终端 `git diff` 逐项一致**
  - 正跑：`bash .iar/evidence/scripts/rv2_diff_view.sh` → `just view --diff --no-open` → `check_viewer_content.py changes` 把界面文件集合与 `+N -M` 逐项对齐终端 `git diff HEAD --name-only` 与 `--numstat`；分支基线在自带 `.git` 的夹具仓库上走同一条 `launch.py` 入口比对 `git diff main...HEAD`。
  - fresh-state probe：在终端给受控文件追加一行 → 界面统计必须同步变化 → 还原后回到原值。
  - 负控：`stub_server.py --stub fake-git-output`（进程内让改动列表多报一个终端不存在的文件）→ 同一条集合断言必须判红。

### Architecture Acceptance

- **能力只落共享工具链层、无 `src/backend/` 依赖**：`rg -n "src/backend|composition|frontend-admin|frontend-public" scripts/shared/view/ justfile.shared`；`git status --short -- src/ frontend-admin/ frontend-public/` 应为空。
- **生命周期只有一份实现**：`rg -n "env\.view-state|idle_timeout|idle-timeout" scripts/shared/view justfile.shared docs/`，登记与空闲参数只出现在查看器目录与文档中。
- **未依赖 `skills/git-diff-report/`**：`rg -n "render_diff_report|skills/git-diff-report" scripts/shared/view docs/guides/file-viewer.md` 无命中。存 `rv-6-docs-registry.txt`。

### Behavior Acceptance

- **复用命中不重启进程（rv-3）**：`bash .iar/evidence/scripts/rv3_lifecycle.sh` 内连续两次真实 `just view`，比对进程号与耗时；存 `rv-3-lifecycle.txt`。
- **陈旧登记被接管（rv-3）**：脚本内 `kill -9` 服务进程后保留登记，再执行打开命令，必须判陈旧、重起服务并打开可用页面（`/api/info` 返回 200）。
  - 负控：把登记里的进程号替换为一个**已退出**进程的进程号（只污染状态文件），同一条判定必须判陈旧并接管。
- **空闲回收 + 显式回收（rv-3）**：`just view --idle-timeout 3` 起实例后静置 → 进程退出、端口关闭、登记被清理；`just view --stop` 立刻回收；此后新 shell 复查端口与登记存在性。
- **只读边界（rv-4）**：`uv run pytest tests/guards/shared/test_view_server.py -v`（真实进程 + 真实 HTTP）＋ `bash .iar/evidence/scripts/rv4_readonly_boundary.sh` 的运行时探针：绑定地址必须是 `127.0.0.1`、四种写方法与非白名单路由被拒、`..`/绝对路径/符号链接逃逸全部 403。
  - 负控：`stub_server.py --stub no-path-guard`（进程内去掉仓库内断言）→ 逃逸请求必须变成可读；脚本另用一段自检证明该判定表达式非空转。
- **查看不改工作区**：rv-4 脚本比对读取前后 `git status --porcelain` 的 SHA-256 指纹。

### Dependency Acceptance

- **Pygments 显式声明（rv-6）**：`rg -n "pygments" pyproject.toml uv.lock`，`pyproject.toml` 必须直接声明而非仅传递引入；对照 `tests/guards/test_runtime_dependency_declaration.py`。
- **未引入终端形态依赖（rv-6）**：`rg -n "git-delta|difftastic|lazygit" justfile.shared scripts/shared docs/` 无命中。

### Frontend Acceptance

- **查看器是独立静态单页**：`rg -n "frontend-admin|frontend-public|node_modules|package.json" scripts/shared/view/assets/` 无命中；`git status --short -- frontend-admin frontend-public` 为空。存 `rv-6-docs-registry.txt`。
- **前端只调只读接口**：`rg -n "fetch\(|/api/" scripts/shared/view/assets/viewer.js` 只出现 `/api/info` / `/api/tree` / `/api/file` / `/api/changes` / `/api/diff` 五个只读路由。
- **失效提示（rv-1/rv-3 截图链）**：服务退出后页面切换到「服务已退出」状态——由 `viewer.js` 的失败分支渲染，原型说明页与原型截图 `file-viewer-interactive-disconnected.png` 呈现该状态。

### Documentation Acceptance

- **三处登记 + 站点导航（rv-6）**：`bash .iar/evidence/scripts/rv6_docs_registry.sh` → `rg -n "just view|file-viewer-interactive" docs/ai-standards/tooling.md docs/guides/file-viewer.md docs/prototypes/prototype-registry.js docs/prototypes/index.md mkdocs.yml` 五处均命中 ＋ `uv run mkdocs build`。
  - 负控：把原型中心登记从临时副本里整段移除，同一条断言必须报红。

### Validation Acceptance

- **守卫测试全绿（rv-4）**：`uv run pytest tests/guards/shared/test_view_server.py -v`。
- **进程侧性能预算（rv-5）**：`python3 .iar/evidence/scripts/rv5_measure.py` → 复用命中 ≤150ms、冷启动到首个接口 200 ≤400ms（按中位数判定；浏览器冷启动 1.5–3s 不计入）。
  - 负控：`rv5_slow_launch.py` 注入固定延迟，同一套计时方法必须超预算判红。
- **证据绑定最终代码树**：`justfile.shared`（入口 recipe）最后一次改动之后，rv-1/rv-2 的截图与日志已重收；rv-3/rv-4/rv-5/rv-6 均在最后一次改动之后采集。
- **低风险门禁**：`just lint`、`just test`。

### Delivery Readiness

- 交付 diff 不含任何 RV 脚本：`git status --short` 与 `git diff --name-only` 只出现实现面文件（`.iar/` 被 `.gitignore` 覆盖）。
- 证据产物落在 `tasks/evidence/P2-FEAT-20260921-111233-local-file-diff-viewer/`（原始工件被 `.gitignore` 白名单挡在版本库外，三份 `.md` 报告随 PRD 提交）。

## 已知限制与披露

- **本机噪音**：采集时本机 load average 在 13–18 之间（与本次交付无关的进程），单次样本会被调度噪声放大，因此性能判定取**中位数**并同时记录最小/最大值。
- **`--diff` 的可选参数是基线不是路径**：`just view --diff justfile.shared` 会被解析成「基线 = justfile.shared」，服务端对该取值返回 HTTP 400（基线白名单），前端按设计回退到「工作区改动」并在下拉框如实显示。见 verifier 报告的 NON-BLOCKING 条目。
