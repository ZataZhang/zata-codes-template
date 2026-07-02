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

默认会同时启动后端、管理平台前端和前台官网：

- 后端默认执行 `uv run python -m backend.main`，端口 `8000`
- 管理平台前端默认进入 `frontend-admin/` 目录执行 `npm run dev`，端口 `5173`
- 前台官网默认进入 `frontend-public/` 目录执行 `pnpm dev`，端口 `3000`

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

如果项目实际目录或命令不同，可以覆盖默认参数：

```bash
just run all frontend_dir=web frontend_cmd="pnpm dev"
just run all frontend_public_dir=web-public frontend_public_cmd="pnpm dev"
```

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
