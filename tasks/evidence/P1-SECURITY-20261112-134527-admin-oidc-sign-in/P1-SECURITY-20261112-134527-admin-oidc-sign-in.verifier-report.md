# 独立验证报告：管理员 OIDC 登录

verdict: PASS
- round: **1**（中途待命不计新轮次）
- reviewer: `/root/oidc_verifier`，独立只读审查；未修改实现、测试或 PRD，未运行会碰验证数据库的测试。
- 需求源：同名 PRD §1、§7.6、§7.7、§9、FR-1–FR-9；审查范围包含 unstaged、staged、untracked、调用方、配置、包、部署及文档。

## 发现与处理

**BLOCKER：0 项未解决。NON-BLOCKING：0 项未解决。SECURITY：0 项。**

首轮审查及真实入口发现的问题已修复并核对：数值 `sso_error=1` 的路由解析、可空管理员邮箱搜索、注册策略错误响应解包、组织状态写入的范围竞态、PostgreSQL nullable join 的锁定对象。协议回调与仓库公共逻辑提取后重新采集了双库 API 和浏览器证据。解绑按钮缺少翻译 key 的非阻塞文案问题也已修复。

## 逐 RV 结论

- **rv-1 PASS（R3 / user flow）**：最终串行运行 `2026-11-13T06-38-59` 的 JUnit 为 4 tests / 0 failures / 0 skipped。实际点击管理端按钮，经过 canonical `/api/admin/auth/oidc/start`、本地 RS256 issuer、callback、数据库绑定和 Redis session；新上下文读取 `/api/admin/auth/me`，同 issuer/subject 改邮箱重登仍返回同一账户。已直接查看目标图及真实登录页截图，表单与企业入口层级相符。这里只验证自动证据，不代替人工视觉接受。
- **rv-2 PASS（R3 / integration）**：`oidc-registration-admin-org-api-{pg,mysql}-current-final.log` 各 48 passed；结合 `test_admin_oidc_login.py`、协议包测试与最终负向浏览器路径核对签名、issuer/audience、exp、nonce、PKCE、未验证邮箱、未知/冲突身份、禁用、缺 Cookie、state 和重放。state/nonce 来自 start；callback 经真实路由与宿主服务；拒绝后检查 session 与独立数据库读取。未使用替换登录用例的旁路。协议包只承担协议能力；宿主维护一次性事务、绑定与现有会话。
- **rv-3 PASS（R2 / migration）**：`rv-3-migration-{postgresql,mysql}-roundtrip.log` 实际执行前版本→管理员 OIDC→降级→升级，验证旧管理员保留；MySQL 实列为 VARBINARY(2048/1020)。迁移和 ORM 精确身份类型相符，组合索引最大 3068 字节；大小写与尾随字符拒绝混同的 API 测试两库通过。
- **rv-4 PASS（R1 / configuration）**：真实应用装配测试覆盖默认开关开启但参数缺失、显式关闭与密码登录兼容；配置读取测试及 Docker 启动证明未配置 IdP 不阻断服务。
- **rv-5 PASS（R1 / frontend）**：`frontend-admin-auth-registration-targeted-tests-current-final.log` 为 4 files / 18 passed，含登录入口显隐及失败状态；实际 E2E 另覆盖数值错误 query 的真实路由。前端 typecheck/build 通过。未用 Python 928 项替代前端证据。
- **rv-6 PASS（R1 / distribution）**：包测试 17 passed；非 editable wheel 的隔离消费者通过真实 HTTP discovery/token/JWKS 验证 RS256 成功与伪签名拒绝（1 passed）；wheel/sdist 交付、实际 `just copy`、复制后源码/包比对和 Docker startup/health 200 均有日志。Docker 中 `zata_oidc` 来自 site-packages，callback/repository 的镜像 SHA 与源一致。复制项目的根 manifest 因项目名替换而哈希不同不等于依赖遗漏；协议包源码一致。

对 R2/R3 oracle 的五项核对：关键值来自真实 start/UI/迁移前行；所列运行边界实际经过；没有以直接写业务状态或替换核心用例取得通过；新的请求/上下文/数据库会话观察后置状态；证据与最终相关实现匹配。身份中心本身是明确声明的替身，不宣称外部 Keycloak live 验证。

## 最终树与验证状态

独立执行仓库 `quality_effective_tree` 得到最终 `test_tree=8e792c937139e42d97ba9ad5f38e2e364982b8b6`、`lint_tree=6ce9aaf917345a5d3d8cffa789ae3688ffe72c88`，与 `source-tree-identity-after-concurrency-test-final.log` 相同。

- `just test all`：928 passed / 6 skipped；发生于最后一个测试补强前。随后仅将最后平台管理员保护用例改为真实认证并发互禁，两库各 1 passed；没有生产行为变更。
- `just lint --repo`：实际执行通过，见 `just-lint-repo-jscpd-ignored-pg-final.log`；含 626 passed / 1 skipped、包 17 passed、严格文档构建及全文件检查。
- `CI=1 just lint --full`：清除 lint warm marker 后实际执行通过，见 `just-lint-full-ci-current-final.log`，不是仅凭缓存标记。
- 最终 jscpd/reuse 检查通过。此前 exit 1 保留为历史；实际认证/仓库/Dialog 重复逻辑已提取。独立复核的局部 ignore 只覆盖 imports、既有 JSX 样板和 Vitest mock 装配，TSX 使用不渲染的 JSX 注释；无权限、事务、校验或断言被屏蔽。
- 最终 E2E 后的生产文本差异仅上述注释；最后变化是测试加强。因此相关真实入口证据仍有效，未将旧失败日志当作通过。

## 评审总结

🔴 严重 0；🟠 高 0；🟡 中 0；🔵 低 0。

需求、代码、验证与文档：通过。结论：**PASS**。Human-Confirmed 项由用户判断，本报告不代表人工接受，不自行归档 PRD。
