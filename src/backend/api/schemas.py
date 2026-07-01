"""API DTO 定义。"""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登录请求。"""

    identifier: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求（public 域；主键 user_id 由后端生成，不接受客户端传入）。"""

    display_name: str
    email: str
    password: str


class UserSessionResponse(BaseModel):
    """用户会话响应（public 域）。"""

    user_id: str
    display_name: str
    email: str


class AdminSessionResponse(BaseModel):
    """管理员会话响应（admin 域）。"""

    user_id: str
    display_name: str
    username: str


class PublicUserResponse(BaseModel):
    """admin 视角下的单个 public 用户。"""

    id: str
    email: str
    display_name: str
    status: str
    created_at: str | None = None


class PublicUserListResponse(BaseModel):
    """分页的 public 用户列表。"""

    items: list[PublicUserResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Agent 数据传输对象
# ---------------------------------------------------------------------------


class AgentCreateRequest(BaseModel):
    """创建 Agent 请求。"""

    name: str
    description: str = ""
    system_prompt: str
    model: str
    tool_ids: list[str] = []


class AgentUpdateRequest(BaseModel):
    """更新 Agent 请求。"""

    name: str
    description: str = ""
    system_prompt: str
    model: str
    tool_ids: list[str] = []
    status: str | None = None


class AgentResponse(BaseModel):
    """Agent 响应。"""

    id: str
    owner_id: str
    name: str
    description: str
    system_prompt: str
    model: str
    tool_ids: list[str]
    status: str
    created_at: str | None = None
    updated_at: str | None = None


# ---------------------------------------------------------------------------
# Tool 数据传输对象
# ---------------------------------------------------------------------------


class ToolResponse(BaseModel):
    """工具响应。"""

    id: str
    name: str
    description: str
    parameters_schema: dict = {}


# ---------------------------------------------------------------------------
# Session / Message 数据传输对象
# ---------------------------------------------------------------------------


class ToolCallDto(BaseModel):
    """工具调用 DTO。"""

    id: str
    tool_name: str
    arguments: dict
    result: object | None = None
    status: str


class ChatMessageResponse(BaseModel):
    """聊天消息响应。"""

    id: str
    session_id: str
    role: str
    content: str
    tool_calls: list[ToolCallDto]
    created_at: str | None = None


class ChatSessionCreateRequest(BaseModel):
    """创建会话请求。"""

    agent_id: str
    title: str | None = None


class ChatSessionResponse(BaseModel):
    """会话响应。"""

    id: str
    owner_id: str
    agent_id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None


class ChatMessageCreateRequest(BaseModel):
    """发送消息请求。"""

    content: str


# ---------------------------------------------------------------------------
# Workflow 数据传输对象
# ---------------------------------------------------------------------------


class WorkflowNodeDto(BaseModel):
    """工作流节点 DTO。"""

    id: str | None = None
    node_type: str
    label: str
    config: dict = {}
    position_x: float = 0.0
    position_y: float = 0.0


class WorkflowEdgeDto(BaseModel):
    """工作流边 DTO。"""

    id: str | None = None
    source_node_id: str
    target_node_id: str


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求。"""

    name: str
    description: str = ""


class WorkflowUpdateRequest(BaseModel):
    """更新工作流请求。"""

    name: str
    description: str = ""
    nodes: list[WorkflowNodeDto]
    edges: list[WorkflowEdgeDto]
    status: str | None = None


class WorkflowResponse(BaseModel):
    """工作流响应。"""

    id: str
    owner_id: str
    name: str
    description: str
    status: str
    nodes: list[WorkflowNodeDto]
    edges: list[WorkflowEdgeDto]
    created_at: str | None = None
    updated_at: str | None = None
