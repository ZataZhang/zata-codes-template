# 配置说明

本项目通过 `src/backend/infrastructure/config/settings.py` 中的 `AppSettings` 统一管理配置，并组合多个子配置模型，实现工程化的配置分层。

## 配置来源优先级

总优先级从高到低：

1. 环境变量（含 `.env` / `.env.local`）
2. `config.toml`
3. 代码默认值

## 关键配置模块

- **应用层配置**：应用名、日志级别、日志目录。
- **数据库配置**：后端类型、主机、端口、库名、驱动。
- **模型配置**：默认聊天模型提供商、模型名和温度。
- **基础设施配置**：MinIO、Qdrant、Embedding、Chunking、Timeout 等。

## 常用实践

- 推荐在 `.env` 中存放密钥与敏感信息。
- 推荐在 `config.toml` 中维护非敏感默认项。
- 所有业务代码统一从 `config` 实例读取，不直接散落调用 `os.getenv`。

## Worktree 相关环境变量

`just worktree`（底层实现位于 `scripts/shared/worktree/create.sh`）支持以下环境变量来控制新 worktree 的依赖准备行为：

- `KODA_WORKTREE_BASE_BRANCH`
  - 新 worktree 默认使用的本地基底分支，默认值为 `main`。
  - 命令行参数 `--base <branch>` 会覆盖这个环境变量。
- `WORKTREE_FRONTEND_STRATEGY`
  - `install-per-worktree`：默认值。扫描 worktree 根目录和子目录中的前端项目，并在各自目录执行锁文件驱动的依赖安装。
  - `symlink-from-main`：不重新安装依赖，而是尝试把新 worktree 中的前端项目 `node_modules` 链接到源仓库对应目录。
- `WORKTREE_SKIP_FRONTEND_INSTALL`
  - 仅在 `WORKTREE_FRONTEND_STRATEGY=install-per-worktree` 时生效。
  - 设为 `true` 后，跳过前端依赖安装步骤。

对包含多个前端子项目的仓库，默认策略会覆盖类似 `demo-frontend/`、`admin-frontend/` 这类嵌套目录，而不是只处理仓库根目录。

## 数据库建库选项

`scripts/shared/template/setup_copied_database.py` 在创建 Worktree 专用数据库前，会从
`.env.local` 读取以下四个选项来控制目标方言的字符集 / 排序规则 / locale。**未设置则
使用脚本默认**，与下游业务标准一致即可无需修改。

| 环境变量 | 作用于 | 默认值 | 说明 |
|---|---|---|---|
| `DATABASE_CHARSET` | MySQL | `utf8mb4` | 新建库的字符集。 |
| `DATABASE_COLLATION` | MySQL | `utf8mb4_unicode_ci` | 新建库的排序规则。 |
| `DATABASE_LOCALE` | PostgreSQL | 空（走 cluster 默认） | 拼到 `CREATE DATABASE ... LOCALE = '<value>'`，仅在显式设置时生效。 |
| `DATABASE_ENCODING` | PostgreSQL | 空（走 cluster 默认） | 拼到 `CREATE DATABASE ... ENCODING = '<value>'`，仅在显式设置时生效。 |

### 何时需要覆盖

- **MySQL 8.0+**：脚本默认 `utf8mb4_unicode_ci` 与 MySQL 5.7 / MariaDB 默认一致，
  跨版本兼容。如项目硬编码依赖 `utf8mb4_0900_ai_ci` 或其他 collation，直接在
  `.env.local` 设 `DATABASE_COLLATION` 即可。
- **PostgreSQL**：脚本默认从 `template0` 复制，**不**主动给 `LOCALE` / `ENCODING`——
  这能避免在某些 OS locale 不匹配的环境里报错。若项目有强制 locale 需求（例如
  想用 `C.UTF-8` 走纯 ASCII 排序加速），在 `.env.local` 设 `DATABASE_LOCALE` /
  `DATABASE_ENCODING` 即可。注意 PostgreSQL 要求 `ENCODING` 与 `LC_COLLATE` /
  `LC_CTYPE` 都与 OS locale 匹配；若集群未安装该 locale 会报错。

### 不要做的

- **不要**只改 `DATABASE_URL` 而不更新字符集相关 env var——脚本会落到默认
  `utf8mb4_unicode_ci`，与迁移链期望不一致时仍会触发 `Illegal mix of collations`。
- **不要**在脚本调用后再手工 `ALTER DATABASE` 改 collation——业务修复应在校验 /
  迁移层做（参见 `just lint --reuse` 与项目自身的 `docs/architecture/system-design.md`）
  而不是在 provisioning 阶段打补丁。

## 模板同步配置

`just sync-template` 会读取 `config.toml` 中的 `[template_sync]` 表，用来决定默认模式下哪些项目路径不参与模板同步。

- `project_skip_paths`：默认跳过的项目路径，例如 `src/backend/`、`frontend-admin/`、`infra/`。
- `project_include_paths`：即使命中 `project_skip_paths` 也仍然显示的路径。

默认模式（不带 `--all`）只显示上游维护的基础设施（`justfile.shared`、`scripts/shared/*`、`scripts/build/*`、工具配置如 `pytest.ini`/`ruff.toml`/`.pre-commit-config.yaml`、`hooks/shared/*`、E2E 基础设施等），**不显示 AI 适配层文件**（`docs/ai-standards/`、`.github/copilot-instructions.md`、`.github/instructions/`、`.cursor/commands/`、`AGENTS.md`、`CLAUDE.md`）--这些文件派生项目常会自定义，只在 `--all` 模式才作为同步候选出现。详见 `scripts/shared/template/sync_template.sh` 的 `_is_ai_adapter_file`。

运行 `just sync-template --all` 时会忽略这些项目路径过滤规则，临时查看所有模板差异。

也可以用环境变量临时覆盖：

- `SYNC_TEMPLATE_PROJECT_SKIP_PATHS`：逗号或空格分隔的跳过路径列表。
- `SYNC_TEMPLATE_PROJECT_INCLUDE_PATHS`：逗号或空格分隔的保留显示路径列表。

## 日志相关配置

日志位于 `logs/` 目录，默认文件为 `logs/app.log`，并通过 `TimedRotatingFileHandler` 按天切分。

## 数据库 URL 解析

`AppSettings.resolved_database_url` 支持：

- 直接使用 `DATABASE_URL`。
- 在未提供完整 URL 时，通过组件拼接生成连接字符串。
