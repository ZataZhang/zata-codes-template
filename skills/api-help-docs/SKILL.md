---
name: api-help-docs
description: "[Created 2026-10-15, Updated 2026-10-19] Build and maintain a public API help center whose Markdown articles are the single source of truth, validated against OpenAPI and published so both people and AI agents can read them (static .md, llms.txt, llms-full.txt). Covers the add-a-new-API checklist, the SPA trap (agents cannot read client-rendered pages), response_model gaps, the public-scope decision, the human-facing SPA page, an integration demo page, and the pure-backend variant. Triggers on: 新增 API 文档, 帮助中心, API 帮助页, 让 agent 能抓取文档, llms.txt, 接口文档怎么更新, publish API docs, api help center, openapi 文档同步, 接入 demo, 演示页."
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Edit
  - Write
---

# API Help Docs

维护一套**以 Markdown 为唯一正文来源**的 API 帮助文档：人看网页，agent 读静态 `.md` 和 `llms.txt`，OpenAPI 只用来**校验**文档，不用来生成文档。

## 先讲清一个事实

帮助页内容来自手写 Markdown，**不会**因为新增路由而自动出现。新增接口必须同时写路由和文章。向用户解释流程时先说这一点，否则用户会误以为 OpenAPI 会自动生成页面。

## 定位边界

- 本 skill：面向**外部调用者**的 API 教程与发布链路。
- `feature-docs`：面向**改代码的人**的代码地图，不要把接入教程写进 `docs/features/`。
- `code-reviewer`：合并前检查文档是否同步的闸门；本 skill 是“怎么写、怎么发”。

## 开始前：判断项目形态

先读目标仓库的实际结构，不凭记忆套用：

| 形态 | 判断依据 | 走哪条路径 |
|---|---|---|
| 带 SPA 前端的帮助中心 | 有 `docs/help/` 且前端用 `import.meta.glob` 之类加载 Markdown | 路径 A |
| 纯后端 | 没有前端构建，只有路由和 `docs/` | 路径 B |
| 已有 springdoc/FastAPI 等 OpenAPI，但没有教程文档 | 有 OpenAPI 导出，缺手写文章 | 先做路径 B 的第 1、2 步 |

先确认三件事再动手：OpenAPI 的实际导出地址、响应模型是否声明、仓库有没有检查脚本。已有就复用，不重写。

### 先定公开范围（动手前）

帮助中心通常**无需登录就能访问**，所以先回答三个问题，并把答案写进回复：

1. **谁能看？** 只给合作方，还是任何人？未登录用户能不能到达入口页（如登录页上的按钮）？
2. **哪些内容可以公开？** 文章里不要出现内部路径、运维配置、内部实现细节、管理端接口。内部指南与对外文章是两份读者不同的文档，不要互相复制。
3. **OpenAPI 能不能公开？** 默认**不**把 `/openapi.json` 写进 `llms.txt`。它会列出后端全部路由；只有后端本来就是纯对外 API（如 partner API）时才公开。同一个后端同时有内部/管理端接口时，不要公开。

内部指南和对外文章同时存在时，会有两份文字需要同步。明确哪一份是对外事实源（接口字段、状态码以它为准），在内部指南开头注明，并如实告诉用户这是两份内容。

## 新增一个 API 的完整流程

1. **写路由并声明响应模型。** 不声明时 OpenAPI 的响应只是 `object`，调用方和 agent 都不知道字段。FastAPI 用 `response_model`（动态附加字段用 `extra="allow"`）；Spring 用带 `@Schema` 的具体返回类型，避免只返回 `JsonNode`/`Map`。
2. **更新维护者路由索引**（如 `docs/api/http-endpoints.md`），若仓库有。
3. **写或改帮助文章。** 每篇一个主要任务，frontmatter 必含 `slug`、`category`、`order`（同分类唯一）、`title`、`summary`、`keywords`、`sections`（`title` 与正文 `##` 标题逐一相同）。接口章节含：接口定义、调用条件、请求字段（参数表）、请求示例（单请求 cURL）、成功响应、错误处理。GET 没有请求体就不要虚构。
4. **登记目录**：分类 `index.md` 与站点 nav（如 `mkdocs.yml`）。产品内页面和 `llms.txt` 是构建时自动收录，不需要手工登记。
5. **运行一致性检查**（如 `just help-api-check`）。报错带 `文件:行号`；修文档或代码，不要削弱检查。
6. **构建并检查产物**：确认新文章的 `.md` 在静态目录，`llms.txt` 含新条目。
7. **部署后用 curl 验证**，别只看本地：`/llms.txt`、`/help/<slug>.md`，且响应不是 SPA 的 `index.html`。
8. **面向接入的文章要配 demo。** 只描述“怎么接”的文章，读者仍不知道接完是什么样。决定做哪种 demo（可运行的参考接入 / 在线 demo / 录屏截图），见 `references/demo-page.md`。在线 demo 会对公网开放并调用真实后端，要过其中的安全清单，做不到就只做前两种以外的形式。

