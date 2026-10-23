# 文档同步交付

依据 `changes.patch` 和当前源码确认：`health_router.ready()` 的注册路径由
`/ready` 改为 `/service-ready`；生产 `composition/app_factory.py:create_app()`
无前缀注册该 router，不存在旧路径兼容别名。三个探针仍直接返回固定状态，
就绪响应不检查数据库等依赖。

## 改动文件

- `README.md`、`README.zh.md`：同步默认探针路径，保留各自语言。
- `docs/features/health.md`：补齐生产调用链、契约、配置边界、修改定位和测试限制。
- `docs/features/index.md`：连接功能地图和客户端指南。
- `docs/guides/probe-client.md`：客户端迁移、真实入口检查与限制。
- `docs/guides/observability.md`：同步路径并披露指标排除项未同步的影响。
- `mkdocs.yml`：将现有探针客户端页加入使用指南导航。
- `DELIVERY.md`：本交付记录。

没有修改源代码、测试或运行配置；`mkdocs.yml` 仅调整文档导航。
归档 PRD 是历史记录，保留旧路径以免改写历史；本次调查未发现其余当前使用文档
宣称 `/ready` 是就绪入口。新文档保留的旧路径用于迁移、负向检查和待修复说明。

## 本次不能修改的代码影响

1. `src/backend/api/middleware/prometheus_metrics.py:_EXCLUDED_PATHS` 仍含
   `/ready`，不含 `/service-ready`。启用 observability 和 metrics 时，新探针会进入
   RED counter/histogram；旧路径仍被排除，不能把它当作新路径的正确指标行为。
2. `tests/test_health.py:test_health_endpoints_return_ok` 通过生产 `create_app()`
   创建应用，再重复注册健康 router；仍请求旧路径并期望 200，静态判断与更名冲突。
3. `tests/guards/test_openapi_schema.py:REQUIRED_PATHS` 仍要求旧路径，静态判断与
   当前 OpenAPI 注册冲突。后续需按明确的契约变更处理守卫与对应文档，不能为绿灯任意放宽断言。
4. `tests/test_metrics.py:test_middleware_ignores_excluded_paths` 用临时 FastAPI，
   只挂 metrics router 和中间件，未挂健康 router；它对旧路径的排除断言不能验证
   新就绪接口或生产装配，应同步路径和相应覆盖。

上述都是静态源码判断，未执行测试，不声称实际失败结果。测试 fixture 与真实外部依赖
初始化行为未确认。外部部署方的探针配置是否仍使用旧地址未确认。

## 实际检查与限制

- 已执行 `python3 hooks/shared/check_guidelines_consistency.py`：通过。
- 已用 Python 标准库检查改动文档的相对 Markdown 链接、尾随空白和全部导航目标存在性：通过。
- 已搜索全仓库旧路径引用并按当前文档、源码消费者、契约测试和归档历史判断语境。
- 已尝试 `uv run --no-sync --offline mkdocs build --strict`：退出 2，环境无 `mkdocs`。
  未安装依赖；uv 自动创建的空 `.venv` 已移除。文档构建与渲染未确认。
- `git diff --check` 和 `git status --short` 无法使用：该快照不是 Git 仓库。
  未执行暂存、提交或推送；以定向静态检查替代空白检查，无法提供 Git diff 证据。
- 未运行 `just lint --repo`、产品测试、HTTP 请求或真实服务验证，以遵守不安装依赖、
  不启动服务和只改文档的边界。

实际修改问题抽查：“就绪探针改名后指标是否仍被排除？”功能地图可定位
`_EXCLUDED_PATHS` 与 `_should_record()`，解释新路径被计入 RED 的影响，并指向
相关测试缺口及生产入口验证；当前不能声称排除正确。

## 后续验证（未执行）

在具备依赖与服务授权的环境完成代码消费者及测试同步后：

1. 运行 `uv run pytest tests/test_health.py tests/test_metrics.py tests/guards/test_openapi_schema.py`，
   确保新契约、响应和指标排除均覆盖。
2. 从生产后端及部署代理入口验证 `/service-ready`、`/health`、`/live` 的 200 和固定 JSON，
   验证旧 `/ready` 在后端为 404，OpenAPI 仅包含新就绪路径。
3. 关闭监控验证探针继续可用；启用指标后验证新就绪请求不产生 RED 样本。
   当前代码尚未同步指标排除项，不能期待此项通过。
4. 执行 `uv run mkdocs build --strict`，确认站点导航与页面渲染。

本次准确 token 用量及完整端到端耗时指标不可获得，未估算或编造。
