# 健康探针

为部署与监控提供进程存活和基础就绪状态。当前入口是 `GET /health`、
`GET /service-ready`、`GET /live`，均直接返回 `{"status": "ok"}`，默认 HTTP 200。
`/service-ready` 替代旧 `/ready`，源码没有注册旧路径别名或重定向。

## 主流程与契约

1. `src/backend/main.py` 的 `create_app()` 委托
   `src/backend/composition/app_factory.py` 的 `create_app()` 完成生产装配。
   工厂先执行迁移、认证依赖构建和用户种子初始化，再注册 `health_router`。
2. 工厂无前缀、无附加依赖地注册 `src/backend/api/health_router.py` 的
   `health_router`；三个 handler 均无认证依赖，也不写业务数据。
3. `health()`、`ready()`、`live()` 直接返回固定状态。`ready()` 尚未检查数据库或
   Redis 等关键依赖；成功响应只能证明当前基础 handler 可响应，不能证明依赖健康。
4. 探针注册不受 `[observability].enabled` 控制；只有同时启用
   `enabled` 和 `metrics_enabled` 才装配指标中间件及 `/metrics`。

## 修改定位、影响与验证

| 要改什么 | 去哪里 | 影响什么、如何验证 |
|---|---|---|
| 路径或返回契约 | `health_router.py` 的装饰器及 `ready()` | 同步客户端、双语 README、可观测性指南及 OpenAPI 契约；从生产入口验证新路径 200 和固定 JSON、旧路径不再可用 |
| 注册或可观测性开关 | `composition/app_factory.py:create_app` | 检查生产装配和关闭监控时的三个探针；不要只验证独立 router |
| 探针是否计入 RED | `api/middleware/prometheus_metrics.py:_EXCLUDED_PATHS`、`_should_record()` | 当前列表仍是 `/ready`，因此启用指标时新 `/service-ready` 会被记录；修正代码后验证实际新路径不产生 counter/histogram 样本 |

`tests/test_health.py:test_health_endpoints_return_ok` 使用 `backend.main.create_app()`
生产工厂，再重复注册 router，经 ASGITransport 断言三端点状态和正文；它当前仍请求
`/ready`，需随契约更名同步。不是独立临时应用，也不是本次已运行的真实服务验证。
`tests/guards/test_openapi_schema.py` 的 `REQUIRED_PATHS` 仍要求旧路径，预期与当前
路由冲突；这是明确的契约更名，后续修改守卫需遵循[测试规范](../ai-standards/testing.md)。

`tests/test_metrics.py:test_middleware_ignores_excluded_paths` 仅创建临时 FastAPI、
装配指标中间件和 metrics router，没有注册健康 router；旧路径请求的“不产生指标”断言
不能证明新就绪端点被排除，需同时更新路径和覆盖边界。
以上是源码静态判断，测试初始化 fixture 及真实外部依赖行为未确认，本次未执行测试。

后续在准备好依赖且允许启动服务的环境运行：

```bash
uv run pytest tests/test_health.py tests/test_metrics.py tests/guards/test_openapi_schema.py
```

再经生产入口及实际部署代理验证，操作见[探针客户端](../guides/probe-client.md)。
现存旧测试与指标排除项属于待同步代码，本次只改文档，不能宣称行为验证通过。

## 相关说明

- [可观测性](../guides/observability.md)：开关和指标使用。
- [架构设计](../architecture/system-design.md)：分层权威说明。
- 历史归档 PRD 中的 `/ready` 记录描述当时交付，保留历史语境，不代表当前入口。
