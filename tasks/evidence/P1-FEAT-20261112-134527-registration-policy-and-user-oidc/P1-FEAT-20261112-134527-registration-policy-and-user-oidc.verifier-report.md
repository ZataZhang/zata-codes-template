# 独立验证报告：注册策略与普通用户 OIDC

verdict: PASS
- round: **1**
- reviewer: `/root/oidc_verifier`，独立只读代码与证据审查。
- 需求源：同名 PRD §1、§7.6、§7.7、§9、FR-1–FR-9；同时核对已确认的同邮箱不自动关联决策。

## 发现与处理

**BLOCKER：0 项未解决。NON-BLOCKING：0 项未解决。SECURITY：0 项。**

本轮发现的非法域名反馈错误已修复：页面按 FastAPI 实际 `{detail:{code,invalid_domains}}` 解包，英文/中文回归通过。`both` 注册页已按 PRD §7.7 补齐密码表单下方的企业账号入口，并由真实 E2E 截图验证。未通过删除需求或修改测试 oracle 缩小范围。

## 逐 RV 结论

- **rv-1 PASS（R2 / user flow）**：最终 fresh suite `2026-11-13T06-38-59` 为 4 tests / 0 failures。策略由管理 UI 保存，前台新空上下文读取 OIDC-only 状态；实际按钮经过 `/api/auth/oidc/start`、RS256 issuer、callback、账户创建及 Redis session 后到 dashboard。另有已验证外域邮箱失败路径，页面显示错误、`/api/auth/me` 401 且无 session Cookie。已查看真实设置、OIDC-only、both 页面与 design-intent 目标的层级，未把目标静态图称为生产验证。
- **rv-2 PASS（R3 / integration）**：真实 `/auth/register` 先创建密码账户，随后同邮箱 OIDC 回调跳回 `account_exists`、不签 Cookie；新数据库会话确认 OIDC 列和密码哈希未改，原密码仍能经登录入口使用。两库联合 API 日志各 48 passed，包含 `test_user_oidc_login.py`。没有直接构造账户解析结果或替换核心登录服务。
- **rv-3 PASS（R2 / integration）**：真实管理 PUT 保存策略、公开状态只含 registration_mode，3 模式×2 渠道×白名单内外的 HTTP 矩阵与存储故障/坏 JSON 的 fail-closed 通过；严格 schema 坏值由服务测试覆盖。只有缺键开放默认值，已绑定分支在读取注册策略之前返回，故新注册策略不阻断既有身份登录。测试包含真实数据库表不可读的场景，恢复后重新读取；非管理员不能读取白名单。新请求和独立数据库会话检查后置状态。
- **rv-4 PASS（R2 / migration）**：两库 `migration-roundtrip-{pg,mysql}-final.log` 实际从 head 降至管理员 OIDC 基线再升级，旧账户标识/行数不变，system_settings/public OIDC 列恢复。不是以 metadata.create_all 替代迁移。管理员单迁移的往返是另一上游 RV，不将其单独冒充本迁移证据。
- **rv-5 PASS（R1 / frontend）**：相关前端 4 files / 18 passed，包含注册设置英文/中文非法条目提示；保存反馈另由真实管理 UI 成功请求及截图覆盖。admin/public typecheck/build 均通过。Python 928 项只计总回归，不作为该前端 oracle 的证据。

R2/R3 五项核对：策略/会话/状态来自真实 UI 或 HTTP producer；经过 API、数据库提交、callback 与消费者边界；未用直接注入 RegistrationPolicy 或写业务库跳过被测动作；新的 HTTP/浏览器/SQL 消费者观察结果；最后相关实现重构后重采了 API 与 E2E。明确仅替换 IdP，本报告不宣称 live Keycloak 互通。

## 验证与树身份

- 独立重算最终 `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6`、`lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`。
- 共用最终证据位于管理员 OIDC evidence 目录：`oidc-registration-admin-org-api-{pg,mysql}-current-final.log` 各 48 passed；`just-test-all-current-final.log` 928 passed / 6 skipped；实际 repo lint 和清除 warm marker 后的 CI full lint 均通过；严格文档构建通过。
- 全套 928 项早于最后一个真实认证并发测试增强；该变化仅在测试，随后两库定向各 1 passed。E2E 后的生产差异仅审过范围的 jscpd 注释，未改变行为，故未无理由要求整套重跑。
- 最终 E2E 明确使用已有的 API 限流配置 1000/min 避免多上下文共用回环 IP 聚合；middleware 仍开启，默认 120/min 未改。本证据不证明默认阈值吞吐量。
- 历史失败、429 和 selector 修复均保留；结论只依据最后成功日志。无真实凭据暴露 finding。

## 评审总结

🔴 严重 0；🟠 高 0；🟡 中 0；🔵 低 0。

需求、代码、验证与文档：通过。结论：**PASS**。页面与流程的人工接受仍由用户完成，本报告未勾选 Human-Confirmed，也未改动 PRD。
