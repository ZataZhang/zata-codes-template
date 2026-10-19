"""验证模板 MCP server 的 2026-07-28 协议入口。"""

from fastapi.testclient import TestClient
from mcp.server.transport_security import TransportSecuritySettings

from backend.engines.mcp.server import create_mcp_server


def test_mcp_server_discovery_and_tool_call_use_current_protocol() -> None:
    """实际 HTTP 入口支持发现、缓存提示与应用信息工具。"""

    mcp_server = create_mcp_server(app_name="Template Test", app_version="1.2.3")
    mcp_app = mcp_server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    request_metadata = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }

    with TestClient(mcp_app) as http_client:
        discover_response = http_client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "server/discover",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "server/discover",
                "params": {"_meta": request_metadata},
            },
        )
        assert discover_response.status_code == 200
        discover_result = discover_response.json()["result"]
        assert "2026-07-28" in discover_result["supportedVersions"]
        assert discover_result["resultType"] == "complete"

        tools_response = http_client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/list",
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {"_meta": request_metadata},
            },
        )
        assert tools_response.status_code == 200
        tools_result = tools_response.json()["result"]
        assert tools_result["resultType"] == "complete"
        assert tools_result["ttlMs"] == 60_000
        assert tools_result["cacheScope"] == "public"
        assert [tool["name"] for tool in tools_result["tools"]] == ["application_info"]

        tool_call_response = http_client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/call",
                "Mcp-Name": "application_info",
            },
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"_meta": request_metadata, "name": "application_info", "arguments": {}},
            },
        )

    assert tool_call_response.status_code == 200
    tool_call_result = tool_call_response.json()["result"]
    assert tool_call_result["resultType"] == "complete"
    assert tool_call_result["structuredContent"] == {
        "name": "Template Test",
        "version": "1.2.3",
    }
