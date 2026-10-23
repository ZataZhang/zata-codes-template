# 健康探针

用于定位后端存活、就绪探针的修改。生产启动链是
`src/backend/main.py::create_app` → `src/backend/composition/app_factory.py::create_app`
→ `include_router(health_router)` → `src/backend/api/health_router.py`。
主入口中的历史兼容包装最终委托 composition root，不是另一套健康检查实现。

## 当前行为

| GET 路径 | 处理函数 | 响应 |
|---|---|---|
| `/health` | `health` | 200，`{"status":"ok"}` |
| `/ready` | `ready` | 200，`{"status":"ok"}` |
| `/live` | `live` | 200，`{"status":"ok"}` |

三个函数都直接返回固定字典，由 FastAPI 序列化；Request 参数未使用，没有认证依赖、
存储读写或 PostgreSQL / Redis 探测，也没有依赖失败返回 503 的分支。
`ready` docstring 中的依赖检查是后续可扩展方向，不能视为已实现。
路由在 composition root 中无条件注册，`observability.enabled` 只控制后面的可观测性中间件
及 metrics 注册，不关闭这些探针。HTTP 成功只证明相应请求可被响应，不证明业务依赖可用。

旧页列出的 legacy_health、check_dependencies 和 legacy 测试均不应作为修改入口；
当前生产注册链指向上述 router，本页已移除失效定位。

## 修改定位与验证

| 要改什么 | 去哪里 | 影响及验证 |
|---|---|---|
| URL、响应字段或状态码 | `health_router.py` 的装饰器与 `health/ready/live` | 同步探针调用方和 [可观测性指南](../guides/observability.md)，检查三个路径的 HTTP 契约 |
| 就绪依赖判断 | `health_router.py::ready`（当前仅固定响应） | 新增行为需要明确失败、超时语义；保留存活检查的独立性，补充成功和依赖异常测试 |
| 是否注册探针 | `app_factory.py::create_app` 的 router 循环 | 需通过真实应用核对启用/关闭 observability 时路由可用性 |

`tests/test_health.py::test_health_endpoints_return_ok` 把实际 router 注册到临时 FastAPI，
以 ASGITransport 检查三个端点的 200 与 JSON。建议命令：
`uv run pytest tests/test_health.py`。它覆盖 router 契约，不覆盖生产初始化及部署代理。
后续真实入口验证可在已有后端环境对 `/health`、`/ready`、`/live` 分别执行
`curl -i http://localhost:8000/health`（替换对应路径），核对响应；本次没有启动服务或运行这些测试。

维护约定见 [测试规范](../ai-standards/testing.md)，部署操作见
[可观测性指南](../guides/observability.md)。部署环境与外部探针设置未确认。
