# Crawler 爬虫模块

这是一个通用的爬虫模块模板，提供了基础的爬虫类和示例实现。

## 目录结构

```
crawler/
├── __init__.py           # 模块入口
├── core/                 # 核心爬虫逻辑
│   ├── __init__.py
│   └── crawler.py        # 基础爬虫类和实现
├── models/               # 数据模型
│   ├── __init__.py
│   └── database.py       # SQLAlchemy 模型示例
└── README.md            # 本文档
```

## 功能特性

- **抽象基类**: `BaseCrawler` 提供统一的爬虫接口
- **HTTP 爬虫**: `SimpleHttpCrawler` 用于简单的 HTTP 请求
- **浏览器爬虫**: `BrowserCrawler` 用于需要浏览器渲染的网站
- **数据模型**: 提供 SQLAlchemy 模型示例
- **错误处理**: 内置错误处理和日志记录
- **性能监控**: 自动记录执行时间

## 快速开始

### 1. 使用 SimpleHttpCrawler（HTTP 请求爬虫）

```python
from crawler.core import SimpleHttpCrawler

# 创建爬虫实例
crawler = SimpleHttpCrawler(
    url="https://api.example.com/data",
    name="MyApiCrawler"
)

# 运行爬虫
result = crawler.run()
print(result)
```

### 2. 继承 BaseCrawler 创建自定义爬虫

```python
from crawler.core import BaseCrawler
from typing import Dict, Any

class MyCustomCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(name="MyCustomCrawler")

    def crawl(self) -> Dict[str, Any]:
        # 实现你的爬取逻辑
        import requests
        response = requests.get("https://example.com")

        return {
            "status": "success",
            "data": response.text
        }

# 使用
crawler = MyCustomCrawler()
result = crawler.run()
```

### 3. 使用 BrowserCrawler（浏览器自动化）

需要先安装 DrissionPage:
```bash
uv add drissionpage
```

创建浏览器爬虫:
```python
from crawler.core import BrowserCrawler
from typing import Dict, Any

class MyBrowserCrawler(BrowserCrawler):
    def __init__(self):
        super().__init__(name="MyBrowserCrawler", headless=True)

    def crawl_with_page(self) -> Dict[str, Any]:
        # 使用 self.page 进行浏览器操作
        self.page.get("https://example.com")
        title = self.page.title

        # 可以进行更多操作，如点击、输入等
        # button = self.page.ele("@text=搜索")
        # button.click()

        return {
            "status": "success",
            "title": title
        }

# 使用（会自动管理浏览器的启动和关闭）
crawler = MyBrowserCrawler()
result = crawler.run()
```

## 使用数据库

### 1. 配置数据库连接

在 `.env` 文件中配置数据库 URL:
```env
DATABASE_URL=sqlite:///./crawler.db
# 或使用 MySQL
# DATABASE_URL=mysql://user:password@localhost:3306/dbname
```

### 2. 初始化数据库

```python
from utils.database import init_database
from crawler.models import CrawlerData, CrawlerLog

# 创建所有表
init_database()
```

### 3. 保存爬取的数据

```python
from utils.database import SessionLocal
from crawler.models import CrawlerData

def save_crawler_data(source: str, title: str, content: str, url: str):
    db = SessionLocal()
    try:
        data = CrawlerData(
            source=source,
            title=title,
            content=content,
            url=url
        )
        db.add(data)
        db.commit()
        print(f"数据已保存: {title}")
    except Exception as e:
        db.rollback()
        print(f"保存失败: {e}")
    finally:
        db.close()

# 在爬虫中使用
class MyDataCrawler(BaseCrawler):
    def crawl(self) -> Dict[str, Any]:
        # 爬取数据
        data = {"title": "示例", "content": "内容", "url": "https://example.com"}

        # 保存到数据库
        save_crawler_data(
            source=self.name,
            title=data["title"],
            content=data["content"],
            url=data["url"]
        )

        return {"status": "success"}
```

## 使用代理

### 1. 配置代理（在 .env 文件中）

```env
# Clash 代理
PROXY_TYPE=CLASH
CLASH_API_URL=http://localhost:9090
CLASH_API_SECRET=your-secret
CLASH_PROXY_GROUP=Proxy
CLASH_PROXY_PORT=7890

# 或使用 HTTP 隧道代理
PROXY_TYPE=TUNNEL
PROXY_USERNAME=your-username
PROXY_PASSWORD=your-password
PROXY_TUNNEL=proxy.example.com:8080
```

### 2. 在爬虫中使用代理

```python
from crawler.utils.proxy_manager import create_proxy_manager
import requests

# 创建代理管理器（自动根据环境变量选择类型）
proxy_manager = create_proxy_manager()

# 获取代理配置
proxies = proxy_manager.get_proxy_config()

# 在请求中使用代理
response = requests.get("https://example.com", proxies=proxies)
```

## 自定义数据模型

在 `crawler/models/database.py` 中定义你自己的模型:

```python
from sqlalchemy import Column, Integer, String, Text
from utils.database import Base

class MyCustomModel(Base):
    __tablename__ = 'my_custom_table'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    def __repr__(self):
        return f"<MyCustomModel(id={self.id}, name='{self.name}')>"
```

## 最佳实践

1. **继承而不是修改**: 继承 `BaseCrawler` 创建新爬虫，而不是修改基类
2. **使用日志**: 使用 `utils.logger.logger` 记录日志，便于调试和监控
3. **错误处理**: 在 `crawl` 方法中使用 try-except 处理特定错误
4. **配置管理**: 将爬虫配置放在 `.env` 文件或 `utils.settings` 中
5. **数据验证**: 在保存数据前进行验证和清洗
6. **遵守规范**: 尊重网站的 robots.txt，添加合理的延迟（使用 `time.sleep()`）

## 示例项目

查看 `main.py` 了解完整的使用示例。

## 常见问题

### Q: 如何添加请求延迟？

A: 在爬虫中使用 `time.sleep()`:
```python
import time

def crawl(self):
    # 爬取逻辑
    time.sleep(2)  # 延迟 2 秒
```

### Q: 如何处理需要登录的网站？

A: 使用 `BrowserCrawler` 并在 `crawl_with_page` 中实现登录逻辑:
```python
def crawl_with_page(self):
    self.page.get("https://example.com/login")
    self.page.ele("@name=username").input("your_username")
    self.page.ele("@name=password").input("your_password")
    self.page.ele("@type=submit").click()
    # 继续爬取...
```

### Q: 如何处理分页数据？

A: 在 `crawl` 方法中使用循环:
```python
def crawl(self):
    all_data = []
    page = 1

    while True:
        url = f"https://api.example.com/data?page={page}"
        response = requests.get(url)
        data = response.json()

        if not data:  # 没有更多数据
            break

        all_data.extend(data)
        page += 1
        time.sleep(1)  # 添加延迟

    return {"status": "success", "data": all_data}
```

## 扩展阅读

- [DrissionPage 文档](https://github.com/g1879/DrissionPage)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [Requests 文档](https://requests.readthedocs.io/)
