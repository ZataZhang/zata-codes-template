"""认证领域模型：认证域标识与已认证主体。

用户账户领域模型 ``UserAccount`` 位于 ``core/shared/models/user_account.py``，
作为可被基础设施层实现引用的跨层契约。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthDomain(str, Enum):
    """认证域标识，用于区分两套相互隔离的用户体系。

    取值会作为 Redis 会话命名空间前缀与已认证主体的归属标记，
    确保 public 与 admin 在数据层与运行期都不互相穿透。
    """

    PUBLIC = "public"
    ADMIN = "admin"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """已认证主体，由接入层注入到业务处理函数。

    Attributes:
        user_id (str): 账户主键，既是会话归属，也用作业务资源 ``owner_id``。
        display_name (str): 展示名称。
        identifier (str): 登录标识（public 邮箱 / admin 用户名）。
        domain (AuthDomain): 主体所属认证域。
    """

    user_id: str
    display_name: str
    identifier: str
    domain: AuthDomain
