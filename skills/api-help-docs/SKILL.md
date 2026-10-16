---
name: api-help-docs
description: "[Created 2026-10-15] Build and maintain a public API help center whose Markdown articles are the single source of truth, validated against OpenAPI and published so both people and AI agents can read them (static .md, llms.txt, llms-full.txt). Covers the add-a-new-API checklist, the SPA trap (agents cannot read client-rendered pages), response_model gaps, and the pure-backend variant. Triggers on: 新增 API 文档, 帮助中心, API 帮助页, 让 agent 能抓取文档, llms.txt, 接口文档怎么更新, publish API docs, api help center, openapi 文档同步."
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

## 新增一个 API 的完整流程

1. **写路由并声明响应模型。** 不声明时 OpenAPI 的响应只是 `object`，调用方和 agent 都不知道字段。FastAPI 用 `response_model`（动态附加字段用 `extra="allow"`）；Spring 用带 `@Schema` 的具体返回类型，避免只返回 `JsonNode`/`Map`。
2. **更新维护者路由索引**（如 `docs/api/http-endpoints.md`），若仓库有。
3. **写或改帮助文章。** 每篇一个主要任务，frontmatter 必含 `slug`、`category`、`order`（同分类唯一）、`title`、`summary`、`keywords`、`sections`（`title` 与正文 `##` 标题逐一相同）。接口章节含：接口定义、调用条件、请求字段（参数表）、请求示例（单请求 cURL）、成功响应、错误处理。GET 没有请求体就不要虚构。
4. **登记目录**：分类 `index.md` 与站点 nav（如 `mkdocs.yml`）。产品内页面和 `llms.txt` 是构建时自动收录，不需要手工登记。
5. **运行一致性检查**（如 `just help-api-check`）。报错带 `文件:行号`；修文档或代码，不要削弱检查。
6. **构建并检查产物**：确认新文章的 `.md` 在静态目录，`llms.txt` 含新条目。
7. **部署后用 curl 验证**，别只看本地：`/llms.txt`、`/help/<slug>.md`，且响应不是 SPA 的 `index.html`。

## 变更要同步什么

| 改了 | 必须同步 | 有无自动检查 |
|---|---|---|
| 请求字段/路径 | 参数表、cURL 示例 | 有（对照 OpenAPI） |
| 响应字段 | 响应模型 + 文章示例响应 | **无**，要人工 |
| 错误码、业务规则 | 文章文字 | **无** |
| slug | 尽量不改；改了旧 `.md` 直链失效 | 无 |

## 路径 A：带 SPA 的帮助中心

核心问题：SPA 只返回空壳 HTML，不执行 JS 的抓取器（含 WebFetch、curl）读不到正文。解法是**构建时把同一份 Markdown 再发布成静态文件**，不要另写一份给 agent。

- 用 `assets/help-static.ts` 作为 Vite 插件（`writeBundle` 阶段）：输出 `help/<slug>.md`、`llms.txt`、`llms-full.txt`。要改的只有：`docs/help` 的相对路径、站点标题文案、OpenAPI 地址。
- nginx 要让 `/help/*.md` 和 `/llms*.txt` 命中真实文件并带 `charset utf-8`；缺文件返回 404。注意 SPA 常见的 `try_files ... /index.html` 会把缺失的 `.md` 变成 200 的 HTML。`text/markdown` 默认不带 charset，需 `charset_types text/markdown;`。
- 页面 `<head>` 加静态 `<link rel="alternate" type="text/plain" href="/llms.txt">`。JS 注入的 per-article 标签只对执行 JS 的客户端有效，不能当作主要手段。
- 实现细节与踩坑见 `references/fsense-implementation.md`。

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

它**不能**判断业务文字是否正确，也无法核对 OpenAPI 未描述的响应语义——这是为什么第 1 步必须声明响应模型。

## 验证与交付

- 汇报时只写实际运行过的：检查脚本结果、构建产物清单、nginx 响应头/状态码。
- **Docker 构建上下文**：若帮助文章在仓库根 `docs/`，而前端镜像的 build context 是子目录，容器内读不到文章，产物会是空的。部署后必须确认 `/llms.txt` 非空；不要因为本地构建通过就认为线上也有。
- 不运行会写共享数据库的集成测试来“证明”响应模型；用模型校验 + 单元测试，并如实说明未覆盖的部分。
- 不执行 `git add`/`commit`，除非用户要求。

## 反模式

- 给 agent 单独写一份文档，与人看的版本并行维护（双份权威）。
- 用 OpenAPI 直接渲染页面却不写业务说明；或反过来只写文章不声明响应模型。
- 为抓取而做 SSR/预渲染：改动大，静态 Markdown 已够。
- 把 `rel=alternate` 当作 agent 发现文档的唯一手段。
- 检查失败时削弱检查，而不是修文档或代码。
