"""使用阿里云 OSS Python SDK 的对象存储适配器。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

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


class AliyunOssObjectStorage:
    """对 OSS PostObject、签名读取和后台对象操作的薄封装。"""

    def __init__(self, settings: ObjectStorageSettings) -> None:
        """创建 OSS bucket 客户端。

        Args:
            settings (ObjectStorageSettings): 服务端 OSS 设置。

        Raises:
            RuntimeError: 消费项目未安装 OSS SDK。
            ValueError: OSS endpoint 不是无凭据的 HTTPS bucket endpoint。
        """
        self._validate_endpoint(settings.endpoint)
        try:
            import oss2
        except ModuleNotFoundError as sdk_error:
            raise RuntimeError("启用对象存储前，请在消费项目安装 oss2。") from sdk_error

        self._settings = settings
        self._bucket = oss2.Bucket(
            oss2.Auth(settings.access_key_id, settings.access_key_secret),
            settings.endpoint,
            settings.bucket,
            region=settings.region,
        )

    def create_upload_grant(self, request: UploadGrantRequest) -> UploadGrant:
        """签发限定对象键、类型、大小、缓存头和过期时间的 PostObject 表单。

        Args:
            request (UploadGrantRequest): 消费项目已授权的上传参数。

        Returns:
            UploadGrant: 可直接提交给 OSS 的短时表单字段。

        Raises:
            ValueError: 上传范围、头字段或过期时间非法。
        """
        self._validate_upload_request(request)
        now_utc_datetime = datetime.now(timezone.utc)
        expires_at_datetime = now_utc_datetime + timedelta(seconds=request.expires_in_seconds)
        policy_dict = {
            "expiration": expires_at_datetime.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "conditions": [
                {"bucket": self._settings.bucket},
                ["eq", "$key", request.object_key],
                ["eq", "$content-type", request.content_type],
                ["eq", "$cache-control", request.cache_control],
                ["eq", "$success_action_status", "201"],
                [
                    "content-length-range",
                    request.minimum_size_bytes,
                    request.maximum_size_bytes,
                ],
            ],
        }
        policy_json_text = json.dumps(policy_dict, separators=(",", ":"), ensure_ascii=False)
        encoded_policy_text = base64.b64encode(policy_json_text.encode("utf-8")).decode("ascii")
        signature_text = base64.b64encode(
            hmac.new(
                self._settings.access_key_secret.encode("utf-8"),
                encoded_policy_text.encode("ascii"),
                hashlib.sha1,
            ).digest()
        ).decode("ascii")

        return UploadGrant(
            url=self._post_object_url(),
            expires_at=expires_at_datetime,
            form_fields={
                "key": request.object_key,
                "policy": encoded_policy_text,
                "OSSAccessKeyId": self._settings.access_key_id,
                "Signature": signature_text,
                "success_action_status": "201",
                "Content-Type": request.content_type,
                "Cache-Control": request.cache_control,
            },
        )

    def create_read_grant(self, request: ReadGrantRequest) -> ReadGrant:
        """签发单键、单 GET 操作的短时 OSS URL。

        Args:
            request (ReadGrantRequest): 消费项目完成领域授权后的对象键和过期时间。

        Returns:
            ReadGrant: 可直接读取私有 OSS 对象的 URL。

        Raises:
            ValueError: 对象键或过期时间非法。
        """
        self._validate_object_key(request.object_key)
        self._validate_expiry(request.expires_in_seconds, MAX_READ_GRANT_TTL_SECONDS)
        expires_at_datetime = datetime.now(timezone.utc) + timedelta(
            seconds=request.expires_in_seconds
        )
        signed_read_url = self._bucket.sign_url(
            "GET", request.object_key, request.expires_in_seconds
        )
        return ReadGrant(url=signed_read_url, expires_at=expires_at_datetime)

    def head_object(self, object_key: str) -> ObjectMetadata:
        """仅查询对象头信息，不读取对象正文。

        Args:
            object_key (str): 已保存到消费项目业务记录中的对象键。

        Returns:
            ObjectMetadata: Content-Type、长度、缓存策略和 ETag。
        """
        self._validate_object_key(object_key)
        object_head_result = self._bucket.head_object(object_key)
        return ObjectMetadata(
            object_key=object_key,
            content_type=object_head_result.content_type,
            content_length=int(object_head_result.content_length or 0),
            cache_control=object_head_result.headers.get("Cache-Control"),
            etag=object_head_result.etag,
        )

    def open_object(self, object_key: str) -> ObjectReader:
        """通过 OSS SDK 流式打开对象，供后台工作进程读取。

        Args:
            object_key (str): 需要处理的对象键。

        Returns:
            ObjectReader: 由调用方关闭的网络读取句柄。
        """
        self._validate_object_key(object_key)
        return self._bucket.get_object(object_key)

    def write_object(self, request: ObjectWriteRequest) -> None:
        """通过 OSS SDK 流式写入后台处理结果及缓存元数据。

        Args:
            request (ObjectWriteRequest): 对象键、字节流和 HTTP 元数据。
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

    def _post_object_url(self) -> str:
        """生成 bucket 域名形式的 PostObject 地址。"""
        endpoint_parts = urlsplit(self._settings.endpoint)
        endpoint_host_text, endpoint_port = self._validate_endpoint(self._settings.endpoint)
        endpoint_authority_text = endpoint_host_text
        if endpoint_port is not None:
            endpoint_authority_text = f"{endpoint_host_text}:{endpoint_port}"
        bucket_host_text = endpoint_authority_text
        if not endpoint_host_text.startswith(f"{self._settings.bucket}."):
            bucket_host_text = f"{self._settings.bucket}.{endpoint_authority_text}"
        return urlunsplit((endpoint_parts.scheme, bucket_host_text, "", "", ""))

    @staticmethod
    def _validate_endpoint(endpoint_url_text: str) -> tuple[str, int | None]:
        """要求 OSS endpoint 使用无 URL 凭据的 HTTPS authority。"""
        endpoint_parts = urlsplit(endpoint_url_text)
        if (
            endpoint_parts.scheme != "https"
            or not endpoint_parts.hostname
            or endpoint_parts.username
            or endpoint_parts.password
            or endpoint_parts.path not in {"", "/"}
            or endpoint_parts.query
            or endpoint_parts.fragment
        ):
            raise ValueError("OSS endpoint 必须是无凭据、无路径的 HTTPS 地址")
        try:
            endpoint_port = endpoint_parts.port
        except ValueError as endpoint_error:
            raise ValueError("OSS endpoint 端口无效") from endpoint_error
        return endpoint_parts.hostname, endpoint_port

    def _validate_upload_request(self, request: UploadGrantRequest) -> None:
        """校验签发授权的输入，避免无限期或无限大小的上传策略。"""
        self._validate_object_key(request.object_key)
        self._validate_header_value(request.content_type, "Content-Type")
        self._validate_header_value(request.cache_control, "Cache-Control")
        if (
            request.minimum_size_bytes < 1
            or request.maximum_size_bytes < request.minimum_size_bytes
        ):
            raise ValueError("上传大小必须是正数且最大值不得小于最小值")
        if request.maximum_size_bytes > MAX_OBJECT_SIZE_BYTES:
            raise ValueError("OSS PostObject 单次上传上限为 5 GB")
        self._validate_expiry(request.expires_in_seconds, MAX_UPLOAD_GRANT_TTL_SECONDS)

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        """校验对象键非空、无首斜线且不超过 OSS 限制。"""
        if not object_key or object_key.startswith("/") or len(object_key.encode("utf-8")) > 1023:
            raise ValueError("对象键必须是非空相对键且 UTF-8 长度不超过 1023 字节")

    @staticmethod
    def _validate_header_value(header_value: str, header_name: str) -> None:
        """拒绝空值和 HTTP 头注入字符。"""
        if not header_value or "\r" in header_value or "\n" in header_value:
            raise ValueError(f"{header_name} 必须是非空 HTTP 头值")

    @staticmethod
    def _validate_expiry(expires_in_seconds: int, maximum_ttl_seconds: int) -> None:
        """限制签名有效期为正整数并设置保守上限。"""
        if (
            not isinstance(expires_in_seconds, int)
            or isinstance(expires_in_seconds, bool)
            or expires_in_seconds < 1
            or expires_in_seconds > maximum_ttl_seconds
        ):
            raise ValueError(f"签名有效期必须在 1 到 {maximum_ttl_seconds} 秒之间")


__all__ = ["AliyunOssObjectStorage"]
