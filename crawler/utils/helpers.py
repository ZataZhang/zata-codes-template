"""爬虫专用辅助函数

提供爬虫相关的工具函数，例如 HTML 解析、数据清洗等。
"""

from typing import Optional, List, Dict
import re


def extract_links(html: str, base_url: str = "") -> List[str]:
    """从 HTML 中提取所有链接

    Args:
        html (str): HTML 内容
        base_url (str): 基础 URL，用于补全相对链接

    Returns:
        List[str]: 链接列表

    Examples:
        >>> html = '<a href="/page1">Link1</a><a href="http://example.com">Link2</a>'
        >>> links = extract_links(html, base_url="http://example.com")
        >>> print(links)
        ['http://example.com/page1', 'http://example.com']
    """
    from urllib.parse import urljoin

    # 简单的正则提取（实际项目中建议使用 BeautifulSoup）
    pattern = r'href=["\'](.*?)["\']'
    links = re.findall(pattern, html)

    # 补全相对链接
    if base_url:
        links = [urljoin(base_url, link) for link in links]

    return links


def clean_text(text: str) -> str:
    """清理文本内容

    移除多余空白、HTML 标签等。

    Args:
        text (str): 原始文本

    Returns:
        str: 清理后的文本

    Examples:
        >>> dirty = "  <p>Hello   World</p>  \\n\\n  "
        >>> clean = clean_text(dirty)
        >>> print(clean)
        Hello World
    """
    # 移除 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 移除多余空白
    text = re.sub(r"\s+", " ", text)
    # 去除首尾空白
    return text.strip()


def parse_table_data(html: str) -> List[Dict[str, str]]:
    """解析 HTML 表格数据为字典列表

    Args:
        html (str): 包含表格的 HTML

    Returns:
        List[Dict[str, str]]: 表格数据，每行为一个字典

    Examples:
        >>> html = '''
        ... <table>
        ...   <tr><th>Name</th><th>Age</th></tr>
        ...   <tr><td>Alice</td><td>30</td></tr>
        ...   <tr><td>Bob</td><td>25</td></tr>
        ... </table>
        ... '''
        >>> data = parse_table_data(html)
        >>> print(data)
        [{'Name': 'Alice', 'Age': '30'}, {'Name': 'Bob', 'Age': '25'}]
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("需要安装 BeautifulSoup: uv add beautifulsoup4")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        return []

    # 获取表头
    headers = []
    header_row = table.find("tr")
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

    # 获取数据行
    data = []
    rows = table.find_all("tr")[1:]  # 跳过表头行

    for row in rows:
        cells = row.find_all("td")
        if cells:
            row_data = {
                headers[i]: cell.get_text(strip=True)
                for i, cell in enumerate(cells)
                if i < len(headers)
            }
            data.append(row_data)

    return data


def validate_url(url: str) -> bool:
    """验证 URL 格式是否正确

    Args:
        url (str): 待验证的 URL

    Returns:
        bool: URL 是否有效

    Examples:
        >>> validate_url("https://example.com")
        True
        >>> validate_url("not a url")
        False
    """
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return url_pattern.match(url) is not None


def extract_domain(url: str) -> Optional[str]:
    """从 URL 中提取域名

    Args:
        url (str): 完整 URL

    Returns:
        Optional[str]: 域名，失败返回 None

    Examples:
        >>> extract_domain("https://www.example.com/path/to/page?query=1")
        'www.example.com'
        >>> extract_domain("invalid")
        None
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return None


def rate_limit_wait(delay: float = 1.0):
    """速率限制等待装饰器

    Args:
        delay (float): 等待时间（秒）

    Examples:
        >>> import time
        >>> @rate_limit_wait(delay=2.0)
        >>> def fetch_page(url):
        >>>     # 每次调用前会等待 2 秒
        >>>     return requests.get(url)
    """
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            time.sleep(delay)
            return func(*args, **kwargs)

        return wrapper

    return decorator
