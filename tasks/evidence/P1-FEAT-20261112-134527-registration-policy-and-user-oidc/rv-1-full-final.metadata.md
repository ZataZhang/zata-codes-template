# Zata Code Template 注册策略与普通用户 OIDC 真实入口验证元数据

- Run: 2026-11-13T06-38-59（artifact ID UTC）；Playwright 实际结束约 1.8 分钟。
- Independent verifier: PASS，0 个未解决 finding；见 [独立验证报告](P1-FEAT-20261112-134527-registration-policy-and-user-oidc.verifier-report.md)。这不代替 PRD Human-Confirmed 人工接受。
- Command: SECURITY_API_REQUESTS_PER_MINUTE=1000 PLAYWRIGHT_OIDC_TESTS=1 ./scripts/shared/e2e/run-with-just-stack.sh 'tests/auth/admin-oidc-sign-in.oidc.no-auth.spec.ts tests/auth/registration-policy-and-user-oidc.oidc.admin.spec.ts tests/admin/organizations-and-admins.oidc.admin.spec.ts --workers=1'
- Result: 4 tests passed，JUnit failures=0；wrapper 实际 exit code 0。cleanup 输出中自有 just-run 进程 SIGTERM 后 exit 143，由 wrapper 正常捕获。
- Result paths: ../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-full-final-post-refactor-rate-limit-override.log；../../../tests/playwright-e2e/test-results/2026-11-13T06-38-59/junit.xml。
- Worktree ports: backend 18400、admin 15573、public 13000；base URL/callback URI 根据临时 run-state 自动拼出，测试后已恢复。
- Fresh state: 专属 PostgreSQL 数据库 template_oidc_prd_e2e_pg 每次 final run 前重建；Redis 只清理 DB 15；三 spec 串行共用本次 fresh issuer。
- Browser: Playwright 1.60.0 / Chromium 158.0.8127.18，headless；viewport 1440×1200 CSS px；light/en-US。
- Mock boundary: 仅 loopback OIDC 身份中心替换；issuer 提供实际 HTTP discovery/JWKS/authorize/token，测试签发并验证真实 RS256 token 与 PKCE/state/nonce。策略设置 UI、注册页、public API、数据库、Redis 与会话均使用真实本地应用。
- Verified assertions: 管理员 UI PUT 保存 oidc_only + example.com；public /register 读取最新策略；空上下文用已验证 new@example.com OIDC 登录后 /api/auth/me 返回该用户；空上下文用已验证 x-<suffix>@other.test 登录被回调拒绝，/login?sso_error=1 显示指定通用错误且 /api/auth/me=401、没有 session_id Cookie。组织 spec 另从 UI 捕获 both 模式的表单与企业账号按钮并实际密码注册用户。
- Rate limit environment: 隔离 run 单次注入 SECURITY_API_REQUESTS_PER_MINUTE=1000；后台读取值验证为 1000。默认 120/min 与 middleware enabled 状态不改。本轮 API 429 计数为 0；不代表默认吞吐容量已测。
- Real user-flow files: rv-1-registration-settings.png、rv-1-register-oidc-only.png、rv-1-user-oidc-dashboard.png、rv-1-user-oidc-domain-rejection.png/.webm、rv-1-user-oidc-sign-in.webm，以及 both-mode 对照图。
- Design pairing: rv-1-design-intent.png 和 rv-1-register-both-design-intent.png 都取自本 PRD §7.7 后静态渲染，明确是 low-fidelity design intent；both 目标描述密码表单下方的企业账号入口。实际 UI 有生产样式、导航、间距和交互，截图为 en-US。
- E2E source tree: test_tree 70c46a70b9f70bdbd1d3fdd8423d6793ea293af5；base HEAD 94b46529e93e7e5a1840d80a92511a94b77725ef。
- Other gates: PostgreSQL/MySQL combined API logs 各 48 passed；两库 migrations roundtrip 日志已留存。rv-5 前端 4 个相关文件 18 passed；Admin/Public typecheck 与两端 build exit 0，路径见对应 RV 表。just test all 928 passed / 6 skipped 在最后一个组织并发测试替换前完成；新替换的 PG/MySQL 并发用例各 1 passed，未改生产源。just copy/source-hash smoke 通过；`just lint --repo` exit 0（包括 reuse、局部测试/包测试、MkDocs strict、全文件 lint），`CI=1 just lint --full` exit 0。最终 test_tree/lint_tree 与差异说明见管理员 PRD 同目录 source-tree-identity-after-concurrency-test-final.log。
- Validation source identities: E2E run uses test_tree `70c46a70b9f70bdbd1d3fdd8423d6793ea293af5`; after the final test-only concurrency replacement, recorded effective test_tree is `8e792c937139e42d97ba9ad5f38e2e364982b8b6` and lint_tree is `6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`. The broad test run and repo lint snapshot are described separately in the evidence report; final source identity note records the later single-case change.
