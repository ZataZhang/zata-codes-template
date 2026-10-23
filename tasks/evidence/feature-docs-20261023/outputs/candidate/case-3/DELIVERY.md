# 交付说明

以当前生产注册链重写 `docs/features/health.md`，修正 legacy 文件、虚构的依赖检查与 503、错误测试定位；同步功能索引和 MkDocs 标题。说明真实入口、三个固定响应、无持久化/认证/依赖检查、observability 开关与探针注册的关系，并补充修改影响和验证路径。

修改文件：`docs/features/health.md`、`docs/features/index.md`、`mkdocs.yml`、`DELIVERY.md`。
依据：`main.py::create_app` 委托 composition root；`app_factory.py::create_app` 无条件 include health_router；`health_router.py::health/ready/live` 直接返回固定状态；`tests/test_health.py::test_health_endpoints_return_ok` 用临时 FastAPI 测试三个路径。保留 `/ready`，没有把其他 case 的变更套入本 case。相关指南保持不变：当前指南的接口路径与源码一致，本任务仅修正功能地图，不扩成指南整理。

实际检查：3 个修改文件 UTF-8 可读、4 个本地链接存在、无行末空白。搜索 legacy_health/check_dependencies 后，只有本页解释旧错误的历史语境，未留下作为可用入口的引用。`python3 -m mkdocs build` 失败：`No module named mkdocs`。未安装依赖、未启动服务、未执行产品测试；页面列出的 pytest/curl 是后续验证计划。生产启动、部署代理与外部探针环境未确认。

调查与编辑计时：2026-10-23 03:58:06 至 03:58:38 UTC，32 秒。最终静态核对时间 03:58:52 UTC。实际 token 用量：不可用。
