"""共享用户账户领域模型（跨认证域、可被基础设施层实现引用的契约）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserAccount:
    """统一的用户账户领域对象。

    两域共用同一结构，差异仅在 ``identifier`` 的语义：public 域为邮箱，
    admin 域为登录用户名。``password_hash`` 仅在认证编排内部流转，不应
    被映射进任何对外响应 DTO。

    Attributes:
        id (str): 账户主键（UUID hex），同时用作业务资源的 ``owner_id``。
        identifier (str): 归一化后的登录标识（public 邮箱 / admin 用户名）。
        display_name (str): 展示名称。
        password_hash (str): 不可逆密码哈希。
        is_active (bool): 是否启用；禁用账户无法登录且既有会话立即失效。
        created_at (datetime | None): 创建时间，未落库时为 None。
    """

    id: str
    identifier: str
    display_name: str
    password_hash: str
    is_active: bool
    created_at: datetime | None = None
