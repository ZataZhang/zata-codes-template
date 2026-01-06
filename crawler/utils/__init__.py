"""爬虫工具模块

提供爬虫专用的工具函数和类。

Modules:
    proxy_manager: 代理管理器（Clash 和 HTTP 隧道）
    helpers: 爬虫相关的辅助函数

Examples:
    >>> from crawler.utils.proxy_manager import create_proxy_manager
    >>>
    >>> # 创建代理管理器
    >>> proxy_manager = create_proxy_manager()
    >>> proxies = proxy_manager.get_proxy_config()
"""

__all__ = []
