"""Session / Message HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException

from backend.api.dependencies import get_current_public_user, get_session_use_case
from backend.api.schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ToolCallDto,
)
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.session.use_cases import SessionUseCase

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _format_datetime(value: object) -> str | None:
    """格式化 datetime 为 ISO 字符串。"""
    return value.isoformat() if value is not None else None


def _to_message_response(message: object) -> ChatMessageResponse:
    """将消息领域对象转换为响应 DTO。"""
    return ChatMessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        tool_calls=[
            ToolCallDto(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                result=tool_call.result,
                status=tool_call.status,
            )
            for tool_call in message.tool_calls
        ],
        created_at=_format_datetime(message.created_at),
    )


def _to_session_response(session: object) -> ChatSessionResponse:
    """将会话领域对象转换为响应 DTO。"""
    return ChatSessionResponse(
        id=session.id,
        owner_id=session.owner_id,
        agent_id=session.agent_id,
        title=session.title,
        created_at=_format_datetime(session.created_at),
        updated_at=_format_datetime(session.updated_at),
    )


@router.get("", response_model=list[ChatSessionResponse])
async def list_sessions(
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: SessionUseCase = Depends(get_session_use_case),
) -> list[ChatSessionResponse]:
    """列出当前用户的所有会话。"""
    sessions = use_case.list_sessions(current_user.user_id)
    return [_to_session_response(session) for session in sessions]


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request_payload: ChatSessionCreateRequest,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: SessionUseCase = Depends(get_session_use_case),
) -> ChatSessionResponse:
    """创建会话。"""
    try:
        session = use_case.create_session(
            owner_id=current_user.user_id,
            agent_id=request_payload.agent_id,
            title=request_payload.title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return _to_session_response(session)


@router.get("/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: SessionUseCase = Depends(get_session_use_case),
) -> ChatSessionResponse:
    """读取指定会话。"""
    try:
        session = use_case.get_session(session_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return _to_session_response(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: SessionUseCase = Depends(get_session_use_case),
) -> None:
    """删除指定会话。"""
    try:
        use_case.delete_session(session_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    session_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: SessionUseCase = Depends(get_session_use_case),
) -> list[ChatMessageResponse]:
    """读取指定会话的所有消息。"""
    try:
        messages = use_case.list_messages(session_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return [_to_message_response(message) for message in messages]


@router.post(
    "/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: str,
    request_payload: ChatMessageCreateRequest,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: SessionUseCase = Depends(get_session_use_case),
) -> ChatMessageResponse:
    """发送消息并生成 assistant 回复。"""
    try:
        message = use_case.send_message(
            session_id=session_id,
            requester_id=current_user.user_id,
            content=request_payload.content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return _to_message_response(message)
