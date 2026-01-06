"""通用辅助函数模块

提供常用的纯函数工具，保持无状态、可复用。
"""

from datetime import datetime
from typing import Optional, Any, Dict, List
import json


def parse_datetime(date_str: str, fmt: str = "%Y/%m/%d %H:%M") -> Optional[datetime]:
    """解析日期时间字符串为 datetime 对象

    Args:
        date_str (str): 日期时间字符串
        fmt (str): 日期时间格式，默认为 '%Y/%m/%d %H:%M'

    Returns:
        Optional[datetime]: 解析后的 datetime 对象，解析失败返回 None

    Examples:
        >>> from utils.helpers import parse_datetime
        >>> dt = parse_datetime("2025/12/01 16:00")
        >>> print(dt)
        2025-12-01 16:00:00
        >>> # 自定义格式
        >>> dt = parse_datetime("2025-12-01", fmt='%Y-%m-%d')
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, fmt)
    except ValueError:
        return None


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全地解析 JSON 字符串

    Args:
        json_str (str): JSON 字符串
        default (Any): 解析失败时返回的默认值，默认为 None

    Returns:
        Any: 解析后的 Python 对象，失败返回 default

    Examples:
        >>> from utils.helpers import safe_json_loads
        >>> data = safe_json_loads('{"key": "value"}')
        >>> print(data)
        {'key': 'value'}
        >>> # 解析失败返回默认值
        >>> data = safe_json_loads('invalid json', default={})
        >>> print(data)
        {}
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_get_nested(data: Dict, keys: List[str], default: Any = None) -> Any:
    """安全地获取嵌套字典中的值

    Args:
        data (Dict): 源字典
        keys (List[str]): 键路径列表
        default (Any): 获取失败时返回的默认值

    Returns:
        Any: 获取到的值，失败返回 default

    Examples:
        >>> from utils.helpers import safe_get_nested
        >>> data = {"a": {"b": {"c": 123}}}
        >>> value = safe_get_nested(data, ["a", "b", "c"])
        >>> print(value)
        123
        >>> # 键不存在时返回默认值
        >>> value = safe_get_nested(data, ["a", "x", "y"], default=0)
        >>> print(value)
        0
    """
    try:
        result = data
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError, IndexError):
        return default


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断字符串到指定长度

    Args:
        text (str): 原始字符串
        max_length (int): 最大长度，默认 100
        suffix (str): 截断后的后缀，默认 "..."

    Returns:
        str: 截断后的字符串

    Examples:
        >>> from utils.helpers import truncate_string
        >>> text = "This is a very long string that needs to be truncated"
        >>> short = truncate_string(text, max_length=20)
        >>> print(short)
        This is a very lo...
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def normalize_whitespace(text: str) -> str:
    """标准化字符串中的空白字符

    将多个连续空白字符替换为单个空格，并去除首尾空白。

    Args:
        text (str): 原始字符串

    Returns:
        str: 标准化后的字符串

    Examples:
        >>> from utils.helpers import normalize_whitespace
        >>> text = "  hello   world  \\n  test  "
        >>> normalized = normalize_whitespace(text)
        >>> print(normalized)
        hello world test
    """
    return " ".join(text.split())


def chunks(lst: List, n: int) -> List[List]:
    """将列表分割为固定大小的块

    Args:
        lst (List): 原始列表
        n (int): 每块的大小

    Returns:
        List[List]: 分割后的列表

    Examples:
        >>> from utils.helpers import chunks
        >>> data = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        >>> result = chunks(data, 3)
        >>> print(result)
        [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    """
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def retry_on_exception(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,),
    default=None,
):
    """对函数进行重试装饰

    Args:
        func: 要执行的函数
        max_retries (int): 最大重试次数
        delay (float): 重试间隔（秒）
        exceptions (tuple): 需要重试的异常类型
        default: 失败后返回的默认值

    Returns:
        函数执行结果或默认值

    Examples:
        >>> from utils.helpers import retry_on_exception
        >>> import requests
        >>>
        >>> def fetch_data():
        >>>     return requests.get("https://api.example.com/data")
        >>>
        >>> result = retry_on_exception(fetch_data, max_retries=3)
    """
    import time

    for attempt in range(max_retries):
        try:
            return func()
        except exceptions:
            if attempt == max_retries - 1:
                return default
            time.sleep(delay)
    return default
