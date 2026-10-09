# Zata Codes Template

[English](README.md) | 简体中文

<p align="center">
  <img src="skills/zata-writer/assets/brand/zata-signature-blue-z-black-ata.png" width="180" alt="Zata 品牌签名字标">
</p>

面向 Python Web 项目的可演进工程模板：后端采用 **FastAPI + 四层模块化单体**，并配有独立的管理后台和用户端前端。模板提供可运行的认证、数据库迁移、运行轨迹诊断和可选沙箱基础设施；具体业务域由派生项目添加。

## 项目特点

- **边界清晰的后端**：按 API、核心编排、可插拔能力和基础设施分层，依赖方向由外向内。
- **两套前端**：管理后台使用 Vite、React 和 TanStack Router；用户端使用 Next.js 16、React 19 和 Tailwind CSS 4。
- **认证与会话**：用户注册和登录、独立的管理后台认证、HTTP-only Cookie 会话及 Redis 会话存储。
- **可选运行能力**：运行轨迹查询、健康探针、Prometheus 指标，以及 filesystem、Docker、E2B 沙箱适配器。
- **工程工作流**：通过 `uv` 管理 Python 依赖、`just` 运行开发任务，并提供 Alembic 迁移、pre-commit、测试和 MkDocs 文档站点。
- **不绑定模型供应商**：模板不内置 LLM 客户端或 provider 目录；派生项目按需读取 OpenAI 兼容端点配置并选择 SDK。

## 架构概览

```text
前端
├── frontend-admin/       管理后台（Vite + React）
└── frontend-public/      用户端（Next.js + React）

后端
├── src/backend/api/                 HTTP 接入与参数校验
├── src/backend/core/                用例、领域规则与接口
├── src/backend/engines/             可插拔的平台能力
├── src/backend/infrastructure/      数据库、配置、日志与外部适配器
└── src/backend/composition/         应用启动与依赖装配
```

后端层间依赖遵循 `api → core → engines → infrastructure`。`composition/` 负责装配各层实现，不承载业务规则。`engines/` 保留为扩展位置，具体业务和平台能力由派生项目按需实现。

## 快速开始

### 环境要求

- Python `>=3.11`（仓库开发环境固定为 Python 3.13）和 [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)
- Node.js 22 和 pnpm 11（运行前端时需要）
- Docker Compose（按下方示例启动本地 PostgreSQL 和 Redis）

### 安装并启动

```bash
cp .env.example .env.local
docker compose -f docker-compose.testing.yml up -d postgres redis
```

在 `.env.local` 中设置本地数据库和 Redis 连接：

```dotenv
DATABASE_URL=postgresql+psycopg2://testuser:testpass@localhost:5432/testdb
REDIS_URL=redis://:redis123@localhost:6379/0
```

安装依赖并启动后端、管理后台和用户端：

```bash
just sync dev
just run
```

`just run` 会在首次运行时安装前端依赖，并输出三个服务的实际访问地址。启动后端时会自动运行数据库迁移。若要登录管理后台，在 `.env.local` 配置 `AUTH_ADMIN_BOOTSTRAP_USERNAME` 和 `AUTH_ADMIN_BOOTSTRAP_PASSWORD`；真实凭据不要提交到 Git。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `just` | 列出可用任务 |
| `just sync dev` | 同步开发依赖并安装 pre-commit hooks |
| `just run` | 启动后端和两个前端 |
| `just run backend` | 只启动后端 |
| `just run frontend` | 只启动管理后台 |
| `just run frontend-public` | 只启动用户端 |
| `just down` | 停止本地服务 |
| `just test` | 运行本地测试集 |
| `just test all` | 运行完整测试集 |
| `just docs-serve` | 本地预览文档站点 |

## 工程工作流

### PRD Skill

仓库的 [PRD skill](skills/prd/SKILL.md) 会把功能需求整理成贴合当前架构、可审查且能执行的计划。它先检查现有代码、扩展点、相关 PRD 和前端入口，再优先复用并推荐满足需求的最小完整改动。每份 PRD 分为两个阅读层次：

- **Part A · 人审层（Review Layer）**：说明问题、用户可观察到的结果，以及需要人工确认的决定，不放实现细节。
- **Part B · 构建层（Build Layer）**：记录架构适配、实现指引、依赖关系，以及包含证据要求的现实验证计划。

PRD 工作流包含四个主要阶段：

1. **理解需求并检查仓库：** 把需求写成具体行为示例，列出假设和范围外事项；检查架构、可复用实现、前端应用、测试，以及相关的待执行或已归档 PRD。
2. **挑战方案：** 只询问会实质影响范围或行为的未决问题；比较复用路径、删去不必要的范围，并按 `R0`–`R3` 风险等级分类重要改动点。
3. **面向两类读者写成一份计划：** Part A 说明用户结果、需要人工决定的事项和验收视图；Part B 说明架构适配、影响范围、依赖和现实验证计划。证据深度随风险调整；用户可见改动要包含真实入口的视觉证据。
4. **执行并闭合证据链：** 执行 `tasks/pending/` 中的 PRD 前，先运行 `just prd start <prd-file>` 领取执行锁。`just ai implement <prd-file>` 负责实现和证据流程，并安排独立 verifier 审查。执行工作验证并完成对账后，将 PRD 移入 `tasks/archive/`。人工验收单独记录：未完成的 `Human-Confirmed` 项继续标记为 `🧍 待人工验收`，直到有人审查确认。

