# 验证计划：组织与平台/组织两级管理员

> 本计划在并行实现过程中按当前批准 PRD 补充核对。它记录验收映射，不声明验证已通过；实际结果、失败尝试和最终树绑定以 evidence-report 为准。

## 环境与证据边界

- PostgreSQL 与 MySQL 使用本任务专属测试库；浏览器流程使用另一专属 E2E 库，避免测试间互相重建表。
- OIDC 只替换身份中心：真实 RS256 签名；应用路由、账户策略、数据库、Redis、前端代理和 Cookie 保持真实。
- 通过与失败日志均保留；静态设计图来自 PRD §7.7，真实截图标注 real user flow，二者不混用。
- 生产边界或关键断言变更后重采相关证据；只有独立 verifier PASS 后才勾选有证据的执行项，人工验收项保持开放。

## rv-1

- 行为：平台管理员建组织与无密码组织管理员，后者经企业账号首绑登录，用户页只显示本组织用户
- 层级：e2e；风险：R3；审阅者：human
- 真实入口：`ADMIN_OIDC_* 指向 Playwright 本地身份中心替身后 just e2e tests/admin/organizations-and-admins.admin.spec.ts`
- 通过标准：管理员页创建 org@example.com（示例组织、无密码）成功；新浏览器上下文企业账号登录后进入后台，侧边栏无组织/管理员入口；用户页仅见已被平台管理员移入示例组织的用户，不见默认组织用户
- 替身边界：只替换身份中心本身（上游 PRD 的真实 RS256 替身）；管理端页面、admin API、数据库、Redis、Vite 代理、OIDC 登录链均为真实
- 必须穿过的边界：管理员页表单 -> /api 代理 -> POST /admin/admins -> admin_user 写入 -> 新上下文 /admin/auth/oidc/start -> 替身 -> callback 首绑 -> 用户页 GET /admin/users 组织过滤
- 禁止旁路：直接写库建管理员、手工设置会话 Cookie、直接调用目录用例、跳过 /api 代理
- 新鲜状态复核：新浏览器上下文以组织管理员会话重开用户页；新数据库会话查询该管理员 role=org、organization_id 正确、oidc_subject 非空
- 负控：把替身声明的 email_verified 设为 false 运行同一用例
- 人审呈递：tasks/evidence/<prd-stem>/rv-1-admin-create.png、rv-1-org-admin-users.png 与 rv-1-org-admin-sign-in.webm；自查：创建对话框类型为组织管理员且密码留空，组织管理员用户页只有示例组织用户
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-142923-organizations-and-two-tier-admins.evidence-report.md`。

## rv-2

- 行为：组织管理员越权全部失败；管理员启停保护与解绑规则生效；管理操作留审计日志
- 层级：integration；风险：R3；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_admin_permissions.py tests/backend/test_admin_directory.py`
- 通过标准：组织管理员访问组织/管理员/注册设置/运行轨迹接口 403；跨组织用户读取与启停 404 且响应无目标信息；禁用自己与禁用最后一个启用平台管理员 400；禁用另一管理员后其密码和 OIDC 新登录均拒绝，密码/OIDC 两种既有 admin 会话的下一次 API 请求均 401；重新启用后按正常规则恢复；未开 OIDC 创建无密码管理员 400；解绑后原身份 A 在仍满足邮箱首绑条件时可重新绑定；A 未绑定时同邮箱身份 B 也可首绑，先成功者占用绑定，之后的身份为 identity_conflict；停用 IdP 中的 A 后拒绝 A；审计日志含操作者/动作/目标且无密码、令牌原文
- 替身边界：身份中心由 ControlledOidcIssuer 提供；FastAPI 应用、路由、权限依赖、目录用例、仓库与测试数据库为真实；Redis 按 tests/backend/conftest.py 约定
- 必须穿过的边界：登录 Cookie -> 权限依赖 -> 路由 -> 目录用例 -> 仓库事务 -> 新请求读取
- 禁止旁路：手工伪造 principal、直接调用用例、直接写库造管理员、从请求体采信组织 ID
- 新鲜状态复核：每个拒绝用例后用新数据库会话读取目标行确认未变；解绑后用新 TestClient 走完整 OIDC 回调
- 负控：在测试装配处用 dependency_overrides 把 get_current_platform_admin 替换为返回组织管理员 principal，重跑 403 矩阵
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-142923-organizations-and-two-tier-admins.evidence-report.md`。

## rv-3

- 行为：组织停用即时阻断登录与会话，启用恢复；新注册用户归默认组织
- 层级：integration；风险：R2；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_org_active_sessions.py`
- 通过标准：停用后：该组织普通用户密码登录 400 提示组织已停用、已有会话下次请求 401；组织管理员密码与 OIDC 登录均拒（organization_inactive）；平台管理员不受影响；重新启用后全部恢复；新注册 public 用户 organization_id=default
- 替身边界：身份中心为替身；其余真实
- 必须穿过的边界：POST /admin/organizations/{id}/disable -> 登录 / 会话解析检查点 -> 新请求 401 -> enable -> 恢复
- 禁止旁路：直接写库改组织状态、直接调用 AuthService
- 新鲜状态复核：停用后用新 TestClient 分别发登录与携带旧会话的请求；启用后再读
- 负控：not needed — 同一账号先登录成功再 401 是具体状态码对比，检查点缺失时必然不同
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-142923-organizations-and-two-tier-admins.evidence-report.md`。

## rv-4

- 行为：迁移可升可降，存量用户与管理员回填对账一致，角色 CHECK 约束生效
- 层级：integration；风险：R2；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_organizations_migration.py`
- 通过标准：upgrade 后 organization 表存在且含默认组织；存量 public_user 全部 organization_id=default；存量 admin_user 全部 role=platform 且 organization_id 为空；role=org 无组织或 platform 有组织违反 CHECK；downgrade 后结构回到上一版本；升降过程用户与管理员行数、标识不变
- 替身边界：真实 Alembic 与测试数据库（沿用 tests/realdb_test_support.py 与 tests/guards/test_migrations.py 约定，覆盖受支持数据库）
- 必须穿过的边界：alembic upgrade head -> downgrade -1 -> upgrade head
- 禁止旁路：Base.metadata.create_all 代替迁移
- 新鲜状态复核：每一步后新连接 inspect 表结构、计数并核对归属
- 负控：not needed — 列 / 表存在与否与归属值为具体值对比
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-142923-organizations-and-two-tier-admins.evidence-report.md`。

## rv-5

- 行为：种子应急：重启同步密码、恢复启用并确保平台角色
- 层级：integration；风险：R1；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_admin_directory.py -k seed`
- 通过标准：种子账号被禁用后，重新执行 seed_admin_user 即恢复启用、role=platform、密码更新为新值；新建种子写 platform 与邮箱
- 替身边界：真实种子函数与测试数据库
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-142923-organizations-and-two-tier-admins.evidence-report.md`。

## rv-6

- 行为：管理端导航与路由按角色显隐，新建管理员表单校验
- 层级：unit；风险：R1；审阅者：verifier
- 真实入口：`cd frontend-admin && pnpm test -- admins organizations sidebar-data`
- 通过标准：org 角色导航无组织/管理员/运行轨迹，platform 角色全有；新建表单 org 类型必选组织、密码留空显示提示；默认组织行无停用按钮
- 替身边界：mock API 客户端与 auth-store 角色
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-142923-organizations-and-two-tier-admins.evidence-report.md`。
