"""Admin 域接入层子包。

集中存放仅服务 admin 认证域的路由（``/admin/auth`` 与 ``/admin/users``），
统一经 ``get_current_admin_user`` 守卫，与 public 域端点隔离。
"""

from __future__ import annotations

from backend.api.admin.admin_auth_router import router as admin_auth_router
from backend.api.admin.admin_user_router import router as admin_user_router

__all__ = ["admin_auth_router", "admin_user_router"]
