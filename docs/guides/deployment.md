# 部署指南

本文档提供模板项目在不同环境下的部署建议。

## 部署前检查

- 确保 `uv lock` 与 `uv sync` 能正常执行。
- 校验环境变量完整性，特别是数据库和模型 API Key。
- 执行测试：`just test`。
- 构建文档：`uv run mkdocs build --strict`。

## GitHub Actions 模板

模板仓库内置两条 GitHub Actions 工作流，默认放在 `.github/workflows/`：

1. `ci.yml`
   - 触发时机：`pull_request`、推送到 `main`、手动触发。
   - 执行内容：`uv sync --all-extras --all-groups --frozen`、`pre-commit`、本地测试集、`mkdocs build --strict`、发布包烟雾构建。
2. `cd.yml`
   - 触发时机：推送 `v*` 标签、手动触发。
   - 执行内容：重复执行发布前校验，生成 `dist/*.zip`，上传构建产物；当事件来自标签推送时，同时创建 GitHub Release。

如果下游项目直接继承此模板，通常只需要根据自身情况调整：

- `PYTHON_VERSION`
- 标签规则（默认 `v*`）
- 测试命令或额外构建步骤
- 是否保留 GitHub Release 发布逻辑

## 运维能力（备份、S3 检查、VPS 初始化）

> **运维能力已迁出**：数据库备份/恢复、S3 连通性诊断、VPS + Traefik 初始化、ACME 修复、日志查看、终端看板等运维能力已迁到`zata-ops` CLI（独立仓库，模板仓库不再自带 `scripts/backup_service/`、`scripts/diagnostics/` 与 `deploy/vps-traefik/*.sh`。

### 安装 `zata-ops`

```bash
cd /path/to/zata-ops
uv tool install --force .
zata-ops --version
```

### 通过模板 just recipe 委托

模板的 `justfile` 提供了对 `zata-ops` 的薄封装：

```bash
just ops-backup --dry-run     # 调 zata-ops db backup --dry-run
just ops-backup --force-full  # 真实执行 full backup
just ops-restore --from 2026-06-07_180000 --restore-db --yes
just ops-provision --host 1.2.3.4 --user deploy --dry-run
just ops-check                # zata-ops db check
just ops-dashboard --mock     # 终端状态看板
```

每条 recipe 都会先验证 `zata-ops` 在 PATH 中存在，然后以当前项目目录为 CWD 调用，
这样 `zata-ops` 会自动加载本项目的 `.env` / `.env.local`。

### 备份调度

`zata-ops` 不再附带常驻 scheduler；请选用：systemd timer、cron、GitHub Actions
`schedule:` workflow、Dokploy Scheduled Job，或在维护窗口前手工执行。完整示例
见 `zata-ops/docs/guides/scheduling.md`。

## 推荐部署流程

1. 拉取代码并同步依赖。
2. 注入生产环境变量。
3. 执行数据库初始化（按项目实际实现）。
4. 启动服务入口（如 `src/backend/main.py`、根目录 `main.py` 包装器，或任务调度器）。
5. 配置 `zata-ops db backup` 的调度方式。

## Dokploy Docker Compose 部署

这是模板项目的默认生产部署路径。

生产环境模板使用根目录的 `docker-compose.dokploy.yml`。该 compose 文件部署三个服务：

- `<slug>-backend`：Python 后端 API，暴露 `/health`、`/auth/*`、`/api/*` 等接口。
- `<slug>-admin`：管理平台前端（`frontend-admin/`），Nginx 监听 80 端口，通过 `admin.${DOMAIN}` 访问。
- `<slug>-public`：前台官网（`frontend-public/`），Next.js standalone 监听 3000 端口，通过 `${DOMAIN}` 访问。

两个前端都直接面向最终用户：public 站点负责营销首页和登录/注册，admin 站点负责登录后的管理 Dashboard。public 前端在容器内通过 `API_BASE_URL` 直接调用后端；admin 前端通过 Nginx 的 `/api/*` 代理到内部 `<slug>-backend:8000`。模板不再包含 `<slug>-backup` 服务——备份能力由独立的 `zata-ops` CLI 提供，通过 Dokploy Scheduled Job 调用即可。

