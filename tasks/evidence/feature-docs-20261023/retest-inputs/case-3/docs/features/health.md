# 服务探针

生产入口在 `src/backend/api/probes_old.py` 的 `probe_dependencies()`。
所有探针需要登录，成功返回 204；就绪检查依赖数据库。
验证文件是 `tests/test_probes_old.py`。