完整约定见 [PRD skill](skills/prd/SKILL.md)、[工具链规范](docs/ai-standards/tooling.md)和[测试规范](docs/ai-standards/testing.md)。

### Justfile 设计

`just` 命令分成两层，让模板通用工具可以同步更新，同时保留项目自己的入口：

- [`justfile`](justfile) 是本仓库的私有适配层，通过 `import 'justfile.shared'` 引入共享命令；裸运行 `just` 会列出可用任务。`run`、`down`、`copy` 等与项目结构有关的命令由这一层维护。
- [`justfile.shared`](justfile.shared) 放置可跨项目复用的模板命令，例如 `sync`、`lint`、`test`、`worktree`、`prd` 和 `e2e`。`just sync-template` 会更新共享层；项目专属命令应写在 `justfile`。

私有层启用了同名 recipe 覆盖，因此仓库可以在本地重写共享命令，而不必修改上游维护的共享文件。`just run` 协调启动后端和两个前端，并把当前 worktree 使用的端口写入被 Git 忽略的 `.env.run-state`；`just down` 据此停止对应服务，不同 worktree 也能避免端口冲突。`just copy <dir>` 会创建数据库和端口独立的派生项目。质量检查支持不同范围：`just lint` 检查暂存改动，`just lint --full` 检查整个仓库，`just lint --reuse` 检查复用和架构问题，`just lint --repo` 执行仓库级检查。冷启动执行 `just test` 时，共享 recipe 会先运行完整 lint，在 Alembic 可用时检查迁移图，再运行本地 pytest 选择集；本地 lint/test 成功标记与当前分支、提交和有效文件树绑定。CI 始终实际运行检查，不信任这些本地标记。所有权和覆盖规则详见[工具链规范](docs/ai-standards/tooling.md)。

### 测试与验证

测试同时覆盖功能行为、仓库约定和真实应用入口：

- **Python：** `tests/` 存放单元和集成测试；`tests/guards/` 守护仓库规范及共享工具契约。默认 `just test` 会排除标记为 `slow`、`real_api` 和 `redis` 的测试；`just test all` 运行完整 pytest 测试集，`just test real` 显式运行依赖真实 API 的测试。
- **前端：** `frontend-admin/` 使用 Vitest（`cd frontend-admin && pnpm test`）。两个前端都有 lint、类型检查和构建命令；`frontend-public/` 当前没有独立测试脚本。
- **端到端：** `tests/playwright-e2e/` 是独立的 TypeScript/Node 测试包。`just e2e no-auth` 运行无需凭据的流程；配置好种子账号后，`just e2e` 可运行更完整的测试集。
- **数据库兼容：** PostgreSQL 和 MySQL 都是支持目标。涉及数据库或迁移的改动应在相关数据库方言上验证，不能只用 SQLite 作为证据。

会写入真实数据库的测试必须使用 `realdb` 标记，并受自动清理和残留哨兵保护。前端视觉证据需要区分组件预览、生产组合和真实用户流程，并注明截图实际验证到哪一层。按改动选择可行的最高保真度：用单元和集成测试验证逻辑与模块边界；可执行行为要经过真实 API、CLI 或启动入口；用户可见流程使用 Playwright。需要凭据或外部服务的 live 测试采用显式 opt-in。完整要求见[测试规范](docs/ai-standards/testing.md)和 [E2E 指南](docs/guides/e2e.md)。

## 从模板创建项目

在模板仓库中运行：

```bash
just copy my-app
```

命令会在上级目录创建 `my-app/`，实例化项目名并准备新项目；它也会初始化 Git 仓库并创建初始提交。运行前请确认本地数据库配置可用，并已设置 Git 的用户名和邮箱。之后进入新目录继续开发：

```bash
cd ../my-app
just sync dev
just run
```

## 配置与扩展

- 非敏感默认值放在 `config.toml`；本地环境变量和密钥放在 `.env.local`。
- 需要接入大模型时，在 `.env.local` 配置 `MODEL_BASE_URL`、`MODEL_API_KEY`、`MODEL_NAME`；三项必须同时填写，模板不负责创建模型客户端。
- 沙箱配置是可选的，支持仅文件操作的 filesystem 模式、隔离容器 Docker 模式和 E2B 沙箱模式。
- 应用默认提供 `/health`、`/ready`、`/live` 健康探针；启用指标时还提供 `/metrics`。

## 加入 QQ 群

QQ群号：**1126828125**。扫码加入项目交流群：

<p align="center">
  <img src="docs/assets/community/qq-group-qr.png" width="360" alt="Zata 项目 QQ 群二维码，群号 1126828125">
</p>

## 文档

- [快速开始与开发环境](docs/getting-started.md)
- [PRD Skill 详细介绍](docs/guides/prd-skill.md)
- [配置说明](docs/guides/configuration.md)
- [系统架构](docs/architecture/system-design.md)
- [沙箱运行环境](docs/guides/sandbox-runtime.md)
- [可观测性](docs/guides/observability.md)
- [部署指南](docs/guides/deployment.md)
- [完整文档目录](docs/index.md)

## 主要目录

```text
src/backend/             FastAPI 后端
frontend-admin/          管理后台
frontend-public/         用户端
alembic/                 数据库迁移
tests/                   Python 测试
tests/playwright-e2e/    独立的 Playwright 端到端测试包
docs/                    MkDocs 文档
deploy/                  沙箱与部署资产
```
