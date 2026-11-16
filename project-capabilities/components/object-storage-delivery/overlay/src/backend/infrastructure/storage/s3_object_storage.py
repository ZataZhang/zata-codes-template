"""基于 boto3 的 S3 兼容对象存储适配器。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

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
LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})


class S3CompatibleObjectStorage:
    """对 S3 预签名上传、预签名读取和后台对象操作的薄封装。"""

    def __init__(self, settings: ObjectStorageSettings) -> None:
        """创建 S3 兼容客户端。

        Args:
            settings (ObjectStorageSettings): 服务端 S3 兼容存储设置。

        Raises:
            RuntimeError: 消费项目未安装 boto3。
            ValueError: endpoint 不是允许的 S3 兼容服务地址。
        """
        self._validate_endpoint(settings.endpoint, settings.allow_insecure_http)
        try:
            import boto3
            from botocore.config import Config
        except ModuleNotFoundError as sdk_error:
            raise RuntimeError("启用对象存储前，请在消费项目安装 boto3。") from sdk_error

        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint,
            region_name=settings.region,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.access_key_secret,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.addressing_style},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def create_upload_grant(self, request: UploadGrantRequest) -> UploadGrant:
        """签发限定对象键、类型、大小、缓存头和过期时间的 POST policy。

        Args:
            request (UploadGrantRequest): 消费项目已授权的上传参数。

        Returns:
            UploadGrant: 可直接提交给 S3 兼容存储的短时表单字段。

        Raises:
            ValueError: 上传范围、头字段或过期时间非法。
        """
        self._validate_upload_request(request)
        expires_at_datetime = datetime.now(timezone.utc) + timedelta(
            seconds=request.expires_in_seconds
        )
        presigned_post = self._client.generate_presigned_post(
            Bucket=self._settings.bucket,
            Key=request.object_key,
            Fields={
                "Content-Type": request.content_type,
                "Cache-Control": request.cache_control,
                "success_action_status": "201",
            },
            Conditions=[
                {"bucket": self._settings.bucket},
                ["eq", "$key", request.object_key],
                ["eq", "$Content-Type", request.content_type],
                ["eq", "$Cache-Control", request.cache_control],
                ["eq", "$success_action_status", "201"],
                [
                    "content-length-range",
                    request.minimum_size_bytes,
                    request.maximum_size_bytes,
                ],
            ],
            ExpiresIn=request.expires_in_seconds,
        )
        return UploadGrant(
            url=presigned_post["url"],
            expires_at=expires_at_datetime,
            form_fields=presigned_post["fields"],
        )

    def create_read_grant(self, request: ReadGrantRequest) -> ReadGrant:
        """签发单键、单 GET 操作的短时预签名 URL。

        Args:
            request (ReadGrantRequest): 消费项目完成领域授权后的对象键和过期时间。

        Returns:
            ReadGrant: 可直接读取私有对象的 URL。

        Raises:
            ValueError: 对象键或过期时间非法。
        """
        self._validate_object_key(request.object_key)
        self._validate_expiry(request.expires_in_seconds, MAX_READ_GRANT_TTL_SECONDS)
        expires_at_datetime = datetime.now(timezone.utc) + timedelta(
            seconds=request.expires_in_seconds
        )
        signed_read_url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._settings.bucket, "Key": request.object_key},
            ExpiresIn=request.expires_in_seconds,
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
        object_head_result = self._client.head_object(Bucket=self._settings.bucket, Key=object_key)
        return ObjectMetadata(
            object_key=object_key,
            content_type=object_head_result.get("ContentType"),
            content_length=int(object_head_result.get("ContentLength") or 0),
            cache_control=object_head_result.get("CacheControl"),
            etag=object_head_result.get("ETag"),
        )

    def open_object(self, object_key: str) -> ObjectReader:
        """通过 S3 客户端流式打开对象，供后台工作进程读取。

        Args:
            object_key (str): 需要处理的对象键。

        Returns:
            ObjectReader: 由调用方关闭的网络读取句柄。
        """
        self._validate_object_key(object_key)
        response = self._client.get_object(Bucket=self._settings.bucket, Key=object_key)
        return response["Body"]

    def write_object(self, request: ObjectWriteRequest) -> None:
        """通过 S3 客户端写入后台处理结果及缓存元数据。

        Args:
            request (ObjectWriteRequest): 对象键、字节流和 HTTP 元数据。
        """
        self._validate_object_key(request.object_key)
        self._validate_header_value(request.content_type, "Content-Type")
        self._validate_header_value(request.cache_control, "Cache-Control")
        self._client.put_object(
            Bucket=self._settings.bucket,
            Key=request.object_key,
            Body=request.content,
            ContentType=request.content_type,
            CacheControl=request.cache_control,
        )

    @staticmethod
    def _validate_endpoint(endpoint_url_text: str, allow_insecure_http: bool) -> None:
        """要求 endpoint 默认使用 HTTPS，仅显式允许 loopback HTTP。"""
        endpoint_parts = urlsplit(endpoint_url_text)
        is_loopback_host = endpoint_parts.hostname in LOOPBACK_HOSTNAMES
        scheme_is_allowed = endpoint_parts.scheme == "https" or (
            allow_insecure_http and endpoint_parts.scheme == "http" and is_loopback_host
        )
        if (
            not scheme_is_allowed
            or not endpoint_parts.hostname
            or endpoint_parts.username
            or endpoint_parts.password
            or endpoint_parts.path not in {"", "/"}
            or endpoint_parts.query
            or endpoint_parts.fragment
        ):
            raise ValueError(
                "S3 endpoint 必须是无凭据、无路径的 HTTPS 地址；"
                "仅当 allow_insecure_http=true 时允许 loopback HTTP"
            )
        try:
            endpoint_parts.port
        except ValueError as endpoint_error:
            raise ValueError("S3 endpoint 端口无效") from endpoint_error

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
            raise ValueError("S3 POST policy 单次上传上限为 5 GB")
        self._validate_expiry(request.expires_in_seconds, MAX_UPLOAD_GRANT_TTL_SECONDS)

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        """校验对象键非空、无首斜线且不超过 S3 限制。"""
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


__all__ = ["S3CompatibleObjectStorage"]
