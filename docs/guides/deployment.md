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

## 推荐部署流程

1. 拉取代码并同步依赖。
2. 注入生产环境变量。
3. 执行数据库初始化（按项目实际实现）。
4. 启动服务入口（如 `src/backend/main.py`、根目录 `main.py` 包装器，或任务调度器）。

## Dokploy Docker Compose 部署

这是模板项目的默认生产部署路径。

生产环境模板使用根目录的 `docker-compose.dokploy.yml`。该 compose 文件通过 Traefik 将外部流量路由到 `<slug>-frontend` 服务，前端 Nginx 再把 `/api/*` 代理到内部 `<slug>-backend:8000`。

> **App-slug 命名空间（共部署约束）**：模板源文件中的服务名、卷名与 nginx 上游主机名统一使用占位前缀 `zata-codes-template-`（如 `zata-codes-template-backend`）。`just copy <slug>` 实例化时会把该前缀替换成项目目录名 `<slug>`，产出 `<slug>-backend` / `<slug>-frontend` / `<slug>-backup` 等唯一名。
>
> 这是为了在同一台服务器上通过 Dokploy 把多个模板派生应用接入同一外部网络 `dokploy-network` 时，避免服务名派生的网络别名相互碰撞。Docker Compose 会为每个服务在其网络上注册一个与服务名同名的别名；若两个应用都叫 `backend`，容器按名解析 `backend` 时 Docker DNS 会在两者间轮询，导致接口 404 或串数据。**同一 `dokploy-network` 上的服务名必须按 slug 唯一**，新项目经 `just copy` 实例化后无需任何手动改名即可满足该约束。

在 Dokploy 的 Compose Environment 中必须配置：

```env
DOMAIN=app.example.com
```

`DOMAIN` 只填写域名，不要包含 `http://`、`https://` 或路径。本地 `.env.dokploy.example` 只是模板文件；如果 Dokploy 的部署命令没有显式使用 `--env-file`，就需要把变量复制到 Dokploy UI 的 Environment 中。

DNS 需要把 `${DOMAIN}` 解析到 Dokploy 服务器。部署后访问 404 时，优先检查：

1. `docker compose -f docker-compose.dokploy.yml config | grep 'Host'` 是否生成了正确域名。
2. `<slug>-frontend` 与 `<slug>-backend` 容器是否都处于运行状态。
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
| `install-docker-traefik.sh` | 在 Ubuntu/Debian VPS 上安装 Docker Engine、Compose 插件和宿主机级 Traefik。 |
| `fix-acme-email.sh` | 修复 Traefik 使用占位 ACME 邮箱后一直返回默认证书的问题。 |
| `bootstrap.sh` | 本地运行的交互式向导：生成 CD SSH key、创建 deploy 用户、上传 compose/env 模板。 |
| `docker-compose.yml` | 服务器 `/opt/apps/<slug>/` 下的生产编排文件，使用外部 Traefik 网络。 |
| `.env.example` | 部署元数据模板：`DOMAIN`、`TRAEFIK_NETWORK`、镜像引用。 |
| `app.env.example` | 运行时配置和密钥模板：数据库、认证、模型 key、备份存储。 |
| `github-actions-deploy.yml.example` | 可选的 GitHub Actions 构建镜像、推送 registry、SSH 更新 compose 示例。 |

### 1. 安装宿主机 Traefik

在服务器上用 root 或具备 sudo 权限的用户运行：

```bash
ACME_EMAIL=you@your-domain.com bash deploy/vps-traefik/install-docker-traefik.sh
```

脚本默认创建外部 Docker 网络 `traefik`，并在传入真实 `ACME_EMAIL` 时启用 `letsencrypt` 证书解析器。不要使用 `admin@example.com`、`you@example.com` 或 `localhost` 这类占位邮箱；Let's Encrypt 不会接受，Traefik 会退回到默认自签证书。

如果服务器已有 Traefik，但浏览器一直显示证书无效，可以在服务器上运行：

```bash
sudo bash fix-acme-email.sh --email you@your-domain.com
```

### 2. 初始化应用目录

在本地项目目录运行：

```bash
./deploy/vps-traefik/bootstrap.sh --server 1.2.3.4 --domain app.example.com
```

常用覆盖参数：

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `--app-slug` | 当前模板占位 `zata-codes-template`，派生项目中为 `<slug>` | 服务名、卷名、镜像名和默认目录前缀。 |
| `--admin-user` | `root` | 首次登录服务器执行 sudo/root 操作的用户。 |
| `--deploy-user` | `deploy` | 后续 CI/CD 通过 SSH 使用的非特权用户。 |
| `--app-dir` | `/opt/apps/<slug>` | 服务器应用目录。 |
| `--traefik-network` | `traefik` | Traefik 外部 Docker 网络名。 |

`bootstrap.sh` 是幂等的：不会覆盖服务器上已有的 `.env` 或 `app.env`。首次创建 `app.env` 时会生成随机 `API_SECRET_KEY`，但 `DATABASE_URL`、`ADMIN_PASSWORD_HASH`、模型 API key、S3 备份配置仍需人工填入。

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
| `SERVER_SSH_KEY` | `bootstrap.sh` 生成的私钥完整内容。 |

可选 `production` environment variables：

| Variable | 用途 |
| --- | --- |
| `PRODUCTION_DOMAIN` | GitHub deployment 页面展示的线上 URL。 |
| `PRODUCTION_APP_DIR` | 服务器应用目录；不填时使用 `/opt/apps/<slug>`。 |
| `PRODUCTION_COMPOSE_PROFILES` | 可选 compose profile，例如填 `backup` 后部署时会同时拉起备份服务。 |

workflow 示例会构建 backend、frontend、backup 三个镜像，用 commit SHA 作为不可变 tag，SSH 到服务器更新 `/opt/apps/<slug>/.env` 中的镜像引用，然后执行 `docker compose pull && docker compose up -d --remove-orphans`。

## 环境变量管理

- 使用平台密钥管理工具保存敏感信息。
- 避免把真实密钥写入仓库。
- 为不同环境准备差异化配置，例如开发、测试、生产。

## 可观测性建议

- 接入集中日志平台采集 `logs/app.log`。
- 补充错误告警策略。
- 针对关键任务建立成功率与耗时监控。
