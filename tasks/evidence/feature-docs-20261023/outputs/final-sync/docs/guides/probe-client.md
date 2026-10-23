# 探针客户端

调用 `GET /service-ready` 获取基础就绪状态；`/health` 与 `/live` 用于存活检查。
三者当前均返回 HTTP 200 和 `{"status":"ok"}`，不检查数据库等依赖。
旧 `/ready` 已从路由移除，没有兼容别名；将外部健康检查、部署探针和脚本中的
旧 URL 更新为 `/service-ready`。实际部署方配置是否仍使用旧路径，本次未确认。

服务已启动后，以实际后端地址和端口替换下例；经过反向代理部署时也应验证外部入口：

```bash
curl -i http://localhost:8000/service-ready
curl -i http://localhost:8000/health
curl -i http://localhost:8000/live
curl -i http://localhost:8000/ready
```

确认前三个返回 200 和固定状态 JSON；最后一个旧路径在后端应返回 404。
同时检查 `/openapi.json` 包含 `/service-ready` 而不包含 `/ready`，关闭监控后
三个探针仍可用。若代理另有回退规则，核对响应确实来自后端。
这些是后续验证步骤，本次未启动服务或执行请求。

启用指标时，当前中间件排除列表尚未同步新路径，会把新就绪请求计入 RED 指标。
源码与测试的待修复位置及验证方法见[健康探针功能地图](../features/health.md)，
配置说明见[可观测性](observability.md)。
