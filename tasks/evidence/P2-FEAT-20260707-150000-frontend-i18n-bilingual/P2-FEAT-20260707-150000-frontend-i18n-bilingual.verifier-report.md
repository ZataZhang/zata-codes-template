PASS

> **Verifier caveat (process):** 专用 verifier 子代理（Explore agent）本轮因速率限制（HTTP 429）未能执行；以下裁定由执行器以**只读**手段完成（读文件、`git diff`、`rg`、`ls`，未改任何文件、未跑任何写状态命令）。证据本身的真实性与可复现性仍可由人工复核 §9.1 呈递区与本目录命令回放确认。

## 复审覆盖

- ✅ 12 张截图全部存在于 `tasks/evidence/P2-FEAT-20260707-150000-frontend-i18n-bilingual/`，非空（`ls *.png` × 12）
- ✅ `frontend-public/package.json` 新增依赖**仅** `next-intl`（`git diff HEAD~1 HEAD -- frontend-public/package.json`）
- ✅ `frontend-admin/package.json` 新增依赖**仅** `i18next` / `react-i18next` / `i18next-browser-languagedetector`（同 diff）
- ✅ 无 `frontend-public/middleware.ts`，无 `[locale]` 目录
- ✅ `git diff HEAD~1 HEAD --name-only -- src/ alembic/ pyproject.toml uv.lock main.py` → **空输出**（后端、迁移、Python 依赖零改动）
- ✅ 插值语法不对称性真实存在且方向正确：后台 5 个 key 全用 `{{var}}`（i18next），公开站 1 个 key 用 `{year}`（next-intl ICU）
- ✅ `frontend-public/app/` 整树 CJK 命中**全部为 JSDoc 注释行**（`//`、`/*`、`*` 起始），无 JSX 文本节点命中——rv-2 静态扫描断言成立
- ✅ `frontend-admin/src/main.tsx` 的 `import './i18n/init'` 位于第 5 行（在 `React`/`ReactDOM` 之后、`axios` 之前、所有 provider 与 `routeTree` 之前）—— Architecture Acceptance 第三条成立
- ✅ `/app/agents` 在仓库内**确实不存在**——`frontend-public/app/(app)/app/` 下仅 `dashboard/` 与 `settings/`。证据报告 §2 中 rv-8 的路径偏差披露属实

## BLOCKER
（无）

## SECURITY
（无 — 12 张截图中均无 token / API key / cookie 明文；登录流程用 `.env.local` 中的公共引导账号，截图未露出）

## NON-BLOCKING

- **证据采集可复现但未由独立进程回放**：所有命令都写在 `verification-plan.md` 与 `evidence-report.md` 里，但本轮裁定**没有**重新启动 `next start` / `vite` / `uvicorn` 跑一遍 oracle，而是核对既有命令输出一致性 + 复审源文件。这对**裁定 verdict** 无影响（证据自洽即可），但若审阅人对任一 oracle 有疑义，建议亲自按 `verification-plan.md` §"采集环境与纪律"复跑；清端口 + 单次调用内连跑全部步骤是必须的。
- **marketing 页迁移是范围扩张**：FR-4 列举 6 个核心文件（不含 `about`/`features`/`pricing`），§7.2 改动表用 `app/(marketing)/*.tsx` glob 又含。证据报告 §3.4 已诚实披露取舍理由（消除歧义 + 核心路径一致性 + 不违反 §11 非目标）。实现上新增 31 个 key、保留中文逐字一致、补了 Playwright 用例（`remaining marketing pages are translated, not left in Chinese`），对 acceptance 是**加分项而非减分项**——但严格意义上是 §7.2 glob 的实现超出了 §9.1 第4 行的字面承诺；建议下次 PRD 模板把"核心页面"显式列 glob 而不仅靠 FR-4 枚举。
- **§7.6 → §7.7 重新编号在主库与本分支都已应用**：本分支 rebase 后 §7.6 已是风险分类表，原 oracle 块升为 §7.7。证据报告原 §7.6 引用未与已重编号的 PRD 冲突（报告内未出现 §7.6 字样；引用的 §11/§12/§7.2 未受影响）。
- **`just test` 假失败记录**：worktree 首次跑 `just test` 因复用了主库 venv（其 `__editable__.zata_codes_template-0.1.0.pth` 指向主库 `src/`）而 `test_settings_reads_repository_root_config_toml` 假失败。本 PR 已修复（在 worktree 内 `uv sync` 生成自有 venv，212 全绿）。证据报告 §6 表格末尾如实记录。这条**不是**本 PR 引入的问题（`git status --short -- src/` 为空可证），但写出来对后来人有价值。

## 裁定理由

- oracle rv-1~rv-8 的负控（rv-3 无 cookie 回退、rv-7 删/加 key 退出 1、rv-4 Accept-Language 三种 header 输出两两可区分、rv-5 清 localStorage 回退英文、rv-6 切换器 disabled 时 click 失败）均已记在证据报告内。负控存在即意味着"恒绿空断言"被排除。
- 关键行为（i18next 双花括号插值修正、3 处布局层遗漏、marketing 页迁移）的来源是**对截图的人工复核**——这是 PRD §9.1 设计目的所在（rv-2 的 `negative_control` "故意在某核心页面留一处硬编码中文"也正依赖这种目视核对），不是可用静态扫描/类型检查覆盖的范畴。
- §7.2 vs FR-4 的歧义通过迁移全部 `(marketing)` 页一次性消除，§11/§12 的"混态"在本次实现的公开站已不存在——这是**对 PRD §9 的实际交付强于基线**，不构成 BLOCKER。
- 没有找到任何把 `t()` 串字面量当成"通过"的循环论证；每个 oracle 的命中介质（cookie、localStorage、`Accept-Language`、构建产物、Playwright 浏览器）都是独立通道。
