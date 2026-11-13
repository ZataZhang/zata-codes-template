"""基于进程环境变量的服务端密钥解析器。"""

from __future__ import annotations

import os
import re

from backend.core.shared.interfaces.secret_resolver import SecretResolver

_ENVIRONMENT_ALIAS_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


class EnvironmentSecretResolver(SecretResolver):
    """只允许解析部署方注入的环境变量名，不接收浏览器密钥值。"""

    def get_secret(self, alias: str) -> str | None:
        """按环境变量别名返回非空密钥。"""
        normalized_alias = alias.strip()
        if not _ENVIRONMENT_ALIAS_PATTERN.fullmatch(normalized_alias):
            raise ValueError("secret_reference_invalid")
        secret_value = os.getenv(normalized_alias, "").strip()
        return secret_value or None


__all__ = ["EnvironmentSecretResolver"]
