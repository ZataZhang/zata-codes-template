# 健康探针

为修改基础 HTTP 探针的开发者提供代码入口。当前探针仅报告进程可响应，不检查 PostgreSQL 或 Redis。

## 当前生产入口与契约

`src/backend/composition/app_factory.py` 注册 `src/backend/api/health_router.py` 中的 `health_router`，没有额外路由前缀或认证依赖。

| 端点 | 实现函数 | 当前响应 |
|---|---|---|
| `GET /health` | `health` | HTTP 200，`{"status":"ok"}` |
| `GET /ready` | `ready` | HTTP 200，`{"status":"ok"}` |
| `GET /live` | `live` | HTTP 200，`{"status":"ok"}` |

`/live` 是与 `/health` 行为一致的替代存活探针。`/ready` 当前也是直接返回 OK 的基础实现，没有依赖探测或 503 分支。此路由不读取数据库模型、会话、配置或持久化状态。

## 修改路线与边界

- 修改响应或就绪逻辑，从 `src/backend/api/health_router.py` 的对应函数开始；生产挂载关系看 `src/backend/composition/app_factory.py`。
- 没有 `legacy_health.py` 或 `check_dependencies()` 这一修改入口；不要依据旧文档去实现或查找历史接口。
- 依赖不可用时，不能据这些固定响应判断数据库与 Redis 正常。新增依赖检测将是行为变化，须同步契约、部署探针与测试。
- 操作与监控背景见 [可观测性指南](../guides/observability.md)，返回 [功能索引](index.md)。

## 测试与验证

`tests/test_health.py::test_health_endpoints_return_ok` 通过 `ASGITransport` 请求三个端点，断言状态均为 200；其中 `/health` 与 `/ready` 断言 JSON，`/live` 只断言状态。测试还显式注册了路由，因此不能单独证明生产装配正确。

依赖就绪后可运行 `uv run pytest tests/test_health.py`；按 [测试规范](../ai-standards/testing.md) 准备运行环境。生产入口验证应向已启动后端请求三个 URL 并核对状态和 JSON。文档站点运行 `uv run mkdocs build --strict`。这些是验证入口，本次仅静态阅读与路径核对，没有运行产品测试或 HTTP 请求。
