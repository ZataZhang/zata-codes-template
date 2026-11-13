# Zata Code Template 组织与两级管理员真实入口验证元数据

- Run: 2026-11-13T06-38-59（artifact ID UTC）；Playwright 实际结束约 1.8 分钟。
- Independent verifier: PASS，0 个未解决 finding；见 [独立验证报告](P1-FEAT-20261112-142923-organizations-and-two-tier-admins.verifier-report.md)。这不代替 PRD Human-Confirmed 人工接受。
- Command: SECURITY_API_REQUESTS_PER_MINUTE=1000 PLAYWRIGHT_OIDC_TESTS=1 ./scripts/shared/e2e/run-with-just-stack.sh 'tests/auth/admin-oidc-sign-in.oidc.no-auth.spec.ts tests/auth/registration-policy-and-user-oidc.oidc.admin.spec.ts tests/admin/organizations-and-admins.oidc.admin.spec.ts --workers=1'
- Result: 组织管理员真实 UI flow passed；全套共 4 tests passed、JUnit failures=0、wrapper 实际 exit code 0。cleanup 的自有 just-run 进程 SIGTERM/143 已被 wrapper 处理。
- Result paths: ../P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-full-final-post-refactor-rate-limit-override.log；../../../tests/playwright-e2e/test-results/2026-11-13T06-38-59/junit.xml。
- Worktree ports: backend 18400、admin 15573、public 13000；结束时 env.run-state 已恢复。
- Fresh state: 本轮专属 PostgreSQL E2E DB 在启动前重建；只清空隔离 Redis DB 15。各匿名与新身份 flow 显式空 storageState；只有 UI OIDC/password 登录之后才复制 session 验证持久状态。单轮用同一 local RS256 issuer。
- Browser: Playwright 1.60.0 / Chromium 158.0.8127.18，headless；CSS viewport 1440×1200，light/en-US。
- Mock boundary: 只替换 OIDC 身份中心；组织/管理员/用户 UI、canonical API、持久库、Redis 和会话检查是本模板真实实现。创建组织和两个管理员、密码注册 public users、移动组织、OIDC/password 登录、session 401 与重启后恢复均经生产页面/API完成。
- Verified assertions: 无密码 OIDC 管理员与有初始密码管理员分别在新 context 登录；organization_id、role=org 正确；用户列表只显示所属组织；org 角色无组织/管理员菜单；解绑清除映射后相同身份按验证邮箱规则重绑；provider-disabled 身份被拒且无应用 session；本地禁用后 OIDC 会话与 password session 下一次 /api/admin/auth/me 均 401；重新启用后全新 OIDC 登录恢复原 user_id。
- Rate limit environment: 此隔离运行单次使用 SECURITY_API_REQUESTS_PER_MINUTE=1000，backend AppSettings 读取值为 1000；默认 120/min 和限流 enabled 均未修改。本轮 API 429 计数 0，不声称测得默认吞吐能力。
- Real user-flow files: rv-1-organizations.png、rv-1-admin-create.png、rv-1-admin-create-with-password.png、rv-1-org-admin-users.png、rv-1-org-admin-password-users.png、rv-1-org-admin-reenabled-users.png 及 OIDC/password/re-enabled 录像。
- Design pairing: rv-1-design-intent.png 从 PRD §7.7 原始 ASCII 结构静态渲染并标为 low-fidelity design intent。真实 UI 使用实际表格、表单、导航和组织列表；PRD 中文 wireframe 与 en-US 截图的排版/文案不同，对照信息结构和角色边界，不是假设两者像素相等。
- E2E source tree: test_tree 70c46a70b9f70bdbd1d3fdd8423d6793ea293af5；base HEAD 94b46529e93e7e5a1840d80a92511a94b77725ef。
- Other gates: combined API PostgreSQL/MySQL 各 48 passed；migration roundtrip 两库日志存在。just test all 928 passed / 6 skipped 是最后一个并发测试替换之前的全回归；最终替换的最后平台管理员互禁用并发用例在 PG/MySQL 各 1 passed，并通过 Ruff/format/diff check，且没有生产源变化。rv-6 前端 4 个相关测试文件 18 passed、ConfirmDialog/admin-filter 2 files 10 passed、Admin typecheck/build exit 0；路径见本报告 RV 表。current-tree Docker runtime、just copy/source-hash smoke 通过；`just lint --repo` exit 0（含 jscpd/pylint、局部测试/包测试、MkDocs strict、末尾全文件 lint），强制 `CI=1 just lint --full` exit 0。最终指纹与差异见管理员 PRD 同目录 source-tree-identity-after-concurrency-test-final.log。
- Validation source identities: E2E run uses test_tree `70c46a70b9f70bdbd1d3fdd8423d6793ea293af5`; after the final test-only concurrency replacement, recorded effective test_tree is `8e792c937139e42d97ba9ad5f38e2e364982b8b6` and lint_tree is `6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`. The broad test run and repo lint snapshot are described separately in the evidence report; final source identity note records the later single-case change.