## 变更要同步什么

| 改了 | 必须同步 | 有无自动检查 |
|---|---|---|
| 请求字段/路径 | 参数表、cURL 示例 | 有（对照 OpenAPI） |
| 响应字段 | 响应模型 + 文章示例响应 | **无**，要人工 |
| 错误码、业务规则 | 文章文字 | **无** |
| slug | 尽量不改；改了旧 `.md` 直链失效 | 无 |

## 路径 A：带 SPA 的帮助中心

核心问题：SPA 只返回空壳 HTML，不执行 JS 的抓取器（含 WebFetch、curl）读不到正文。解法是**构建时把同一份 Markdown 再发布成静态文件**，不要另写一份给 agent。路径 A 有两半，缺一不可：

**给 agent 读的静态文件**

- 用 `assets/help-static.ts` 作为 Vite 插件（`writeBundle` 阶段）：输出 `help/<slug>.md`、`llms.txt`、`llms-full.txt`。通过选项配置：`siteTitle`、`siteDescription`、`helpDirectory`（相对 Vite root，按前端子目录深度调整）、可选的 `openApiUrl`（默认不写，见“先定公开范围”）。它还会校验 frontmatter 必填字段、slug/order 唯一、`sections` 与正文 `##` 标题一致，文章集为空时让构建失败。
- nginx 要让 `/help/*.md` 和 `/llms*.txt` 命中真实文件并带 `charset utf-8`；缺文件返回 404。注意 SPA 常见的 `try_files ... /index.html` 会把缺失的 `.md` 变成 200 的 HTML。`text/markdown` 默认不带 charset，需 `charset_types text/markdown;`。
- **`help/` 目录与 SPA 路由冲突。** 构建产物里有 `help/` 目录时，SPA 兜底写成 `try_files $uri $uri/ /index.html` 会让 `/help` 返回 301、`/help/` 返回 403，到不了前端的 `/help` 路由。改成 `try_files $uri /index.html;`，改之前确认站点没有靠目录索引提供的页面。
- 页面 `<head>` 加静态 `<link rel="alternate" type="text/plain" href="/llms.txt">`。JS 注入的 per-article 标签只对执行 JS 的客户端有效，不能当作主要手段。

**给人看的页面**

- 读同一份 Markdown：`assets/help-articles.ts`（`import.meta.glob`）、`assets/help-markdown.tsx`（渲染并改写站内 `.md` 链接）。路由、依赖、登录守卫、入口位置、i18n 见 `references/spa-help-page.md`。

`references/fsense-implementation.md` 记录的是**这套做法最初来自的一个项目**。其中的目录名（`docs/help/api`）、产品文案、OpenAPI 地址都是那个项目的假设，不是通用事实，照搬前先核对。

## 路径 B：纯后端

不需要 Vite 插件、nginx 防回落、`rel=alternate`。最小集合：

1. 路由 + 响应模型 → OpenAPI。
2. `docs/` 下带 frontmatter 的 Markdown。
3. 运行 `scripts/build_llms_txt.py` 生成 `.md`、`llms.txt`、`llms-full.txt`：

脚本依赖 `pyyaml`；系统 Python 通常没有，直接运行会报 `ModuleNotFoundError: No module named 'yaml'`，用 `uv run --with pyyaml` 带上依赖：

```bash
uv run --with pyyaml python skills/api-help-docs/scripts/build_llms_txt.py \
  --docs-dir docs/help --out-dir build/help-static \
  --title "<产品名> 帮助中心" --description "<一句话>" \
  --base-path /help/ --openapi-url /api/openapi.json
```

