"""跨数据库持久层专用 SQLAlchemy 类型。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator


class OidcIdentifierString(TypeDecorator[str]):
    """保持 OIDC issuer/subject 大小写与尾随字符精确语义的字符串类型。"""

    impl = String
    cache_ok = True

    def __init__(self, length: int) -> None:
        """按最大 Unicode 字符数限制 OIDC 身份字段。"""
        self._length = length
        super().__init__(length=length)

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        """PostgreSQL 使用精确比较文本；MySQL 使用二进制字节列。"""
        if dialect.name == "mysql":
            return dialect.type_descriptor(VARBINARY(self._length * 4))
        return dialect.type_descriptor(String(self._length))

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | bytes | None:
        """MySQL 绑定参数按 UTF-8 字节写入，其他方言保留字符串。"""
        if value is None:
            return None
        if len(value) > self._length:
            raise ValueError("OIDC identity value exceeds the configured character limit.")
        return value.encode("utf-8") if dialect.name == "mysql" else value

    def process_result_value(self, value: str | bytes | None, dialect: Dialect) -> str | None:
        """把 MySQL 二进制列还原为核心契约使用的字符串。"""
        if value is None or isinstance(value, str):
            return value
        return value.decode("utf-8")


__all__ = ["OidcIdentifierString"]
