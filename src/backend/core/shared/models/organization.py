"""组织领域模型及默认组织常量。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DEFAULT_ORGANIZATION_ID: str = "default"
DEFAULT_ORGANIZATION_NAME: str = "默认组织"


@dataclass(frozen=True)
class Organization:
    """表示一个平台内的组织。"""

    id: str
    name: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "DEFAULT_ORGANIZATION_ID",
    "DEFAULT_ORGANIZATION_NAME",
    "Organization",
]
