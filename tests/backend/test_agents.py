"""Agent API 测试。"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_agent_crud_lifecycle() -> None:
    """测试 Agent 创建、读取、列表和删除生命周期。"""
    from backend.main import create_app

    client = TestClient(create_app())
    email: str = f"agenttest-{uuid.uuid4().hex[:12]}@example.com"

    register_response = client.post(
        "/auth/register",
        json={
            "display_name": "Agent Test",
            "email": email,
            "password": "testpass123",
        },
    )
    assert register_response.status_code == 201

    create_response = client.post(
        "/agents",
        json={
            "name": "Test Agent",
            "description": "A test agent.",
            "system_prompt": "You are a test agent.",
            "model": "openai/gpt-4o-mini",
            "tool_ids": [],
        },
    )
    assert create_response.status_code == 201
    agent = create_response.json()
    assert agent["name"] == "Test Agent"

    list_response = client.get("/agents")
    assert list_response.status_code == 200
    agents = list_response.json()
    assert any(item["id"] == agent["id"] for item in agents)

    get_response = client.get(f"/agents/{agent['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == agent["id"]

    delete_response = client.delete(f"/agents/{agent['id']}")
    assert delete_response.status_code == 204
