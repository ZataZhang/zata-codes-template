# Extract Ops Toolkit into zata-ops

## 1. Introduction & Goals

### Problem Statement

`zata_code_template` 当前把运维能力（数据库备份/恢复、S3 诊断、VPS 环境初始化、Traefik 部署）内嵌在应用模板仓库中。这些能力散落在 `scripts/backup_service/`、`scripts/diagnostics/` 和 `deploy/vps-traefik/` 目录下，并通过 `just copy` 复制到每个下游项目。这带来了三个问题：

1. **N 份相同的脚本副本**：N 个下游项目各自维护一份完全相同的备份/部署脚本。
2. **Bug 修复无法自动同步**：备份逻辑或部署脚本有改进时，必须手动逐个回退到每个项目。
3. **模板仓库职责不纯**：模板仓库的核心是提供一个后端+前端应用脚手架，现在却背负了基础设施运维的包袱。

### Objectives

1. 将可复用的运维能力提取到一个独立的 CLI 工具 `zata-ops` 中。
2. `zata-ops` 可通过 `uv tool install` 全局安装，并在任意下游项目目录中运行。
3. 从 `zata_code_template` 中移除运维代码；用 `just` recipe 委托给 `zata-ops` CLI。
4. `zata-ops` 本身通过 `zata_code_template` 的 `just copy` 启动，从而继承相同的 `justfile` / `docs/ai-standards/` / pre-commit 规范。
5. 保持向后兼容：现有下游项目可以继续使用已复制的运维脚本，直到主动切换到 `zata-ops`。

### Realistic Validation

- [x] **DB backup dry-run 真实验证**：通过 `zata-ops db backup --project test --db-url postgresql://... --s3-endpoint http://localhost:9000 --dry-run` 验证参数解析、S3 key/manifest 预览、retention 计划全部正确，且不发起真实网络请求。
- [x] **zata-ops 安装真实验证**：通过 `cd /path/to/zata-ops && uv tool install --force . && zata-ops --version` 验证 CLI 可从本地源码安装并暴露 entry point。
- [x] **模板 just 委托真实验证**：通过 `just ops-backup --dry-run` 验证 `zata_code_template` 的 recipe 能读取项目 `.env` 并调用 `zata-ops db backup`。
- [x] **模板仓库清理真实验证**：通过 `rg "backup_service|scripts/diagnostics|BACKUP_IMAGE" . --glob '!tasks/**' --glob '!.git/**' --glob '!.venv/**'` 确认模板可执行代码、配置、文档中不存在遗留 ops 脚本引用；通过 `just lint --full` 确认无残留 import 错误。
- [x] **为什么单元测试不够**：单元测试只能验证 `zata-ops` 内部函数在 fixture 中的行为；真实验证需要证明 CLI 安装入口、参数透传、项目 `.env` 加载、以及模板仓库的 `just` 委托路径可用。

---

## 2. Requirement Shape

| Field | Value |
|---|---|
| **Actor** | 维护一个或多个 Zata 下游项目的开发者 / DevOps 工程师 |
| **Trigger** | 需要初始化服务器、备份/恢复数据库、检查 S3 连通性、排查部署日志、或查看项目健康看板 |
| **Expected Behavior** | 全局执行一次 `uv tool install`（例如 `cd /path/to/zata-ops && uv tool install --force .`）；然后在任意项目目录中运行 `zata-ops <command>`，传入项目专属参数（显式 CLI flag 或自动从 `.env` 加载） |
| **Scope Boundary** | `zata-ops` 是一个独立仓库；本 PRD 是大项目目标态，覆盖创建它、迁移现有 ops 能力、增加 logs/dashboard/migrate 等运维命令、以及从 `zata_code_template` 中移除运维代码。不涉及重写应用业务逻辑、修改 AI 模型 provider 体系或改动前端代码 |

---

## 3. Repository Context And Architecture Fit

### Current Relevant Modules

| Path | Role |
|---|---|
| `scripts/backup_service/` | 独立的 Python 包（含 Dockerfile + main.py），负责数据库 dump、logs/resources 归档、manifest 上传、retention 清理、交互式 restore/list，以及容器内 scheduler。所有配置从环境变量读取 |
| `scripts/diagnostics/check_s3_config.py` | CLI 脚本，通过上传测试对象验证 S3 endpoint/bucket/凭证 |
| `scripts/diagnostics/check_claude_code.sh` | Shell 脚本，检查 Claude Code CLI 是否可用 |
| `deploy/vps-traefik/` | VPS 部署资产：`docker-compose.yml`、`bootstrap.sh`、`install-docker-traefik.sh`、`fix-acme-email.sh`、`.env.example`、`app.env.example`、`github-actions-deploy.yml.example` |
| `docker-compose.dokploy.yml` | 生产环境 compose，包含 `zata-codes-template-backup` 服务（profile `backup`） |
| `docker-compose.yml` | 本地开发 compose，包含相同的 backup 服务 |
| `.env.example` / `.env.dokploy.example` / `deploy/vps-traefik/app.env.example` | 环境变量模板，包含 `S3_*`、`BACKUP_TIME`、`FULL_BACKUP_DAY`、`RETENTION_DAYS`、`BACKUP_IMAGE` |
| `justfile` | 项目 recipe，包括 `run`、`down`、`frontend`、`copy` |
| `.github/workflows/ci.yml` / `cd.yml` | CI/CD 流水线（此前已清理 stale 的 `--ignore=tests/test_model_loader_real.py`） |
| `deploy/vps-traefik/github-actions-deploy.yml.example` | 可选 VPS 部署 workflow 示例，当前构建 backend/frontend/backup 三个镜像，并通过 `BACKUP_IMAGE` 更新服务器 `.env` |
| `tests/test_backup_database.py` / `tests/test_backup_restore.py` | 当前直接导入 `scripts.backup_service`，迁出后必须删除、替换为 repo audit，或移动到 `zata-ops` |

