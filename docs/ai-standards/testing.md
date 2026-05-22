# Testing Standards

## Validation Is Mandatory

完成实现前，必须运行与改动范围相匹配的验证。

优先策略：

- 小改动跑最相关的 targeted tests
- 文档或规范改动至少跑一致性检查和 `mkdocs build`
- 后端行为变更跑对应的 `pytest`
- 会改变 API、CLI、前端流程、后台任务、持久化、启动或部署行为时，补充最高可行保真度的真实入口验证

## Realistic Validation

测试分层应覆盖“逻辑正确”和“真实入口可用”两件事。

常见层级：

- unit：验证纯逻辑、边界条件和错误分支
- integration：验证模块组合、存储适配、配置解析和跨层契约
- real entry：通过项目实际入口验证行为，例如 HTTP API、CLI、应用启动、worker job、migration、service composition root
- user flow：通过 Playwright 或等价端到端流程验证用户可见行为
- sandbox/live：仅在外部服务行为无法用本地替身证明时使用，且必须显式 opt-in

规则：

- 不要求所有变更都上 live 外部服务，但必须说明最高可行保真度是什么。
- mock 可以用于慢速、昂贵或不稳定依赖；关键边界本身需要尽量保持真实，例如路由、配置加载、序列化、数据库迁移或启动装配。
- 需要凭据、沙箱账号或外部服务时，验证命令必须用环境变量显式开启，并记录无凭据时仍需通过的 fallback 验证。
- PRD 或 planning 任务必须写明真实入口、mock 边界、数据/环境需求、命令或人工沙箱流程，以及该验证是否阻塞验收。

## Python Test Workflow

优先使用仓库现有命令：

- `just test`
- `just test all`
- `uv run pytest ...`

验证架构和规范时，也常用：

- `uv run python hooks/check_architecture.py`
- `uv run python hooks/check_guidelines_consistency.py`
- `uv run mkdocs build`

## Playwright Boundary

`tests/playwright-e2e/` 是**独立的 TypeScript/Node.js 包**。

规则：

- 包管理器使用 `npm`
- 不要对该目录强加 Python SSA 命名规则
- 先看 `tests/playwright-e2e/README.md` 的适配说明

常用命令：

- `just e2e-install`
- `just e2e`
- `just e2e smoke`
- `just e2e no-auth`

`just test` 会先执行 `SKIP=check-test-flag just lint --full`；当测试最终通过时，会同时刷新 `just test` 与 full lint 的本地通过标记。若代码有效 tree 未变化，后续 `just lint --full` 可以复用该标记走快速路径，但提交门禁仍会检查 `just test` 标记。

交付前建议：

- 日常迭代先跑 `just lint`，确认 staged 变更与真实 pre-commit hook 一致。
- 涉及复用边界、架构、AI 规范入口或重复风险时补跑 `just lint --reuse`。
- 最终交付、PRD 归档或合并前跑 `just lint --repo`；若无法运行总入口，至少跑 `just lint --full`、`just lint --reuse`、`just test` 和受影响文档的 `uv run mkdocs build --strict`。

## Change Recording

当任务带有 PRD 或 planning 记录时，记录实际执行的验证命令和结果。
