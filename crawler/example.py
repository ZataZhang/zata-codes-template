"""Crawler 使用示例

展示如何使用 crawler 模块进行数据爬取。
"""

from crawler.core import BaseCrawler, SimpleHttpCrawler
from typing import Dict, Any


def example_simple_http_crawler():
    """示例 1: 使用 SimpleHttpCrawler 爬取 API 数据"""
    print("\n=== 示例 1: SimpleHttpCrawler ===")

    # 创建爬虫实例
    crawler = SimpleHttpCrawler(url="https://httpbin.org/json", name="HttpbinCrawler")

    # 运行爬虫
    result = crawler.run()

    # 打印结果
    print(f"状态: {result.get('status')}")
    print(f"状态码: {result.get('status_code')}")
    print(f"数据: {result.get('data')}")


def example_custom_crawler():
    """示例 2: 继承 BaseCrawler 创建自定义爬虫"""
    print("\n=== 示例 2: 自定义爬虫 ===")

    class WeatherCrawler(BaseCrawler):
        """天气数据爬虫示例"""

        def __init__(self, city: str = "beijing"):
            super().__init__(name=f"WeatherCrawler-{city}")
            self.city = city

        def crawl(self) -> Dict[str, Any]:
            """爬取天气数据"""
            import requests

            # 模拟 API 调用（实际使用时替换为真实 API）
            url = f"https://api.example.com/weather?city={self.city}"

            try:
                # 这里只是示例，实际会因为 API 不存在而失败
                # 在真实场景中，使用真实的天气 API
                response = requests.get(url, timeout=5)
                response.raise_for_status()

                return {"status": "success", "city": self.city, "data": response.json()}
            except Exception:
                # 返回模拟数据作为示例
                return {
                    "status": "success",
                    "city": self.city,
                    "data": {
                        "temperature": "20°C",
                        "weather": "晴天",
                        "note": "这是模拟数据（因为示例 API 不存在）",
                    },
                }

    # 创建并运行爬虫
    crawler = WeatherCrawler(city="beijing")
    result = crawler.run()
    print(f"结果: {result}")


def example_with_database():
    """示例 3: 爬取数据并保存到数据库"""
    print("\n=== 示例 3: 保存到数据库 ===")

    from utils.database import SessionLocal, init_database
    from crawler.models import CrawlerData

    # 初始化数据库（创建表）
    print("初始化数据库...")
    init_database()

    class NewsItemCrawler(BaseCrawler):
        """新闻条目爬虫"""

        def __init__(self):
            super().__init__(name="NewsItemCrawler")

        def crawl(self) -> Dict[str, Any]:
            """爬取新闻数据并保存"""
            # 模拟爬取的新闻数据
            news_items = [
                {
                    "title": "示例新闻 1",
                    "content": "这是第一条示例新闻的内容...",
                    "url": "https://example.com/news/1",
                },
                {
                    "title": "示例新闻 2",
                    "content": "这是第二条示例新闻的内容...",
                    "url": "https://example.com/news/2",
                },
            ]

            # 保存到数据库
            db = SessionLocal()
            saved_count = 0

            try:
                for item in news_items:
                    news = CrawlerData(
                        source=self.name,
                        title=item["title"],
                        content=item["content"],
                        url=item["url"],
                    )
                    db.add(news)
                    saved_count += 1

                db.commit()
                print(f"成功保存 {saved_count} 条数据到数据库")

                return {"status": "success", "saved_count": saved_count}

            except Exception as e:
                db.rollback()
                print(f"保存失败: {e}")
                return {"status": "error", "error": str(e)}
            finally:
                db.close()

    # 运行爬虫
    crawler = NewsItemCrawler()
    result = crawler.run()
    print(f"结果: {result}")

    # 查询保存的数据
    print("\n查询保存的数据:")
    db = SessionLocal()
    items = db.query(CrawlerData).limit(5).all()
    for item in items:
        print(f"  - [{item.source}] {item.title} ({item.created_at})")
    db.close()


def example_with_retry():
    """示例 4: 带重试机制的爬虫"""
    print("\n=== 示例 4: 带重试机制 ===")

    import time

    class RobustCrawler(BaseCrawler):
        """具有重试机制的爬虫"""

        def __init__(self):
            super().__init__(name="RobustCrawler")
            self.max_retries = 3

        def crawl(self) -> Dict[str, Any]:
            """带重试的爬取逻辑"""
            import requests

            url = "https://httpbin.org/status/500"  # 模拟会失败的请求

            for attempt in range(self.max_retries):
                try:
                    print(f"尝试 {attempt + 1}/{self.max_retries}...")
                    response = requests.get(url, timeout=5)
                    response.raise_for_status()

                    return {"status": "success", "attempts": attempt + 1}

                except Exception as e:
                    print(f"失败: {e}")
                    if attempt < self.max_retries - 1:
                        wait_time = 2**attempt  # 指数退避
                        print(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        return {
                            "status": "error",
                            "error": f"重试 {self.max_retries} 次后仍失败",
                            "last_error": str(e),
                        }

    # 运行爬虫
    crawler = RobustCrawler()
    result = crawler.run()
    print(f"最终结果: {result}")


def main():
    """运行所有示例"""
    print("=" * 60)
    print("Crawler 模块使用示例")
    print("=" * 60)

    # 运行各个示例
    example_simple_http_crawler()
    example_custom_crawler()
    example_with_database()
    example_with_retry()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