> **App-slug 命名空间（共部署约束）**：模板源文件中的服务名、卷名与 nginx 上游主机名统一使用占位前缀 `zata-codes-template-`（如 `zata-codes-template-backend`）。`just copy <slug>` 实例化时会把该前缀替换成项目目录名 `<slug>`，产出 `<slug>-backend` / `<slug>-admin` / `<slug>-public` 等唯一名。
>
> 这是为了在同一台服务器上通过 Dokploy 把多个模板派生应用接入同一外部网络 `dokploy-network` 时，避免服务名派生的网络别名相互碰撞。Docker Compose 会为每个服务在其网络上注册一个与服务名同名的别名；若两个应用都叫 `backend`，容器按名解析 `backend` 时 Docker DNS 会在两者间轮询，导致接口 404 或串数据。**同一 `dokploy-network` 上的服务名必须按 slug 唯一**，新项目经 `just copy` 实例化后无需任何手动改名即可满足该约束。

在 Dokploy 的 Compose Environment 中必须配置：

```env
DOMAIN=app.example.com
```

`DOMAIN` 只填写域名，不要包含 `http://`、`https://` 或路径。本地 `.env.dokploy.example` 只是模板文件；如果 Dokploy 的部署命令没有显式使用 `--env-file`，就需要把变量复制到 Dokploy UI 的 Environment 中。

DNS 需要把 `${DOMAIN}` 与 `admin.${DOMAIN}` 都解析到 Dokploy 服务器。部署后访问 404 时，优先检查：

1. `docker compose -f docker-compose.dokploy.yml config | grep 'Host'` 是否生成了 `Host(\`${DOMAIN}\`)` 与 `Host(\`admin.${DOMAIN}\`)` 两条规则。
2. `<slug>-admin`、`<slug>-public` 与 `<slug>-backend` 容器是否都处于运行状态。
3. `docker logs <slug>-backend --tail=100` 是否有数据库、迁移或配置错误。
4. 实际访问的域名是否正好匹配 Traefik 的 Host rule。

前端 Nginx 配置使用 Docker 内置 DNS 做运行时重解析：

- `resolver 127.0.0.11 ipv6=off valid=5s`
- `set $backend_upstream <slug>-backend:8000`（模板源文件中为 `zata-codes-template-backend:8000`，实例化时替换）
- `/api/*` 先 `rewrite` 去掉 `/api` 前缀，再 `proxy_pass http://$backend_upstream`

这样可以避免 Dokploy 或 Docker Compose 只重建 backend 时，未重启的前端 Nginx 继续使用旧 backend 容器 IP。使用变量形式的 `proxy_pass` 时不要在 upstream 后追加尾部 `/`，否则 Nginx 不会沿用普通 `proxy_pass http://<slug>-backend:8000/` 的 URI 替换语义，可能把请求错误转发到根路径。

## VPS + Traefik 部署

`deploy/vps-traefik/` 提供一条可选的自托管 VPS 部署路径，适用于不走 Dokploy、但仍希望使用 Docker Compose + 宿主机级 Traefik 的项目。该目录会随 `just copy <slug>` 一起实例化，默认占位前缀 `zata-codes-template` 会替换为新项目目录名。

目录内容：

| 文件 | 用途 |
| --- | --- |
| `docker-compose.yml` | 服务器 `/opt/apps/<slug>/` 下的生产编排文件，使用外部 Traefik 网络。 |
| `.env.example` | 部署元数据模板：`DOMAIN`、`TRAEFIK_NETWORK`、镜像引用。 |
| `app.env.example` | 运行时配置和密钥模板：数据库、认证、模型 key。 |
| `github-actions-deploy.yml.example` | 可选的 GitHub Actions 构建镜像、推送 registry、SSH 更新 compose 示例。 |
| `README.md` | 部署目录索引。 |

