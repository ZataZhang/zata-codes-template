# 管理员 OIDC 登录验证报告

> 人工确认项均保持未勾选。本报告呈递 §9.1 真实入口证据；E2E run 绑定到 `70c46a70b9f70bdbd1d3fdd8423d6793ea293af5`，最终验证指纹为 `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6` / `lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`。`just lint --repo` 与强制全文件 lint 均通过。FreshAI 只作为 PRD 所述上游参考，不是本次被测应用。

独立 verifier 结论：**PASS**，0 个未解决 finding；[查看独立验证报告](P1-SECURITY-20261112-134527-admin-oidc-sign-in.verifier-report.md)。这不代表 Human-Confirmed 项已经由用户接受，以下方框仍留空。

## §9.1 Human Review Surface · R3

### 主演示脚本

1. 打开管理端 /sign-in，确认密码登录表单下方显示企业账号入口。
2. 点击入口，使用本地身份中心替身完成授权；授权请求带有 PKCE S256。
3. 使用种子平台管理员已验证邮箱登录，返回后台首页；/api/admin/auth/me 返回 platform 角色。
4. 使用未验证邮箱的组织管理员身份登录，返回错误页、显示通用失败提示；匿名 /api/admin/auth/me 为 401，未签发 admin_session_id。

本轮成功登录截图及录屏已保存。未验证身份的错误提示和 401 由同一轮组织管理员真实流程断言，但未单独保存该失败页面截图；请人工确认界面时以录屏和入口/结果截图为准，失败 UI 的截图缺口在此披露。

### Human-Confirmed（PRD 原文，待人工判断）

- [ ] 首次绑定规则（已验证邮箱 + 唯一匹配 + 未绑定 + 启用）与 `admin_user` 新增三列符合预期 —— 证据：rv-2 各拒绝用例输出、rv-3 迁移往返输出
- [ ] 登录临时数据存 Redis、一次性使用符合预期 —— 证据：rv-2 重放与无 Cookie 用例输出
- [ ] 已查看 9.1 演示录屏与截图，登录页与登录结果符合预期

### 真实页面与 PRD §7.7 目标

PRD 目标图是 low-fidelity design intent，只表达按钮、错误提示和表单层级，不是组件渲染或真实页面验证。实际页面使用生产布局、排版和状态；目标文字为中文，截图为 en-US，因此对比信息层级和行为，不逐字对齐。

![PRD §7.7 low-fidelity design intent](rv-1-design-intent.png)

![Real user flow: admin sign-in entry](rv-1-sign-in-button.png)

![Real user flow: OIDC sign-in result](rv-1-admin-dashboard.png)

[播放真实登录流程录屏](rv-1-admin-oidc-sign-in.webm)

### E2E 元数据与断言

- 最终 fresh run：2026-11-13T06-38-59；Playwright JUnit 为 4 tests、0 failures；套件 4 passed（1.8m），wrapper 实际 exit code 0。
- Browser: Playwright 1.60.0 / Chromium 158.0.8127.18，headless；viewport 1440×1200 CSS px；light / en-US。
- Fresh state：专属 PostgreSQL 数据库重建、仅清理隔离 Redis DB 15；匿名路径显式空 storageState；成功登录后才在新上下文复制 session。全串行运行期间同一 loopback RS256 issuer 处理 discovery、JWKS、authorize 和 token 请求，并验证 PKCE/state/nonce。
- Mock boundary：只替换身份中心。Zata Code Template 后端、应用页面、API、数据库、Redis 与会话均是真实本地实现。浏览器点击实际页面并断言 canonical /api/admin/auth/oidc/status、start、callback、/api/admin/auth/me、密码登录请求；没有直接设置 Cookie 或写业务数据库。
- 本地测试环境单次注入已有配置 SECURITY_API_REQUESTS_PER_MINUTE=1000，以免多浏览器 context 合并的 loopback 请求超过默认 120/min。限流保持启用；默认配置未改；最终日志中 API 429 次数为 0；[Settings 实际读取值记录](e2e-api-rate-limit-config-check.log) 输出 1000。本轮不作为默认限流吞吐量验证。
- Combined log: [最终完整运行日志](rv-1-full-final-post-refactor-rate-limit-override.log)；[JUnit](../../../tests/playwright-e2e/test-results/2026-11-13T06-38-59/junit.xml)；[run metadata](rv-1-full-final.metadata.md)。

### RV 与共用 gate 证据

