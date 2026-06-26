"""双认证域 API 测试：注册契约、越权隔离、禁用即时失效。"""

from __future__ import annotations

import uuid
from typing import Callable

from fastapi.testclient import TestClient


def test_public_register_without_user_id_then_me(
    build_client: Callable[[], TestClient],
    unique_email: Callable[[], str],
) -> None:
    """public 注册请求体不含 user_id，主键由后端生成；随后 /auth/me 可用。"""
    client = build_client()
    email = unique_email()
    register_response = client.post(
        "/auth/register",
        json={"display_name": "Alice", "email": email, "password": "secret123"},
    )
    assert register_response.status_code == 201, register_response.text
    body = register_response.json()
    assert body["email"] == email
    assert body["user_id"]  # 后端生成的 UUID 主键

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email


def test_public_session_cannot_reach_admin_api(
    build_client: Callable[[], TestClient],
    unique_email: Callable[[], str],
) -> None:
    """持 public 会话的请求访问 admin 端点应被拒（401）。"""
    client = build_client()
    client.post(
        "/auth/register",
        json={"display_name": "Bob", "email": unique_email(), "password": "secret123"},
    )
    assert client.get("/admin/users").status_code == 401


def test_public_token_rejected_as_admin_cookie(
    build_client: Callable[[], TestClient],
    unique_email: Callable[[], str],
) -> None:
    """把 public 会话 token 伪装成 admin Cookie 仍无法通过 admin 守卫。

    验证物理隔离：两域共用同一 Redis 实例但命名空间前缀不同，admin 守卫
    在 admin 命名空间查不到 public token。
    """
    client = build_client()
    client.post(
        "/auth/register",
        json={"display_name": "Cara", "email": unique_email(), "password": "secret123"},
    )
    public_token = client.cookies.get("session_id")
    assert public_token

    forge_client = build_client()
    forge_client.cookies.set("admin_session_id", public_token)
    assert forge_client.get("/admin/users").status_code == 401


def test_admin_session_cannot_reach_business_api(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """持 admin 会话的请求访问 public 业务 API 应被拒（401）。"""
    username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(username, "adminpass1")
    client = build_client()
    login_response = client.post(
        "/admin/auth/login", json={"identifier": username, "password": "adminpass1"}
    )
    assert login_response.status_code == 200
    # 仅持 admin_session_id，业务 API 走 public 守卫
    assert client.get("/agents").status_code == 401


def test_admin_login_me_and_no_register(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """admin 可登录并取会话；admin 域不存在注册端点。"""
    username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(username, "adminpass1")
    client = build_client()

    login_response = client.post(
        "/admin/auth/login", json={"identifier": username, "password": "adminpass1"}
    )
    assert login_response.status_code == 200
    assert login_response.json()["username"] == username

    me_response = client.get("/admin/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == username

    # admin 域不开放注册
    register_response = client.post(
        "/admin/auth/register",
        json={"display_name": "x", "email": "x@example.com", "password": "secret123"},
    )
    assert register_response.status_code == 404


def test_disabled_public_user_session_invalidated(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
) -> None:
    """admin 禁用 public 用户后，其既有会话下次请求立即失效。

    单 client 同时持 public 与 admin 两个 Cookie：经真实 admin 端点禁用，再
    用 public 会话访问 /auth/me 应立即 401。
    """
    client = build_client()
    email = unique_email()
    register_response = client.post(
        "/auth/register",
        json={"display_name": "Dan", "email": email, "password": "secret123"},
    )
    user_id = register_response.json()["user_id"]
    assert client.get("/auth/me").status_code == 200

    admin_username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(admin_username, "adminpass1")
    assert (
        client.post(
            "/admin/auth/login",
            json={"identifier": admin_username, "password": "adminpass1"},
        ).status_code
        == 200
    )
    assert client.post(f"/admin/users/{user_id}/disable").status_code == 200

    # public 会话（同一 client 的 session_id Cookie）立即失效
    assert client.get("/auth/me").status_code == 401


def test_wrong_password_rejected(
    build_client: Callable[[], TestClient],
    unique_email: Callable[[], str],
) -> None:
    """错误密码登录返回 401。"""
    client = build_client()
    email = unique_email()
    client.post(
        "/auth/register",
        json={"display_name": "Eve", "email": email, "password": "secret123"},
    )
    login_response = client.post(
        "/auth/login", json={"identifier": email, "password": "wrong-password"}
    )
    assert login_response.status_code == 401
