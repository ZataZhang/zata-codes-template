"""Admin 管理 public 用户 API 测试。"""

from __future__ import annotations

import uuid
from typing import Callable

from fastapi.testclient import TestClient


def _login_admin(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> TestClient:
    """种入并登录一个管理员，返回持 admin 会话的客户端。"""
    username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(username, "adminpass1")
    client = build_client()
    login_response = client.post(
        "/admin/auth/login", json={"identifier": username, "password": "adminpass1"}
    )
    assert login_response.status_code == 200
    return client


def test_admin_lists_and_toggles_public_user(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
) -> None:
    """admin 可按关键字列出 public 用户并启用 / 禁用。"""
    admin_client = _login_admin(build_client, seed_admin)

    public_client = build_client()
    email = unique_email()
    register_response = public_client.post(
        "/auth/register",
        json={"display_name": "Managed", "email": email, "password": "secret123"},
    )
    user_id = register_response.json()["user_id"]

    list_response = admin_client.get("/admin/users", params={"keyword": email})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] >= 1
    assert any(item["id"] == user_id for item in list_body["items"])

    disable_response = admin_client.post(f"/admin/users/{user_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["status"] == "disabled"

    get_response = admin_client.get(f"/admin/users/{user_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "disabled"

    enable_response = admin_client.post(f"/admin/users/{user_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["status"] == "active"


def test_admin_get_unknown_user_returns_404(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """查询不存在的 public 用户返回 404。"""
    admin_client = _login_admin(build_client, seed_admin)
    assert admin_client.get("/admin/users/does-not-exist").status_code == 404


def test_admin_user_management_requires_admin_session(
    build_client: Callable[[], TestClient],
) -> None:
    """无 admin 会话访问管理端点返回 401。"""
    client = build_client()
    assert client.get("/admin/users").status_code == 401
    assert client.post("/admin/users/whatever/disable").status_code == 401


def test_status_filter_disabled(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
) -> None:
    """status=disabled 过滤仅返回被禁用用户。"""
    admin_client = _login_admin(build_client, seed_admin)

    public_client = build_client()
    email = unique_email()
    register_response = public_client.post(
        "/auth/register",
        json={"display_name": "Filterable", "email": email, "password": "secret123"},
    )
    user_id = register_response.json()["user_id"]
    admin_client.post(f"/admin/users/{user_id}/disable")

    filtered_response = admin_client.get(
        "/admin/users", params={"keyword": email, "status": "disabled"}
    )
    assert filtered_response.status_code == 200
    items = filtered_response.json()["items"]
    assert any(item["id"] == user_id for item in items)
    assert all(item["status"] == "disabled" for item in items)
