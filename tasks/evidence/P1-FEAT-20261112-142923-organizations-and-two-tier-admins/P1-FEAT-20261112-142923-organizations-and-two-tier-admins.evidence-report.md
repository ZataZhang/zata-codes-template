# 组织与两级管理员验证报告

> 人工确认项保持未勾选；报告供人工核对 §9.1 的真实页面与安全 oracle。组织授权按模板本地模型实现；身份中心只提供 OIDC 外部身份。

独立 verifier 结论：**PASS**，0 个未解决 finding；[查看独立验证报告](P1-FEAT-20261112-142923-organizations-and-two-tier-admins.verifier-report.md)。这不代表 Human-Confirmed 项已经由用户接受，以下方框仍留空。

## §9.1 Human Review Surface · R3

### 主演示脚本

1. 平台管理员登录后台，检查“组织”“管理员”导航。
2. 通过管理 UI 创建“E2E Organization …”，再创建两个同组织管理员：一个不填密码、一个输入初始密码。
3. 用真实前台注册页创建两个 public 用户，再由平台管理员 UI 把其中一个移动到新组织。
4. 空 browser context 分别执行组织管理员 OIDC 登录和密码登录；两者的 /api/admin/auth/me 都返回 role=org 与该组织 ID；用户页仅列出新组织用户，且不显示组织/管理员管理入口。
5. 平台管理员通过确认框解绑无密码管理员的 IdP 关联；同一仍启用、邮箱已验证的 issuer/subject 可再次绑定。另以 IdP 停用身份尝试时不产生本地 session。
6. 平台管理员禁用 OIDC 管理员和密码管理员；各自已有 session 下一次 /api/admin/auth/me 均 401。重新启用 OIDC 管理员后，在新空上下文再次登录并验证同一 user_id 恢复。

本轮所有演示步骤经生产 UI/API 完成。专属 E2E 数据库与 local issuer 仅用于本地隔离验证，不直接写业务表或 Cookie。

### Human-Confirmed（PRD 原文，待人工判断）

- [ ] 组织模型与用户归属（一人一个组织、默认组织兜底、停用即生效）符合预期 —— 证据：rv-3、rv-4 输出
- [ ] 两级管理员创建与保护规则（仅平台管理员可创建、密码可选、禁用保护）符合预期 —— 证据：rv-2 输出
- [ ] 解绑只清除本地映射、允许符合条件的原身份重新首绑，且组织管理员权限受白名单约束 —— 证据：rv-2 解绑与越权用例输出
- [ ] 已查看 9.1 截图与录屏，页面与流程符合预期

### 真实页面与 PRD §7.7 目标

PRD §7.7 的 low-fidelity design intent 描述管理员表格、组织列表和用户归属列；静态目标表达信息结构，不代表组件级验证。真实图来自平台 UI 和组织管理员真实登录后的用户页。目标 wireframe 为中文，截图为 en-US，颜色、间距、字段排序和真实文案有差异；对照重点是角色、操作、组织范围。

![PRD §7.7 low-fidelity design intent](rv-1-design-intent.png)

![Real user flow: organization created in admin UI](rv-1-organizations.png)

![Real user flow: passwordless organization admin creation](rv-1-admin-create.png)

![Real user flow: password-enabled organization admin creation](rv-1-admin-create-with-password.png)

![Real user flow: organization-scoped OIDC admin users](rv-1-org-admin-users.png)

![Real user flow: organization-scoped password admin users](rv-1-org-admin-password-users.png)

![Real user flow: OIDC administrator after re-enable](rv-1-org-admin-reenabled-users.png)

[OIDC 首绑与组织范围录像](rv-1-org-admin-sign-in.webm) · [密码管理员录像](rv-1-org-admin-password-sign-in.webm) · [重新启用后的 OIDC 登录录像](rv-1-org-admin-reenabled-sign-in.webm)

### E2E 元数据与断言

