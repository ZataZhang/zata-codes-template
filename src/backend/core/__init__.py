"""核心编排层（core）。

放置用例、领域契约和纯业务规则。
负责业务规则与任务编排，不依赖具体 SDK、数据库或 HTTP 客户端。

依赖规则：
    - 只能依赖抽象接口和纯业务模型（backend/core/shared/interfaces）
    - 不得直接依赖 backend/engines/ 或 backend/infrastructure/ 的具体实现
"""
