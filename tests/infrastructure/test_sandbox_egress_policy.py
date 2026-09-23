"""沙箱出站网络策略测试。

三档语义（none / allowlist / open）与"看起来已限制、实际全开或全断"的配置必须被
拒绝：放行档缺代理、缺网络名或清单为空都要立刻失败。
"""

from __future__ import annotations

import pytest

from backend.infrastructure.sandbox.egress_policy import SandboxEgressPolicy


def test_default_policy_is_offline() -> None:
    """缺省档完全断网：容器 network_mode 为 none，不注入任何代理变量。"""
    egress_policy = SandboxEgressPolicy()

    assert egress_policy.container_network_mode() == "none"
    assert egress_policy.container_environment() == {}
    assert egress_policy.attachable_network() is None


def test_open_policy_uses_default_bridge() -> None:
    """open 档直连外网：不指定 network_mode、不注入代理、不接入额外网络。"""
    egress_policy = SandboxEgressPolicy(mode="open")

    assert egress_policy.container_network_mode() is None
    assert egress_policy.container_environment() == {}
    assert egress_policy.attachable_network() is None


def test_allowlist_policy_injects_proxy_without_host_credentials() -> None:
    """allowlist 档只注入代理地址，接入 internal 网络，供容器按域名出站。"""
    egress_policy = SandboxEgressPolicy(
        mode="allowlist",
        allowed_domains=("pypi.tuna.tsinghua.edu.cn",),
        proxy_url="http://sandbox-egress-proxy:3128",
        network_name="sandbox-egress",
    )

    assert egress_policy.container_network_mode() is None
    assert egress_policy.attachable_network() == "sandbox-egress"
    assert egress_policy.container_environment() == {
        "HTTP_PROXY": "http://sandbox-egress-proxy:3128",
        "HTTPS_PROXY": "http://sandbox-egress-proxy:3128",
        "http_proxy": "http://sandbox-egress-proxy:3128",
        "https_proxy": "http://sandbox-egress-proxy:3128",
        "NO_PROXY": "localhost,127.0.0.1",
    }


def test_unknown_mode_is_rejected() -> None:
    """未知模式被拒绝，不让错别字退化成"未配置"。"""
    with pytest.raises(ValueError, match="未知的沙箱出站模式"):
        SandboxEgressPolicy(mode="whitelist")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("policy_kwargs", "expected_message"),
    [
        ({}, "非空放行域名清单"),
        ({"allowed_domains": ("pypi.tuna.tsinghua.edu.cn",)}, "出站代理地址"),
        (
            {
                "allowed_domains": ("pypi.tuna.tsinghua.edu.cn",),
                "proxy_url": "http://proxy:3128",
            },
            "Docker 网络名",
        ),
    ],
)
def test_allowlist_requires_domains_proxy_and_network(
    policy_kwargs: dict[str, object], expected_message: str
) -> None:
    """放行档缺清单/代理/网络名任一都拒绝启动，避免静默全断。"""
    with pytest.raises(ValueError, match=expected_message):
        SandboxEgressPolicy(mode="allowlist", **policy_kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_domain", ["*", "example", "http://example.com", "*.example.com"])
def test_allowlist_rejects_invalid_domains(invalid_domain: str) -> None:
    """裸通配与非法域名被拒绝，避免放行清单退化成全开却仍显示为"已限制"。"""
    with pytest.raises(ValueError, match="非法域名"):
        SandboxEgressPolicy(
            mode="allowlist",
            allowed_domains=(invalid_domain,),
            proxy_url="http://proxy:3128",
            network_name="sandbox-egress",
        )