### Existing Architecture Patterns

- **Python 后端**：`uv` + `pydantic-settings` + `pydantic` + `tomllib`
- **CLI 工具**：模板中尚未使用 `typer`；`zata-ops` 可新增 `typer` 作为 CLI 框架（类型驱动，与 pydantic 风格一致）
- **终端输出**：当前 lockfile 未包含 `rich`；`zata-ops` 可新增 `rich` 作为终端输出/看板依赖
- **配置加载**：`settings.py` 中的 `_load_toml_section_data` 读取 `config.toml` section；`.env` 通过 `pydantic-settings` 加载
- **测试**：当前模板使用 `pytest`；`zata-ops` 可新增 `pytest-mock`、`moto`、testcontainers 或 MinIO/Postgres integration fixtures 作为运维工具测试依赖
- **文档**：`mkdocs` + `mkdocstrings`
- **任务运行器**：`just`
- **Docker**：多阶段构建，`docker-compose.yml` + `docker-compose.dokploy.yml`

### Ownership And Dependency Boundaries

- `zata_code_template` 拥有：应用脚手架、`just copy` / `sync-template` 工作流、AI 编码规范（`docs/ai-standards/`）
- `zata-ops` 将拥有：所有基础设施/运维能力
- 跨边界契约：`zata_code_template` 只通过 `just` recipe 和文档引用 `zata-ops`；不存在 Python import 依赖

### Constraints

1. `zata-ops` 必须通过 `zata_code_template` 的 `just copy` 启动，以继承现有规范。
2. `zata-ops` 必须保持作为独立 CLI 的可安装性（`uv tool install`），不能要求克隆仓库。
3. 已存在的下游项目（通过 `just copy` 创建的）不在强制迁移范围内；它们保留已复制的脚本，直到手动更新。
4. `zata_code_template` 的 `deploy/vps-traefik/` 目录包含与模板服务名（`zata-codes-template-backend` 等）紧耦合的 Traefik 部署配置；提取前这些服务名引用必须参数化。

### Existing Capability Parity And Allowed Changes

本 PRD 是一个大项目目标态，但第一批必须先避免无意回归：

- **必须迁移的现有能力**：PostgreSQL/SQLite dump、数据库 restore、S3 list/check/upload/download、manifest、retention、logs/resources 归档、full/incremental 备份、restore chain、交互式 list/restore 的非交互替代路径。
- **允许改变的现有能力**：旧的容器内 scheduler 不再作为模板 compose service 常驻运行；调度改为外部触发（systemd timer、cron、GitHub Actions、Dokploy scheduled job 或手动 `zata-ops db backup`）。`zata-ops` 只需要提供可调度的单次执行命令和文档化示例。
- **允许删除的现有能力**：`scripts/diagnostics/check_claude_code.sh` 不迁入 `zata-ops`，除非实现阶段发现它仍有实际运维价值；删除时需在文档中说明 Claude Code 检查不属于项目运行时 ops 能力。
- **新增目标态能力**：`db migrate`、`logs tail/search`、`dashboard` 属于本大项目范围，但不能阻塞第一批“现有 ops 能力迁出 + 模板清理”闭环；它们必须有最小可运行入口、明确 mock/真实边界和独立验收项。

### Potential Redundancy Risks

- **风险 1**：`zata-ops` 可能重复 `zata_code_template` 已有的 `pydantic-settings` 配置加载模式。缓解：`zata-ops` 使用针对运维场景定制的独立 `Settings` 类；不需要共享代码。
- **风险 2**：`backup_service` 已有自己的 `config.py`（读取环境变量）。提取时必须把以环境变量为中心的配置替换为 CLI 参数 + `.env` 加载（pydantic-settings），才能跨项目真正复用。
- **风险 3**：两个仓库都会有 `Dockerfile` 和 `docker-compose.yml`。这可以接受，因为它们目的不同（应用 vs 运维工具箱）。

---

## 4. Recommendation

### Recommended Approach

通过 `zata_code_template` 的 `just copy` 启动一个新的 `zata-ops` 仓库，然后：

1. **在 `zata-ops` 中**：构建基于 `typer` 的 CLI。目标态提供以下子命令：
   - `zata-ops db backup`
   - `zata-ops db restore`
   - `zata-ops db list`
   - `zata-ops db migrate`
   - `zata-ops db check`
   - `zata-ops env provision`
   - `zata-ops env fix`
   - `zata-ops logs tail`
   - `zata-ops logs search`
   - `zata-ops dashboard`

2. **先完成 baseline 闭环**：`db backup`、`db restore`、`db list`、`db check`、`env provision`、`env fix` 必须先达到可安装、可运行、可从模板 `just` 委托调用的状态。

3. **迁移代码**：`scripts/backup_service/` → `zata-ops/db/backup.py` + `restore.py` + `list.py`；`scripts/diagnostics/check_s3_config.py` → `zata-ops/db/check.py`；`deploy/vps-traefik/*.sh` → `zata-ops/env/provision.py` + `fix.py`（可保留 shell 模板，由 Python 渲染并执行）。

4. **扩展目标态命令**：在 baseline 完成后实现 `db migrate`、`logs tail/search`、`dashboard`。这些命令是本 PRD 范围内的目标态，但必须独立验收，不能影响 baseline 的迁移和模板清理。

5. **在 `zata_code_template` 中**：删除 `scripts/backup_service/`、`scripts/diagnostics/`、`deploy/vps-traefik/*.sh`（Traefik 专属 compose 文件作为项目级部署配置保留）。在 `justfile` 中新增 `ops-backup`、`ops-restore`、`ops-provision` recipe，通过 shell 调用 `zata-ops`。

### Why This Fits

