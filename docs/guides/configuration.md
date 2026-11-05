# 配置说明

## `.env.example` 与必填变量

`.env.example` 中未注释的变量会进入默认环境，应仅用于默认流程必填项；可选功能或独立发布流程才需要的变量保持注释，并注明启用条件。密钥即使必填也只能提供空值，不能把真实凭据或可用默认值写入示例。密钥属性决定值如何保护，是否必填决定变量是否默认启用。

模板本身不启用模型调用、E2B 沙箱或 OTLP 外部上报，因此对应变量默认保持注释；派生项目启用这些能力时，再在本地 `.env.local` 中取消注释并填写。

本项目通过 `src/backend/infrastructure/config/settings.py` 中的 `AppSettings` 统一管理配置，并组合多个子配置模型，实现工程化的配置分层。

## 配置来源优先级

总优先级从高到低：

1. 环境变量（含 `.env` / `.env.local`）
2. `config.toml`
3. 代码默认值

## 关键配置模块

- **应用层配置**：应用名、日志级别、日志目录。
- **数据库配置**：后端类型、主机、端口、库名、驱动。
- **可观测性配置**：指标/请求 ID 开关、服务名、日志格式。
- **认证配置**：初始管理员种子、会话窗口。
- **主模型配置**：调用大模型所需的端点三件套（见下节，按需启用）。
- **基础设施配置**：Redis 等（派生项目按需扩展）。

## 常用实践

- 推荐在 `.env` 中存放密钥与敏感信息。
- 推荐在 `config.toml` 中维护非敏感默认项。
- 所有业务代码统一从 `config` 实例读取，不直接散落调用 `os.getenv`。

## 可替换的运行时配置中心

模板默认使用本地 provider：它从 `config.toml` 的 `[runtime_config]` 表读取参数，不连接外部服务。
需要集中管理或热更新非敏感运行时参数时，只需填写 Nacos 地址和应用账号；地址非空就会自动
切换到 Nacos。连接信息和应用账号放在后端自己的 `.env` / `.env.local`，服务器部署则写入
`deploy/vps-traefik/app.env`。

```dotenv
NACOS_SERVER_ADDR=nacos:8848
NACOS_USERNAME=application-reader
NACOS_PASSWORD=由密钥管理器提供
```

Nacos SDK 已包含在项目依赖和后端镜像中，不需要额外安装开关。默认使用 public Namespace、
`DEFAULT_GROUP` 和 `my-app-runtime.json`；需要调整作用域或 Data ID 时，只改 `config.toml` 的
`[config_provider]`，普通使用无需设置这些字段。

Nacos 文档使用 JSON 对象格式，例如：

```json
{
  "feature_flags": {
    "new_flow": false
  },
  "limits": {
    "max_batch_size": 20
  }
}
```

应用启动时会将快照放入 `app.state.runtime_config`；Nacos 更新经过 JSON 解析后会替换整份快照。
消费者应在每次使用时读取当前快照。非法更新会被忽略，已有快照继续生效。本地 provider 不监听
文件变化。Nacos SDK 会优先尝试本地 failover / snapshot，再读取服务端；没有可用本地快照且远程
读取失败时，应用启动会报错，避免使用空配置继续运行。

`NACOS_SERVER_ADDR` 接受 `host:port`。VPS + Traefik 部署与 `zata-ops` 的 Nacos 容器共用
`traefik` 网络时可用 `nacos:8848`。Dokploy 使用独立的 `dokploy-network`，需配置 Nacos 服务器私网
地址并确认容器能访问，或由运维将两个容器接入同一个受控 Docker 网络。Nacos 客户端还需要 gRPC
端口 `9848` 可达；不要把该端口作为 HTTP 路由代理。`NACOS_USERNAME`
和 `NACOS_PASSWORD` 应使用专门的应用账号，并只授予目标 Namespace / Group / Data ID 的读取
权限；它们与 Nacos 服务容器自身的 `NACOS_AUTH_TOKEN`、identity key/value 是不同凭据。

Nacos 仅用于非敏感运行时参数。数据库 URL、模型 API Key、应用密钥和 Nacos 客户端密码仍留在
`.env` / `app.env` 或专门的密钥管理服务，禁止放入 Nacos 配置文档。切换其他配置平台时，在
`src/backend/infrastructure/config/providers/` 实现同一 `ConfigProvider` 契约，并在 provider
工厂中注册；消费方不直接导入 Nacos SDK。

## 主模型配置

需要调用大模型的项目，在 `.env` / `.env.local` 声明端点三件套：

| 环境变量 | 作用 | 说明 |
|---|---|---|
| `MODEL_BASE_URL` | OpenAI 协议端点 | 通常以 `/v1` 结尾 |
| `MODEL_API_KEY` | 端点密钥 | 无需鉴权的本地端点（Ollama / vLLM）也要填占位值 |
| `MODEL_NAME` | 模型 id | 原样发送给端点，自带斜杠的写法（如 `anthropic/claude-3.5-sonnet`）同样可用 |

示例：

