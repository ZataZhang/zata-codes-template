"""Agent API 测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.infrastructure.persistence.database import (
    Base,
    engine,
)


@pytest.fixture(scope="module", autouse=True)
def setup_database() -> None:
    """创建测试数据库表。"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_agent_crud_lifecycle() -> None:
    """测试 Agent 创建、读取、列表和删除生命周期。"""
    from backend.main import create_app

    app = create_app()
    client = TestClient(app)

    register_response = client.post(
        "/auth/register",
        json={
            "user_id": "agenttest",
            "display_name": "Agent Test",
            "email": "agenttest@example.com",
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