- 尊重现有的 `uv` + `just` + `mkdocs` 工具链。
- 使用 `typer`（与 pydantic 模式兼容）构建 CLI，学习成本最低。
- 让 `zata_code_template` 专注于应用脚手架，运维能力集中管理。
- `uv tool install` 分发是 Python CLI 的最简路径；初期不需要 Homebrew 或 PyPI。

### Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **保留 ops 在模板中，改进 `just copy`** | 无法解决 N 份副本的维护问题。Bug 修复仍需手动逐个回退。 |
| **用 Git submodule 管理 ops** | Submodule 对非专业用户很脆弱；`uv tool install` 更简单且版本固定。 |
| **用 Go 写 zata-ops** | 用户明确选择 Python（熟悉）；Go 会分裂工具链（没有 `uv` 和 `mkdocstrings`）。 |
| **把 zata-ops 做成被应用导入的库** | 运维能力（备份、初始化）通常在开发机或 CI 中运行，不在应用进程内部。CLI 是正确的边界。 |

---

## 5. Implementation Guide

> This section is a living implementation guide based on current repository analysis. If implementation discovers additional affected files, hidden dependencies, edge cases, or a better path, update this PRD before proceeding.

### Core Logic

1. **启动 `zata-ops` 仓库**：在 `zata_code_template` 中执行 `cd /parent && just copy zata-ops`。这会自动获得 `justfile`、`pyproject.toml`、`docs/ai-standards/`、pre-commit hooks 等。
2. **在 `zata-ops` 中替换应用专属代码**为运维专属代码：
   - 删除 `src/backend/`、`frontend/`、`tests/`（旧的应用测试）。
   - 创建 `src/zata_ops/` 包，包含 `cli.py`、`config.py`、`db/`、`env/`、`logs/`、`observability/`。
   - 更新 `pyproject.toml` 依赖（添加 `typer`、`rich`、`boto3`、`psycopg[binary]`、`pydantic-settings` 等；`moto`、`pytest-mock`、testcontainers 放 dev 依赖）。
   - 更新 `pyproject.toml` entry point：`zata-ops = "zata_ops.cli:app"`。
3. **迁移备份逻辑**：
   - 阅读 `scripts/backup_service/main.py`、`archiver.py`、`db.py`、`s3_client.py`。
   - 提取纯函数（dump DB、logs/resources 归档、manifest、上传 S3、执行 retention）到 `zata_ops/db/_backup_impl.py`。
   - 在 `zata_ops/db/backup.py` 中用 `typer` 命令包装。
   - 把硬编码的环境变量读取替换为 `pydantic-settings` `.env` 加载 + CLI 参数覆盖。
   - 保留 full/incremental 语义和 manifest shape，避免新 restore 无法读取旧备份。
   - 删除旧容器内 scheduler 作为常驻服务的职责；提供 `zata-ops db backup` 单次执行命令，调度交给外部 scheduler。
4. **迁移恢复逻辑**：与备份类似，来源为 `scripts/backup_service/restore.py`。保留数据库 restore、logs/resources restore、chain restore、list、`--yes` 非交互执行、破坏性 flag 的显式确认/保护。
5. **迁移检查逻辑**：来源为 `scripts/diagnostics/check_s3_config.py`。
6. **迁移初始化脚本**：阅读 `deploy/vps-traefik/install-docker-traefik.sh`、`bootstrap.sh`、`fix-acme-email.sh`。优先保留 shell 模板作为 `zata_ops/env/templates/` 中的资源，由 Python 渲染、dry-run 输出并通过本地 `ssh`/`scp` 或可选 `[ssh]` extra 执行；不要把复杂 shell 一次性硬翻译成 Python 业务逻辑。
7. **扩展 logs/dashboard/migrate**：
   - `logs tail/search` 封装 `docker logs` / `journalctl` / 本地日志路径，必须支持 dry-run 或 command preview。
   - `db migrate` 先定义为 PostgreSQL 到 PostgreSQL 的显式迁移命令（dump + restore），不要和 Alembic schema migration 混名；命令帮助必须说明语义。
   - `dashboard` 使用 `rich` 的 `Layout`/`Table`/`Panel`，默认只读本地项目配置和 mockable status providers。
8. **清理 `zata_code_template`**：
   - 删除 `scripts/backup_service/`、`scripts/diagnostics/`。
   - 删除 `deploy/vps-traefik/*.sh`（保留 `.env.example`、`app.env.example`、`docker-compose.yml` 等项目级部署配置）。
   - 从所有 `.env*` 模板中移除 `BACKUP_IMAGE`、`S3_*`、`BACKUP_TIME`、`FULL_BACKUP_DAY`、`RETENTION_DAYS`。
   - 从 `docker-compose.yml` 和 `docker-compose.dokploy.yml` 中移除 `zata-codes-template-backup` 服务。
   - 更新 `deploy/vps-traefik/github-actions-deploy.yml.example`，只构建 backend/frontend 镜像，不再构建 backup 镜像或写入 `BACKUP_IMAGE`。
   - 在 `justfile` 中新增 `ops-backup`、`ops-restore`、`ops-provision` recipe；如需要，新增 `ops-check` 和 `ops-dashboard`。
   - 删除或迁移 `tests/test_backup_database.py`、`tests/test_backup_restore.py` 中对 `scripts.backup_service` 的 import；相关行为测试移动到 `zata-ops`。

### Change Impact Tree

