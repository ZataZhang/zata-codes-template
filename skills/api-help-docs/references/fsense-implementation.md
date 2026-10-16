# fsense 参考实现

本 skill 的路径 A 来自 `~/code/fsense`（2026-10-15）。照搬前先核对该仓库当前状态，以下文件可能已变化。

## 数据流

```text
FastAPI 路由 ──► app.openapi() ──┐
                                ├─ scripts/docs/check_help_api.py（just help-api-check）
docs/help/api/*.md ─────────────┘          只校验，不生成
        │
        ├─► admin-frontend/studio/src/help-center/help-articles.ts
        │     import.meta.glob("docs/help/{product,api}/**/*.md", ?raw) → 打进 JS → /help/<slug>（客户端渲染）
        ├─► vite-plugins/help-static.ts（writeBundle）→ dist/help/<slug>.md、llms.txt、llms-full.txt
        └─► mkdocs.yml nav（手工登记）→ MkDocs 站
```

## 关键文件

| 文件 | 职责 |
|---|---|
| `docs/guides/public-help-center.md` | 目录职责、文章模板、契约规则、静态发布说明 |
| `docs/help/api/*.md` | 文章正文，唯一来源 |
| `scripts/docs/check_help_api.py` + `help_api_*.py` | 与 OpenAPI 的一致性检查 |
| `admin-frontend/studio/vite-plugins/help-static.ts` | 静态发布（本 skill 的 `assets/help-static.ts` 为其副本） |
| `admin-frontend/nginx.conf` | `.md`、`llms*.txt` 的类型与 404 规则 |
| `src/fsense_service/api/partner_document_recognition_schemas.py` | Partner API 响应模型 |

## 踩坑记录

- **WebFetch 只看到 `<title>Refine + shadcn/ui Admin Template</title>`**：这是 SPA 空壳。后端的 `/api/openapi.json` 是可读的，可先从它取接口契约。
- **slug 与文件名无关**：`submit-runs.md` 的 slug 是 `api/upload`，网址和 `.md` 直链都取自 slug。
- **nginx 回落**：`location / { try_files $uri $uri/ /index.html; }` 会让缺失的静态文件返回 200 HTML。给 `.md`、`llms*.txt` 单独写 `location` 并 `try_files $uri =404`。
- **charset**：nginx 的 `charset utf-8` 默认不覆盖 `text/markdown`，需 `charset_types text/markdown;`，否则中文可能乱码。
- **构建上下文**：`docker-compose*.yml` 里 `admin-frontend` 的 `context: ./admin-frontend` 读不到仓库根的 `docs/help`；插件和加载器读同一目录，上下文缺文章时会产出空文章集。已修复：compose 上下文改为仓库根，`admin-frontend/Dockerfile` 里 `COPY docs/help /docs/help`，并用 `admin-frontend/Dockerfile.dockerignore` 覆盖根 `.dockerignore` 对 `docs` 的排除；插件在空集时改为 `this.error` 使构建失败。`vite-plugins/` 下还跟踪着编译出的 `help-static.js`，需与 `.ts` 同步修改。
- **响应模型**：Partner API 原先响应只是 `object`。补模型时，动态附加字段（如 `include_bbox` 的 `bbox`、`page_number`）用 `extra="allow"` 并声明为可选，避免被 `response_model` 过滤。
- **集成测试**：fsense 的 Partner 集成测试被标记为 `slow`，会涉及真实数据库，默认被排除。不要为验证响应模型强行运行。

## 验证清单（本地）

```bash
just help-api-check
cd admin-frontend/studio && npm run build
ls dist/help/api && head dist/llms.txt
# 用 nginx 容器挂载 nginx.conf 与 dist，检查：
#   /help/api/upload.md → 200 text/markdown; charset=utf-8
#   /help/api/nope.md   → 404
#   /llms.txt           → 200 text/plain
```
