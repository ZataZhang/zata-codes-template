"""Agent、Skill、A2A 与组织 Run 诊断路由聚合器。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.admin.a2a_management_router import router as a2a_management_router
from backend.api.admin.agent_management_router import router as agent_management_router
from backend.api.admin.run_management_router import router as run_management_router
from backend.api.admin.skill_management_router import router as skill_management_router

router = APIRouter()
router.include_router(agent_management_router)
router.include_router(skill_management_router)
router.include_router(a2a_management_router)
router.include_router(run_management_router)

__all__ = ["router"]
