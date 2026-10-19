# Model Context Protocol

模板通过官方 MCP Python SDK v2 提供 MCP server，当前锁定的 SDK 为 `2.3.0`，协议版本为 `2026-07-28`。SDK 负责协议校验、现代 `server/discover` 发现流程、逐请求 `_meta`、Streamable HTTP 标准头、缓存提示及多轮往返请求；同一个 server 也兼容旧版 `initialize` 客户端。

## 当前入口

默认 MCP endpoint 为 `POST /api/mcp`，使用无会话的 Streamable HTTP。模板只注册 `application_info` 工具，返回应用名称和版本。工具在 `src/backend/engines/mcp/server.py` 中注册，派生项目可以在同一个 `MCPServer` 上添加领域工具、资源和 prompts。

SDK 2.x 的核心实现支持 MCP `2026-07-28`，并保留较早的 Streamable HTTP 与 stdio 协议版本。模板只开放 HTTP endpoint；HTTP+SSE 已被 MCP 规范弃用，不作为新入口提供。Tasks 属于独立扩展，当前 SDK 版本尚未实现，因此模板不声明该扩展。

## 从 MCP 客户端连接

推荐使用官方 SDK 客户端。客户端默认先发 `server/discover`，并在连接旧版服务器时回退到 `initialize`：

```python
from mcp import Client


async with Client("http://localhost:8000/api/mcp") as mcp_client:
    available_tools = await mcp_client.list_tools()
    tool_result = await mcp_client.call_tool("application_info", {})
```

新版请求使用 `2026-07-28` 协议版本、每请求客户端元数据和 `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name` HTTP headers。server 无需 `initialize` 握手或 `Mcp-Session-Id`，可以由任意应用实例独立处理请求。工具列表与发现结果带有 SDK 生成的缓存提示。

## 注册工具

在 `create_mcp_server()` 中使用 SDK 的 decorator 注册工具。工具参数类型会生成 MCP 输入 schema，函数说明会作为工具描述：

```python
@mcp_server.tool()
def lookup_order(order_id: str) -> dict[str, str]:
    """查询订单状态。"""
    return {"order_id": order_id, "status": "processing"}
```

模板默认未接入用户身份认证，当前只暴露应用名称和版本。派生项目在注册返回用户数据、凭证或其他敏感信息的工具前，必须先为 MCP 请求加入与该工具匹配的认证和授权策略。

## Host 与 Origin 安全设置

SDK 的 DNS rebinding 防护默认开启。`config.toml` 的 `[mcp]` 默认只允许本机 Host；部署到域名后，应将实际反向代理 Host 明确加入白名单：

```toml
[mcp]
allowed_hosts = ["mcp.example.com"]
allowed_origins = ["https://mcp.example.com"]
```

也可以用 `MCP_ALLOWED_HOSTS` 与 `MCP_ALLOWED_ORIGINS` 环境变量覆盖，值使用 JSON 字符串数组。不要使用 `*` 放开 Host / Origin 校验。

## 主要实现位置

- `src/backend/engines/mcp/server.py`：构建 MCP server 并注册模板工具。
- `src/backend/composition/app_factory.py`：挂载 `/api/mcp`，并在应用 lifespan 中启动 SDK session manager。
- `src/backend/infrastructure/config/settings.py`：加载 MCP Host / Origin allowlist。
- `tests/backend/test_mcp_server.py`：通过 Streamable HTTP 验证发现、缓存字段和工具调用。
