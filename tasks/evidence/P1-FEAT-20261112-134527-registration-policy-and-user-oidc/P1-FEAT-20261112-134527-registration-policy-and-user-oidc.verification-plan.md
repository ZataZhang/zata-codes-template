# 验证计划：注册策略与普通用户企业账号（OIDC）登录

> 本计划在并行实现过程中按当前批准 PRD 补充核对。它记录验收映射，不声明验证已通过；实际结果、失败尝试和最终树绑定以 evidence-report 为准。

## 环境与证据边界

- PostgreSQL 与 MySQL 使用本任务专属测试库；浏览器流程使用另一专属 E2E 库，避免测试间互相重建表。
- OIDC 只替换身份中心：真实 RS256 签名；应用路由、账户策略、数据库、Redis、前端代理和 Cookie 保持真实。
- 通过与失败日志均保留；静态设计图来自 PRD §7.7，真实截图标注 real user flow，二者不混用。
- 生产边界或关键断言变更后重采相关证据；只有独立 verifier PASS 后才勾选有证据的执行项，人工验收项保持开放。

## rv-1

- 行为：管理员改注册策略后前台注册页随之变化；前台企业账号首次登录按策略自动开户并进入应用
- 层级：e2e；风险：R2；审阅者：human
- 真实入口：`导出 USER_OIDC_* 指向 Playwright 本地身份中心替身后 just e2e tests/workflows/registration-policy-and-user-oidc.admin.spec.ts`
- 通过标准：保存“仅企业账号可注册 + example.com”后，前台 /register 显示仅企业账号提示且无密码表单；new@example.com 企业账号登录后落在 /app/dashboard，/api/auth/me 返回该用户
- 替身边界：只替换身份中心；管理端页面、admin API、数据库、Redis、Next rewrite、前台页面均为真实
- 必须穿过的边界：管理端表单 -> /api 代理 -> PUT /admin/settings/registration-policy -> system_settings 提交 -> 前台 /register -> GET /auth/registration-status；前台按钮 -> /auth/oidc/start -> 替身 -> /auth/oidc/callback -> public_user 建号 -> Redis 会话
- 禁止旁路：直接写 system_settings、直接调用服务对象、手工设置会话 Cookie
- 新鲜状态复核：新的浏览器上下文打开 /register；新的数据库会话查询 new@example.com 存在且 oidc_subject 非空
- 人审呈递：tasks/evidence/<prd-stem>/rv-1-registration-settings.png、rv-1-register-oidc-only.png、rv-1-user-oidc-sign-in.webm；自查：设置页选中“仅企业账号可注册”且域名为 example.com，注册页无密码输入框
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-134527-registration-policy-and-user-oidc.evidence-report.md`。

## rv-2

- 行为：本地已有同邮箱密码账号时按 §2 决策处理，且不能被接管
- 层级：integration；风险：R3；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_user_oidc_login.py -k existing_email`
- 通过标准：回调 302 到 /login?sso_error=account_exists、无会话 Cookie、原账号 oidc 列为空且原密码仍可登录；不得自动关联或修改原账号凭据与数据
- 替身边界：身份中心为 ControlledOidcIssuer；应用、路由、服务、仓库、数据库为真实
- 必须穿过的边界：POST /auth/register -> /auth/oidc/start -> /auth/oidc/callback -> 仓库 -> POST /auth/login
- 禁止旁路：直接插库造账号、直接调用 OidcLoginService
- 新鲜状态复核：新数据库会话读取该账号 oidc 列与 password_hash 是否变化；新 TestClient 用原密码登录
- 负控：在 tests/ 下的仓库替身中让“按邮箱查找”恒返回 None，重跑
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-134527-registration-policy-and-user-oidc.evidence-report.md`。

## rv-3

- 行为：策略读写仅管理员可用，公开状态不含白名单，保存后两个注册入口即时受控
- 层级：integration；风险：R2；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_registration_policy_api.py tests/backend/test_user_oidc_login.py -k policy`
- 通过标准：无会话 / public 会话读写返回 401；非法域名 422 指出该项；/auth/registration-status 响应键集合仅为 {registration_mode}；缺少策略记录时密码注册按 both + 空白名单运行；数据库读取异常、JSON 损坏或字段无效时，密码注册与公开注册状态接口返回 503 registration_policy_unavailable，OIDC 未绑定建号不创建用户且不签会话、记录同一 reason；策略恢复后正常；三种模式 × 两个渠道 × 白名单内外的组合结果与 §7.1 规则一致
- 替身边界：身份中心为替身；其余真实
- 必须穿过的边界：PUT /admin/settings/registration-policy -> system_settings -> 新请求 POST /auth/register 与 /auth/oidc/callback
- 禁止旁路：在测试中直接构造 RegistrationPolicy 注入服务
- 新鲜状态复核：保存后用新 TestClient 发注册请求，并用新数据库会话读取 system_settings
- 负控：not needed — 组合用例比较具体状态码（201 vs 400 / 登录成功 vs 失败），策略未生效时必然不同
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-134527-registration-policy-and-user-oidc.evidence-report.md`。

## rv-4

- 行为：迁移可升可降，既有 public 用户保留
- 层级：integration；风险：R2；审阅者：verifier
- 真实入口：`uv run pytest tests/backend/test_registration_policy_migration.py`
- 通过标准：upgrade 后 system_settings 存在、public_user 两列可空且组合唯一；downgrade 后结构回到上一版本；用户行数与邮箱不变
- 替身边界：真实 Alembic 与测试数据库
- 必须穿过的边界：alembic upgrade head -> downgrade -1 -> upgrade head
- 禁止旁路：Base.metadata.create_all 代替迁移
- 新鲜状态复核：每一步后新连接 inspect 并计数
- 负控：not needed — 表 / 列存在与否为具体值对比
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-134527-registration-policy-and-user-oidc.evidence-report.md`。

## rv-5

- 行为：管理端注册设置页的表单校验与保存反馈
- 层级：unit；风险：R1；审阅者：verifier
- 真实入口：`cd frontend-admin && pnpm test -- registration`
- 通过标准：加载显示当前策略；非法域名显示后端返回的错误；保存成功提示
- 替身边界：mock 注册策略 API 客户端
- 证据位置：本目录内对应 rv 日志、截图/录屏，汇总到 `P1-FEAT-20261112-134527-registration-policy-and-user-oidc.evidence-report.md`。
