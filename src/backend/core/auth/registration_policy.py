"""注册策略值对象、邮箱域名规范化与渠道判断。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

RegistrationMode = Literal["both", "oidc_only", "closed"]
RegistrationChannel = Literal["password", "oidc"]

REGISTRATION_POLICY_KEY: str = "registration_policy"
REGISTRATION_MODES: frozenset[str] = frozenset({"both", "oidc_only", "closed"})


# 名称是已冻结的跨层错误契约。
class InvalidEmailDomains(ValueError):  # noqa: N818
    """域名白名单含不符合 DNS 主机名规则的输入。"""

    def __init__(self, invalid_domains: Sequence[str]) -> None:
        """保存原始非法输入，供 API 返回逐项校验错误。

        Args:
            invalid_domains (Sequence[str]): 请求中未通过校验的原始域名。
        """
        self.invalid_domains: list[str] = list(invalid_domains)
        super().__init__("invalid_email_domains")


def normalize_email_domain(domain: str) -> str:
    """校验域名并生成小写 IDNA ASCII 形式。

    Args:
        domain (str): 管理员输入的邮箱域名。

    Returns:
        str: 可用于邮箱域匹配的规范化 ASCII 域名。

    Raises:
        ValueError: 输入不是有效 DNS 域名时。
    """
    stripped_domain: str = domain.strip()
    if not stripped_domain or stripped_domain.startswith(".") or stripped_domain.endswith("."):
        raise ValueError("invalid_email_domain")
    try:
        ascii_domain: str = stripped_domain.encode("idna").decode("ascii").lower()
    except UnicodeError as domain_error:
        raise ValueError("invalid_email_domain") from domain_error

    if len(ascii_domain) > 253:
        raise ValueError("invalid_email_domain")
    domain_labels: list[str] = ascii_domain.split(".")
    if any(not _is_valid_domain_label(domain_label) for domain_label in domain_labels):
        raise ValueError("invalid_email_domain")
    return ascii_domain


def _is_valid_domain_label(domain_label: str) -> bool:
    """判断单个规范化 DNS 标签是否符合字母数字与连字符约束。"""
    return bool(
        len(domain_label) <= 63 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", domain_label)
    )


@dataclass(frozen=True)
class RegistrationPolicy:
    """前台注册模式及允许的邮箱域名。

    Attributes:
        registration_mode (RegistrationMode): 注册渠道策略。
        allowed_email_domains (tuple[str, ...]): 规范化的允许域名；空元组不限域。
    """

    registration_mode: RegistrationMode
    allowed_email_domains: tuple[str, ...]

    def allows(self, channel: RegistrationChannel, email: str) -> bool:
        """判断指定渠道及邮箱是否可以创建 public 账户。

        Args:
            channel (RegistrationChannel): ``password`` 或 ``oidc``。
            email (str): 注册邮箱。

        Returns:
            bool: 策略允许注册时返回 True。
        """
        if self.registration_mode == "closed":
            return False
        if self.registration_mode == "oidc_only" and channel == "password":
            return False
        if channel not in {"password", "oidc"}:
            return False
        if not self.allowed_email_domains:
            return True
        if email.count("@") != 1:
            return False
        email_domain: str = email.rsplit("@", maxsplit=1)[1]
        try:
            normalized_email_domain: str = normalize_email_domain(email_domain)
        except ValueError:
            return False
        return normalized_email_domain in self.allowed_email_domains


DEFAULT_REGISTRATION_POLICY: RegistrationPolicy = RegistrationPolicy(
    registration_mode="both",
    allowed_email_domains=(),
)


__all__ = [
    "DEFAULT_REGISTRATION_POLICY",
    "REGISTRATION_MODES",
    "REGISTRATION_POLICY_KEY",
    "InvalidEmailDomains",
    "RegistrationChannel",
    "RegistrationMode",
    "RegistrationPolicy",
    "normalize_email_domain",
]
