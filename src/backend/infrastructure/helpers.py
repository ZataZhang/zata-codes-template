"""可复用的基础设施层辅助函数。"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional


def parse_datetime(date_str: str, fmt: str = "%Y/%m/%d %H:%M") -> Optional[datetime]:
    """将日期时间字符串解析为 ``datetime`` 对象。

    Args:
        date_str (str): 输入的日期时间字符串。
        fmt (str): 日期时间格式字符串。

    Returns:
        Optional[datetime]: 解析后的日期时间；解析失败时返回 ``None``。
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, fmt)
    except ValueError:
        return None


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全地解析 JSON 文本。

    Args:
        json_str (str): 原始 JSON 字符串。
        default (Any): 解析失败时返回的值。

    Returns:
        Any: 解析后的对象或 ``default``。
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_get_nested(source_dict: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """安全地读取嵌套字典路径。

    Args:
        source_dict (dict[str, Any]): 源字典。
        keys (list[str]): 嵌套键路径。
        default (Any): 任意一次查找失败时返回的值。

    Returns:
        Any: 解析后的嵌套值或 ``default``。
    """
    try:
        resolved_value: Any = source_dict
        for nested_key in keys:
            resolved_value = resolved_value[nested_key]
        return resolved_value
    except (KeyError, TypeError, IndexError):
        return default


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """将字符串截断到最大长度。

    Args:
        text (str): 原始字符串。
        max_length (int): 最大输出长度。
        suffix (str): 截断后追加的后缀。

    Returns:
        str: 截断后的字符串。
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def normalize_whitespace(text: str) -> str:
    """将连续空白折叠为单个空格。

    Args:
        text (str): 原始字符串。

    Returns:
        str: 规范化后的字符串。
    """
    return " ".join(text.split())


def chunks(values: list[Any], size: int) -> list[list[Any]]:
    """将列表按固定大小分块。

    Args:
        values (list[Any]): 输入列表。
        size (int): 每块大小。

    Returns:
        list[list[Any]]: 分块后的列表。
    """
    return [values[index : index + size] for index in range(0, len(values), size)]


def retry_on_exception(
    func: Callable[[], Any],
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    default: Any = None,
) -> Any:
    """当指定异常发生时重试执行可调用对象。

    Args:
        func (Callable[[], Any]): 待执行的可调用对象。
        max_retries (int): 最大重试次数。
        delay (float): 两次重试之间的间隔秒数。
        exceptions (tuple[type[BaseException], ...]): 允许重试的异常类型。
        default (Any): 最终失败后的回退值。

    Returns:
        Any: 可调用对象的结果或 ``default``。
    """
    import time

    for attempt_index in range(max_retries):
        try:
            return func()
        except exceptions:
            if attempt_index == max_retries - 1:
                return default
            time.sleep(delay)
    return default