| RV / Gate | 结果 | 证据 |
|---|---|---|
| rv-1 管理员真实登录与密码回归 | 本轮真实浏览器流程通过；同一 issuer/subject 改变 IdP 邮箱后仍返回同一 admin user_id | 本节截图、录屏、JUnit 与最终完整运行日志 |
| rv-2 首绑、失败、重放、会话和账号冲突 | main 报告 PostgreSQL 48 passed、MySQL 48 passed 的联合 API 回归 | [PG API](oidc-registration-admin-org-api-pg-current-final.log)、[MySQL API](oidc-registration-admin-org-api-mysql-current-final.log) |
| rv-3 migration | PostgreSQL 和 MySQL roundtrip 日志已生成 | [PostgreSQL migration](rv-3-migration-postgresql-roundtrip.log)、[MySQL migration](rv-3-migration-mysql-roundtrip.log) |
| rv-4 配置与文档 | 配置加载测试通过；mkdocs strict 构建退出 0 | [配置测试](settings-config-test-after-env-isolation.log)、本次 uv run mkdocs build --strict exit 0 |
| rv-5 管理端登录 UI 单测 | 4 个相关前端测试文件 18 passed；ConfirmDialog/admin-filter focused tests 10 passed；Admin typecheck/build exit 0 | [前端 targeted tests](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/frontend-admin-auth-registration-tests-after-jscpd-markers.log)、[ConfirmDialog/admin-filter](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/admin-confirm-dialog-tests.log)、[typecheck](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/frontend-admin-typecheck-after-jscpd-markers.log)、[build](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/frontend-admin-build-after-jscpd-markers.log) |
| rv-6 独立 zata-oidc 包与消费者边界 | 包测试 17 passed；wheel/sdist 外部 consumer 真实 RS256 成功与无效签名拒绝 1 passed；just copy、源码哈希对比、Docker current-tree hash/health 通过 | [包测试](package-tests-rv6-final.log)、[wheel/sdist SHA 与源匹配](package-release-artifacts-hashes-final.log)、[消费者协议测试](copy-project-wheel-protocol-test-final.log)、[copy 源哈希比较](copy-project-source-hashes-compare-final.log)、[Docker current-tree](docker-runtime-rv6-current-tree-final.log) |
| just lint --repo（含 reuse） | exit 0；jscpd、pylint duplicate、架构/规范检查通过；本地测试 626 passed / 1 skipped，包测试 17 passed，MkDocs strict 与末尾全文件 lint 通过 | [repo lint 日志](just-lint-repo-jscpd-ignored-pg-final.log) |
| `CI=1 just lint --full` | exit 0；删除的仅 lint 专用缓存标记，实际全文件 lint hooks 全部通过 | [强制全文件 lint](just-lint-full-ci-current-final.log)、[缓存标记处理记录](force-full-lint-marker-final.log) |
| `just test all` broad regression | 928 passed、6 skipped；这是最后单条并发测试替换之前的全量回归。该替换只改测试用例，未改生产源；最终替换用例另以 PostgreSQL 与 MySQL 各验证 1 passed | [完整回归](just-test-all-jscpd-ignored-current-final.log)、[PG 并发用例](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/org-last-platform-concurrency-pg-final.log)、[MySQL 并发用例](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/org-last-platform-concurrency-mysql-final.log)、[Ruff/format/diff check](../P1-FEAT-20261112-142923-organizations-and-two-tier-admins/org-last-platform-concurrency-ruff-final.log) |
| E2E source tree | test_tree 70c46a70b9f70bdbd1d3fdd8423d6793ea293af5；base HEAD 94b46529e93e7e5a1840d80a92511a94b77725ef | [最终完整运行日志](rv-1-full-final-post-refactor-rate-limit-override.log) |
| Final effective source identity | 最终 `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6`、`lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`；仅替换组织并发安全测试，详见备注 | [最终 source tree 指纹及差异](source-tree-identity-after-concurrency-test-final.log) |

最新 E2E 前保留了两次失败记录：一次是测试漏点管理员重新启用确认按钮；下一次命中默认共享回环 IP 限流，并有注册错误提示 selector 的严格匹配冲突。测试已补确认交互、30 秒 canonical API 等待上限及精确提示定位；本报告所引用的最终日志是上述修正后的 fresh 4/4 结果。早期 reuse 尝试的失败日志也保留；其后的 `just lint --repo` 和强制全文件 lint 均通过。不要把历史日志当作本轮通过证据。

<details>
<summary>历史失败截图（已定位并修复，不作为 PASS 证据）</summary>

**初轮管理员 OIDC 回调超时。** 本地图片说明：浏览器当时仍停在回环身份中心的测试登录表单，授权尚未完成；这张图记录超时现场，不证明 callback 或应用登录成功。

![历史失败现场：管理员 OIDC 尚停在本地身份中心表单](rv-1-playwright-admin-oidc-callback-timeout.png)

仓库根目录打开命令：`open tasks/evidence/P1-SECURITY-20261112-134527-admin-oidc-sign-in/rv-1-playwright-admin-oidc-callback-timeout.png`
</details>