- 最终 fresh run：2026-11-13T06-38-59；Playwright JUnit 为 4 tests、0 failures；套件 4 passed（1.8m），wrapper 实际 exit code 0。
- Browser: Playwright 1.60.0 / Chromium 158.0.8127.18，headless；viewport 1440×1200 CSS px；light / en-US。
- Fresh state：全套共用本轮专属 PostgreSQL E2E DB，Redis DB 15 单独清空；OIDC issuer 在一轮串行 suite 生命周期内保持同一 RS256 公钥/issuer。匿名 OIDC 和重新登录上下文显式为空；复制的 session 只在第一次真实登录后用于持久会话断言。
- Mock boundary：只替换身份中心；组织/管理员创建、注册用户、用户迁移、路由、角色菜单、org-scoped list、解绑/重绑、本地禁用及下次 API 请求都由本模板后端、页面、数据库和 Redis 真实处理。命令和 API 结果在最终 E2E log/JUnit；无数据库旁路、无手设 Cookie。
- 本地单次注入 SECURITY_API_REQUESTS_PER_MINUTE=1000，限流仍开启且默认 120/min 未变；本轮日志 API 429 计数 0；[Settings 实际读取值记录](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/e2e-api-rate-limit-config-check.log) 输出 1000，不宣称默认配置吞吐量已验证。
- [完整运行日志](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-full-final-post-refactor-rate-limit-override.log) · [JUnit](../../../tests/playwright-e2e/test-results/2026-11-13T06-38-59/junit.xml) · [run metadata](rv-1-full-final.metadata.md)。

### RV 与共用 gate 证据

| RV / Gate | 结果 | 证据 |
|---|---|---|
| rv-1 组织创建、管理员登录与组织范围 | 本轮真实浏览器 spec 通过；含 OIDC 首绑/解绑后重绑、密码管理员登录、两种既有 session 的禁用后 401、重新启用后的新登录 | 本节截图/录像、最终日志与 JUnit |
| rv-2 双层权限、禁用保护、解绑与审计 | PostgreSQL/MySQL 各 48 passed 联合 API 回归；最后平台管理员并发禁用保护在两库各 1 passed | [PG API](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/oidc-registration-admin-org-api-pg-current-final.log)、[MySQL API](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/oidc-registration-admin-org-api-mysql-current-final.log)、[PG org security](rv-2-org-security-realdb-final.log)、[PG 并发保护](org-last-platform-concurrency-pg-final.log)、[MySQL 并发保护](org-last-platform-concurrency-mysql-final.log)、[Ruff/format/diff check](org-last-platform-concurrency-ruff-final.log)、[PG admin disable](admin-disable-api-pg-final.log)、[MySQL admin disable](admin-disable-api-mysql-final.log) |
| rv-3 组织归属和作用域 | PostgreSQL/MySQL 组织范围日志 | [PG organization scope](organization-scope-pg-final.log)、[MySQL organization scope](organization-scope-mysql-final.log) |
| rv-4 migration | PostgreSQL/MySQL roundtrip | [PostgreSQL migration](migration-roundtrip-pg-final.log)、[MySQL migration](migration-roundtrip-mysql-final.log) |
| rv-5 seed admin recovery | 真实数据库测试 5 passed，覆盖 seed 将已禁用组织管理员恢复为配置的平台账号；仓库总回归另有 928 passed、6 skipped | [seed recovery / organization security](rv-2-org-security-realdb-final.log)、[just test all](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-test-all-current-final.log) |
| rv-6 角色导航与管理员表单前端单测 | 4 个相关前端测试文件 18 passed；ConfirmDialog/admin-filter 2 个 focused files 10 passed；Admin typecheck/build exit 0 | [frontend targeted tests](frontend-admin-auth-registration-tests-after-jscpd-markers.log)、[ConfirmDialog/admin-filter](admin-confirm-dialog-tests.log)、[typecheck](frontend-admin-typecheck-after-jscpd-markers.log)、[build](frontend-admin-build-after-jscpd-markers.log) |
| just test all | 928 passed、6 skipped（全回归在单一并发用例替换前；该替换没有生产源改动）。最终并发用例另外在 PostgreSQL/MySQL 各 1 passed | [just test all](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-test-all-jscpd-ignored-current-final.log)、[PG 并发用例](org-last-platform-concurrency-pg-final.log)、[MySQL 并发用例](org-last-platform-concurrency-mysql-final.log) |
| just lint --repo（含 reuse） | exit 0；jscpd、pylint duplicate、架构/规范检查通过；本地测试 626 passed / 1 skipped、包测试 17 passed、MkDocs strict 和末尾全文件 lint 通过 | [repo lint 日志](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-lint-repo-jscpd-ignored-pg-final.log) |
| `CI=1 just lint --full` | exit 0；强制实际全文件 lint hooks 全通过 | [强制全文件 lint](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/just-lint-full-ci-current-final.log)、[缓存标记处理记录](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/force-full-lint-marker-final.log) |
| E2E source tree | test_tree 70c46a70b9f70bdbd1d3fdd8423d6793ea293af5；base HEAD 94b46529e93e7e5a1840d80a92511a94b77725ef | [最终完整运行日志](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-full-final-post-refactor-rate-limit-override.log) |
| Final effective source identity | `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6`、`lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`；相对 E2E run 仅替换并发测试，无生产代码变化 | [source tree 指纹和差异](../P1-SECURITY-20261112-134527-admin-oidc-sign-in/source-tree-identity-after-concurrency-test-final.log) |

