"""Crawling capability implementations."""

import time
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from infrastructure.config.settings import config
from infrastructure.logging.logger import logger


class BaseCrawler(ABC):
    """基础爬虫抽象类

    所有爬虫应继承此类并实现 crawl 方法。

    Attributes:
        name (str): 爬虫名称
        config (Config): 配置对象

    Examples:
        >>> class MyCrawler(BaseCrawler):
        >>>     def __init__(self):
        >>>         super().__init__(name="MyCrawler")
        >>>
        >>>     def crawl(self) -> Dict[str, Any]:
        >>>         # 实现爬取逻辑
        >>>         return {"status": "success", "data": [...]}
        >>>
        >>> crawler = MyCrawler()
        >>> result = crawler.run()
    """

    def __init__(self, name: str = "BaseCrawler"):
        """初始化爬虫

        Args:
            name (str): 爬虫名称，用于日志标识
        """
        self.name = name
        self.config = config
        logger.info(f"{self.name} 已初始化")

    @abstractmethod
    def crawl(self) -> Dict[str, Any]:
        """执行爬取任务（抽象方法）

        子类必须实现此方法，定义具体的爬取逻辑。

        Returns:
            Dict[str, Any]: 爬取结果

        Raises:
            NotImplementedError: 子类未实现此方法时抛出
        """
        pass

    def run(self) -> Dict[str, Any]:
        """运行爬虫（入口方法）

        包含错误处理和日志记录。

        Returns:
            Dict[str, Any]: 爬取结果，失败时返回错误信息

        Examples:
            >>> crawler = MyCrawler()
            >>> result = crawler.run()
            >>> if result.get("status") == "success":
            >>>     print("爬取成功")
        """
        logger.info(f"开始执行 {self.name}")
        start_time = time.time()

        try:
            result = self.crawl()
            elapsed = time.time() - start_time
            logger.info(f"{self.name} 执行完成，耗时 {elapsed:.2f} 秒")
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{self.name} 执行失败: {e}，耗时 {elapsed:.2f} 秒")
            return {"status": "error", "error": str(e), "crawler": self.name}


class SimpleHttpCrawler(BaseCrawler):
    """简单 HTTP 爬虫示例

    展示如何使用 requests 库进行简单的 HTTP 请求爬取。

    Examples:
        >>> crawler = SimpleHttpCrawler(
        >>>     url="https://api.example.com/data",
        >>>     name="ExampleAPI"
        >>> )
        >>> result = crawler.run()
        >>> print(result)
    """

    def __init__(
        self,
        url: str,
        name: str = "SimpleHttpCrawler",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        """初始化 HTTP 爬虫

        Args:
            url (str): 目标 URL
            name (str): 爬虫名称
            headers (Dict[str, str], optional): 请求头
            timeout (int): 请求超时时间（秒），默认 30
        """
        super().__init__(name=name)
        self.url = url
        self.timeout = timeout
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def crawl(self) -> Dict[str, Any]:
        """执行 HTTP 请求爬取

        Returns:
            Dict[str, Any]: 包含状态和响应数据的字典

        Examples:
            >>> crawler = SimpleHttpCrawler("https://httpbin.org/json")
            >>> result = crawler.crawl()
            >>> print(result["status"])
            success
        """
        import requests

        logger.info(f"正在请求: {self.url}")

        response = requests.get(self.url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()

        logger.info(f"请求成功，状态码: {response.status_code}")

        return {
            "status": "success",
            "status_code": response.status_code,
            "url": self.url,
            "data": response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else response.text,
        }


class BrowserCrawler(BaseCrawler):
    """浏览器爬虫基类

    使用 DrissionPage 进行浏览器自动化爬取。
    需要安装: uv add drissionpage

    Examples:
        >>> class MyBrowserCrawler(BrowserCrawler):
        >>>     def crawl_with_page(self) -> Dict[str, Any]:
        >>>         self.page.get("https://example.com")
        >>>         title = self.page.title
        >>>         return {"status": "success", "title": title}
        >>>
        >>> crawler = MyBrowserCrawler()
        >>> result = crawler.run()
    """

    def __init__(self, name: str = "BrowserCrawler", headless: bool = None):
        """初始化浏览器爬虫

        Args:
            name (str): 爬虫名称
            headless (bool, optional): 是否使用无头模式，None 则从配置读取
        """
        super().__init__(name=name)
        self.headless = (
            headless if headless is not None else getattr(config, "HEADLESS", False)
        )
        self.page = None

    def start_browser(self):
        """启动浏览器

        根据 headless 配置启动有头或无头浏览器。
        """
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            raise ImportError("请先安装 DrissionPage: uv add drissionpage")

        if self.headless:
            options = ChromiumOptions()
            options.headless()
            options.set_argument("--window-size=1920,1080")
            options.set_argument("--disable-gpu")
            options.set_argument("--no-sandbox")
            options.set_argument("--disable-dev-shm-usage")
            self.page = ChromiumPage(options)
            logger.info(f"{self.name} - 浏览器已以无头模式启动")
        else:
            self.page = ChromiumPage()
            logger.info(f"{self.name} - 浏览器已以有头模式启动")

    def close_browser(self):
        """关闭浏览器"""
        if self.page:
            self.page.quit()
            self.page = None
            logger.info(f"{self.name} - 浏览器已关闭")

    def crawl(self) -> Dict[str, Any]:
        """执行浏览器爬取

        自动管理浏览器的启动和关闭。

        Returns:
            Dict[str, Any]: 爬取结果
        """
        try:
            self.start_browser()
            result = self.crawl_with_page()
            return result
        finally:
            self.close_browser()

    @abstractmethod
    def crawl_with_page(self) -> Dict[str, Any]:
        """使用浏览器页面进行爬取（抽象方法）

        子类需要实现此方法，在其中使用 self.page 进行操作。

        Returns:
            Dict[str, Any]: 爬取结果

        Raises:
            NotImplementedError: 子类未实现此方法时抛出
        """
        pass
