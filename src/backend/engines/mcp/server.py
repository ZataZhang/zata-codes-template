"""基于官方 MCP Python SDK 创建模板 MCP server。"""

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer


def create_mcp_server(*, app_name: str, app_version: str) -> MCPServer:
    """创建一个可扩展的 MCP server，并附带安全的应用信息工具。

    Args:
        app_name: 对外展示的应用名称。
        app_version: 对外展示的应用版本。

    Returns:
        支持当前 MCP 协议并兼容旧版客户端的 server。
    """

    mcp_server = MCPServer(
        name=app_name,
        version=app_version,
        instructions="提供应用基础信息；派生项目可在此 server 上注册领域工具。",
        cache_hints={
            "server/discover": CacheHint(ttl_ms=3_600_000, scope="public"),
            "tools/list": CacheHint(ttl_ms=60_000, scope="public"),
        },
    )

    @mcp_server.tool(name="application_info")
    def get_application_info() -> dict[str, str]:
        """返回应用名称与版本。"""

        return {"name": app_name, "version": app_version}

    return mcp_server


__all__ = ["create_mcp_server"]
