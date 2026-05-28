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

生产环境模板使用根目录的 `docker-compose.dokploy.yml`。该 compose 文件通过 Traefik 将外部流量路由到 `frontend` 服务，前端 Nginx 再把 `/api/*` 代理到内部 `backend:8000`。

在 Dokploy 的 Compose Environment 中必须配置：

```env
DOMAIN=app.example.com
```

`DOMAIN` 只填写域名，不要包含 `http://`、`https://` 或路径。本地 `.env.dokploy.example` 只是模板文件；如果 Dokploy 的部署命令没有显式使用 `--env-file`，就需要把变量复制到 Dokploy UI 的 Environment 中。

DNS 需要把 `${DOMAIN}` 解析到 Dokploy 服务器。部署后访问 404 时，优先检查：

1. `docker compose -f docker-compose.dokploy.yml config | grep 'Host'` 是否生成了正确域名。
2. `frontend` 与 `backend` 容器是否都处于运行状态。
3. `docker logs app-backend --tail=100` 是否有数据库、迁移或配置错误。
4. 实际访问的域名是否正好匹配 Traefik 的 Host rule。

前端 Nginx 配置使用 Docker 内置 DNS 做运行时重解析：

- `resolver 127.0.0.11 ipv6=off valid=5s`
- `set $backend_upstream backend:8000`
- `/api/*` 先 `rewrite` 去掉 `/api` 前缀，再 `proxy_pass http://$backend_upstream`

这样可以避免 Dokploy 或 Docker Compose 只重建 `backend` 时，未重启的前端 Nginx 继续使用旧 backend 容器 IP。使用变量形式的 `proxy_pass` 时不要在 upstream 后追加尾部 `/`，否则 Nginx 不会沿用普通 `proxy_pass http://backend:8000/` 的 URI 替换语义，可能把请求错误转发到根路径。

## 环境变量管理

- 使用平台密钥管理工具保存敏感信息。
- 避免把真实密钥写入仓库。
- 为不同环境准备差异化配置，例如开发、测试、生产。

## 可观测性建议

- 接入集中日志平台采集 `logs/app.log`。
- 补充错误告警策略。
- 针对关键任务建立成功率与耗时监控。

## TODO

- TODO: 补充非 Dokploy 容器化部署模板。
