# 服务探针

用于区分 HTTP 进程可响应与就绪入口；当前三条探针都直接返回固定状态，没有依赖健康检查。

## 入口与主流程

生产入口为 `src/backend/main.py` 的 `app = create_app()`；其 `create_app()` 委托
`src/backend/composition/app_factory.py:create_app()`，后者在路由列表中无前缀注册
`src/backend/api/health_router.py:health_router`。测试中的额外注册不是生产注册的唯一来源。

| HTTP 入口 | 处理函数 | 当前结果 |
|---|---|---|
| `GET /health` | `health()` | 200，JSON `{"status": "ok"}` |
| `GET /ready` | `ready()` | 200，同上 |
| `GET /live` | `live()` | 200，同上；存活探针别名 |

请求经生产应用已配置的中间件到对应函数，再由 FastAPI 序列化字典。
路由和三个函数没有登录依赖，`_request` 未被读取，也没有数据库查询、Redis 调用或持久化写入。
`app_factory.py:create_app()` 的中间件注册是请求上下文与指标，不是全局登录校验。
`ready()` 的 docstring 中数据库检查属于后续扩展意图，当前并未实现。

应用装配与探针请求要分开看：`app_factory.py:create_app()` 会调用
`composition/bootstrap.py:run_migrations()` 执行 Alembic upgrade，并装配认证组件和按配置种子用户；
`composition/auth_wiring.py:build_auth_components()` 使用 `config.redis.url` 构造 Redis 客户端。
因此探针返回 OK 不证明数据库或 Redis 健康，也不能据此声称应用启动不需要外部依赖。
探针本身没有独立配置键。

## 修改定位与验证

| 要改什么 | 去哪里 | 影响与验证 |
|---|---|---|
| 路径或响应负载 | `api/health_router.py` 的路由装饰器与三个处理函数 | 同步调用方、[可观测性指南](../guides/observability.md)和 `tests/test_health.py` 的请求/断言 |
| 生产注册、前缀或启动装配 | `composition/app_factory.py:create_app()`；`main.py:create_app()` 是兼容入口 | 检查生产应用路由，避免测试额外注册掩盖漏注册；再通过真实 HTTP 入口验证 |
| 增加依赖就绪检查 | `api/health_router.py:ready()`，依赖契约按[架构权威说明](../architecture/system-design.md)确定 | 需定义失败状态及依赖故障断言；现有固定 OK 测试不能证明故障处理 |

`tests/test_health.py:test_health_endpoints_return_ok()` 导入 `backend.main.create_app`，创建生产工厂应用，
又调用 `include_router(health_router)`；通过 `ASGITransport` 发出无登录凭据的三个 GET，断言 200 与固定 JSON。
这是使用生产工厂的进程内 HTTP 检查，额外注册使其不能单独证明生产注册完整性。
没有显式管理 lifespan，也没有声明 Redis 替身或数据库替身；导入 `main` 还会创建模块级应用。
`tests/conftest.py:_disable_otlp_trace_export` 只关闭 OTLP，`_realdb_residue_sentinel` 仅对 realdb 标记生效，
不能把本测试描述成完全隔离外部依赖或已经验证数据库可用性。

具备项目依赖、测试数据库及所需配置后，可先运行
`uv run pytest tests/test_health.py -q -n 0`；该命令本次未执行。
生产入口验证应在允许启动服务的环境，匿名请求 `/health`、`/ready`、`/live`，
逐项核对 200 与 JSON，而不是仅检查 curl 退出码；还应检查 OpenAPI/路由列表及实际调用方配置。
这些检查不证明外部网关、容器探针或负载均衡部署已切换，部署状态未确认。
文档构建使用 `uv run mkdocs build --strict`，依赖不可用时只做静态路径与引用核对。

相关：[功能索引](index.md)、[测试规范](../ai-standards/testing.md)、
[部署指南](../guides/deployment.md)。本次仅维护文档，未执行产品行为验证。
