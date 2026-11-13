"""认证用例读取注册策略的抽象端口。"""

from __future__ import annotations

from typing import Protocol

from backend.core.auth.registration_policy import RegistrationPolicy


class RegistrationPolicyProvider(Protocol):
    """提供按请求实时读取的注册策略。"""

    def get_registration_policy(self) -> RegistrationPolicy:
        """读取当前注册策略。

        Returns:
            RegistrationPolicy: 当前注册策略或缺少配置时的默认策略。

        Raises:
            RegistrationPolicyUnavailable: 存储不可用或记录无法解码时。
        """
        ...


__all__ = ["RegistrationPolicyProvider"]
