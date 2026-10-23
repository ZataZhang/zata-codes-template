# 健康探针

`src/backend/api/health_router.py` 提供 `/health`、`/readiness` 和 `/live`。

生产注册入口为 `src/backend/composition/app_factory.py`，三个端点均无认证依赖，当前直接返回 `{"status":"ok"}`。就绪探针没有检查数据库。调用与改名验证见 [探针调用](../guides/probe-client.md)。
