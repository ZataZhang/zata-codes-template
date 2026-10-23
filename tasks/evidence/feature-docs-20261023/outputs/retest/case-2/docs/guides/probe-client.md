# 调用探针

就绪调用使用 `GET /operational-ready`，成功为 200，JSON `{"status": "ok"}`；无需登录。
旧路径 `/ready` 已由源码更名，没有兼容路由或重定向。外部监控、容器 readinessProbe、
负载均衡等调用配置应改为新路径；实际部署配置是否已经迁移未确认。
存活请求仍使用 `GET /health` 或 `GET /live`。

在已运行并获准访问的目标服务上，将 `PROBE_BASE_URL` 设置为实际地址后检查：

```bash
curl -i "${PROBE_BASE_URL}/operational-ready"
curl -i "${PROBE_BASE_URL}/health"
curl -i "${PROBE_BASE_URL}/live"
```

逐项核对 200 与响应 JSON，并确认旧 `/ready` 不再作为就绪入口。
本次没有执行这些请求。当前就绪函数直接返回 OK，不检查数据库或 Redis。
实现定位及现有测试仍使用旧路径的限制见[服务探针功能地图](../features/health.md)。
