"""Admin 域接入层子包。

集中存放仅服务 admin 认证域的路由（``/admin/auth``、``/admin/users``、
``/admin/run-traces``、组织与管理员目录）；平台接口使用角色守卫，与 public 域隔离。
"""

from __future__ import annotations

from backend.api.admin.admin_auth_router import router as admin_auth_router
from backend.api.admin.admin_directory_router import (
    admin_directory_router,
)
from backend.api.admin.admin_user_router import router as admin_user_router
from backend.api.admin.agent_router import router as agent_admin_router
from backend.api.admin.organization_router import organization_router
from backend.api.admin.registration_policy_router import registration_policy_router
from backend.api.admin.run_trace_router import router as run_trace_router

__all__ = [
    "admin_auth_router",
    "agent_admin_router",
    "admin_directory_router",
    "admin_user_router",
    "organization_router",
    "registration_policy_router",
    "run_trace_router",
]
