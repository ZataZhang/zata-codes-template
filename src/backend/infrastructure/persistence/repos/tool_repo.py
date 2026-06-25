"""Tool Repository SQLAlchemy 实现。"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy.orm import Session

from backend.core.shared.interfaces.tool_repository import ToolRepository
from backend.core.shared.models.agent import ToolDefinition
from backend.infrastructure.persistence.models.tool import ToolModel


def _to_tool_definition(model: ToolModel) -> ToolDefinition:
    """将 ORM 模型转换为 ToolDefinition。"""
    return ToolDefinition(
        id=model.id,
        name=model.name,
        description=model.description,
        schema=model.schema or {},
    )


class SqlAlchemyToolRepository(ToolRepository):
    """基于 SQLAlchemy 的工具元数据 Repository 实现。"""

    def __init__(self, db_session: Session) -> None:
        self._session = db_session

    def list_tools(self) -> Sequence[ToolDefinition]:
        """返回所有工具元数据。"""
        models = self._session.query(ToolModel).order_by(ToolModel.name).all()
        return [_to_tool_definition(model) for model in models]

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """根据 ID 读取工具元数据。"""
        model = self._session.get(ToolModel, tool_id)
        if model is None:
            return None
        return _to_tool_definition(model)
