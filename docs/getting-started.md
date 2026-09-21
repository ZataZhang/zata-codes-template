# 快速开始

本文档说明如何在本地初始化并运行该模板项目。

## 环境要求

- Python 版本：`>=3.14`
- 包管理器：`uv`
- 推荐任务工具：`just`

## 安装依赖

安装主依赖和开发依赖：

```bash
just sync
```

首次启动开发环境（含 pre-commit hook 安装）：

```bash
just dev
```

## 运行项目

```bash
just run
```

默认会同时启动后端、管理平台前端和前台官网。各服务端口读取当前 `.env.run-state`；`just copy` 会为派生项目预写随机端口，实际访问地址以 `just run` 的终端输出为准：

- 后端执行 `uv run python -m backend.main`
- 管理平台前端在 `frontend-admin/` 中执行 `pnpm dev`
- 前台官网在 `frontend-public/` 中执行 `pnpm dev`

可以通过参数指定端口；端口会保存到 Git 本地状态文件，下次 `just run` 会自动复用：

```bash
just run backend_port=8010 frontend_admin_port=13173 frontend_public_port=3001
just run
```

停止本地服务时会读取同一份端口状态：

```bash
just down
just down backend
just down frontend
just down frontend-public
```

如果只想启动其中一部分，可以这样运行：

```bash
just run backend
just run frontend
just run frontend-public
```

`just frontend dev` 与 `just frontend-public dev` 也会委托给上述 `just run` 入口，因此不会绕过已保存的端口。`just run docker` 同样用 run-state 设置主机侧端口映射；Docker 容器内部端口保持固定。

如果项目实际目录或命令不同，可以覆盖默认参数：

```bash
just run all frontend_dir=web frontend_cmd="pnpm dev"
just run all frontend_public_dir=web-public frontend_public_cmd="pnpm dev"
```

### 前台官网 dev server 的堆上限

`frontend-public/package.json` 的 `dev` 脚本带了 `NODE_OPTIONS=--max-old-space-size=3072`，不要删。

`next dev` 在未显式指定 `max-old-space-size` 时，会把 V8 老生代上限设成**物理内存的一半**
（见 `next/dist/cli/next-dev.js`，32G 机器上就是 16 GiB，并非 Node 自己的默认值），
而 dev server 的堆会随会话单调增长。实测跑满 45 分钟后堆到 8.6 GB、峰值 12.6 GB，
整机进入 swap thrash；Next 自带的熔断要到约 14 GB 才触发重启，那时早已拖垮其他进程。

该默认值只在 `NODE_OPTIONS` 未声明此参数时生效，所以显式写上即可接管；
需要更大堆时改这里的数值，临时放开整段逻辑可用 `NEXT_DISABLE_MEM_OVERRIDE=1`。

排查时注意 `ps` 的 RSS 会骗人（堆被压缩换出后只报 1 GB 上下且剧烈抖动），
真实值在 `frontend-public/.next/dev/trace` 的 `memory-usage` 事件里（`memory.heapUsed`）。
`frontend-admin` 走 vite，不受这段逻辑影响。

## 测试

运行默认本地测试集：

```bash
just test
```

运行完整测试集：

```bash
just test all
```

## 文档预览

本项目已集成 MkDocs：

```bash
just docs-serve
```

构建静态文档：

```bash
uv run mkdocs build --strict
```

## Git Worktree

创建新的 worktree：

```bash
just worktree feature-branch
```

默认会从本地 `main` 分支创建 worktree。需要从其他本地分支创建时，传入 `--base`：

```bash
just worktree feature-branch --base develop
```

执行一次 `just sync all` 并重新打开终端后，Bash 和 Zsh 会为
`just worktree -o <Tab>`、`just worktree -d <Tab>` 与
`just worktree -D <Tab>` 补全本地分支名，并为 `just prd <Tab>` 补全
子命令（`status`、`start`、`heartbeat`、`release`）、为 `just prd status <Tab>` 补全 scope
（`all`、`pending`、`archive`）与 `--detail` 旗标（二者可互换位置）。

打开已有 worktree 用 `just worktree -o <名称>`。除分支全名外，名称还接受分支最后一段、
PRD slug、PRD 文件名（可带 `.md`）与 `tasks/pending/....md` 路径——`just prd status`
的 ACTIVITY 列里 `@` 后的名称可以直接复制过来。命中多个 worktree 时会报错并列出候选，
改用分支全名即可；完全找不到时会把当前可打开的 worktree 列出来，便于区分名字写错与
worktree 尚未创建。

批量清理已经并进 base 的本地分支及其 worktree：

```bash
just worktree --prune --dry-run    # 只列计划，不做任何变更
just worktree --prune              # 列计划 → 一次确认 → 批量删除
just worktree --prune --yes        # 跳过确认
just worktree --prune --force      # 额外纳入「远端已删但本地仍有独有提交」的分支
just worktree --prune --base develop
```

判据全部离线成立，只读本地引用，不联网：

- **默认可删**：分支已经是 base 的祖先（`git merge-base --is-ancestor <branch> <base>` 成立）。
- **需 `--force`**：上游远端分支已被删除（`%(upstream:track)` 为 `[gone]`），但本地仍有独有提交。
  这通常是 squash merge 之后远端分支被删，但 git 无法把它和「PR 直接关掉、代码没合进去」
  区分开，所以默认只列出，由你核对后再加 `--force`——注意 `--force` 是强制删除，
  会一并丢掉未合并的提交。
- **永不触碰**：base 分支、`main` / `master`、当前检出的分支。

base 取 `--base`；未传时读 `KODA_WORKTREE_BASE_BRANCH`，再退回 `main`。该模式只清理本地分支
与关联 worktree——远端分支和 worktree 孤儿数据库仍由 `just worktree --doctor [--gc]` 负责。

`just worktree`（底层实现位于 `scripts/shared/worktree/create.sh`）在创建 worktree 后会自动执行两类依赖准备：

- Python：如果仓库根目录存在 `pyproject.toml`，则运行 `uv sync --all-extras`。
- Frontend：扫描 worktree 根目录及其子目录中的 `package.json`，并在每个前端项目目录内按锁文件选择对应安装命令，例如 `npm ci`、`pnpm install`、`yarn install` 或 `bun install`。

这意味着像 `demo-frontend/`、`admin-frontend/` 这类把 `package.json` 放在子目录里的前端项目，也会在新 worktree 中自动完成依赖安装。

## 目录说明

- `src/backend/infrastructure/config/`：应用配置与环境变量解析。
- `src/backend/infrastructure/logging/`：日志器配置。
- `src/backend/infrastructure/helpers.py`：无状态通用辅助函数。
- `src/backend/engines/`：平台能力扩展点（项目按需挂载具体能力）。
- `src/backend/infrastructure/persistence/`：数据库接入与通用持久化工具。
- `frontend-admin/`：管理平台前端（Vite + React + TanStack Router + shadcn-admin）。
- `frontend-public/`：前台官网（Next.js + React + Tailwind CSS v4 + shadcn/ui）。
- `tests/`：单元测试与集成测试。
- `tests/playwright-e2e/`：端到端测试（独立 Node 包）。
- `docs/`：项目文档源目录。
