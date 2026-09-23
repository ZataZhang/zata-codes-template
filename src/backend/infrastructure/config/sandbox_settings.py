"""沙箱执行后端配置加载。

独立于 ``settings.py``:该文件已接近单文件行数阈值,且沙箱配置的生命周期与主配置
不同——未配置 ``[sandbox_agent]`` 段时沙箱后端根本不注册,调用方在装配期即拿到
``None``,而不是在运行时才发现后端缺失。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.infrastructure.sandbox.egress_policy import SandboxEgressPolicy

_PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parents[4]
_TOML_CONFIG_FILE_PATH: Path = _PROJECT_ROOT_PATH / "config.toml"
_DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
_DEFAULT_MEMORY_LIMIT = "1g"
_DEFAULT_E2B_TIMEOUT_SECONDS = 900
_DEFAULT_E2B_USERNAME = "user"
_DEFAULT_E2B_API_KEY_ENV = "E2B_API_KEY"
_SUPPORTED_PROVIDERS = ("filesystem", "docker", "e2b")


class SandboxAgentConfigError(RuntimeError):
    """沙箱 Runtime 配置非法时抛出。

    启动期 fail-fast:配置写错比沙箱不可用更危险——一个"看起来已限制、实际全开"
    的出站策略不应该被静默接受。
    """


@dataclass(frozen=True)
class E2bSandboxSettings:
    """云沙箱后端的非密钥配置。

    这里只放环境变量**别名**而不是密钥值:真实凭据由 ``.env`` / ``.env.local`` 注入,
    配置加载阶段不读取它,因此默认环境未填写时配置仍能正常加载,只是该 Runtime 不会
    注册。

    Attributes:
        api_url (str): 控制面基地址。
        api_key_env (str): 控制面凭据所在的环境变量名。
        template_id (str): 平台自建执行模板标识。
        timeout_seconds (int): 新建沙箱的存活窗口秒数。
        username (str): 执行通道文件读写使用的沙箱用户名。
        allow_internet_access (bool): 是否允许沙箱出网;默认关闭。
    """

    api_url: str
    api_key_env: str
    template_id: str
    timeout_seconds: int
    username: str
    allow_internet_access: bool


@dataclass(frozen=True)
class SandboxAgentConfig:
    """沙箱 Runtime 的完整配置。

    Attributes:
        provider (str): ``filesystem``、``docker`` 或 ``e2b``。
        image (str): Docker 档使用的沙箱镜像。
        command_timeout_seconds (int): 沙箱内单条命令的超时秒数。
        workspace_root (str): filesystem 档的会话目录父目录。
        memory_limit (str): Docker 档的容器内存上限。
        model (str | None): 模型标识;为 ``None`` 时沿用主模型。
        egress (SandboxEgressPolicy): 出站网络策略。
        skills_paths (tuple[str, ...]): 可信宿主 Skill 来源目录;为空表示沙箱
            Runtime 不暴露任何 Skill。
        e2b (E2bSandboxSettings | None): 云沙箱档配置;非 ``e2b`` 后端时为 ``None``。
    """

    provider: str
    image: str
    command_timeout_seconds: int
    workspace_root: str
    memory_limit: str
    model: str | None
    egress: SandboxEgressPolicy
    skills_paths: tuple[str, ...]
    e2b: E2bSandboxSettings | None = None


def load_sandbox_agent_config(
    config_path: str | Path | None = None,
) -> SandboxAgentConfig | None:
    """加载 ``config.toml`` 中的 ``[sandbox_agent]`` 段。

    Args:
        config_path (str | Path | None): 可选配置文件路径;缺省为仓库根 config.toml。

    Returns:
        SandboxAgentConfig | None: 已校验的沙箱配置;未配置该段时为 ``None``,
            调用方据此不注册沙箱 Runtime。

    Raises:
        SandboxAgentConfigError: 配置段存在但字段非法。
    """
    resolved_toml_path = Path(config_path) if config_path else _TOML_CONFIG_FILE_PATH
    if not resolved_toml_path.is_file():
        return None
    try:
        with open(resolved_toml_path, "rb") as toml_file_handle:
            raw_toml_data: dict[str, Any] = tomllib.load(toml_file_handle)
    except (OSError, tomllib.TOMLDecodeError) as toml_error:
        raise SandboxAgentConfigError(f"无法读取 config.toml: {toml_error}") from toml_error
    sandbox_section = raw_toml_data.get("sandbox_agent")
    if not isinstance(sandbox_section, dict):
        return None

    configured_provider = str(sandbox_section.get("provider", "filesystem"))
    if configured_provider not in _SUPPORTED_PROVIDERS:
        raise SandboxAgentConfigError(
            "[sandbox_agent] provider 只支持 "
            f"{'、'.join(_SUPPORTED_PROVIDERS)}，收到 {configured_provider}"
        )
    e2b_settings = _build_e2b_settings(sandbox_section) if configured_provider == "e2b" else None
    return SandboxAgentConfig(
        provider=configured_provider,
        image=str(sandbox_section.get("image", "zata-sandbox:latest")),
        command_timeout_seconds=int(
            sandbox_section.get("command_timeout_seconds", _DEFAULT_COMMAND_TIMEOUT_SECONDS)
        ),
        workspace_root=str(sandbox_section.get("workspace_root", "sandbox-workspace")),
        memory_limit=str(sandbox_section.get("memory_limit", _DEFAULT_MEMORY_LIMIT)),
        model=_optional_str(sandbox_section.get("model")),
        egress=_build_egress_policy(
            sandbox_section, provider=configured_provider, e2b_settings=e2b_settings
        ),
        skills_paths=_resolve_skills_paths(sandbox_section),
        e2b=e2b_settings,
    )


def _build_e2b_settings(sandbox_section: dict[str, Any]) -> E2bSandboxSettings:
    """解析云沙箱档的 ``[sandbox_agent.e2b]`` 段。

    端点与模板缺失时直接失败:这两项无法从环境变量兜底,而一个"以为连上了云端、
    实际根本没配置"的后端比不注册更难排查。

    Args:
        sandbox_section (dict[str, Any]): ``[sandbox_agent]`` 段原始数据。

    Returns:
        E2bSandboxSettings: 已校验的云沙箱配置。

    Raises:
        SandboxAgentConfigError: 段缺失、不是表,或缺少 api_url / template_id。
    """
    e2b_section = sandbox_section.get("e2b")
    if not isinstance(e2b_section, dict):
        raise SandboxAgentConfigError(
            '[sandbox_agent] provider = "e2b" 必须提供 [sandbox_agent.e2b] 段，'
            "至少包含 api_url 与 template_id。"
        )
    api_url = _optional_str(e2b_section.get("api_url"))
    template_id = _optional_str(e2b_section.get("template_id"))
    if not api_url:
        raise SandboxAgentConfigError("[sandbox_agent.e2b] 缺少 api_url")
    if not template_id:
        raise SandboxAgentConfigError("[sandbox_agent.e2b] 缺少 template_id")
    return E2bSandboxSettings(
        api_url=api_url.rstrip("/"),
        api_key_env=str(e2b_section.get("api_key_env", _DEFAULT_E2B_API_KEY_ENV)),
        template_id=template_id,
        timeout_seconds=int(e2b_section.get("timeout_seconds", _DEFAULT_E2B_TIMEOUT_SECONDS)),
        username=str(e2b_section.get("username", _DEFAULT_E2B_USERNAME)),
        allow_internet_access=bool(e2b_section.get("allow_internet_access", False)),
    )


def _resolve_skills_paths(sandbox_section: dict[str, Any]) -> tuple[str, ...]:
    """解析可信宿主 Skill 来源目录。

    缺省为空:未声明来源的沙箱 Runtime 不暴露任何 Skill,保持无 Skill 行为。声明了
    但指向不存在的目录则直接失败——静默降级会让运维以为 Skill 已生效。

    Args:
        sandbox_section (dict[str, Any]): ``[sandbox_agent]`` 段原始数据。

    Returns:
        tuple[str, ...]: 已校验的来源目录。

    Raises:
        SandboxAgentConfigError: 声明不是数组、含空项或目录不存在。
    """
    raw_skills_paths = sandbox_section.get("skills_paths", [])
    if not isinstance(raw_skills_paths, list):
        raise SandboxAgentConfigError("[sandbox_agent] skills_paths 必须是数组")
    resolved_skills_paths: list[str] = []
    for raw_skills_path in raw_skills_paths:
        normalized_skills_path = str(raw_skills_path).strip()
        if not normalized_skills_path:
            raise SandboxAgentConfigError("[sandbox_agent] skills_paths 不允许空路径")
        if not Path(normalized_skills_path).is_dir():
            raise SandboxAgentConfigError(
                f"[sandbox_agent] skills_paths 指向的目录不存在：{normalized_skills_path}"
            )
        resolved_skills_paths.append(normalized_skills_path)
    return tuple(resolved_skills_paths)


def _build_egress_policy(
    sandbox_section: dict[str, Any],
    *,
    provider: str,
    e2b_settings: E2bSandboxSettings | None = None,
) -> SandboxEgressPolicy:
    """按配置构造出站策略。

    filesystem 档没有网络概念,固定为断网,不校验代理与清单——否则未部署代理的
    本地开发会因为一段用不上的配置而启动失败。云沙箱只有"断网"与"直连"两档,
    没有按域名放行的代理通道,因此由 ``[sandbox_agent.e2b] allow_internet_access``
    直接映射到 ``none`` / ``open``。

    Args:
        sandbox_section (dict[str, Any]): ``[sandbox_agent]`` 段原始数据。
        provider (str): 已校验的沙箱后端类型。
        e2b_settings (E2bSandboxSettings | None): 已解析的云沙箱配置。

    Returns:
        SandboxEgressPolicy: 已校验的出站策略。

    Raises:
        SandboxAgentConfigError: 出站配置非法。
    """
    if provider == "e2b":
        # 这里的 mode 只用于让"出网姿态"在配置层可读可断言；e2b 档真正的出网开关是
        # 创建沙箱时传给控制面的 allow_internet_access（见 e2b_control_plane），
        # 该策略对象本身不被云沙箱后端消费。
        is_internet_allowed = bool(e2b_settings and e2b_settings.allow_internet_access)
        return SandboxEgressPolicy(mode="open" if is_internet_allowed else "none")
    if provider != "docker":
        return SandboxEgressPolicy(mode="none")
    egress_section = sandbox_section.get("egress")
    if not isinstance(egress_section, dict):
        raise SandboxAgentConfigError(
            '[sandbox_agent] provider = "docker" 必须提供 [sandbox_agent.egress] 段；'
            "默认档为按域名放行，需要 proxy_url、network_name 与 allowed_domains。"
        )
    raw_allowed_domains = egress_section.get("allowed_domains", [])
    if not isinstance(raw_allowed_domains, list):
        raise SandboxAgentConfigError("[sandbox_agent.egress] allowed_domains 必须是数组")
    try:
        return SandboxEgressPolicy(
            mode=str(egress_section.get("mode", "allowlist")),  # type: ignore[arg-type]
            allowed_domains=tuple(str(domain) for domain in raw_allowed_domains),
            proxy_url=_optional_str(egress_section.get("proxy_url")),
            network_name=_optional_str(egress_section.get("network_name")),
        )
    except ValueError as policy_error:
        raise SandboxAgentConfigError(f"[sandbox_agent.egress] 配置非法: {policy_error}") from (
            policy_error
        )


def _optional_str(raw_value: Any) -> str | None:
    """把可选配置值规范化为非空字符串或 ``None``。"""
    if raw_value is None:
        return None
    normalized_value = str(raw_value).strip()
    return normalized_value or None


__all__ = [
    "E2bSandboxSettings",
    "SandboxAgentConfig",
    "SandboxAgentConfigError",
    "load_sandbox_agent_config",
]