```bash
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=sk-xxxx
MODEL_NAME=qwen3-max
```

用 `load_primary_model_settings()` 读取：

```python
from backend.infrastructure.config.settings import load_primary_model_settings

primary_model_settings = load_primary_model_settings()
if primary_model_settings is not None:
    chat_model = ChatOpenAI(  # 或 openai.OpenAI(...)，模板不限定 SDK
        base_url=primary_model_settings.base_url,
        api_key=primary_model_settings.api_key.get_secret_value(),
        model=primary_model_settings.model_name,
    )
```

规则：

- 三项必须同时填写或同时留空。只填一部分会抛 `PrimaryModelConfigError` 并列出缺失的变量名——
  静默回退会让调用方在真正发请求时才收到含义不明的 401 或 404。
- 三项都留空时返回 `None`，表示本项目不使用模型；这是模板的默认状态，不影响启动。
- `api_key` 是 `SecretStr`，取值要显式 `.get_secret_value()`，避免误打进日志。
- **模板不内置 LLM 客户端，也不维护 provider 目录**（见归档 PRD
  `tasks/archive/20260518-164340-prd-decouple-template-from-business.md`）。需要同时接多个端点的
  项目，在这三个值之上自建注册表。

## Worktree 相关环境变量

`just worktree`（底层实现位于 `scripts/shared/worktree/create.sh`）支持以下环境变量来控制新 worktree 的依赖准备行为：

- `KODA_WORKTREE_BASE_BRANCH`
  - 新 worktree 默认使用的本地基底分支，默认值为 `main`。
  - 命令行参数 `--base <branch>` 会覆盖这个环境变量。
  - `just worktree --prune` 也用同一个值作为默认比对基线（同样可被 `--base` 覆盖）。
- `WORKTREE_FRONTEND_STRATEGY`
  - `install-per-worktree`：默认值。扫描 worktree 根目录和子目录中的前端项目，并在各自目录执行锁文件驱动的依赖安装。
  - `symlink-from-main`：不重新安装依赖，而是尝试把新 worktree 中的前端项目 `node_modules` 链接到源仓库对应目录。
- `WORKTREE_SKIP_FRONTEND_INSTALL`
  - 仅在 `WORKTREE_FRONTEND_STRATEGY=install-per-worktree` 时生效。
  - 设为 `true` 后，跳过前端依赖安装步骤。
- `WORKTREE_SKIP_SUBMODULES`
  - 仓库含 `.gitmodules` 时，新 worktree 会在安装前端依赖前执行 `git submodule update --init --recursive`。
  - 设为 `true` 后跳过这一步；依赖 submodule 的前端（例如 `file:` 指向 submodule 的包）可能无法安装或构建。

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

默认模式（不带 `--all`）只显示上游维护的基础设施（`justfile.shared`、`scripts/shared/*`、`scripts/build/*`、`.pre-commit-config.yaml`、`hooks/shared/*`、E2E 基础设施等）。`pytest.ini` 与 `ruff.toml` 需要承载项目自己的 markers、addopts 和 lint 例外，因此归项目所有，默认不同步。默认模式也**不显示 AI 适配层文件**（`docs/ai-standards/`、`.github/copilot-instructions.md`、`.github/instructions/`、`.cursor/commands/`、`AGENTS.md`、`CLAUDE.md`）--这些文件派生项目常会自定义，只在 `--all` 模式才作为同步候选出现。详见 `scripts/shared/template/sync_template.sh` 的 `_is_ai_adapter_file`。

运行 `just sync-template --all` 时会忽略这些项目路径过滤规则，临时查看所有模板差异。

也可以用环境变量临时覆盖：

- `SYNC_TEMPLATE_PROJECT_SKIP_PATHS`：逗号或空格分隔的跳过路径列表。
- `SYNC_TEMPLATE_PROJECT_INCLUDE_PATHS`：逗号或空格分隔的保留显示路径列表。
- `SYNC_TEMPLATE_PYTHON`：指定解析 `config.toml` 所用的 Python 解释器。

读取 `[template_sync]` 需要 TOML 解析器：Python 3.11+ 自带 `tomllib`，更低版本需装 `tomli`。脚本按 `SYNC_TEMPLATE_PYTHON` → 项目 `.venv/bin/python` → `PATH` 上的 `python3` → `python3.14`/`3.13`/`3.12`/`3.11` 的顺序挑第一个可用的。macOS 自带的 `python3` 至今是 3.9，通常由项目 `.venv` 兜底。一个都挑不到、而 `config.toml` 又确实写了 `[template_sync]` 时，脚本会**报错退出**而不是静默回退到内置默认跳过列表——否则你配的路径会被丢弃且毫无提示。

## 日志相关配置

日志位于 `logs/` 目录，默认文件为 `logs/app.log`，并通过 `TimedRotatingFileHandler` 按天切分。

## 数据库 URL 解析

`AppSettings.resolved_database_url` 支持：

- 直接使用 `DATABASE_URL`。
- 在未提供完整 URL 时，通过组件拼接生成连接字符串。
