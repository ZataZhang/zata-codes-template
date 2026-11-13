"""注册策略读取、写入与严格持久化解码。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from backend.core.auth.registration_policy import (
    DEFAULT_REGISTRATION_POLICY,
    REGISTRATION_MODES,
    REGISTRATION_POLICY_KEY,
    InvalidEmailDomains,
    RegistrationPolicy,
    normalize_email_domain,
)
from backend.core.shared.interfaces.registration_policy_provider import (
    RegistrationPolicyProvider,
)
from backend.core.shared.interfaces.system_setting_repository import SystemSettingRepository


# 名称是已冻结的跨层错误契约。
class RegistrationPolicyUnavailable(RuntimeError):  # noqa: N818
    """注册策略存储或内容不可用，调用方必须拒绝新注册。"""

    def __init__(self, reason: str) -> None:
        """设置不含存储值或异常原文的内部失败类别。

        Args:
            reason (str): ``read_failed``、``write_failed``、``invalid_json`` 或
                ``invalid_schema`` 等安全类别。
        """
        self.reason = reason
        super().__init__("registration_policy_unavailable")


class RegistrationPolicyService(RegistrationPolicyProvider):
    """通过系统设置端口为认证和管理 API 提供注册策略。"""

    def __init__(self, system_setting_repository: SystemSettingRepository) -> None:
        """初始化注册策略服务。

        Args:
            system_setting_repository (SystemSettingRepository): JSON 设置仓库端口。
        """
        self._system_setting_repository = system_setting_repository

    def get_registration_policy(self) -> RegistrationPolicy:
        """每次从存储读取策略；仅缺少键时使用开放默认值。

        Returns:
            RegistrationPolicy: 当前策略或默认兼容策略。

        Raises:
            RegistrationPolicyUnavailable: 存储异常、JSON 损坏或字段无效时。
        """
        try:
            stored_value_json: str | None = self._system_setting_repository.get(
                REGISTRATION_POLICY_KEY
            )
        except Exception as storage_error:
            raise RegistrationPolicyUnavailable("read_failed") from storage_error
        if stored_value_json is None:
            return DEFAULT_REGISTRATION_POLICY
        if not isinstance(stored_value_json, str):
            raise RegistrationPolicyUnavailable("invalid_storage_value")
        try:
            stored_policy_value: Any = json.loads(stored_value_json)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as decode_error:
            raise RegistrationPolicyUnavailable("invalid_json") from decode_error
        try:
            return self._decode_policy(stored_policy_value)
        except (InvalidEmailDomains, TypeError, ValueError, KeyError) as schema_error:
            raise RegistrationPolicyUnavailable("invalid_schema") from schema_error

    def update_registration_policy(
        self,
        registration_mode: str,
        allowed_email_domains: Sequence[str],
    ) -> RegistrationPolicy:
        """校验并保存新策略，保存完成后立即返回可供后续请求使用的值对象。

        Args:
            registration_mode (str): ``both``、``oidc_only`` 或 ``closed``。
            allowed_email_domains (Sequence[str]): 邮箱域名白名单。

        Returns:
            RegistrationPolicy: 规范化并保存后的策略。

        Raises:
            InvalidEmailDomains: 邮箱域名包含非法条目时。
            ValueError: 注册模式非法或策略存储失败时。
            RegistrationPolicyUnavailable: 写入系统设置失败时。
        """
        if registration_mode not in REGISTRATION_MODES:
            raise ValueError("invalid_registration_mode")
        normalized_domains: tuple[str, ...] = self._normalize_domains(allowed_email_domains)
        normalized_policy = RegistrationPolicy(
            registration_mode=registration_mode,  # type: ignore[arg-type]
            allowed_email_domains=normalized_domains,
        )
        serialized_policy: str = json.dumps(
            {
                "registration_mode": normalized_policy.registration_mode,
                "allowed_email_domains": list(normalized_policy.allowed_email_domains),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            self._system_setting_repository.put(REGISTRATION_POLICY_KEY, serialized_policy)
        except Exception as storage_error:
            raise RegistrationPolicyUnavailable("write_failed") from storage_error
        return normalized_policy

    @staticmethod
    def _normalize_domains(allowed_email_domains: Sequence[str]) -> tuple[str, ...]:
        """逐项规范化域名并保留首次出现顺序。

        Args:
            allowed_email_domains (Sequence[str]): 原始邮箱域名列表。

        Returns:
            tuple[str, ...]: 去重后的规范化域名。

        Raises:
            InvalidEmailDomains: 输入容器类型或一项以上域名无效时。
        """
        if isinstance(allowed_email_domains, (str, bytes)) or not isinstance(
            allowed_email_domains, Sequence
        ):
            raise InvalidEmailDomains([str(allowed_email_domains)])
        normalized_domain_values: list[str] = []
        invalid_domain_values: list[str] = []
        for raw_domain in allowed_email_domains:
            if not isinstance(raw_domain, str):
                invalid_domain_values.append(str(raw_domain))
                continue
            try:
                normalized_domain = normalize_email_domain(raw_domain)
            except ValueError:
                invalid_domain_values.append(raw_domain)
                continue
            if normalized_domain not in normalized_domain_values:
                normalized_domain_values.append(normalized_domain)
        if invalid_domain_values:
            raise InvalidEmailDomains(invalid_domain_values)
        return tuple(normalized_domain_values)

    @classmethod
    def _decode_policy(cls, stored_policy_value: Any) -> RegistrationPolicy:
        """严格校验 JSON 记录形状并转换为注册策略值对象。"""
        expected_fields: set[str] = {"registration_mode", "allowed_email_domains"}
        if not isinstance(stored_policy_value, dict) or set(stored_policy_value) != expected_fields:
            raise ValueError("registration_policy_fields_invalid")
        registration_mode: Any = stored_policy_value["registration_mode"]
        raw_domain_values: Any = stored_policy_value["allowed_email_domains"]
        if not isinstance(registration_mode, str) or registration_mode not in REGISTRATION_MODES:
            raise ValueError("registration_mode_invalid")
        if not isinstance(raw_domain_values, list) or any(
            not isinstance(raw_domain, str) for raw_domain in raw_domain_values
        ):
            raise ValueError("allowed_email_domains_invalid")
        return RegistrationPolicy(
            registration_mode=registration_mode,  # type: ignore[arg-type]
            allowed_email_domains=cls._normalize_domains(raw_domain_values),
        )


__all__ = ["RegistrationPolicyService", "RegistrationPolicyUnavailable"]
