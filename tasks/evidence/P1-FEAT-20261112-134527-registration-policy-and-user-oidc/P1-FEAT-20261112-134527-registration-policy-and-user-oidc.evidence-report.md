# 注册策略与普通用户 OIDC 登录验证报告

> 人工确认项均保持未勾选。本报告先呈递 PRD §9.1 人工审阅流程。FreshAI 是注册策略的上游参考，不是本次被测应用或运行依赖。

独立 verifier 结论：**PASS**，0 个未解决 finding；[查看独立验证报告](P1-FEAT-20261112-134527-registration-policy-and-user-oidc.verifier-report.md)。这不代表 Human-Confirmed 项已经由用户接受，以下方框仍留空。

## §9.1 Human Review Surface · R3

### 主演示脚本

1. 平台管理员打开 /registration，设置“仅企业账号可注册”及 example.com 并保存。
2. 前台打开 /register，只显示 OIDC-only 提示和企业账号入口，不显示密码表单。
3. 新的空浏览器上下文以 new@example.com 通过本地身份中心替身登录，进入 /app/dashboard。
4. 新的空浏览器上下文以已验证的 x-<随机后缀>@other.test 试登录；返回 /login?sso_error=1，页面显示通用失败提示，/api/auth/me 为 401，且没有 session_id Cookie。

PRD 的第四步是对不在白名单域名的 OIDC 登录回调做负控。本轮已用实际 public OIDC flow 覆盖并保存失败截图、录像；模拟身份中心的邮件已验证，应用拒绝创建本地用户与 session。

### Human-Confirmed（PRD 原文，待人工判断）

- [ ] 同邮箱密码账号的处理方式符合 §2 所选方案 —— 证据：rv-2 输出
- [ ] 三种模式 + 白名单、`system_settings` 表与 `public_user` 两列符合预期 —— 证据：rv-3、rv-4 输出
- [ ] 白名单仅管理员可见、公开接口只返回模式 —— 证据：rv-3 输出
- [ ] 已查看 9.1 截图与录屏，页面与流程符合预期

### 真实页面与 PRD §7.7 目标

以下图片分别呈递 PRD §7.7 的 low-fidelity design intent 与真实页面。目标图取自 PRD 指定的状态，没有从实现页面倒推；静态目标只用于对比层级。真实 UI 使用 en-US 与产品布局，PRD 为中文 ASCII 图。

![PRD §7.7 OIDC-only low-fidelity design intent](rv-1-design-intent.png)

![Real user flow: OIDC-only registration page](rv-1-register-oidc-only.png)

![Real user flow: admin saved registration policy](rv-1-registration-settings.png)

![Real user flow: allowed public OIDC login dashboard](rv-1-user-oidc-dashboard.png)

![Real user flow: disallowed verified external-domain callback](rv-1-user-oidc-domain-rejection.png)

[播放外域 OIDC 回调失败录像](rv-1-user-oidc-domain-rejection.webm) · [播放允许域名 OIDC 登录录像](rv-1-user-oidc-sign-in.webm)

PRD §7.7 的 both 模式还明确要求现有密码表单下方显示企业账号入口；本轮注册截图由组织 E2E flow 的 UI 注册 context 捕获：

![PRD §7.7 both-mode low-fidelity design intent](rv-1-register-both-design-intent.png)

![Real user flow: both-mode registration page](rv-1-register-both.png)

### E2E 元数据与断言

- 最终 fresh run：2026-11-13T06-38-59；Playwright JUnit 为 4 tests、0 failures；套件 4 passed（1.8m），wrapper 实际 exit code 0。
- Browser: Playwright 1.60.0 / Chromium 158.0.8127.18，headless；viewport 1440×1200 CSS px；light / en-US。
- Fresh state：专属 PostgreSQL 数据库重建、仅清理隔离 Redis DB 15；策略由管理端 UI 保存，前台另用空 browser context 检查策略状态、注册与登录。
- Mock boundary：只由本机 loopback HTTP RS256 issuer 替换身份中心。真实管理页和前台页面、策略 API、注册/登录 callback、数据库、Redis 与会话保持真实。断言实际 canonical /api/admin/settings/registration-policy、/api/auth/registration-status、/api/auth/oidc/start、callback 与 /api/auth/me。未直接写 Cookie 或用户行。
- 本地单次注入 SECURITY_API_REQUESTS_PER_MINUTE=1000，避免多浏览器 context 共用 127.0.0.1 的请求总量超过默认 120/min。限流保持启用，默认配置未更改；最终日志 API 429 计数为 0；[Settings 实际读取值记录](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/e2e-api-rate-limit-config-check.log) 输出 1000。本轮不验证默认限流吞吐量。
- [完整运行日志](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-full-final-post-refactor-rate-limit-override.log) · [JUnit](../../../tests/playwright-e2e/test-results/2026-11-13T06-38-59/junit.xml) · [run metadata](rv-1-full-final.metadata.md)。

