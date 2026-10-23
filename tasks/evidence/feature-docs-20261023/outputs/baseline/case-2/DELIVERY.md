# 交付说明

依据 changes.patch 和当前生产 health_router，将功能页、可观测性指南和探针调用指南中的就绪入口同步为 `/readiness`；明确旧 `/ready` 无别名、基础探针不检查依赖。MkDocs 新增已有探针调用指南导航，保留功能索引入口。

已静态核对生产路由与 app_factory 注册；全文搜索旧 URL 后，仅保留指南中明确说明改名和 404 的历史 URL。未执行产品测试、HTTP 请求或启动服务。已在指南列出真实 HTTP 验证步骤。

尝试 `UV_OFFLINE=1 uv run --no-sync mkdocs build --strict`，缺少 mkdocs 可执行文件，构建未完成；未安装依赖，自动创建的 .venv 已删除。依赖就绪后重跑构建。没有生产代码修改或 Git 写操作。

计时：2026-10-23 03:55:56–03:56:34 UTC，38 秒，另有交付记录写入时间。实际 token 用量：不可用。

最终范围检查尝试 `git diff --name-only` 与 `git status --short`，均因隔离快照没有 .git 失败；因此未获得 Git diff 检查结果。改动范围按实际写入路径记录，未修改源码。
