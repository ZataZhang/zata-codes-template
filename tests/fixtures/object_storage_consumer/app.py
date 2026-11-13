"""供真实 OSS/CDN 浏览器验证使用的独立消费项目 API。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.composition.object_storage_wiring import build_object_storage
from backend.core.shared.interfaces.object_storage import (
    ObjectStorage,
    ReadGrantRequest,
    UploadGrantRequest,
)

TEST_IMAGE_CONTENT_TYPE = "image/png"
UPLOAD_GRANT_TTL_SECONDS = 300
PRIVATE_READ_TTL_SECONDS = 6
MAXIMUM_IMAGE_SIZE_BYTES = 1_048_576
OVERSIZE_CONTROL_LIMIT_BYTES = 65_536


class UploadGrantBody(BaseModel):
    """测试消费项目申请上传授权时使用的有限请求。"""

    visibility: Literal["public", "private", "oversize-control", "uncached-control"]


class UploadCompletionBody(BaseModel):
    """浏览器直传完成后提交的元数据确认。"""

    upload_id: str


class PrivateReadBody(BaseModel):
    """读取私有测试对象的消费项目请求。"""

    upload_id: str


class UploadRecord(BaseModel):
    """本测试消费项目在内存中保存的业务对象引用。"""

    upload_id: str
    object_key: str
    visibility: str
    cache_control: str
    owner_identity: str
    complete: bool = False


config_path_value = os.environ.get("OBJECT_STORAGE_E2E_CONFIG_PATH", "")
if not config_path_value:
    raise RuntimeError("OBJECT_STORAGE_E2E_CONFIG_PATH 未配置")

object_storage: ObjectStorage | None = build_object_storage(Path(config_path_value))
if object_storage is None:
    raise RuntimeError("真实 OSS 验证要求启用对象存储配置")

cdn_base_url = os.environ.get("OBJECT_STORAGE_E2E_CDN_BASE_URL", "").rstrip("/")
object_prefix = os.environ.get("OBJECT_STORAGE_E2E_OBJECT_PREFIX", "issue-59")
browser_origin = os.environ.get("OBJECT_STORAGE_E2E_BROWSER_ORIGIN", "http://127.0.0.1:19777")
upload_record_by_id: dict[str, UploadRecord] = {}

app = FastAPI(title="Object storage E2E consumer fixture")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[browser_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Test-Identity"],
)


def _require_storage() -> ObjectStorage:
    """返回已装配的真实 OSS adapter。"""
    if object_storage is None:
        raise RuntimeError("对象存储未装配")
    return object_storage


def _find_upload_record(upload_id: str) -> UploadRecord:
    """读取当前验证进程中的项目对象关系。"""
    upload_record = upload_record_by_id.get(upload_id)
    if upload_record is None:
        raise HTTPException(status_code=404, detail="Upload record not found")
    return upload_record


@app.get("/health")
def get_health() -> dict[str, str]:
    """向验证 runner 报告消费项目 API 已就绪。"""
    return {"status": "ready"}


@app.post("/api/upload-grants")
def create_upload_grant(
    request_body: UploadGrantBody,
    x_test_identity: str = Header(default=""),
) -> dict[str, Any]:
    """验证消费项目授权并返回 OSS 直传表单，不接收文件正文。"""
    if x_test_identity != "owner":
        raise HTTPException(status_code=403, detail="Upload is not authorized")

    upload_id = uuid.uuid4().hex
    object_key = f"{object_prefix}/{request_body.visibility}/{upload_id}.png"
    if request_body.visibility == "private":
        cache_control_value = "private, no-store"
    elif request_body.visibility == "uncached-control":
        cache_control_value = "no-store"
    else:
        cache_control_value = "public, max-age=31536000, immutable"
    maximum_size_bytes = (
        OVERSIZE_CONTROL_LIMIT_BYTES
        if request_body.visibility == "oversize-control"
        else MAXIMUM_IMAGE_SIZE_BYTES
    )
    upload_record = UploadRecord(
        upload_id=upload_id,
        object_key=object_key,
        visibility=request_body.visibility,
        cache_control=cache_control_value,
        owner_identity=x_test_identity,
    )
    upload_record_by_id[upload_id] = upload_record

    upload_grant = _require_storage().create_upload_grant(
        UploadGrantRequest(
            object_key=object_key,
            content_type=TEST_IMAGE_CONTENT_TYPE,
            cache_control=cache_control_value,
            minimum_size_bytes=1,
            maximum_size_bytes=maximum_size_bytes,
            expires_in_seconds=UPLOAD_GRANT_TTL_SECONDS,
        )
    )
    return {
        "upload_id": upload_id,
        "object_key": object_key,
        "upload_url": upload_grant.url,
        "form_fields": dict(upload_grant.form_fields),
        "expires_at": upload_grant.expires_at.isoformat(),
    }


@app.post("/api/upload-completions")
def complete_upload(
    request_body: UploadCompletionBody,
    x_test_identity: str = Header(default=""),
) -> dict[str, Any]:
    """验证 OSS 对象元数据并更新消费项目的业务引用状态。"""
    if x_test_identity != "owner":
        raise HTTPException(status_code=403, detail="Upload is not authorized")
    upload_record = _find_upload_record(request_body.upload_id)
    object_metadata = _require_storage().head_object(upload_record.object_key)
    if object_metadata.content_type != TEST_IMAGE_CONTENT_TYPE:
        raise HTTPException(status_code=400, detail="Uploaded content type is not allowed")
    if not 0 < object_metadata.content_length <= MAXIMUM_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Uploaded size is not allowed")
    upload_record.complete = True
    return {
        "upload_id": upload_record.upload_id,
        "object_key": upload_record.object_key,
        "content_type": object_metadata.content_type,
        "content_length": object_metadata.content_length,
        "cache_control": object_metadata.cache_control,
        "etag": object_metadata.etag,
    }


@app.get("/api/public-deliveries/{upload_id}")
def get_public_delivery(upload_id: str) -> dict[str, str]:
    """返回公开对象的 CDN 地址与缓存元数据。"""
    upload_record = _find_upload_record(upload_id)
    if not upload_record.complete or upload_record.visibility not in {"public", "uncached-control"}:
        raise HTTPException(status_code=404, detail="Public object not found")
    if not cdn_base_url:
        raise HTTPException(status_code=503, detail="CDN is not configured")
    encoded_object_key = quote(upload_record.object_key, safe="/")
    return {
        "url": f"{cdn_base_url}/{encoded_object_key}",
        "object_key": upload_record.object_key,
        "cache_control": upload_record.cache_control,
    }


@app.post("/api/private-read-grants")
def create_private_read_grant(
    request_body: PrivateReadBody,
    x_test_identity: str = Header(default=""),
) -> dict[str, str]:
    """先检查测试业务关系，再生成私有对象短时读取 URL。"""
    upload_record = _find_upload_record(request_body.upload_id)
    if (
        x_test_identity != upload_record.owner_identity
        or not upload_record.complete
        or upload_record.visibility != "private"
    ):
        raise HTTPException(status_code=403, detail="Private object is not authorized")

    read_grant = _require_storage().create_read_grant(
        ReadGrantRequest(
            object_key=upload_record.object_key,
            expires_in_seconds=PRIVATE_READ_TTL_SECONDS,
        )
    )
    return {
        "read_url": read_grant.url,
        "expires_at": read_grant.expires_at.isoformat(),
        "object_key": upload_record.object_key,
    }
