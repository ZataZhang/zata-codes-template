"""阿里云 OSS 对象存储适配器。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from backend.core.shared.interfaces.object_storage import (
    ObjectMetadata,
    ObjectReader,
    ObjectWriteRequest,
    ReadGrant,
    ReadGrantRequest,
    UploadGrant,
    UploadGrantRequest,
)
from backend.infrastructure.config.object_storage_settings import ObjectStorageSettings

MAX_OBJECT_SIZE_BYTES = 5_000_000_000
MAX_UPLOAD_GRANT_TTL_SECONDS = 900
MAX_READ_GRANT_TTL_SECONDS = 900
OSS_POST_SIGNATURE_VERSION = "OSS4-HMAC-SHA256"


class AliyunOSSObjectStorage:
    """通过 OSS SDK 生成短期授权并读写对象。"""

    def __init__(self, settings: ObjectStorageSettings) -> None:
        """使用消费项目的 OSS 服务端凭据创建 Bucket 客户端。

        Args:
            settings (ObjectStorageSettings): 已校验的 OSS 连接与凭据配置。

        Raises:
            RuntimeError: 消费项目未安装 OSS Python SDK。
            ValueError: OSS endpoint 不是 HTTPS authority。
        """
        _validate_endpoint(settings.endpoint)
        try:
            import oss2
        except ImportError as sdk_error:
            raise RuntimeError("启用对象存储前，请在消费项目安装 oss2。") from sdk_error

        self._settings = settings
        auth = oss2.AuthV4(settings.access_key_id, settings.access_key_secret)
        self._bucket: Any = oss2.Bucket(
            auth,
            settings.endpoint,
            settings.bucket,
            region=settings.region,
        )

    def create_upload_grant(self, request: UploadGrantRequest) -> UploadGrant:
        """为单个 OSS 对象签发短期 PostObject 表单授权。

        Args:
            request (UploadGrantRequest): 项目已授权的对象键、类型、大小和有效期。

        Returns:
            UploadGrant: 浏览器直接提交给 OSS 的表单地址与字段。

        Raises:
            ValueError: 对象键、请求头、大小范围或有效期不合法。
        """
        self._validate_upload_request(request)
        issued_at = datetime.now(timezone.utc).replace(microsecond=0)
        expires_at = issued_at + timedelta(seconds=request.expires_in_seconds)
        date_scope = issued_at.strftime("%Y%m%d")
        oss_timestamp = issued_at.strftime("%Y%m%dT%H%M%SZ")
        credential_scope = (
            f"{self._settings.access_key_id}/{date_scope}/"
            f"{self._settings.region}/oss/aliyun_v4_request"
        )
        conditions: list[dict[str, str] | list[Any]] = [
            {"bucket": self._settings.bucket},
            {"x-oss-signature-version": OSS_POST_SIGNATURE_VERSION},
            {"x-oss-credential": credential_scope},
            {"x-oss-date": oss_timestamp},
            ["eq", "$key", request.object_key],
            ["eq", "$Content-Type", request.content_type],
            ["eq", "$Cache-Control", request.cache_control],
            ["eq", "$success_action_status", "201"],
            ["content-length-range", request.minimum_size_bytes, request.maximum_size_bytes],
        ]
        policy_json = json.dumps(
            {
                "expiration": expires_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "conditions": conditions,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        encoded_policy = base64.b64encode(policy_json.encode("utf-8")).decode("ascii")
        signature = _sign_post_policy(
            self._settings.access_key_secret,
            self._settings.region,
            date_scope,
            encoded_policy,
        )
        endpoint_parts = urlsplit(self._settings.endpoint)
        bucket_netloc = f"{self._settings.bucket}.{endpoint_parts.netloc}"
        post_url = urlunsplit((endpoint_parts.scheme, bucket_netloc, "/", "", ""))
        form_fields = {
            "key": request.object_key,
            "policy": encoded_policy,
            "x-oss-signature-version": OSS_POST_SIGNATURE_VERSION,
            "x-oss-credential": credential_scope,
            "x-oss-date": oss_timestamp,
            "x-oss-signature": signature,
            "success_action_status": "201",
            "Content-Type": request.content_type,
            "Cache-Control": request.cache_control,
        }
        return UploadGrant(url=post_url, form_fields=form_fields, expires_at=expires_at)

    def create_read_grant(self, request: ReadGrantRequest) -> ReadGrant:
        """为已通过领域授权的对象生成短期 OSS GET 地址。

        Args:
            request (ReadGrantRequest): 项目已授权的对象键与有效期。

        Returns:
            ReadGrant: 可由调用方直接访问 OSS 的临时 GET 地址。

        Raises:
            ValueError: 对象键或有效期不合法。
        """
        self._validate_object_key(request.object_key)
        self._validate_expiry(request.expires_in_seconds, MAX_READ_GRANT_TTL_SECONDS)
        signed_url = self._bucket.sign_url(
            "GET",
            request.object_key,
            request.expires_in_seconds,
            slash_safe=True,
        )
        return ReadGrant(
            url=signed_url,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=request.expires_in_seconds),
        )

    def public_url(self, object_key: str) -> str:
        """用项目配置的 CDN 域名生成公开对象地址。

        Args:
            object_key (str): 项目生成的不可变或唯一对象键。

        Returns:
            str: 经过 URL 编码的公开 CDN 地址。

        Raises:
            ValueError: 对象键非法或未配置 HTTPS CDN 域名。
        """
        self._validate_object_key(object_key)
        cdn_base_url = self._settings.cdn_base_url
        if not cdn_base_url:
            raise ValueError("生成公开对象地址前必须配置 cdn_base_url")
        cdn_parts = urlsplit(cdn_base_url)
        if (
            cdn_parts.scheme != "https"
            or not cdn_parts.netloc
            or cdn_parts.username
            or cdn_parts.password
            or cdn_parts.query
            or cdn_parts.fragment
        ):
            raise ValueError("cdn_base_url 必须是无凭据、无查询参数的 HTTPS 地址")
        encoded_key = quote(object_key, safe="/")
        base_path = cdn_parts.path.rstrip("/")
        public_path = f"{base_path}/{encoded_key}" if base_path else f"/{encoded_key}"
        return urlunsplit((cdn_parts.scheme, cdn_parts.netloc, public_path, "", ""))

    def head_object(self, object_key: str) -> ObjectMetadata:
        """读取对象元数据，不下载对象正文。

        Args:
            object_key (str): OSS 对象键。

        Returns:
            ObjectMetadata: 对象长度、类型、缓存头与 ETag。

        Raises:
            ValueError: 对象键非法。
        """
        self._validate_object_key(object_key)
        metadata_result = self._bucket.head_object(object_key)
        response_headers = {
            header_name.lower(): header_value
            for header_name, header_value in metadata_result.headers.items()
        }
        return ObjectMetadata(
            object_key=object_key,
            content_type=response_headers.get("content-type"),
            content_length=int(response_headers.get("content-length", "0")),
            cache_control=response_headers.get("cache-control"),
            etag=response_headers.get("etag"),
        )

    def open_object(self, object_key: str) -> ObjectReader:
        """流式读取对象，供后台任务处理。

        Args:
            object_key (str): OSS 对象键。

        Returns:
            ObjectReader: 由调用方负责关闭的 OSS 响应流。

        Raises:
            ValueError: 对象键非法。
        """
        self._validate_object_key(object_key)
        return self._bucket.get_object(object_key)

    def write_object(self, request: ObjectWriteRequest) -> None:
        """将后台处理结果写入 OSS。

        Args:
            request (ObjectWriteRequest): 对象键、字节流和对象元数据。

        Raises:
            ValueError: 对象键、内容类型或缓存头非法。
        """
        self._validate_object_key(request.object_key)
        self._validate_header_value(request.content_type, "Content-Type")
        self._validate_header_value(request.cache_control, "Cache-Control")
        self._bucket.put_object(
            request.object_key,
            request.content,
            headers={
                "Content-Type": request.content_type,
                "Cache-Control": request.cache_control,
            },
        )

    def _validate_upload_request(self, request: UploadGrantRequest) -> None:
        """校验 OSS 表单授权的对象范围、头部、大小和有效期。"""
        self._validate_object_key(request.object_key)
        self._validate_header_value(request.content_type, "Content-Type")
        self._validate_header_value(request.cache_control, "Cache-Control")
        if (
            not isinstance(request.minimum_size_bytes, int)
            or isinstance(request.minimum_size_bytes, bool)
            or not isinstance(request.maximum_size_bytes, int)
            or isinstance(request.maximum_size_bytes, bool)
            or request.minimum_size_bytes < 1
            or request.maximum_size_bytes < request.minimum_size_bytes
        ):
            raise ValueError("上传大小必须是正数且最大值不得小于最小值")
        if request.maximum_size_bytes > MAX_OBJECT_SIZE_BYTES:
            raise ValueError("OSS PostObject 单次上传上限为 5,000,000,000 字节")
        self._validate_expiry(request.expires_in_seconds, MAX_UPLOAD_GRANT_TTL_SECONDS)

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        """校验对象键长度、相对路径和控制字符。"""
        if (
            not object_key
            or object_key.startswith("/")
            or len(object_key.encode("utf-8")) > 1023
            or any(ord(character) < 32 for character in object_key)
        ):
            raise ValueError("对象键必须是非空相对键且 UTF-8 长度不超过 1023 字节")

    @staticmethod
    def _validate_header_value(header_value: str, header_name: str) -> None:
        """拒绝空值和 HTTP 头注入字符。"""
        if (
            not header_value
            or "\r" in header_value
            or "\n" in header_value
            or any(ord(character) < 32 or ord(character) == 127 for character in header_value)
        ):
            raise ValueError(f"{header_name} 必须是非空 HTTP 头值")

    @staticmethod
    def _validate_expiry(expires_in_seconds: int, maximum_ttl_seconds: int) -> None:
        """限制授权有效期为正整数并设置保守上限。"""
        if (
            not isinstance(expires_in_seconds, int)
            or isinstance(expires_in_seconds, bool)
            or expires_in_seconds < 1
            or expires_in_seconds > maximum_ttl_seconds
        ):
            raise ValueError(f"签名有效期必须在 1 到 {maximum_ttl_seconds} 秒之间")


def _sign_post_policy(
    access_key_secret: str,
    region: str,
    date_scope: str,
    encoded_policy: str,
) -> str:
    """按 OSS V4 规则对 Base64 policy 计算十六进制签名。"""
    date_key = hmac.new(
        f"aliyun_v4{access_key_secret}".encode("utf-8"),
        date_scope.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    region_key = hmac.new(date_key, region.encode("utf-8"), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"oss", hashlib.sha256).digest()
    signing_key = hmac.new(service_key, b"aliyun_v4_request", hashlib.sha256).digest()
    return hmac.new(
        signing_key,
        encoded_policy.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _validate_endpoint(endpoint: str) -> None:
    """确保签名请求只通过 HTTPS OSS authority 发送。"""
    endpoint_parts = urlsplit(endpoint)
    if (
        endpoint_parts.scheme != "https"
        or not endpoint_parts.hostname
        or endpoint_parts.username
        or endpoint_parts.password
        or endpoint_parts.path not in {"", "/"}
        or endpoint_parts.query
        or endpoint_parts.fragment
    ):
        raise ValueError("OSS endpoint 必须是无凭据、无路径、无查询参数的 HTTPS authority")
    try:
        endpoint_parts.port
    except ValueError as endpoint_error:
        raise ValueError("OSS endpoint 端口无效") from endpoint_error


__all__ = [
    "AliyunOSSObjectStorage",
    "MAX_OBJECT_SIZE_BYTES",
    "MAX_READ_GRANT_TTL_SECONDS",
    "MAX_UPLOAD_GRANT_TTL_SECONDS",
]
