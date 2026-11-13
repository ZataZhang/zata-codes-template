# 独立验证报告：组织与两级管理员

verdict: PASS
- round: **1**
- reviewer: `/root/oidc_verifier`，独立只读审查；仅写本报告，未修改实现、测试或 PRD，未触碰验证数据库。
- 需求源：同名 PRD §1、§7.6、§7.7、§9、FR-1–FR-8，以及用户确认的“解绑只清关联、允许符合原规则的身份重新首绑”。

## 发现与处理

**BLOCKER：0 项未解决。NON-BLOCKING：0 项未解决。SECURITY：0 项。**

本轮明确问题已处理：旧管理员 email=null 搜索崩溃；组织用户启停的先读范围、后无范围写入竞态；PostgreSQL eager LEFT JOIN 上无目标限定的 FOR UPDATE；解绑按钮缺翻译 key。现已分别采用 nullable 类型/安全过滤、写入时组织 WHERE、只锁管理员表和双语翻译。确认框复用现成组件后无业务语义变化。

逐 rv 核对时还指出最后平台管理员用例伪造 principal 违反 oracle。现已替换为真实两个平台管理员密码登录、独立 cookie/client 的并发互禁；测试只在调用原始 resolve_session 得到真实 principal 后通过 Barrier 控制调度，没有生产钩子或伪造认证结果。

## 逐 RV 结论

- **rv-1 PASS（R3 / user flow）**：最终 suite `2026-11-13T06-38-59` 4 tests / 0 failures；真实 UI 创建组织、注册用户、转组与创建无密码/有密码组织管理员。空上下文 OIDC/密码登录后只见本组织成员和允许的导航；解绑确认明确不撤销 IdP 身份，原身份可再绑；本地禁用后两种已有 session 下一请求 401，重新启用后新空上下文登录恢复。直接查看了 PRD 目标图、管理员创建及组织用户真实截图，确认其角色/组织/密码留空层级；不是组件 preview。
- **rv-2 PASS（R3 / integration）**：两库联合 API 各 48 passed；`test_organization_security.py` 使用真实登录与创建接口验证平台-only 403、跨组/不存在用户同形 404、拒绝后 fresh SQL 状态不变、未配 OIDC 的无密码创建被拒、管理员禁用后两种新旧登录失效、审计安全信息；E2E 提供解绑/重绑/IdP 停用路径。组织写入 TOCTOU 回归两库各 1 passed。最终 `org-last-platform-concurrency-{pg,mysql}-final.log` 各 1 passed：两个真实会话通过权限边界后同时互禁，返回一 200 和一 400(last_platform_admin)，独立 SQL session 确认恰一启用平台管理员。原伪 principal case 不再作为最终依据。
- **rv-3 PASS（R2 / integration）**：真实组织 API 创建、停用和恢复，普通用户/组织管理员的 password/OIDC 新登录及四条既有 session 均经实际入口拒绝或恢复；平台管理员不受影响。新用户默认组织由真实注册/callback 后的数据库读取证明。旧 PRD 示例写 password 登录 400，而沿用认证入口实际为 401；该差异不放宽安全结果，拒绝与组织原因已明确断言。
- **rv-4 PASS（R2 / migration）**：PG/MySQL 实际升级/降级/再升级，账户标识和行数保持、默认组织回填、角色和外键结构恢复；`test_organization_security.py` 在两种真实库验证不合法角色/组织组合违反命名 CHECK。MySQL 错误 3819 使用 OperationalError 分类，与未拒绝写入区分；不是以泛化异常当通过。
- **rv-5 PASS（R1 / startup integration）**：通过真实平台 API 创建并禁用组织管理员，随后实际 create_app 启动种子同步，独立数据库读取确认启用、platform、organization_id=None、规范化邮箱及新密码；新客户端真实登录恢复。与种子创建测试共同覆盖应急语义。
- **rv-6 PASS（R1 / frontend）**：相关前端 4 files / 18 passed、focused ConfirmDialog/admin-filter 10 passed，typecheck/build 通过；真实 E2E 补充组织角色导航、平台路由重定向、组织必选和无密码表单。默认组织不允许停用由 UI 代码和真实 API 拒绝回归共同核对。未将 Python 总测试数冒充前端单测。

R2/R3 oracle 五项核对：关键组织/admin/user ID 与 Cookie 来自真实 producer；运行跨越权限依赖、目录、仓库提交及新消费者；未用伪 principal/直接写业务状态绕过被测动作；拒绝和写入结果有独立 SQL/HTTP/新上下文观察；最终相关代码重构后双库 API 与 E2E 重采。约束测试直接写非法行是约束自己的被测入口，非绕过用户工作流。

## 最终验证与可追溯性

独立重算最终 `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6`、`lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`，与管理员目录中的 `source-tree-identity-after-concurrency-test-final.log` 一致。

- `just test all` 实际 928 passed / 6 skipped，早于最后一个测试增强；新并发 case 随后仅定向两库各 1 passed，无生产行为改变。该时间差已披露，不谎称 928 在新 case 后运行。
- 实际 `just lint --repo` 与移除 lint warm marker 后 `CI=1 just lint --full` 均通过，含严格文档构建。最终 jscpd/reuse 通过，之前失败保留。
- 独立审过局部 jscpd ignore：仅 imports、既有 JSX 展示样板与 Vitest mock；没有遮账户策略、权限、事务、回调或 assertion，JSX 注释不渲染。
- E2E 明确仅替换 IdP，并使用专属数据库/Redis；测试已有 API 限流配置为 1000/min，默认 120/min 未改，不扩大证据到默认吞吐能力。历史限流与测试调度失败不作产品通过证据。

## 评审总结

🔴 严重 0；🟠 高 0；🟡 中 0；🔵 低 0。

需求、代码、验证与文档：通过。结论：**PASS**。Human-Confirmed 仍待用户决定；独立报告不等于人工接受，不负责 PRD 归档。
