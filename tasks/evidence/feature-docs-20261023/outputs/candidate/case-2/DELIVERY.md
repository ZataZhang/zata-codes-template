# 交付说明

根据 changes.patch 与当前生产 router，将就绪路径从 `/ready` 同步为 `/readiness`。更新功能页、功能索引、可观测性指南、探针调用指南及 MkDocs 页面标题。未修改源代码或测试。

修改文件：`docs/features/health.md`、`docs/features/index.md`、`docs/guides/observability.md`、`docs/guides/probe-client.md`、`mkdocs.yml`、`DELIVERY.md`。
依据：`health_router.py::ready` 的新装饰器与固定字典返回；`app_factory.py::create_app` 的无条件注册。旧 URL 无 router 别名，readiness 仍无数据库/Redis 检查。现有 `tests/test_health.py` 仍请求旧 URL，文档明确指出预计失败及后续修复/验证方向，未擅自修测试。部署客户端实际迁移状态未确认。

实际检查：5 个修改文件 UTF-8 可读、6 个本地链接目标存在、无行末空白；搜索文档中的旧路径后，剩余 `/ready` 只在迁移与旧测试说明中保留。`python3 -m mkdocs build` 失败：`No module named mkdocs`。未安装依赖、未启动服务、未执行 pytest 或 curl；文档明确给出后续 router 与真实应用验证计划。

调查与编辑计时：2026-10-23 03:57:34 至 03:58:06 UTC，32 秒。最终静态核对时间 03:58:52 UTC。实际 token 用量：不可用。