### RV 与共用 gate 证据

| RV / Gate | 结果 | 证据 |
|---|---|---|
| rv-1 注册策略即时生效和 public OIDC | 真实管理 UI 保存策略；外域 OIDC 被拒并显示错误；允许域登录进入 dashboard；本轮通过 | 最终完整运行日志、JUnit 与上方截图/录像 |
| rv-2 同邮箱冲突不自动关联 | main 报告 PostgreSQL 48 passed、MySQL 48 passed 的联合 API 回归 | [PG API](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/oidc-registration-admin-org-api-pg-current-final.log)、[MySQL API](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/oidc-registration-admin-org-api-mysql-current-final.log)、[same-email PG](public-oidc-same-email-pg-final.log) |
| rv-3 策略矩阵、白名单隔离与 fail-closed | PostgreSQL service/API 日志及 main 的两库联合 API 回归 | [policy service](registration-policy-service-green.log)、[policy API PG](registration-policy-api-pg-final.log)、[两库 API PG](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/oidc-registration-admin-org-api-pg-current-final.log)、[两库 API MySQL](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/oidc-registration-admin-org-api-mysql-current-final.log) |
| rv-4 migration | registration migration upgrade/head 日志与 PostgreSQL/MySQL roundtrip | [PG upgrade](pg-upgrade-head-final.log)、[PG roundtrip](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-3-migration-postgresql-roundtrip.log)、[MySQL roundtrip](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-3-migration-mysql-roundtrip.log) |
| rv-5 注册设置前端测试 | 4 个相关前端测试文件 18 passed；Admin/Public typecheck 与两端 build exit 0 | [frontend targeted tests](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/frontend-admin-auth-registration-tests-after-jscpd-markers.log)、[Admin typecheck](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/frontend-admin-typecheck-after-jscpd-markers.log)、[Public typecheck](frontend-public-typecheck-after-jscpd-markers.log)、[Admin build](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/frontend-admin-build-after-jscpd-markers.log)、[Public build](frontend-public-build-after-jscpd-markers.log) |
| just lint --repo（含 reuse） | exit 0；jscpd、pylint duplicate、架构/规范检查通过；本地测试 626 passed / 1 skipped、包测试 17 passed、MkDocs strict 和末尾全文件 lint 通过 | [repo lint 日志](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-lint-repo-jscpd-ignored-pg-final.log) |
| `CI=1 just lint --full` | exit 0；强制实际全文件 lint hooks 全通过 | [强制全文件 lint](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-lint-full-ci-current-final.log)、[缓存标记处理记录](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/force-full-lint-marker-final.log) |
| just test all | 928 passed、6 skipped，是最后一个组织并发测试替换前的全回归；替换只改测试用例，未改生产源。新用例 PostgreSQL、MySQL 各 1 passed | [完整回归](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-test-all-jscpd-ignored-current-final.log)、[PG 并发用例](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/org-last-platform-concurrency-pg-final.log)、[MySQL 并发用例](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/org-last-platform-concurrency-mysql-final.log)、[Ruff/format/diff check](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/org-last-platform-concurrency-ruff-final.log) |
| E2E source tree | test_tree 70c46a70b9f70bdbd1d3fdd8423d6793ea293af5；base HEAD 94b46529e93e7e5a1840d80a92511a94b77725ef | [最终完整运行日志](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-full-final-post-refactor-rate-limit-override.log) |
| Final effective source identity | `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6`、`lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`；最终指纹与差异见记录 | [source tree 指纹](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/source-tree-identity-after-concurrency-test-final.log) |

历史失败已保留，不作为本轮结果：callback 重构后 first run 曾因 org spec 漏点启用确认超时；下一 run 遇到默认 120/min 限流与 route-announcer 的重复 role=alert。已分别修正 UI 确认动作、E2E 环境限流配置和错误提示 locator；当前报告只引用 fresh 4/4 run。