```text
.
├── zata-ops/ (NEW REPOSITORY)
│   ├── pyproject.toml
│   │   [修改]
│   │   【总结】替换 app 依赖为 ops CLI 依赖，改 entry point 为 zata-ops
│   │   ├── 删除 backend/frontend 相关依赖
│   │   ├── 添加 typer, rich, boto3, psycopg[binary], pydantic-settings
│   │   ├── dev 依赖添加 moto, pytest-mock, testcontainers 或等效 integration fixtures
│   │   └── 改 project.scripts: zata-ops = "zata_ops.cli:app"
│   ├── src/zata_ops/
│   │   ├── cli.py
│   │   │   [新增]
│   │   │   【总结】typer 顶层入口，挂载 db/env/logs/observability 子命令
│   │   ├── config.py
│   │   │   [新增]
│   │   │   【总结】pydantic-settings 加载 ~/.config/zata-ops/ 和项目 .zata-ops.toml
│   │   ├── db/
│   │   │   ├── backup.py
│   │   │   │   [新增]
│   │   │   │   【总结】typer 命令包装，调 _backup_impl.run_backup
│   │   │   ├── restore.py
│   │   │   │   [新增]
│   │   │   │   【总结】typer 命令包装，调 _restore_impl.run_restore
│   │   │   ├── migrate.py
│   │   │   │   [新增]
│   │   │   │   【总结】PostgreSQL 到 PostgreSQL 的显式数据迁移命令（pg_dump + psql），不同于 Alembic schema migration
│   │   │   ├── check.py
│   │   │   │   [新增]
│   │   │   │   【总结】S3 连通性检查，从 diagnostics/check_s3_config.py 移植
│   │   │   ├── _backup_impl.py
│   │   │   │   [新增]
│   │   │   │   【总结】纯函数：dump DB、归档 logs/resources、生成 manifest、上传 S3、按 retention_days 清理旧备份
│   │   │   └── _restore_impl.py
│   │   │       [新增]
│   │   │       【总结】纯函数：从 S3 下载、解压、恢复 DB/logs/resources，并支持 incremental chain
│   │   ├── env/
│   │   │   ├── provision.py
│   │   │   │   [新增]
│   │   │   │   【总结】VPS 初始化：渲染/执行 shell 模板，安装 Docker/Traefik、配置 swap、防火墙
│   │   │   └── fix.py
│   │   │       [新增]
│   │   │       【总结】修复脚本：渲染/执行 shell 模板，修复 ACME 邮箱、Traefik 路由、证书问题
│   │   ├── env/templates/
│   │   │   [新增]
│   │   │   【总结】保存从 deploy/vps-traefik/*.sh 迁出的 shell 模板，供 dry-run 和 SSH 执行复用
│   │   ├── logs/
│   │   │   ├── tail.py
│   │   │   │   [新增]
│   │   │   │   【总结】docker logs / journalctl 封装，支持 --project --since
│   │   │   └── search.py
│   │   │       [新增]
│   │   │       【总结】日志内容过滤搜索
│   │   └── observability/
│   │       ├── dashboard.py
│   │       │   [新增]
│   │       │   【总结】rich 终端仪表盘：项目状态、资源用量、备份时间线
│   ├── tests/
│   │   ├── test_db_backup.py
│   │   │   [新增]
│   │   │   【总结】mock S3 + 临时 PG 容器（integration marker）测试 backup dry-run、manifest、retention、logs/resources
│   │   ├── test_db_restore.py
│   │   │   [新增]
│   │   │   【总结】round-trip 测试：backup 后 restore，校验 DB/logs/resources 数据一致性和 incremental chain
│   │   ├── test_db_check.py
│   │   │   [新增]
│   │   │   【总结】S3 连通性检查命令的参数解析、test object 上传/删除、错误输出
│   │   ├── test_logs_dashboard.py
│   │   │   [新增]
│   │   │   【总结】logs 命令 command preview 与 dashboard mock provider 渲染 smoke
│   │   └── test_env_provision.py
│   │       [新增]
│   │       【总结】dry-run 模式测试 provision/fix 命令参数解析和 shell 模板渲染
│   └── docker/
│       └── Dockerfile
│           [新增]
│           【总结】最小化镜像，供无法装 Python 的环境用
│
├── zata_code_template/ (THIS REPOSITORY)
│   ├── scripts/backup_service/
│   │   [删除]
│   │   【总结】全部迁出到 zata-ops，本仓库不再维护备份服务
│   ├── scripts/diagnostics/
│   │   [删除]
│   │   【总结】S3 检查迁到 zata-ops db check；claude_code 检查价值低，删除
│   ├── deploy/vps-traefik/
│   │   ├── bootstrap.sh
│   │   │   [删除]
│   │   │   【总结】迁到 zata-ops env provision
│   │   ├── install-docker-traefik.sh
│   │   │   [删除]
│   │   │   【总结】迁到 zata-ops env provision
│   │   ├── fix-acme-email.sh
│   │   │   [删除]
│   │   │   【总结】迁到 zata-ops env fix
│   │   ├── docker-compose.yml
│   │   │   [保留]
│   │   │   【总结】项目级部署 compose，只删 backup service 和 BACKUP_IMAGE 引用
│   │   ├── .env.example
│   │   │   [修改]
│   │   │   【总结】删 BACKEND_IMAGE/FRONTEND_IMAGE 之外的所有镜像变量和 S3/备份变量
│   │   └── app.env.example
│   │       [修改]
│   │       【总结】删 S3_*、BACKUP_TIME、RETENTION_DAYS 等 ops 变量
│   ├── docker-compose.yml
│   │   [修改]
│   │   【总结】删除 zata-codes-template-backup service 整段和 S3 环境变量
│   ├── docker-compose.dokploy.yml
│   │   [修改]
│   │   【总结】同上，删除 backup service 和 S3 相关 env
│   ├── deploy/vps-traefik/github-actions-deploy.yml.example
│   │   [修改]
│   │   【总结】删除 backup image 构建矩阵、BACKUP_IMAGE env 注入和服务器 .env 写入
│   ├── .env.example
│   │   [修改]
│   │   【总结】删除 S3/备份/ops 相关变量，添加注释指向 zata-ops 仓库
│   ├── .env.dokploy.example
│   │   [修改]
│   │   【总结】同上
│   ├── justfile
│   │   [修改]
│   │   【总结】新增 ops-backup / ops-restore / ops-provision recipes，调 zata-ops CLI
│   ├── tests/
│   │   [修改]
│   │   【总结】删除或迁移直接导入 scripts.backup_service 的测试，新增模板清理审计测试
│   └── docs/
│       ├── guides/deployment.md
│       │   [修改]
│       │   【总结】更新部署文档，说明 ops 能力已外迁
│       └── guides/backup.md (if exists)
│           [修改]
│           【总结】替换为 zata-ops 使用说明
```

