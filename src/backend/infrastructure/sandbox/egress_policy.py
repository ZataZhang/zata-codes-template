"""沙箱出站网络策略。

三档而非开关:真实需求是"访问某几个服务",完全断网会让沙箱不可用,全开则给正在
处理业务数据的 agent 留下无审计的外传通道。默认档经出站代理按域名放行,清单外
一律拒绝。

放行清单只由部署配置提供,沙箱容器没有修改它的路径。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

EgressMode = Literal["none", "allowlist", "open"]

# 允许普通域名与单层前缀通配(``.example.com`` 形式由代理自行解释);拒绝裸通配,
# 因为 ``*`` 会让放行清单退化成全开却仍显示为"已限制"。
_DOMAIN_PATTERN = re.compile(r"^\.?[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9-]+)+$")


@dataclass(frozen=True)
class SandboxEgressPolicy:
    """沙箱容器的出站网络策略。

    Attributes:
        mode (EgressMode): ``none`` 完全断网;``allowlist`` 经代理按域名放行;
            ``open`` 直连外网,仅限本地开发。
        allowed_domains (tuple[str, ...]): 放行域名清单;仅 ``allowlist`` 有意义。
        proxy_url (str | None): 出站代理地址;仅 ``allowlist`` 有意义。
        network_name (str | None): ``allowlist`` 档下容器接入的 Docker 网络名;
            该网络应为 internal,使容器只能到达代理而非外网。
    """

    mode: EgressMode = "none"
    allowed_domains: tuple[str, ...] = ()
    proxy_url: str | None = None
    network_name: str | None = None

    def __post_init__(self) -> None:
        """校验策略自洽,拒绝"看起来已限制、实际全开或全断"的配置。

        Raises:
            ValueError: 放行档缺少代理或清单,或清单含非法域名。
        """
        if self.mode not in ("none", "allowlist", "open"):
            raise ValueError(f"未知的沙箱出站模式: {self.mode}")
        if self.mode != "allowlist":
            return
        if not self.allowed_domains:
            # 清单为空时拒绝启动,避免出现"以为放行了其实全断"的静默故障。
            raise ValueError("allowlist 出站模式必须提供非空放行域名清单")
        if not self.proxy_url:
            raise ValueError("allowlist 出站模式必须提供出站代理地址")
        if not self.network_name:
            raise ValueError("allowlist 出站模式必须提供容器接入的 Docker 网络名")
        for allowed_domain in self.allowed_domains:
            if not _DOMAIN_PATTERN.fullmatch(allowed_domain):
                raise ValueError(f"放行清单包含非法域名: {allowed_domain}")

    def container_network_mode(self) -> str | None:
        """返回容器的 Docker ``network_mode`` 取值。

        Returns:
            str | None: ``none`` 档返回 ``"none"``;``allowlist`` 档返回 ``None``
                并由调用方接入 ``network_name`` 指定的 internal 网络;``open``
                档返回 ``None`` 走默认 bridge。
        """
        return "none" if self.mode == "none" else None

    def container_environment(self) -> dict[str, str]:
        """返回注入容器的出站相关环境变量。

        只注入代理地址,不注入任何宿主凭据。

        Returns:
            dict[str, str]: 代理环境变量;非放行档为空字典。
        """
        if self.mode != "allowlist" or not self.proxy_url:
            return {}
        return {
            "HTTP_PROXY": self.proxy_url,
            "HTTPS_PROXY": self.proxy_url,
            "http_proxy": self.proxy_url,
            "https_proxy": self.proxy_url,
            "NO_PROXY": "localhost,127.0.0.1",
        }

    def attachable_network(self) -> str | None:
        """返回容器创建后需要接入的 Docker 网络名;其他档为 ``None``。"""
        return self.network_name if self.mode == "allowlist" else None


__all__ = ["EgressMode", "SandboxEgressPolicy"]
