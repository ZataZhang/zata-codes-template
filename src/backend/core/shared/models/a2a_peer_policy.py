"""A2A 对端登记与调用共用的 URL 信任边界校验。"""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit


class A2APeerUrlValidationError(ValueError):
    """登记的 A2A Card 和 endpoint URL 不符合目录契约。"""


def validate_a2a_peer_urls(*, card_url: str, endpoint_url: str) -> tuple[str, str]:
    """验证不含内嵌凭据的 HTTP(S) URL，并要求 Card 与 endpoint 同源。

    Args:
        card_url (str): 外部 Agent Card 的登记地址。
        endpoint_url (str): 外部 Agent 的 A2A REST endpoint。

    Returns:
        tuple[str, str]: 去除首尾空白后的 Card 与 endpoint URL。

    Raises:
        A2APeerUrlValidationError: URL 无效、包含凭据或查询参数，或两者不同源。
    """
    normalized_card_url = card_url.strip()
    normalized_endpoint_url = endpoint_url.strip()
    parsed_card_url = _parse_registered_peer_url(normalized_card_url)
    parsed_endpoint_url = _parse_registered_peer_url(normalized_endpoint_url)
    if _url_origin(parsed_card_url) != _url_origin(parsed_endpoint_url):
        raise A2APeerUrlValidationError("peer_url_origin_mismatch")
    return normalized_card_url, normalized_endpoint_url


def _parse_registered_peer_url(url: str) -> SplitResult:
    """拒绝会被管理接口回显到浏览器的 URL 凭据和不支持的语法。"""
    if not url or any(character.isspace() or ord(character) < 0x20 for character in url):
        raise A2APeerUrlValidationError("peer_url_invalid")
    try:
        parsed_url = urlsplit(url)
        hostname = parsed_url.hostname
        port = parsed_url.port
    except ValueError as parse_error:
        raise A2APeerUrlValidationError("peer_url_invalid") from parse_error
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or not hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
        or port == 0
    ):
        raise A2APeerUrlValidationError("peer_url_invalid")
    return parsed_url


def _url_origin(parsed_url: SplitResult) -> tuple[str, str, int]:
    """生成 Card 与 REST endpoint 比较用的标准 origin。"""
    hostname = (parsed_url.hostname or "").lower().rstrip(".")
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    return parsed_url.scheme, hostname, port


__all__ = ["A2APeerUrlValidationError", "validate_a2a_peer_urls"]
