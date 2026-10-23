# 健康探针

生产入口 `src/backend/composition/app_factory.py::create_app` 无条件注册
`src/backend/api/health_router.py::health_router`，不依赖 observability 开关。

| HTTP GET 路径 | 实现符号 | 当前结果 |
|---|---|---|
| `/health` | `health` | 200，`{"status":"ok"}` |
| `/readiness` | `ready` | 200，`{"status":"ok"}` |
| `/live` | `live` | 200，`{"status":"ok"}` |

请求由 FastAPI 匹配对应函数，函数直接返回固定字典，再序列化为 JSON；不读写存储，
不调用认证依赖，也不检查数据库或 Redis。readiness 只是基础实现，不能据此判定依赖健康。
`changes.patch` 将就绪 URL 从 `/ready` 改为 `/readiness`，Python 函数仍叫 `ready`；
当前 router 未保留旧 URL 别名。未确认外部部署客户端是否已经迁移。

| 修改需求 | 定位 | 影响与验证 |
|---|---|---|
| 更改 URL / 返回结构 | `health_router.py` 的装饰器及 `health/ready/live` | 同步调用方、[可观测性指南](../guides/observability.md)、[探针客户端](../guides/probe-client.md) 和测试 |
| 增加依赖健康检查 | `health_router.py::ready` | 当前无此能力；应明确失败状态与超时，避免把存活探针绑定依赖 |
| 调整注册条件 | `app_factory.py::create_app` | 与 `observability.enabled` 的区别需回归真实应用注册 |

验证计划：`uv run pytest tests/test_health.py`。现有 `test_health_endpoints_return_ok`
仍请求 `/ready`，与当前源码不符，预计其 200 断言失败；本次仅改文档，不修改测试。
后续行为维护应把用例改到新路径并增加旧路径不再提供的断言。
真实环境可分别 `curl -i http://localhost:8000/readiness`、请求 `/health` 与 `/live`，
检查状态码及 JSON，并核对旧 `/ready` 不再由此 router 注册。
测试当前只把 router 注册到临时 FastAPI，不能代替生产 composition root 验证。
命令为待执行计划，本次未运行产品测试或启动服务。

操作背景见 [可观测性](../guides/observability.md)，验证约定见 [测试规范](../ai-standards/testing.md)。
