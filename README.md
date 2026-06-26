# Zata Codes Template

一套面向 AI Agent 平台演进的 Python 项目模板，遵循 **DDD 边界意识 + Clean Architecture 依赖方向 + 模块化单体** 的设计理念。

它保留了模板的低门槛启动体验，同时把仓库的目标结构明确为四层后端 + 双前端：

- `src/backend/api/` 请求接入层
- `src/backend/core/` 核心编排层
- `src/backend/engines/` 平台能力层
- `src/backend/infrastructure/` 基础设施层
- `frontend-admin/` 管理平台前端（Vite + React + TanStack Router + shadcn-admin）
- `frontend-public/` 前台官网（Next.js 16 + React 19 + Tailwind CSS v4 + shadcn/ui）

当前仓库的正式结构以 `src/backend/api/`、`src/backend/core/`、`src/backend/engines/`、`src/backend/infrastructure/` 四层目录与 `frontend-admin/`、`frontend-public/` 两个前端目录为准。

## 快速开始

```bash
just sync dev   # 安装全部依赖 + pre-commit hooks
just run        # 同时启动后端 + 管理平台前端 + 前台官网
```

启动后会同时运行三个服务：

- 后端 API：`http://localhost:8000`
- 管理平台前端：`http://localhost:5173`
- 前台官网：`http://localhost:3000`

认证使用 HTTP-only `session_id` cookie：在 `/login` 或 `/register` 登录/注册后，同一域名下的 `/dashboard` 等页面会自动携带会话。

## Task Runner（just）

所有常用开发任务通过 `just` 驱动，直接运行 `just` 可列出所有命令。

### 依赖管理

| 命令 | 说明 |
|------|------|
| `just sync` | 同步 dev 依赖（默认） |
| `just sync prod` | 仅同步生产依赖，不含 dev |
| `just sync all` | 全部 extras + 安装 worktree bash 补全 |
| `just sync dev` | 全部 extras + 安装 pre-commit hooks |

### 开发

| 命令 | 说明 |
|------|------|
| `just run` | 默认同时启动后端、管理平台前端和前台官网；会复用当前 Git worktree 保存的端口 |
| `just run backend_port=8010 frontend_port=5178 frontend_public_port=3001` | 指定并保存后端/管理平台/前台端口 |
| `just down` | 按保存的端口停止本地后端和两个前端 |
| `just run backend` | 只启动后端（默认命令为 `uv run python -m backend.main`） |
| `just run frontend` | 只启动管理平台前端（默认进入 `frontend-admin/` 执行 `npm run dev`） |
| `just run frontend-public` | 只启动前台官网（默认进入 `frontend-public/` 执行 `pnpm dev`） |
| `just frontend-public dev` | 在 `frontend-public/` 运行 `pnpm dev` |
| `just run all frontend_dir=web frontend_cmd="pnpm dev"` | 覆盖前端目录或启动命令 |
| `just test` | 运行本地测试（无需 API key） |
| `just test all` | 运行全部测试 |
| `just test real` | 运行需要 API key 的测试 |
| `just docs-serve` | 本地预览 MkDocs 文档（`127.0.0.1:8000`） |
| `just docs-serve port=9000` | 指定端口 |
| `just clean` | 清理缓存与构建产物 |
| `just check net` | 检查当前终端的代理、Claude 服务连通性与出口 IP 地区 |
| `just check s3` | 端到端验证 S3 配置（put → exists → presign → get → cleanup） |
| `just staged_changes` | 将暂存区 diff 导出为 `staged_changes.diff` |

### Git Worktree

所有 worktree 操作统一在 `just worktree` 下：

| 命令 | 说明 |
|------|------|
| `just worktree <branch>` | 创建 worktree 并进入交互式 shell |
| `just worktree <branch> --cmd trae` | 创建 worktree 并在指定编辑器中打开 |
| `just worktree <branch> enter_shell=false` | 创建 worktree 但不进入 shell |
| `just worktree -d <branch>` | 删除 worktree 及分支 |
| `just worktree -m <feature> [base=main] [flags]` | 将 feature worktree 合并到 base 分支 |
| `just worktree --doctor` | 扫描所有 worktree 的健康状况 |
| `just worktree --doctor <branch>` | 检查指定 worktree |

### 模版与项目管理

| 命令 | 说明 |
|------|------|
| `just copy <name>` | 将本模版复制为新项目到 `../<name>/`，不包含 `node_modules`、`dist` 等依赖和构建产物；目标目录非空时可用 `--force` 覆盖 |
| `just sync-template` | 与上游模版对比，交互式选择更新。默认同步模板维护的通用文件；跳过 `tasks/`、环境/缓存产物、`config.toml` 中 `[template_sync].project_skip_paths` 配置的项目路径，以及 README、CLAUDE.md、main.py、justfile、pyproject.toml、config.toml、mkdocs.yml、uv.lock 等项目特定文件。如有模板技能更新，可选择安装到 `~/.cc-switch/skills`，若该目录不存在则提示选择 Codex 或 Claude 的 skills 目录 |
| `just sync-template --all` | 同上，但额外包含 `project_skip_paths` 中的项目路径（如 `src/backend/`、`frontend-admin/`、`docs/`、`tests/`、`deploy/` 等）；`tasks/` 和顶层身份文件仍跳过 |
| `just release` | 通过 `scripts/shared/release.py` 构建发布包 |

