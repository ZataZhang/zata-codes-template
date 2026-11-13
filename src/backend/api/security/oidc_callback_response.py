"""在认证路由中共享 OIDC 回调响应编排。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from fastapi import Request, status
from fastapi.responses import RedirectResponse
from zata_oidc import OidcAuthenticationError

from backend.api.security.session_cookies import set_session_cookie
from backend.core.auth.oidc_login import OidcLoginError, OidcLoginService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OidcCallbackResponseConfig:
    """描述认证域成功、失败及会话 Cookie 的回调响应差异。"""

    portal: Literal["admin", "public"]
    transaction_cookie_name: str
    session_cookie_name: str
    failure_redirect_path: str
    success_redirect_path: str
    account_conflict_error: str | None = None


def build_oidc_callback_response(
    request: Request,
    oidc_login_service: OidcLoginService | None,
    callback_config: OidcCallbackResponseConfig,
) -> RedirectResponse:
    """消费 OIDC 回调并按认证域策略签发会话 Cookie 或失败跳转。"""
    transaction_id = request.cookies.get(callback_config.transaction_cookie_name)
    authorization_code = request.query_params.get("code")
    state = request.query_params.get("state")
    session_token: str | None = None
    failure_reason = "transaction_invalid"
    if transaction_id and authorization_code and state and oidc_login_service is not None:
        try:
            session_token, _principal = oidc_login_service.complete_login(
                transaction_id=transaction_id,
                state=state,
                code=authorization_code,
            )
        except OidcAuthenticationError as oidc_error:
            failure_reason = oidc_error.reason.value
        except OidcLoginError as login_error:
            failure_reason = login_error.reason.value
        except Exception:
            failure_reason = "internal_error"

    if session_token is None:
        logger.warning(
            "auth.oidc outcome=failed portal=%s reason=%s",
            callback_config.portal,
            failure_reason,
        )
        failure_marker = (
            callback_config.account_conflict_error
            if failure_reason == "user_account_conflict"
            and callback_config.account_conflict_error is not None
            else "1"
        )
        response = RedirectResponse(
            f"{callback_config.failure_redirect_path}?sso_error={failure_marker}",
            status_code=status.HTTP_302_FOUND,
        )
    else:
        logger.info("auth.oidc outcome=success portal=%s", callback_config.portal)
        response = RedirectResponse(
            callback_config.success_redirect_path,
            status_code=status.HTTP_302_FOUND,
        )
        set_session_cookie(
            response,
            cookie_name=callback_config.session_cookie_name,
            token=session_token,
            secure=request.app.state.auth_cookie_secure,
        )

    response.delete_cookie(key=callback_config.transaction_cookie_name, path="/")
    return response
