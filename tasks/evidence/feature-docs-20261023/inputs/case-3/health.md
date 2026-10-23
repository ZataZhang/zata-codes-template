# 健康检查

入口为 `src/backend/api/legacy_health.py`。
`GET /ready` 会连接 PostgreSQL 与 Redis，任一依赖不可用时返回 503。
修改依赖检查应改 `check_dependencies()`。
测试位于 `tests/test_legacy_health.py`。
