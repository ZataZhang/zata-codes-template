# Zata Code Template 管理员 OIDC 真实入口验证元数据

- Run: 2026-11-13T06-38-59（artifact ID UTC）；Playwright 实际结束约 1.8 分钟。
- Independent verifier: PASS，0 个未解决 finding；见 [独立验证报告](P1-SECURITY-20261112-134527-admin-oidc-sign-in.verifier-report.md)。这不代替 PRD Human-Confirmed 人工接受。
- Command: SECURITY_API_REQUESTS_PER_MINUTE=1000 PLAYWRIGHT_OIDC_TESTS=1 ./scripts/shared/e2e/run-with-just-stack.sh 'tests/auth/admin-oidc-sign-in.oidc.no-auth.spec.ts tests/auth/registration-policy-and-user-oidc.oidc.admin.spec.ts tests/admin/organizations-and-admins.oidc.admin.spec.ts --workers=1'
- Result: 4 tests passed，JUnit failures=0；wrapper 的实际 exit code 为 0。最终日志包含其自有 just-run 进程在 cleanup 中接到 SIGTERM 的 exit 143，这由 wrapper 正常捕获。
- Result paths: rv-1-full-final-post-refactor-rate-limit-override.log；../../../tests/playwright-e2e/test-results/2026-11-13T06-38-59/junit.xml。
- Worktree ports: backend 18400、admin 15573、public 13000；wrapper 根据 worktree env.run-state 生成 base/callback URLs 并在结束后还原文件。
- Fresh state: dedicated PostgreSQL E2E DB template_oidc_prd_e2e_pg 在 run 前重建；只清理隔离 Redis DB 15。全套串行使用同一个本地 OIDC issuer 生命周期和 RS256 key。运行未使用默认共享 test database。
- Browser: Playwright 1.60.0，Chromium 158.0.8127.18，headless，CSS viewport 1440×1200，device scale factor 1，light/en-US。
- Mock boundary: loopback HTTP OIDC issuer 是唯一身份中心替身，提供 discovery、JWKS、authorize、token，并由测试实际执行 PKCE/state/nonce 校验。Zata Code Template 的前后端页面、API、Redis、PostgreSQL 与 session 处理是真实本地实现。未直写 Cookie 或业务表。
- Verified assertions: canonical admin status/start/callback 与 /api/admin/auth/me；新邮箱已验证账户首绑；相同 issuer/subject、IdP 邮箱变化后仍解析为同一 admin user_id；admin password login 回归；组织 spec 还覆盖未验证邮箱错误页、401 与不签 admin session cookie。
- Rate limit environment: 本轮隔离 wrapper 单次传入 SECURITY_API_REQUESTS_PER_MINUTE=1000；后台已用 AppSettings 验证读取值 1000。默认 120/min、限流启用状态均未修改。本轮 log 中 API 429 计数 0；[AppSettings 读取值日志](e2e-api-rate-limit-config-check.log) 为 1000。此运行不验证默认 120/min 吞吐容量。
- Real user-flow files: rv-1-sign-in-button.png、rv-1-admin-dashboard.png、rv-1-admin-oidc-sign-in.webm。未验证身份错误页通过真实浏览器断言但本轮未单独保存截图。
- Design pairing: rv-1-design-intent.png 是直接从本 PRD §7.7 提取并渲染的 low-fidelity design intent，不是组件预览或真实页面验证。PRD wireframe 中文，真实页面 en-US，比较按钮/提示层级与行为。
- E2E source tree: test_tree 70c46a70b9f70bdbd1d3fdd8423d6793ea293af5；base HEAD 94b46529e93e7e5a1840d80a92511a94b77725ef。
- Current non-browser gates: PG/MySQL combined API logs 各 48 passed；just test all 为 928 passed / 6 skipped，发生在最后一个组织并发测试替换之前，新增用例之后在 PG/MySQL 各 1 passed。Admin rv-5 前端 targeted 4 files 18 passed、focused ConfirmDialog/admin-filter 2 files 10 passed、Admin typecheck/build exit 0；Admin rv-6 包测试 17 passed、wheel/sdist consumer 1 passed、artifact SHA/source match、just copy source-hash smoke 与 Docker current-tree health 通过。`just lint --repo` exit 0（含 reuse、本地测试 626/1 skip、包 17 passed、MkDocs strict 与末尾全文件 lint）；强制 `CI=1 just lint --full` exit 0。最终指纹见 source-tree-identity-after-concurrency-test-final.log；MkDocs 仅输出仓库既有 INFO。
- Validation source identities: E2E run uses test_tree `70c46a70b9f70bdbd1d3fdd8423d6793ea293af5`; after the final test-only concurrency replacement, recorded effective test_tree is `8e792c937139e42d97ba9ad5f38e2e364982b8b6` and lint_tree is `6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`. The broad test run and repo lint snapshot are described separately in the evidence report; final source identity note records the later single-case change.
