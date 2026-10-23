# 探针调用

部署客户端应使用 `GET /readiness` 判断基础就绪状态；原 `/ready` 已改名，生产路由没有保留该别名。配置客户端时同步替换 URL。

当前接口直接返回 HTTP 200 与 `{"status":"ok"}`，没有检查数据库或 Redis，不能据此断言所有依赖可用。协议说明见 [可观测性](observability.md)，修改入口见 [健康探针](../features/health.md)。

变更后在实际后端入口请求 `/readiness`、`/health`、`/live`，核对均为 200 与上述 JSON；请求原 `/ready` 应为 404。随后核对部署探针配置使用新 URL。该验证需要已运行的后端，本次仅静态同步文档，未启动服务。
