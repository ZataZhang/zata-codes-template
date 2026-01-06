"""工具模块 - 提供通用的配置管理、日志记录和辅助函数

此模块为所有项目提供可复用的工具组件。

Modules:
    settings: 配置管理，集中处理环境变量和配置项
    logger: 日志管理，提供单例模式的日志记录器
    helpers: 通用辅助函数，提供无状态的工具函数
    database: 数据库连接和会话管理（SQLAlchemy）

Examples:
    >>> from utils.logger import logger
    >>> from utils.settings import config
    >>> from utils.database import SessionLocal, init_database
    >>> from utils.helpers import parse_datetime, safe_json_loads
    >>>
    >>> logger.info(f"应用名称: {config.APP_NAME}")
    >>> logger.debug("这是一条调试日志")
    >>>
    >>> # 初始化数据库
    >>> init_database()
    >>>
    >>> # 使用辅助函数
    >>> dt = parse_datetime("2025/12/01 16:00")
"""

from utils.logger import logger
from utils.settings import config

__all__ = ["logger", "config"]
