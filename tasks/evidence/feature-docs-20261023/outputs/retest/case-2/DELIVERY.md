# 交付记录

仅修改文档。调查了 Agent 入口、规范索引、文档/测试/工具规范、功能索引、探针路由、main 入口、composition 工厂、认证装配、启动迁移/种子与根测试夹具、探针测试及相关调用说明。

实际静态检查：搜索探针及旧路径引用；逐项核对函数、注册与断言；用 Python 标准库核对修改页面相对链接、导航及修改文件哈希范围。相对链接无缺失，修改范围仅 docs/ 和 mkdocs.yml（另有本交付记录）。快照无 .git，git status 返回“not a git repository”，无法给出 Git diff；以修改前后 SHA-256 范围比较替代。

当前环境未找到 mkdocs 可执行文件或本地 .venv/bin/mkdocs，Python 也无 mkdocs 模块。因此未运行严格构建，未安装依赖；未运行 pytest、服务或真实请求，不声称产品验证通过。后续命令及判据已写入功能地图。实际部署、网关和外部依赖状态均未确认。

修改文件：
- `mkdocs.yml`
- `docs/features/index.md`
- `docs/features/health.md`
- `docs/guides/probe-client.md`
- `docs/guides/observability.md`

关键发现：changes.patch 只更改就绪路由，新路径为 /operational-ready；旧测试仍请求 /ready，已记录缺口，未修改源码或测试。已同步调用指南、可观测性指南、功能索引及调用指南导航；旧路径文字仅在迁移说明中保留。

修改问题自检：若修改就绪路径，功能地图可定位 ready 装饰器、生产注册、调用指南/监控影响与测试断言，并披露现有测试额外注册不能证明生产注册。

计时：未记录完整起止时间，不提供估算；工具返回的单次写入/静态检查耗时不等于任务耗时。token 使用无可用计量。