### Executor Drift Guard

清理 `zata_code_template` 时，对已删除运维文件的隐藏引用可能存在于：

- `docs/` markdown 文件中提及 `backup_service` 或 `scripts/diagnostics` 的地方
- `CLAUDE.md` 或 `AGENTS.md` 中引用 ops 路径的地方
- `tests/` 中从 `scripts.backup_service` 导入的代码（当前存在，需要删除或迁到 `zata-ops`）
- `.github/workflows/` 中构建/推送 backup 镜像的步骤
- `deploy/vps-traefik/github-actions-deploy.yml.example` 中构建/推送 backup 镜像和写入 `BACKUP_IMAGE` 的步骤
- `justfile.shared` 或 `justfile` 中引用 backup 命令的地方

用以下命令验证清理完整性：

```bash
# 查找任何残留的 backup_service 引用（PRD 自身可以保留历史说明）
cd /Users/zata/code/zata_code_template
rg "backup_service" . --glob '!tasks/**' --glob '!.git/**' --glob '!.venv/**'

# 查找 diagnostics 脚本的残留引用
rg "check_s3_config|check_claude_code|scripts/diagnostics" . --glob '!tasks/**' --glob '!.git/**' --glob '!.venv/**'

# 查找 BACKUP_IMAGE 引用（迁移后应只在 zata-ops 中出现）
rg "BACKUP_IMAGE" . --glob '!tasks/**' --glob '!.git/**' --glob '!.venv/**'

# 查找模板 env/compose/deploy 文件中的备份变量；docs 中允许保留迁移说明或 zata-ops 使用说明
rg "S3_ENDPOINT|S3_ACCESS_KEY|S3_SECRET_KEY|S3_BUCKET|S3_PREFIX|S3_ADDRESSING_STYLE|BACKUP_TIME|FULL_BACKUP_DAY|RETENTION_DAYS" \
  .env.example .env.dokploy.example docker-compose.yml docker-compose.dokploy.yml deploy/vps-traefik

# 检查测试是否导入已删除的模块
rg "from scripts\.backup_service|import scripts\.backup_service" --type py

# 检查 GitHub Actions / deploy 示例是否仍构建 backup image
rg "zata-codes-template-backup|service: backup|BACKUP_IMAGE|scripts/backup_service/Dockerfile" \
  .github deploy/vps-traefik --glob '!tasks/**'
```

### Flow / Architecture Diagram

```mermaid
flowchart TD
    subgraph "Developer Machine / CI"
        A["uv tool install ."]
        B["just ops-backup"]
        C["zata-ops db backup --project my-app ..."]
        D["zata-ops env provision --host vps1 ..."]
        E["zata-ops dashboard"]
    end

    subgraph "zata_code_template (per project)"
        F["justfile<br/>ops-backup recipe"]
        G[".env<br/>project secrets"]
        H["src/backend/<br/>application code"]
    end

    subgraph "zata-ops (shared CLI)"
        I["zata_ops/cli.py<br/>typer entry point"]
        J["zata_ops/db/<br/>backup/restore/migrate/check"]
        K["zata_ops/env/<br/>provision/fix"]
        L["zata_ops/observability/<br/>dashboard"]
    end

    subgraph "Infrastructure"
        M["PostgreSQL"]
        N["S3-compatible Storage"]
        O["VPS / Docker / Traefik"]
    end

    A --> I
    B --> F
    F --> C
    C --> I
    I --> J
    J --> M
    J --> N
    D --> I
    I --> K
    K --> O
    E --> I
    I --> L
    G -.-> C
    G -.-> D
```

### Realistic Validation Plan

| Behavior | Real Entry Point | Test Layer | Mock Boundary | Data/Env Needed | Command Or Procedure | Required For Acceptance |
|---|---|---|---|---|---|---|
| `zata-ops` CLI 安装并显示帮助 | `uv tool install` + `zata-ops --help` | e2e / smoke | None (local filesystem) | `uv` installed, `zata-ops` source | `cd /path/to/zata-ops && uv tool install --force . && zata-ops --help && zata-ops --version` | Yes |
| DB backup dry-run | `zata-ops db backup --dry-run` | real entry + integration | No live S3/DB calls; S3/DB clients replaced by dry-run plan | `zata-ops` installed; local project `.env` or explicit flags | `zata-ops db backup --project test --db-url postgresql://user:pass@localhost:5432/app --s3-endpoint http://localhost:9000 --s3-bucket app-backups --s3-access-key key --s3-secret-key secret --dry-run` | Yes |
| DB backup + restore round-trip | `zata-ops db backup` then `zata-ops db restore` | integration (opt-in) | Local MinIO + Postgres testcontainer, no production services | `DOCKER_HOST` available, `pytest` with `-m integration` | `cd /path/to/zata-ops && uv run pytest tests/test_db_restore.py -v -m integration` | No (opt-in) |
| S3 check command | `zata-ops db check` | integration | S3 via moto/local MinIO | S3 fixture or local MinIO | `cd /path/to/zata-ops && uv run pytest tests/test_db_check.py -v` | Yes |
| VPS provision dry-run | `zata-ops env provision --dry-run` | real entry smoke | No SSH call; render command/script only | local filesystem | `zata-ops env provision --host example.com --user deploy --profile vps-traefik --dry-run` | Yes |
| 模板 just 委托 | `just ops-backup --dry-run` | real entry smoke | No live S3/DB calls; delegates to installed `zata-ops` dry-run | `zata-ops` installed; project `.env` or `.env.local` fixture | `cd /Users/zata/code/zata_code_template && just ops-backup --dry-run` | Yes |
| 模板仓库无 ops 脚本引用 | `rg` search | repo audit | None | N/A | `cd /Users/zata/code/zata_code_template && rg "backup_service|scripts/diagnostics|BACKUP_IMAGE" . --glob '!tasks/**' --glob '!.git/**' --glob '!.venv/**'` | Yes |
| 模板 `just lint --full` 通过 | `just lint --full` | CI-like | None | `uv`, `pre-commit` | `cd zata_code_template && just lint --full` | Yes |
| `zata-ops` logs/dashboard 渲染 | `zata-ops logs tail --dry-run` + `zata-ops dashboard --mock` | real entry smoke | External process/API calls mocked or previewed | `rich` installed | `zata-ops logs tail --project test --since 1h --dry-run && zata-ops dashboard --mock` | Yes |

