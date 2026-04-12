# Zata Codes Template

一套面向 AI Agent 平台演进的 Python 项目模板，遵循 **DDD 边界意识 + Clean Architecture 依赖方向 + 模块化单体** 的设计理念。

它保留了模板的低门槛启动体验，同时把仓库的目标结构明确为四层：

- `apps/` 请求接入层
- `core/` 核心编排层
- `capabilities/` 平台能力层
- `infrastructure/` 基础设施层

`utils/` 和 `ai_agent/` 会在迁移期内保留兼容出口，但最终目标是收敛到上述四层结构。

## 快速开始

```bash
just sync dev   # 安装全部依赖 + pre-commit hooks
just run        # 同时启动后端 + 前端
```

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
| `just run` | 默认同时启动后端和前端 |
| `just run backend` | 只启动后端（默认命令为 `uv run python main.py`） |
| `just run frontend` | 只启动前端（默认进入 `frontend/` 执行 `npm run dev`） |
| `just run all frontend_dir=web frontend_cmd="pnpm dev"` | 覆盖前端目录或启动命令 |
| `just test` | 运行本地测试（无需 API key） |
| `just test all` | 运行全部测试 |
| `just test real` | 运行需要 API key 的测试 |
| `just docs-serve` | 本地预览 MkDocs 文档（`127.0.0.1:8000`） |
| `just docs-serve port=9000` | 指定端口 |
| `just clean` | 清理缓存与构建产物 |
| `just check-net` | 检查当前终端的代理、Claude 服务连通性与出口 IP 地区 |
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
| `just copy <name>` | 将本模版复制为新项目到 `../<name>/` |
| `just sync-template` | 与上游模版对比，交互式选择更新（跳过项目特定文件）；如有模板技能更新，可选择安装到 `~/.cc-switch/skills`，若该目录不存在则提示选择 Codex 或 Claude 的 skills 目录 |
| `just sync-template --all` | 同上，但包含 README、pyproject.toml 等项目特定文件 |
| `just release` | 通过 `scripts/release.py` 构建发布包 |

### Secrets

| 命令 | 说明 |
|------|------|
| `just export-env-encrypted` | 将所有被 gitignore 的 `.env*` 文件打包为加密 zip（`<项目名>_secrets.zip`），压缩和解压均需输入密码 |

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

## utils 目录

`utils/` 当前仍保留跨项目可复用能力，但它正在向 `infrastructure/` 迁移。迁移期内，这里只应保留薄封装或兼容出口，不应继续扩张成最终架构。

### `utils/settings.py`
集中管理环境变量与路径配置，统一从 `.env` 加载，其余模块只从 `config` 对象读取。

### `utils/logger.py`
单例 `Logger`，读取 `config.LOG_LEVEL` 与 `config.LOG_FILE`，同时输出到控制台与文件，在 Windows 上处理 UTF-8。

```python
from utils.logger import logger
logger.info("started")
```

### `utils/helpers.py`
无状态的小工具函数，可按需补充，如格式化时间、批量重试等。

## 架构口径

这个仓库不是微服务模板，也不是单纯的脚本集合，而是一个 **四层模块化单体** 的 AI Agent 骨架：

1. `apps/` 负责接入。
2. `core/` 负责业务编排和领域规则。
3. `capabilities/` 负责可插拔能力。
4. `infrastructure/` 负责具体技术实现。

架构参考来自整洁架构与 DDD 的组合思路。外部文章提供的是设计方向和结构示例，本仓库会结合自己的模板定位、目录现状和迁移成本做落地，不机械照搬命名。
