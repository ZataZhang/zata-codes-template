# 人看的帮助页（路径 A 的前端部分）

`assets/help-static.ts` 只负责把 Markdown 发布成静态文件给 agent 读。**人看的页面**是另一半，同样读同一份 Markdown，不要另写。

## 组成

| 文件 | 作用 |
|---|---|
| `assets/help-articles.ts` | `import.meta.glob(?raw)` 把文章打进 JS；解析标量 frontmatter；`helpArticleList`、`findHelpArticle(slug)` |
| `assets/help-markdown.tsx` | 用 `react-markdown` + `remark-gfm` 渲染正文；把兄弟文章的相对 `.md` 链接改写成站内路径 |
| 路由 | 一个列表页 `/help` 和一个文章页 `/help/<slug>` |
| 页面壳 | 左侧按分类列文章，右侧正文，文末放“查看 Markdown 原文”链接 `/help/<slug>.md` |

依赖：`react-markdown`、`remark-gfm`（运行时），`yaml`（构建插件用，devDependency）。先看 monorepo 里别的包是否已在用同版本，用同一个版本号。

## 要改的地方（别照抄）

- `help-articles.ts` 里 glob 的 `../` 层数要与前端子目录深度、插件的 `helpDirectory` 指向同一个目录。
- `help-markdown.tsx` 的类名是 Tailwind 示例，换成项目自己的样式；没有 typography 插件时逐元素映射最省事。
- 页面壳里的文案放进项目现有的 i18n，不要硬编码。

## 路由注意

- **slug 含 `/`**（如 `integration/ticket-auth`）。文件路由用 splat：TanStack Router 是 `help/$.tsx`，取 `_splat`；React Router 用 `/help/*`。
- **要放在登录守卫之外。** 帮助页是否对未登录用户可见是先在“公开范围判断”里定的，不是路由顺手决定的。放在需要登录的布局里，外部读者会被重定向到登录页。
- 组件里不要直接调 `Route.useParams()` 又放在路由文件里导出；多数 lint 规则（`react-hooks/rules-of-hooks`、`react-refresh/only-export-components`）会拦。把页面组件放到 feature 目录，路由文件只引用它。

## 入口

人需要能找到它。最有效的入口是**未登录用户第一眼看到的页面**（登录页）上的一个明显按钮。纯文字链接如果颜色与正文一致，看起来不像链接，用带图标的描边按钮。

## nginx 要同时满足两件事

1. `/help/*.md`、`/llms*.txt` 命中构建产物里的真实文件，缺失返回 404（见 SKILL.md 路径 A）。
2. **SPA 兜底不能带 `$uri/`。** 构建产物里有 `help/` 目录，`try_files $uri $uri/ /index.html` 会把 `/help` 当目录：`/help` 返回 301，`/help/` 返回 403，到不了 SPA 的 `/help` 路由。改成 `try_files $uri /index.html;`。前提是站点没有靠目录索引提供的页面，改之前确认。