**Failure Triage Notes:**
- 如果 `uv tool install` 失败：确认命令是 `uv tool install --force .` 或 `uv tool install --force /path/to/zata-ops`；检查 `pyproject.toml` `[project.scripts]` 和 `src/zata_ops/cli.py:app` 是否存在。
- 如果 `zata-ops db backup` 失败：检查 `pydantic-settings` `.env` 加载与 CLI 参数的优先级；验证 `--dry-run` 是否跳过了实际 S3 上传。
- 如果清理后 `just lint --full` 失败：检查 `.pre-commit-config.yaml` 是否引用了已删除的路径；检查 `tests/` 中是否有陈旧的 import。

### Low-Fidelity Prototype

Not required. This is a CLI/backend refactor with no UI layout ambiguity.

### ER Diagram

No data model changes in this PRD. `zata-ops` uses ephemeral CLI state and external services (DB, S3); no persistent schema.

### Interactive Prototype Change Log

No interactive prototype file changes in this PRD.

### External Validation

Checked `uv tool install` command shape because the installation syntax is an external tool contract and can change by uv version.

- Checked: local `uv tool install --help` on `uv 0.11.12` and official Astral uv CLI reference.
- Sources: <https://docs.astral.sh/uv/reference/cli/>
- Inference: `uv tool install` accepts the package/path as a positional argument; `--from` belongs to `uv tool run`, so install validation must use `uv tool install --force .` or `uv tool install --force /path/to/zata-ops`.

---

## 6. Definition Of Done

1. `zata-ops` 仓库已创建并从 `zata_code_template` 启动。
2. `zata-ops` CLI 具备可用的 `db backup`、`db restore`、`db list`、`db check`、`env provision`、`env fix` baseline 命令。
3. `zata-ops` CLI 具备目标态扩展命令 `db migrate`、`logs tail`、`logs search`、`dashboard` 的最小可运行入口。
4. `zata-ops` 可通过 `cd /path/to/zata-ops && uv tool install --force .` 干净安装。
5. `zata_code_template` 中不存在 `scripts/backup_service/`、`scripts/diagnostics/` 或 `deploy/vps-traefik/*.sh` 文件。
6. `zata_code_template` 的 `.env*` 文件中不包含 `S3_*`、`BACKUP_TIME`、`FULL_BACKUP_DAY`、`RETENTION_DAYS`、`BACKUP_IMAGE` 变量。
7. `zata_code_template` 的 `docker-compose.yml`、`docker-compose.dokploy.yml` 和 `deploy/vps-traefik/docker-compose.yml` 中无 backup 服务。
8. `deploy/vps-traefik/github-actions-deploy.yml.example` 不再构建 backup image 或写入 `BACKUP_IMAGE`。
9. `zata_code_template` 的 `justfile` 中有委托给 `zata-ops` 的 `ops-backup`、`ops-restore`、`ops-provision` recipe。
10. 所有测试通过：`zata-ops` pytest 套件 + `zata_code_template` `just lint --full` + `just test`。
11. 两个仓库的文档均已更新。

---

## 7. Acceptance Checklist

### Architecture Acceptance

- [x] `zata-ops` 是独立仓库，对 `zata_code_template` 无 Python import 依赖。
- [x] `zata_code_template` 仅通过 `just` recipe 和文档引用 `zata-ops`（无代码导入）。
- [x] `zata-ops` 使用与 `zata_code_template` 相同的工具链（`uv`、`just`、`mkdocs`、`ruff`、`pytest`）。
- [x] `zata-ops` 的 baseline 命令和扩展命令都挂载在单一 `zata_ops.cli:app` entry point 下，无第二套 CLI 入口。

### Dependency Acceptance

- [x] `zata-ops` 的 `pyproject.toml` 在 dependencies 中列出 `typer>=0.12`、`rich>=13`、`boto3>=1.35`、`psycopg[binary]>=3.2`、`pydantic-settings>=2`。
- [x] `zata-ops` 的 dev dependencies 中列出 S3/CLI/mock/integration 测试所需依赖（例如 `moto`、`pytest-mock`、testcontainers 或等效本地 fixture）。
- [x] `zata_code_template` 的 `pyproject.toml` 中不再残留 `boto3` 或 backup-service 专属依赖。
- [x] 在 `zata_code_template` 的可执行代码、测试、compose、deploy workflow 示例中，`rg "backup_service|scripts/diagnostics|BACKUP_IMAGE" . --glob '!tasks/**' --glob '!.git/**' --glob '!.venv/**'` 无命中。
- [x] 在 `zata_code_template` 的 env/compose/deploy 模板中，`rg "S3_ENDPOINT|S3_ACCESS_KEY|S3_SECRET_KEY|S3_BUCKET|S3_PREFIX|S3_ADDRESSING_STYLE|BACKUP_TIME|FULL_BACKUP_DAY|RETENTION_DAYS" .env.example .env.dokploy.example docker-compose.yml docker-compose.dokploy.yml deploy/vps-traefik` 无命中。

