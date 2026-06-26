"""Tool HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_current_public_user, get_tool_registry
from backend.api.schemas import ToolResponse
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.shared.interfaces.tool_registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> list[ToolResponse]:
    """列出所有可用工具。"""
    tools = registry.list_tools()
    return [
        ToolResponse(
            id=tool.id,
            name=tool.name,
            description=tool.description,
            parameters_schema=tool.schema,
        )
        for tool in tools
    ]
