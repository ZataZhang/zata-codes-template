"""平台管理员注册策略管理路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT, HTTP_503_SERVICE_UNAVAILABLE

from backend.api.dependencies import get_current_platform_admin, get_registration_policy_service
from backend.api.schemas import RegistrationPolicyRequest, RegistrationPolicyResponse
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.registration_policy import InvalidEmailDomains, RegistrationPolicy
from backend.core.auth.registration_policy_service import (
    RegistrationPolicyService,
    RegistrationPolicyUnavailable,
)

logger = logging.getLogger(__name__)

registration_policy_router = APIRouter(
    prefix="/admin/settings/registration-policy",
    tags=["registration-policy"],
)


def _to_registration_policy_response(policy: RegistrationPolicy) -> RegistrationPolicyResponse:
    """把注册策略值对象映射为管理端响应 DTO。"""
    return RegistrationPolicyResponse(
        registration_mode=policy.registration_mode,
        allowed_email_domains=list(policy.allowed_email_domains),
    )


def _raise_policy_unavailable(error: RegistrationPolicyUnavailable) -> None:
    """记录不含策略值的失败类别，并返回稳定 503 错误码。"""
    logger.warning("registration_policy outcome=unavailable reason=%s", error.reason)
    raise HTTPException(
        status_code=HTTP_503_SERVICE_UNAVAILABLE,
        detail="registration_policy_unavailable",
    )


@registration_policy_router.get("", response_model=RegistrationPolicyResponse)
def get_registration_policy(
    _admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    service: RegistrationPolicyService = Depends(get_registration_policy_service),
) -> RegistrationPolicyResponse:
    """读取当前注册策略。"""
    try:
        policy: RegistrationPolicy = service.get_registration_policy()
    except RegistrationPolicyUnavailable as unavailable_error:
        _raise_policy_unavailable(unavailable_error)
    return _to_registration_policy_response(policy)


@registration_policy_router.put("", response_model=RegistrationPolicyResponse)
def update_registration_policy(
    request: RegistrationPolicyRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    service: RegistrationPolicyService = Depends(get_registration_policy_service),
) -> RegistrationPolicyResponse:
    """校验并保存注册策略，成功或失败均记录不含域名内容的审计信息。"""
    try:
        updated_policy: RegistrationPolicy = service.update_registration_policy(
            request.registration_mode,
            request.allowed_email_domains,
        )
    except InvalidEmailDomains as invalid_domains_error:
        logger.warning(
            "admin.audit actor_id=%s action=registration_policy.update "
            "target_id=registration_policy outcome=failure reason=invalid_email_domains",
            admin.user_id,
        )
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_email_domains",
                "invalid_domains": invalid_domains_error.invalid_domains,
            },
        ) from invalid_domains_error
    except RegistrationPolicyUnavailable as unavailable_error:
        _raise_policy_unavailable(unavailable_error)
    except ValueError as policy_error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(policy_error),
        ) from policy_error

    logger.info(
        "admin.audit actor_id=%s action=registration_policy.update "
        "target_id=registration_policy outcome=success",
        admin.user_id,
    )
    return _to_registration_policy_response(updated_policy)


__all__ = ["registration_policy_router"]
