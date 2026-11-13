"""账户目录列表筛选条件。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountListFilter:
    """供多个账户目录共用的筛选条件。"""

    status: str | None = None
    keyword: str | None = None
    organization_id: str | None = None


__all__ = ["AccountListFilter"]