> 之前的 `install-docker-traefik.sh`、`bootstrap.sh`、`fix-acme-email.sh` 已迁入 `zata-ops`，请使用 `zata-ops env provision --host ... --acme-email ...` 与 `zata-ops env fix --host ... --email ...` 代替。

### 1. 安装宿主机 Traefik

通过 `zata-ops`（推荐 dry-run 先看一次再真正执行）：

```bash
zata-ops env provision \
    --host 1.2.3.4 \
    --user root \
    --acme-email you@your-domain.com \
    --traefik-network traefik \
    --dry-run
```

去掉 `--dry-run` 后会通过本地 `ssh` 在远程主机上运行打包好的 `install-docker-traefik.sh` 模板。

如果服务器已有 Traefik 但浏览器一直显示证书无效：

```bash
zata-ops env fix --host 1.2.3.4 --user root --email you@your-domain.com
```

### 2. 部署应用目录

`deploy/vps-traefik/docker-compose.yml` 仍由模板维护；将其连同 `.env` / `app.env` 放在 `/opt/apps/<slug>/` 下，然后 `docker compose up -d`。可通过 SSH 手工准备目录与 `deploy` 用户，或参考 `zata-ops env provision` 输出脚手脚本自行执行。

### 3. 启用可选 GitHub Actions 部署

模板仓库默认 `.github/workflows/cd.yml` 只生成 release zip，不会部署服务器。派生项目若要启用 VPS 部署，可复制示例 workflow：

```bash
cp deploy/vps-traefik/github-actions-deploy.yml.example .github/workflows/deploy-vps-traefik.yml
```

Repository secrets：

| Secret | 用途 |
| --- | --- |
| `REGISTRY_HOST` | 镜像仓库 host，例如 `ghcr.io` 或 `registry.cn-shanghai.aliyuncs.com`。 |
| `REGISTRY_NAMESPACE` | 镜像仓库命名空间、组织或用户名。 |
| `REGISTRY_USERNAME` | 推送镜像使用的 registry 用户名。 |
| `REGISTRY_PASSWORD` | 推送镜像使用的密码或 token。 |

`production` environment secrets：

| Secret | 用途 |
| --- | --- |
| `SERVER_HOST` | VPS IP 或域名。 |
| `SERVER_USER` | 通常为 `deploy`。 |
| `SERVER_SSH_KEY` | 由你自己（或 `zata-ops env provision` 流程）准备的 deploy 用户 SSH 私钥完整内容。 |

可选 `production` environment variables：

| Variable | 用途 |
| --- | --- |
| `PRODUCTION_DOMAIN` | GitHub deployment 页面展示的线上 URL。 |
| `PRODUCTION_APP_DIR` | 服务器应用目录；不填时使用 `/opt/apps/<slug>`。 |

workflow 示例构建 backend、admin（`frontend-admin/`）和 public（`frontend-public/`）三个镜像，用 commit SHA 作为不可变 tag，SSH 到服务器更新 `/opt/apps/<slug>/.env` 中的镜像引用，然后执行 `docker compose pull && docker compose up -d --remove-orphans`。备份镜像不再由模板 CD 构建。

镜像命名：

- `<registry>/<namespace>/<slug>-backend:<sha>`
- `<registry>/<namespace>/<slug>-admin:<sha>`
- `<registry>/<namespace>/<slug>-public:<sha>`

并在 `deploy/vps-traefik/docker-compose.yml` 中定义对应服务。

## 环境变量管理

- 使用平台密钥管理工具保存敏感信息。
- 避免把真实密钥写入仓库。
- 为不同环境准备差异化配置，例如开发、测试、生产。
- `zata-ops` 自动加载当前 CWD 下的 `.env` / `.env.local`，所以备份 / S3 配置可以放在与应用相同的 env 文件里，但应用容器自身不再读取 S3 credentials。

## 可观测性建议

- 接入集中日志平台采集 `logs/app.log`。
- 补充错误告警策略。
- 针对关键任务建立成功率与耗时监控。
- 在维护操作前用 `zata-ops dashboard` 快速查看项目健康状态。
