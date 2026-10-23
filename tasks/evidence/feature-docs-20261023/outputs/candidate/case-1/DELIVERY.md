# 交付说明

已沿现有 `docs/architecture/authentication.md` 增补认证功能代码地图，保留现有体系，未新建第二套功能说明。补充生产注册链、双前端调用链、认证/注册/会话解析数据流、域隔离、配置与 Cookie 寿命差异、修改影响和测试定位；纠正“禁用即删除 Redis 记录”的说明。`docs/ai-standards/index.md` 新增阅读入口，站点已有认证导航，未重复新增。

修改文件：`docs/architecture/authentication.md`、`docs/ai-standards/index.md`、`DELIVERY.md`。
依据：两个认证 router、dependencies、AuthService、auth_wiring、app_factory、RedisSessionStore、两端 auth API/client、admin 登录表单与 store。重要约束：注册只开放 public；Cookie / Redis 前缀 / 用户模型各自隔离；禁用靠解析时回查用户；Redis 窗口配置不自动改变 router 固定 Cookie Max-Age；rememberMe 未传后端。

实际检查：2 篇修改文档 UTF-8 可读，15 个本地链接目标存在，无行末空白。`python3 -m mkdocs build` 失败：`No module named mkdocs`，未安装依赖。尝试 `git diff --check` 失败：快照不是 Git 仓库，已改用静态空白核对。未跑产品测试、未启动服务；页面中的 pytest / just / E2E 命令是后续验证计划，不是通过证据。部署 Cookie 覆盖和真实 Redis/代理行为未确认。

调查与初稿计时：2026-10-23 03:56:29 至 03:57:34 UTC，65 秒。随后补做构建尝试与最终静态核对，最终核对时间 03:58:52 UTC（与其他 case 交错，不把整段算作独占工时）。实际 token 用量：不可用。