### Behavior Acceptance

- [x] `zata-ops db backup --help` 显示所有必需 flag（`--project`、`--db-url`、`--s3-endpoint` 等）。
- [x] `zata-ops db backup --dry-run` 在无网络调用的情况下完成，并打印预期的 S3 key。
- [x] `zata-ops db backup` 保留旧 `backup_service` 的 DB、logs、resources、manifest、full/incremental、retention 语义。
- [x] `zata-ops db restore --from <s3-key> --target-db-url <url>` 可恢复先前备份的数据库，并支持 logs/resources restore 与 incremental chain。
- [x] `zata-ops db list` 可列出 S3 中可用备份及其 manifest type。
- [x] `zata-ops db check --s3-endpoint ... --s3-bucket ...` 验证 S3 连通性。
- [x] `zata-ops env provision --dry-run` 和 `zata-ops env fix --dry-run` 可渲染将执行的 VPS/Traefik shell 操作，不发起 SSH。
- [x] `zata-ops db migrate --help` 明确说明该命令是 PostgreSQL 数据迁移，不是 Alembic schema migration。
- [x] `zata-ops logs tail/search --dry-run` 可输出将执行的日志查询命令或本地日志读取计划。
- [x] `zata-ops dashboard --mock` 可使用 mock provider 渲染终端看板。
- [x] `zata_code_template` 的 `just ops-backup` recipe 调用 `zata-ops db backup` 并传入项目 `.env` 值。

### Documentation Acceptance

- [x] `zata-ops/README.md` 说明安装方式（`uv tool install`）和基本用法。
- [x] `zata-ops/docs/` 说明 backup 调度推荐方式（systemd timer、cron、GitHub Actions、Dokploy scheduled job 或手动调用），并说明旧 compose backup service 已移除。
- [x] `zata_code_template/docs/guides/deployment.md` 已更新，引用 `zata-ops` 进行环境初始化。
- [x] `zata_code_template/docs/guides/backup.md`（或等效文档）已更新，引用 `zata-ops` 进行备份/恢复。

### Validation Acceptance

- [x] **CLI 安装冒烟测试**：`cd /path/to/zata-ops && uv tool install --force . && zata-ops --version` 返回版本号。
- [x] **模板 just 委托冒烟测试**：`cd /Users/zata/code/zata_code_template && just ops-backup --dry-run` 退出码为 0，并输出 `zata-ops db backup` dry-run 计划。
- [x] **模板仓库清理审计**：在 `zata_code_template` 中执行 `rg "backup_service|scripts/diagnostics|BACKUP_IMAGE"`（排除 `.git`、`.venv`）返回零命中。
- [x] **模板测试套件通过**：`cd zata_code_template && just test` 退出码为 0。
- [x] **模板 lint 通过**：`cd zata_code_template && just lint --full` 退出码为 0。

---

## 8. Functional Requirements

**FR-1**: `zata-ops` 必须可作为独立 CLI 通过 `uv tool install` 安装。

**FR-2**: `zata-ops db backup` 必须接受 `--project`、`--db-url`、`--s3-endpoint`、`--s3-bucket`、`--s3-access-key`、`--s3-secret-key`、`--s3-prefix`、`--s3-addressing-style`、`--retention-days` 和 `--dry-run` 参数。

**FR-3**: `zata-ops db backup` 在未设置 `--dry-run` 时，必须 dump PostgreSQL/SQLite 数据库、压缩、上传到指定的 S3 兼容存储，并删除超过 `--retention-days` 的旧备份。

**FR-4**: `zata-ops db backup` 必须支持旧 `backup_service` 的 logs/resources 归档、manifest 生成、full/incremental 类型判断和 S3 key layout，除非实现阶段更新 PRD 并明确记录兼容性取舍。

**FR-5**: `zata-ops db restore` 必须接受 `--from`（S3 key 或 backup date）和 `--target-db-url` 参数，下载备份、解压并恢复到目标数据库。

**FR-6**: `zata-ops db restore` 必须支持旧 `backup_service` 的 logs/resources restore、incremental chain restore、backup list、`--yes` 非交互执行、以及 `--clean-target-schema` / `--drop-target-db` 这类破坏性操作的显式保护。

**FR-7**: `zata-ops db list` 必须列出 S3 中可用备份日期、备份类型和 manifest 摘要。

**FR-8**: `zata-ops db check` 必须通过上传并删除测试对象来验证 S3 endpoint 连通性。

**FR-9**: `zata-ops env provision` 必须接受 `--host`、`--user`、`--ssh-key`、`--profile` 和 `--dry-run` 参数；非 dry-run 通过 SSH 或可选 `[ssh]` extra 执行远程服务器初始化（Docker、Traefik、swap、防火墙）。

**FR-10**: `zata-ops env fix` 必须提供 ACME email / Traefik 证书相关修复入口，并支持 `--dry-run` 渲染将执行的 shell 操作。

**FR-11**: `zata-ops db migrate` 必须提供 PostgreSQL 到 PostgreSQL 的显式数据迁移入口，并在帮助文案中说明它不是 Alembic schema migration。

**FR-12**: `zata-ops logs tail` 和 `zata-ops logs search` 必须支持项目名、时间窗口、服务名和 `--dry-run`，可封装 `docker logs`、`journalctl` 或本地日志路径。

**FR-13**: `zata-ops dashboard` 必须使用 `rich` 渲染终端看板，显示项目健康状态、最近备份和资源用量，并支持 mock provider smoke validation。

**FR-14**: `zata_code_template` 必须移除 `scripts/backup_service/`、`scripts/diagnostics/` 和 `deploy/vps-traefik/*.sh`。

