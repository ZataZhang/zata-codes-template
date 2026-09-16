# Verification Plan: 前端界面中英文 i18n 双语能力

对应 PRD：`tasks/pending/P2-FEAT-20260707-150000-frontend-i18n-bilingual.md`

本文件把 §9 Acceptance Checklist 每条验收项映射到具体可执行命令；证据按 rv-id / 验收组命名落在本目录。

## 采集环境与纪律

| 项 | 值 |
|---|---|
| 公开站 | `next build --webpack` 产物 + `next start -p 3929`（生产构建，真实 SSR） |
| 后台 | `vite --port 5842`（真实 dev server） |
| 后端 | `uvicorn backend.main:app --port 8000`（Postgres/Redis 已起，Alembic 已应用，引导账号已 seed） |
| 验证层级 | **real user flow**：真实构建产物、真实路由、真实切换器点击；唯一脚本化动作是"登录" |

两条必须遵守的纪律（否则会得到假结果）：

1. `next build` 必须在**无 server 运行**时执行。旧 `next start` 存活时构建会覆盖它正在读取的 `.next`，破坏 server action 清单；而公开站切换器写 cookie 正是走 server action，于是切换静默失效（表现为 3 条 Playwright 用例失败、耗时异常升高）。起服务前先清空 3929/5842/8000。
2. 沙箱会在工具调用结束后回收/遗留子进程，因此起服务、跑 oracle、跑 Playwright、截图必须在**同一次调用**内完成。

## 验收项 → 命令映射

### Human-Confirmed（人审，§9.1 呈递区）

- **rv-1 首访默认 locale = en**
  - 命令：`curl -s http://localhost:3929/ | grep -oE '<html[^>]*lang="[^"]*"'` → `<html lang="en"`。
  - 后台侧：`npx playwright test tests/i18n/admin-locale.no-auth.spec.ts -g "default"`。
  - 呈递物：`s1-first-visit-default.png`。
- **rv-2 核心页面双语、无漏翻**
  - 静态：`rg -nP '[\x{4e00}-\x{9fff}]' frontend-public/app` → 仅中文注释命中，无 JSX 文本命中。
  - 动态：对 `/about`、`/features`、`/pricing` 各带 zh/en cookie curl，比对 `<html lang>`；并抽查 `/about` 的 `关于本模板` / `About this template`。
  - E2E：`npx playwright test tests/i18n/public-locale.no-auth.spec.ts`（含 `core pages follow the chosen language`、`remaining marketing pages are translated, not left in Chinese`）。
  - 呈递物：`s4-core-{en,zh}.png`、`s4-settings-{en,zh}.png`、`s4-marketing-{en,zh}.png`。
- **rv-3 cookie 持久化 + SSR 跟随**
  - 正跑：`curl -s -b 'NEXT_LOCALE=zh' .../login` → `lang="zh"` + `登录`；`-b 'NEXT_LOCALE=en'` → `lang="en"` + `Sign in`。
  - 负控：不带 cookie curl → 回退 `lang="en"` + `Sign in`，与 zh 形成可见差异。
  - E2E：`-g 'persists across reloads'`。
  - 呈递物：`s2-switch-before.png` / `s2-switch-after.png` / `s3-after-reload.png`。
- **rv-5 后台 react-i18next + localStorage 持久化**
  - E2E：`-g 'persists in localStorage'`（断言 `localStorage.i18nextLng === 'zh'`）、`-g 'survives reload'`。
  - 负控：用例内先 `removeItem('i18nextLng')` 再 reload，断言回退英文。
  - 呈递物：`s5-admin-{zh,en}.png`。
- **rv-6 切换器可见可操作、点击即整页切换**
  - E2E：两端 `-g 'switch'`，均先断言切换器可见再点击 `language-option-zh`，随后断言 `html[lang=zh]` + 目标语言文案。
  - 负控：切换器 disabled 时点击会失败。
  - 呈递物：复用 rv-3 / rv-5 截图（切换器在 `s1`/`s2`/`s4-marketing-*`/`s5-admin-*` 中均可见）。

