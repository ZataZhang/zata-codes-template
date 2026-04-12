"""平台能力层（capabilities）。

放置 skills、RAG、registry 等可插拔能力。
实现 core/shared/interfaces 定义的端口契约。

依赖规则：
    - 可以依赖 core/shared/interfaces 中的抽象
    - 可以依赖 infrastructure/ 的具体实现
    - 不得包含业务编排逻辑
"""