### Template Sync 规则说明

`just sync-template` 默认只同步上游模板维护的通用骨架文件。下面的清单解释**哪些目录/文件不进 diff、不会被覆盖**。

**永久跳过**（`--all` 也不会同步）

- `tasks/`：项目任务文件。

**默认跳过**（`--all` 会把"项目特定目录"那部分一起纳入 diff）

- **顶层项目身份/配置**：`README.md`、`CLAUDE.md`、`main.py`、`justfile`、`pyproject.toml`、`config.toml`、`mkdocs.yml`、`uv.lock`、`findings.md`、`progress.md`、`task_plan.md`、`.dockerignore`、`.gitignore`、`.DS_Store`。
- **环境/缓存/产物**：`.git/`、`.venv/`、`.uv-cache/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、`logs/`、`site/`、`.env`、`.env.*`、`*.pyc`、`*.egg-info`。
- **项目特定目录**（来自 `config.toml` 的 `[template_sync].project_skip_paths`，`--all` 时纳入 diff）：`src/backend/`、`frontend-admin/`、`docs/`、`tests/`、`deploy/`、`apps/`、`services/`、`infra/`、`helm/`、`terraform/`、`ansible/`、`data/`、`uploads/`、`artifacts/`、`tmp/`。
- **项目私有脚本**：`scripts/` 根目录下非 `shared/` 的文件。`scripts/shared/` 由上游模板维护，**始终同步**，不在跳过清单里。
- **其他**：`prompt/`、`skills/`、`.claude/`。

完整过滤逻辑见 `scripts/shared/template/sync_template.sh` 中的 `_is_never_synced()` 与 `_is_skipped_by_default()`。

### Secrets

| 命令 | 说明 |
|------|------|
| `just export-env-encrypted` | 将所有被 gitignore 的 `.env*` 文件打包为加密 zip（`<项目名>.zip`），压缩和解压均需输入密码 |

## 项目结构

```text
.
├── src/backend/           # Python 后端（四层 Clean Architecture）
│   ├── api/               # HTTP 接入层
│   ├── core/              # 业务编排与领域规则
│   ├── engines/           # 可插拔平台能力
│   └── infrastructure/    # 配置、日志、数据库、外部客户端
├── frontend-admin/        # 管理平台（shadcn-admin）
├── frontend-public/       # 前台官网（Next.js + shadcn/ui）
├── tests/                 # 单元测试与集成测试
├── tests/playwright-e2e/  # 端到端测试（独立 Node 包）
├── docs/                  # 项目文档源目录
├── alembic/               # 数据库迁移
├── deploy/vps-traefik/    # 可选 VPS 部署配置
└── justfile               # 任务入口
```

## Hooks

本模板使用 [`pre-commit`](https://pre-commit.com/) 统一管理提交前的质量保障，配置在 `.pre-commit-config.yaml` 中，涵盖基础文件卫生检查与 Ruff（Lint + Format）。

`just sync dev` 会自动完成安装。手动安装：

```bash
uv run pre-commit install
uv run pre-commit run --all-files   # 首次全量检查（可选）
```

升级 hook 依赖：

```bash
uv run pre-commit autoupdate
```

## 基础设施模块

### `src/backend/infrastructure/config/settings.py`
集中管理环境变量与路径配置，统一从 `.env` 与 `config.toml` 加载，其余模块只从 `config` 对象读取。

### `src/backend/infrastructure/logger.py`
单例 `Logger`，读取 `config.log_level` 与 `config.log_file`，同时输出到控制台与文件，在 Windows 上处理 UTF-8。

```python
from backend.infrastructure.logger import logger
logger.info("started")
```

### `src/backend/infrastructure/helpers.py`
无状态的小工具函数，可按需补充，如格式化时间、批量重试等。

## 架构口径

这个仓库不是微服务模板，也不是单纯的脚本集合，而是一个 **四层模块化单体** 的 AI Agent 骨架：

1. `src/backend/api/` 负责接入。
2. `src/backend/core/` 负责业务编排和领域规则。
3. `src/backend/engines/` 负责可插拔能力。
4. `src/backend/infrastructure/` 负责具体技术实现。

架构参考来自整洁架构与 DDD 的组合思路。外部文章提供的是设计方向和结构示例，本仓库会结合自己的模板定位、目录现状和迁移成本做落地，不机械照搬命名。