本轮之前的 post-refactor 失败日志保留：首轮因未点击重新启用确认按钮超时；第二轮因本机多个 context 共用 127.0.0.1 超过默认 API 限额 120/min。当前 E2E 运行显式使用已有 API 请求限额配置 1000，保持 middleware 开启，日志没有 429。此次运行成功不覆盖默认 120/min 吞吐容量验证。

<details>
<summary>历史失败截图（已定位并修复，不作为 PASS 证据）</summary>

**第一次组织流程在进入用例前停止。** 本地图片说明：截图为空白，是因为用例仍处于 `about:blank` 时从页面脚本用相对地址执行 `/api/admin/auth/me`，浏览器无法解析 URL；后续改为有应用基址的真实页面/请求后，组织流程完成。

![历史失败现场：about:blank 上的相对 fetch 无法解析](rv-1-first-run-org-context-failure.png)

仓库根目录打开命令：`open tasks/evidence/P1-FEAT-20261112-142923-organizations-and-two-tier-admins/rv-1-first-run-org-context-failure.png`

**串行运行中的定位器冲突。** 本地图片说明：以下三张分别保留当时管理端注册设置页和两张刚创建的测试 workspace 快照。该轮在查找按钮时同时匹配到顶栏命令搜索和页面表单搜索（strict-mode violation），没有完成后续组织管理员场景；workspace 名称与邮箱都是本地 `.example.test` 测试数据。

![历史失败现场：串行用例停在管理端注册设置页](rv-1-serial-first-failure.png)

仓库根目录打开命令：`open tasks/evidence/P1-FEAT-20261112-142923-organizations-and-two-tier-admins/rv-1-serial-first-failure.png`

![历史失败现场：此前测试注册的组织 workspace](rv-1-serial-first-failure-2.png)

仓库根目录打开命令：`open tasks/evidence/P1-FEAT-20261112-142923-organizations-and-two-tier-admins/rv-1-serial-first-failure-2.png`

![历史失败现场：此前测试注册的默认组织 workspace](rv-1-serial-first-failure-3.png)

仓库根目录打开命令：`open tasks/evidence/P1-FEAT-20261112-142923-organizations-and-two-tier-admins/rv-1-serial-first-failure-3.png`

**管理员禁用 API 返回 500 的早期运行。** 本地图片说明：当时真实页面的请求断言收到 500，后续将锁定查询限制到管理员行并在 PostgreSQL/MySQL 验证保护行为；截图只保留错误发生时的管理页面，不作为成功禁用或会话撤销证据。

![历史失败现场：管理员禁用请求返回 500](rv-1-admin-disable-500.png)

仓库根目录打开命令：`open tasks/evidence/P1-FEAT-20261112-142923-organizations-and-two-tier-admins/rv-1-admin-disable-500.png`

**匿名上下文负控曾意外复用平台管理员状态。** 本地图片说明：截图显示仍登录的平台管理页面；Playwright 的 `newContext()` 继承了项目 storageState，导致当时 `/api/admin/auth/me` 为 200。随后新匿名上下文显式使用空 storageState，并断言没有 `admin_session_id`，最终测试确认失败 callback 后为 401；此旧图不作为负控通过证据。

![历史失败现场：负控上下文意外带有平台管理员会话](rv-1-unverified-session-200.png)

仓库根目录打开命令：`open tasks/evidence/P1-FEAT-20261112-142923-organizations-and-two-tier-admins/rv-1-unverified-session-200.png`
</details>
