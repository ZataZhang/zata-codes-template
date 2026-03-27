# Zata Codes Template

一套极简的 Python 项目骨架，带好用的 hooks 与通用工具集合，方便你在任何新项目里直接复用。

## 快速开始

```bash
just sync dev   # 安装全部依赖 + pre-commit hooks
just run        # 运行主程序
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
| `just run` | 运行主程序（`main.py`） |
| `just test` | 运行本地测试（无需 API key） |
| `just test all` | 运行全部测试 |
| `just test real` | 运行需要 API key 的测试 |
| `just docs-serve` | 本地预览 MkDocs 文档（`127.0.0.1:8000`） |
| `just docs-serve port=9000` | 指定端口 |
| `just clean` | 清理缓存与构建产物 |
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
| `just sync-template` | 与上游模版对比，交互式选择更新（跳过项目特定文件） |
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

`utils/` 收纳所有跨项目可复用的底层能力，建议保持纯函数/可注入式配置，避免引入业务耦合。

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
