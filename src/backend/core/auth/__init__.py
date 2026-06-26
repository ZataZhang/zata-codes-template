"""认证核心编排子包。

聚合两套相互隔离的认证域（public / admin）所共享的领域模型与用例编排：

- `models`：跨域复用的纯领域对象（`AuthDomain` / `UserAccount` / `AuthenticatedPrincipal`）。
- `service`：单一 `AuthService` 编排，差异通过注入（仓库 / 会话存储 / 是否允许注册）区分。
- `directory`：`PublicUserDirectory`，供 admin 域只读与启停 public 用户。

具体存储、哈希与会话实现位于基础设施层，本子包只依赖 `core/shared/interfaces`
中的抽象端口，遵循依赖向内原则。
"""

from __future__ import annotations

from backend.core.auth.directory import PublicUserDirectory, PublicUserPage
from backend.core.auth.models import AuthDomain, AuthenticatedPrincipal
from backend.core.auth.service import AuthService
from backend.core.shared.models.user_account import UserAccount

__all__ = [
    "AuthDomain",
    "AuthService",
    "AuthenticatedPrincipal",
    "PublicUserDirectory",
    "PublicUserPage",
    "UserAccount",
]