**FR-15**: `zata_code_template` 必须从根 compose、Dokploy compose、VPS compose 和 VPS GitHub Actions 示例中移除 backup service、backup image 和 `BACKUP_IMAGE`。

**FR-16**: `zata_code_template` 的 `justfile` 必须提供 `ops-backup`、`ops-restore` 和 `ops-provision` recipe，调用 `zata-ops` 并传入项目 `.env` 值。

**FR-17**: `zata_code_template` 不再提供常驻 compose backup scheduler；备份调度必须在文档中交给外部 scheduler 示例或手动命令。

---

## 9. Non-Goals

1. 重写 AI 模型 provider 体系（由独立 PRD 覆盖）。
2. 修改前端代码或前端构建流水线。
3. 强制现有下游项目迁移到 `zata-ops`；迁移是可选的。
4. 在 `zata-ops` 中支持非 OpenAI 协议的 LLM provider。
5. 把 `zata-ops` 做成被运行中应用导入的库；它仅为 CLI 工具。
6. 初始版本提供 `zata-ops dashboard` 的 Web UI（仅终端看板）。
7. Kubernetes-native operator 或 Helm chart。
8. 多云抽象（AWS/GCP/Azure）；仅以 S3 兼容存储为目标。
9. 保留旧 compose profile `backup` 作为常驻 scheduler；调度交给外部 scheduler 或手动命令。
10. 迁移 `scripts/diagnostics/check_claude_code.sh`；Claude Code 本机可用性检查不属于应用 ops toolkit baseline。

---

## 10. Risks And Follow-Ups

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `zata-ops` SSH 初始化（`paramiko`）增加重依赖和安全面 | 中 | 中 | 将 `paramiko` 设为可选依赖 `[ssh]`；默认安装不包含 |
| 提取后下游项目已复制的 `deploy/vps-traefik/` 逐渐过时 | 高（现有项目） | 低 | 文档说明现有项目不强制迁移；新项目使用 `zata-ops` |
| `zata-ops` 与 `zata_code_template` 的 `justfile.shared` 逐渐漂移 | 中 | 低 | 两个仓库都使用 `just sync-template` 从共同上游拉取共享 justfile 更新 |
| 备份/恢复往返测试需要真实 Postgres + MinIO，导致 CI 变慢 | 中 | 中 | 使用 `pytest` marker（`integration`、`slow`）；CI 默认只运行单元测试 |
| `deploy/vps-traefik/` 中的 shell 脚本与 Ubuntu/Debian 紧耦合；Python 初始化可能丢失平台特定边缘情况 | 低 | 中 | 保留 shell 模板作为 Python 渲染的 Jinja2 模板；在目标 VPS OS 上测试 |
| `db migrate`、`logs`、`dashboard` 扩展命令拖慢 baseline 迁出 | 中 | 中 | baseline 命令先达到安装、dry-run、模板委托和清理验收；扩展命令有独立最小可运行验收 |
| 移除 compose backup scheduler 后用户忘记设置外部调度 | 中 | 中 | `zata-ops` README 和模板 backup 文档提供 systemd timer、cron、GitHub Actions、Dokploy scheduled job 示例 |
| 新 restore 不能读取旧 manifest / incremental chain | 中 | 高 | 保留旧 S3 key layout 和 manifest shape；添加旧 fixture 的 compatibility tests |

---

## 11. Decision Log

| ID | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| D-01 | zata-ops 语言 | Python (uv + typer + rich) | Go | 用户更熟悉 Python；与现有 `uv`/`pydantic` 工具链一致；`typer` 以最小样板提供类型安全 CLI |
| D-02 | 分发机制 | `uv tool install` from source / git | PyPI publish, Homebrew, npm | `uv tool install` 是该生态中 Python CLI 的最简零配置路径；PyPI 可后续添加而不破坏兼容性 |
| D-03 | zata-ops 启动来源 | `zata_code_template` 的 `just copy` | 空白仓库或 Cookiecutter | 免费继承 `justfile`、`docs/ai-standards/`、pre-commit hooks 和 mkdocs 配置；与现有工作流一致 |
| D-04 | 备份调度方式 | 从模板中移除；由用户自选（systemd timer / GitHub Actions / k8s CronJob） | 保留 compose profile `backup` 并在容器内运行 cron | 将调度与工具解耦；`zata-ops` 按需调用或由外部调度器触发；避免容器化 cron 的复杂性 |
| D-05 | SSH 初始化依赖 | `paramiko` 作为可选 extra `[ssh]` | 始终包含 `paramiko` 或仅使用 shell `ssh` 命令 | `paramiko` 很重且有安全更新负担；大多数用户可能通过 `ssh` + 远程脚本手动运行初始化 |
| D-06 | zata-ops 环境变量加载 | `pydantic-settings` with `.env` + CLI override | 像旧 `backup_service` 一样纯环境变量 | `pydantic-settings` 提供验证、类型安全和 `.env` 文件加载；CLI flag 允许每次调用时覆盖而无需修改环境变量 |
| D-07 | 大项目范围切分 | Baseline 迁出 + 扩展命令同属本 PRD，但验收分组明确 | 把 dashboard/logs/migrate 另开 PRD，或把所有命令混成单一 MVP | 用户确认这是大项目；分组验收避免 baseline 被扩展命令拖死，同时保留目标态规划 |
| D-08 | `uv tool install` 命令形态 | `cd /path/to/zata-ops && uv tool install --force .` 或 `uv tool install --force /path/to/zata-ops` | `uv tool install --from /path/to/zata-ops zata-ops` | 当前 `uv tool install` 接受 package/path 作为位置参数；`--from` 是 `uv tool run` 的选项，不适用于 install |
| D-09 | 旧 backup manifest 兼容 | 保留旧 S3 key layout 和 manifest shape | 重新设计 manifest 后要求用户手动迁移旧备份 | 提取工具不能让现有备份不可恢复；新 manifest 版本化可后续追加 |
