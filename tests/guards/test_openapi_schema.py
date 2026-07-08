"""守护公开 HTTP 契约（OpenAPI schema）的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

This test guards against accidental breaking changes to the public HTTP
contract: it loads the FastAPI application without starting a server and
asserts that critical paths, tags, and response schemas are present.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.main import create_app

# Paths that every consumer of the template API can rely on.
REQUIRED_PATHS = {
    "/health",
    "/ready",
    "/live",
}

# Tags that group the documented operations.
REQUIRED_TAGS = {
    "observability",
}


def _get_openapi_schema() -> dict[str, Any]:
    """Build the app and return its generated OpenAPI schema."""
    app = create_app()
    return app.openapi()


def test_openapi_schema_has_required_paths() -> None:
    schema = _get_openapi_schema()
    paths = set(schema.get("paths", {}).keys())

    missing = REQUIRED_PATHS - paths
    assert not missing, f"OpenAPI schema missing required paths: {missing}"


def test_openapi_schema_has_required_tags() -> None:
    schema = _get_openapi_schema()
    used_tags: set[str] = set()
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                used_tags.update(operation.get("tags", []))

    missing = REQUIRED_TAGS - used_tags
    assert not missing, f"OpenAPI schema missing required tags: {missing}"


def test_health_endpoint_contract() -> None:
    schema = _get_openapi_schema()
    health_methods = schema["paths"]["/health"]

    assert "get" in health_methods, "/health must expose GET"
    get_operation = health_methods["get"]
    assert "observability" in get_operation.get("tags", []), "health tag mismatch"

    responses = get_operation.get("responses", {})
    assert "200" in responses, "/health must document a 200 response"


def test_health_endpoint_returns_ok() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