### verifier-only（不进 §9.1）

- **rv-4 Accept-Language 协商**
  - 命令：对 `zh-CN,zh;q=0.9` / `en-US,en;q=0.9` / `fr-FR,fr;q=0.9` 三种 header curl `.../login`，比对 `<html lang>`；期望 `zh` / `en` / `en`（回退默认）。
  - 负控：删 `negotiate.ts` 的 zh 分支后三种 header 应输出相同 lang。
  - 另由 Playwright `unsupported browser language › falls back to the default locale`（`test.use({ locale: 'fr-FR' })`）覆盖。
- **rv-7 文案 key 对齐**
  - 正跑：`node scripts/check-i18n-keys.mjs` → 退出码 0，`missing-in-zh` / `extra-in-zh` 均为 `[]`。
  - 负控：删 `common.loading` + 加 `common.orphanKey` 后重跑 → 退出码 1 且列出该 key。
- **rv-8 构建通过 + 未迁移页面不坏**
  - `cd frontend-public && npx next build --webpack` → 退出码 0，列出全部路由。
  - `cd frontend-admin && npx tsc -b --force`。
  - `npx vitest run --browser.headless`（后台 16 files / 107 tests）。
  - **偏差披露**：rv-8 原文的 `curl .../app/agents` 期望 200，但本仓库无该路由（路径抄自 `freshai`），实际 404。命题改由"全部真实路由均生成且渲染正常 + 后台单测/smoke 全绿"证明。

### Architecture / Dependency Acceptance

- **两前端库不混用**：`git diff HEAD -- frontend-public/package.json frontend-admin/package.json` → 公开站仅 `next-intl`；后台仅 `i18next` / `react-i18next` / `i18next-browser-languagedetector`。
- **`<html lang>` 动态化 + `generateMetadata` 走 i18n**：读 `frontend-public/app/layout.tsx`，确认 `getLocale()` → `<html lang={locale}>`、`getTranslations("html")` → metadata。
- **后台组件前初始化 i18n**：读 `frontend-admin/src/main.tsx`，确认 `import './i18n/init'` 早于组件与 Provider。
- **不引入 URL 前缀路由**：`ls frontend-public/middleware.ts` 不存在；`find frontend-public/app -type d -name '[locale]'` 无结果。
- **不动后端 / 数据库**：`git status --short -- src/ alembic/ pyproject.toml uv.lock main.py` → 空输出。

### Behavior / Frontend Acceptance

- 上述 rv-1~rv-8 覆盖。
- **两前端构建与类型检查**：`npx next build --webpack`（公开站）、`npx tsc --noEmit`（公开站）、`npx tsc -b --force`（后台）。

### Documentation Acceptance

- **FR-7 文档**：读 `docs/guides/i18n.md`（架构、cookie/localStorage 约定、key 命名规范、非目标）。
- **导航同步**：`rg -n 'guides/i18n.md' mkdocs.yml` 命中。
- **`docs/ai-standards/` 是否需要更新**：判定不需要——该目录属 upstream-owned（`sync_template.sh` 会覆盖），前端 key 命名规范写在项目自有的 `docs/guides/i18n.md`。

### Delivery Readiness

- `just test`（期望 212 passed）→ 写入 `just test` 标记。
- `just lint --full`（期望通过）。
- 截图落盘：`scripts/shared/just/check_prd_evidence.sh <prd> <worktree>` → 找到 12 个 `.png`。
- 密钥扫描：`scripts/shared/just/scan_evidence_secrets.sh tasks/evidence/P2-FEAT-20260707-150000-frontend-i18n-bilingual`。

## 证据命名约定

- 截图按 PRD §9.1 表命名：`s1-*`、`s2-*`、`s3-*`、`s4-*`、`s5-*`。
- 截图由 `tests/playwright-e2e/support/capture-i18n-evidence.mjs` 生成，可复现。
- 命令输出以摘要形式写入 `*.evidence-report.md`（原始日志不入库，`.gitignore` 只保留 `*.md`）。
