"""对象存储能力的 SDK 无关核心契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import BinaryIO, Mapping, Protocol


@dataclass(frozen=True)
class UploadGrantRequest:
    """生成一次受限浏览器上传授权所需的项目输入。"""

    object_key: str
    content_type: str
    cache_control: str
    maximum_size_bytes: int
    expires_in_seconds: int
    minimum_size_bytes: int = 1


@dataclass(frozen=True)
class UploadGrant:
    """浏览器直接提交给对象存储的短时表单授权。"""

    url: str
    form_fields: Mapping[str, str] = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class ReadGrantRequest:
    """生成一次短时私有对象读取授权所需的项目输入。"""

    object_key: str
    expires_in_seconds: int


@dataclass(frozen=True)
class ReadGrant:
    """浏览器或受信调用方直接读取私有对象的短时授权。"""

    url: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class ObjectMetadata:
    """对象存储返回的轻量元数据，不包含对象正文。"""

    object_key: str
    content_type: str | None
    content_length: int
    cache_control: str | None
    etag: str | None


@dataclass(frozen=True)
class ObjectWriteRequest:
    """后台处理任务写入对象所需的内容与元数据。"""

    object_key: str
    content: bytes | BinaryIO
    content_type: str
    cache_control: str


class ObjectReader(Protocol):
    """对象存储返回的流式读取句柄。"""

    def read(self, size: int = -1) -> bytes:
        """读取最多指定字节数；省略大小时读取剩余正文。"""
        ...

    def close(self) -> None:
        """关闭底层网络响应。"""
        ...


class ObjectStorage(Protocol):
    """提供短时授权、对象元数据与后台字节处理能力。"""

    def create_upload_grant(self, request: UploadGrantRequest) -> UploadGrant:
        """为项目已授权的单个对象键生成受限上传表单。"""
        ...

    def create_read_grant(self, request: ReadGrantRequest) -> ReadGrant:
        """为项目已完成领域授权的单个对象键生成短时读取 URL。"""
        ...

    def head_object(self, object_key: str) -> ObjectMetadata:
        """查询对象元数据，不下载对象正文。"""
        ...

    def open_object(self, object_key: str) -> ObjectReader:
        """以流方式读取对象，供后台工作进程处理。"""
        ...

    def write_object(self, request: ObjectWriteRequest) -> None:
        """以流方式写入对象，供后台工作进程保存处理结果。"""
        ...


__all__ = [
    "ObjectMetadata",
    "ObjectReader",
    "ObjectStorage",
    "ObjectWriteRequest",
    "ReadGrant",
    "ReadGrantRequest",
    "UploadGrant",
    "UploadGrantRequest",
]