4. 把输出目录作为静态资源发布；若只给内部 agent 读，可直接让它读仓库里的 Markdown 和导出的 OpenAPI，省掉发布。

只有一两个控制器时，不要为一致性检查专门写脚本；手写文档加评审更划算。出现多篇文章、多人维护或频繁漂移再加。

## 一致性检查：做什么、不做什么

检查器应核对：文章里的 `METHOD /path` 在 OpenAPI 中存在；参数表（用 `<!-- openapi-parameters: METHOD /path -->` 标记）的字段、位置、类型、必填一致；cURL 的方法、路径、请求头、表单字段合法；frontmatter 完整、slug 与 order 唯一、sections 与标题一致。

本 skill **不附带**这个检查器（它是各项目自己的脚本，参考项目里叫 `check_help_api.py`）；`assets/help-static.ts` 只做 frontmatter 层面的校验，不对照 OpenAPI。接口字段、状态码没有自动检查时，必须对照路由与响应模型手工核对，并在交付里如实说明。

它**不能**判断业务文字是否正确，也无法核对 OpenAPI 未描述的响应语义——这是为什么第 1 步必须声明响应模型。

## 验证与交付

- 汇报时只写实际运行过的：检查脚本结果、构建产物清单、nginx 响应头/状态码。
- **Docker 构建上下文**：若帮助文章在仓库根 `docs/`，而前端镜像的 build context 是子目录，容器内读不到文章，产物会是空的：页面空白、`/llms.txt` 404 是同一个原因。部署后必须确认 `/llms.txt` 非空；不要因为本地构建通过就认为线上也有。修法：
  1. compose 的 `context` 改成仓库根，`dockerfile` 指向前端 Dockerfile；Dockerfile 里所有 `COPY` 加前端目录前缀，并 `COPY docs/help` 到与加载器 glob、构建插件一致的相对位置（`/app/<前端子目录>/../../docs/help`）。
  2. 仓库根 `.dockerignore` 常排除 `docs`，会让上一步的 COPY 失败。先检查能否用精确规则只放行 `docs/help`（例如 `docs/*`、`!docs/help`）。若根规则被多个镜像共用，放行会扩大其他镜像的构建上下文，再给前端镜像配同目录的 `<Dockerfile>.dockerignore`；专属文件会取代根 `.dockerignore`，需保留构建所需的通用排除项，并确认 `COPY docs/help` 可见。
  3. 构建插件在文章集为空时必须 `this.error` 失败，不能只 warn 跳过，否则会静默上线空帮助中心。若仓库还跟踪了编译产物（如 `help-static.js`），两份一起改。
  4. 离线可做的验证：用不跑 npm 的最小 Dockerfile 确认上下文里有文章；移走 `docs/help` 确认构建失败。完整镜像构建受网络影响时如实说明没测到的部分。
- **从入口走一遍**：未登录打开入口页 → 点进帮助页 → 打开一篇文章 → 点文章内的相对链接 → 用 curl 确认 `.md` 与 `llms.txt`。窄屏也看一眼。只验证“组件能渲染”不算。
- 有 demo 时：部署后确认 demo 链接能打开，且页面里的接入代码与文章一致。
- 不运行会写共享数据库的集成测试来“证明”响应模型；用模型校验 + 单元测试，并如实说明未覆盖的部分。
- 不执行 `git add`/`commit`，除非用户要求。

## 反模式

- 给 agent 单独写一份文档，与人看的版本并行维护（双份权威）。
- 用 OpenAPI 直接渲染页面却不写业务说明；或反过来只写文章不声明响应模型。
- 为抓取而做 SSR/预渲染：改动大，静态 Markdown 已够。
- 把 `rel=alternate` 当作 agent 发现文档的唯一手段。
- 检查失败时削弱检查，而不是修文档或代码。
- 手写一份对外 HTML 页面作为“帮助页”，同时仓库里又有 Markdown 版本（双份权威，我们在真实项目里犯过）。
- 不判断公开范围，就把 `/openapi.json` 写进 `llms.txt`，或把内部指南原样发布。
- 只写“怎么接”，不给 demo；或者为了 demo 方便，用生产密钥对公网开放一个换票接口。
- 把 demo 的接入代码和文章里的写成两个版本。
