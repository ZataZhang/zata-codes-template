"""Docker Compose 仓库约定检查。

防范派生项目中常见的三类问题：

1. `docker-compose.yml` 中新增了服务，却未同步到
   `docker-compose.dokploy.yml`（例如某个异步 worker 从未部署到生产环境）。
2. 模板自带的通用容器名（如 ``app-backend``）泄漏到共享部署主机，导致跨项目
   名称冲突。
3. `docker-compose.yml` 引用了环境变量，但 `.env.example` 中未声明，导致新成员
   不知道要配置什么。

仅解析 YAML，不需要 ``docker`` CLI。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]
_LOCAL_COMPOSE_PATH = _PROJECT_ROOT_PATH / "docker-compose.yml"
_DOKPLOY_COMPOSE_PATH = _PROJECT_ROOT_PATH / "docker-compose.dokploy.yml"

# Services that intentionally exist only in `docker-compose.yml` because they
# are local-development-only (e.g. a bundled cache/queue container that
# production replaces with a managed service). Empty because the local stack
# no longer bundles PostgreSQL.
_LOCAL_ONLY_SERVICES: frozenset[str] = frozenset()

# Container-name prefixes that signal a copy-paste from the template that the
# derived project failed to specialize. Add project-specific exceptions here
# only with a comment explaining why.
_GENERIC_CONTAINER_NAME_PREFIXES: tuple[str, ...] = ("app-",)


def _load_compose(compose_file_path: Path) -> dict[str, Any]:
    with open(compose_file_path, "r", encoding="utf-8") as compose_handle:
        parsed_compose_doc: dict[str, Any] = yaml.safe_load(compose_handle) or {}
    return parsed_compose_doc


def _service_definitions(compose_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_services_dict: dict[str, Any] = compose_doc.get("services", {}) or {}
    return {
        service_name: service_def
        for service_name, service_def in raw_services_dict.items()
        if isinstance(service_def, dict)
    }


def _extract_required_env_vars(compose_doc: dict[str, Any]) -> set[str]:
    """提取 compose 文件中需要从外部注入的环境变量名。

    覆盖两种 ``environment:`` 写法：

    - 裸变量列表：``- REDIS_URL``
    - 插值形式：``- DATABASE_URL=${DATABASE_URL}``、
      ``- API_BASE_URL=${API_BASE_URL:-http://localhost:8000}``、
      ``- ${DOMAIN:?Set DOMAIN in Dokploy environment}``

    硬编码值（如 ``HOST=0.0.0.0``）会被忽略。
    """
    required_env_var_name_set: set[str] = set()
    interpolation_pattern: re.Pattern[str] = re.compile(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[-?+][^}]*)?\}"
    )

    for service_def in _service_definitions(compose_doc).values():
        raw_environment_block: Any = service_def.get("environment")
        if isinstance(raw_environment_block, list):
            for raw_env_entry in raw_environment_block:
                if not isinstance(raw_env_entry, str):
                    continue
                if "=" not in raw_env_entry:
                    env_var_name_str = raw_env_entry.strip()
                    if env_var_name_str:
                        required_env_var_name_set.add(env_var_name_str)
                else:
                    _, value_part = raw_env_entry.split("=", 1)
                    required_env_var_name_set.update(interpolation_pattern.findall(value_part))
        elif isinstance(raw_environment_block, dict):
            for env_value in raw_environment_block.values():
                if isinstance(env_value, str):
                    required_env_var_name_set.update(interpolation_pattern.findall(env_value))

    return required_env_var_name_set


def _load_env_example_var_names(env_example_path: Path) -> set[str]:
    """从 ``.env.example`` 提取已声明的变量名（含注释掉的示例行）。"""
    declared_env_var_name_set: set[str] = set()
    declaration_pattern: re.Pattern[str] = re.compile(r"^(?:#\s*)?([A-Za-z_][A-Za-z0-9_]*)=")

    if not env_example_path.is_file():
        return declared_env_var_name_set

    with open(env_example_path, "r", encoding="utf-8") as env_example_handle:
        for line in env_example_handle:
            match = declaration_pattern.match(line.strip())
            if match:
                declared_env_var_name_set.add(match.group(1))

    return declared_env_var_name_set


def _environment_var_names(service_def: dict[str, Any]) -> set[str]:
    """Extract the set of explicit environment variable names for a service.

    Compose supports two ``environment:`` shapes:
      * list:   ``- FOO=bar`` or bare ``- FOO``
      * dict:   ``FOO: bar``
    Both are normalized to a set of variable names. ``env_file`` is
    intentionally ignored — this check is about explicit declarations only.
    """
    raw_environment_block: Any = service_def.get("environment")
    extracted_env_var_names: set[str] = set()
    if isinstance(raw_environment_block, list):
        for raw_env_entry in raw_environment_block:
            if not isinstance(raw_env_entry, str):
                continue
            env_var_name_str = raw_env_entry.split("=", 1)[0].strip()
            if env_var_name_str:
                extracted_env_var_names.add(env_var_name_str)
    elif isinstance(raw_environment_block, dict):
        for env_var_name_key in raw_environment_block.keys():
            if isinstance(env_var_name_key, str):
                extracted_env_var_names.add(env_var_name_key)
    return extracted_env_var_names


@pytest.fixture(scope="module")
def local_compose_doc() -> dict[str, Any]:
    return _load_compose(_LOCAL_COMPOSE_PATH)


@pytest.fixture(scope="module")
def dokploy_compose_doc() -> dict[str, Any]:
    return _load_compose(_DOKPLOY_COMPOSE_PATH)


def test_dokploy_has_all_non_local_services(
    local_compose_doc: dict[str, Any],
    dokploy_compose_doc: dict[str, Any],
) -> None:
    """Every non-dev service in local compose must also appear in dokploy compose.

    Catches the case where a developer adds (for example) an async worker to
    `docker-compose.yml` but forgets to mirror it into the production compose,
    so the deployed stack silently has no consumer for queued work.
    """
    local_service_name_set = set(_service_definitions(local_compose_doc).keys())
    dokploy_service_name_set = set(_service_definitions(dokploy_compose_doc).keys())

    expected_dokploy_service_name_set = local_service_name_set - _LOCAL_ONLY_SERVICES
    missing_in_dokploy_service_name_set = (
        expected_dokploy_service_name_set - dokploy_service_name_set
    )

    assert not missing_in_dokploy_service_name_set, (
        "Services present in docker-compose.yml but missing in "
        "docker-compose.dokploy.yml: "
        f"{sorted(missing_in_dokploy_service_name_set)}. Either add them to "
        "the production compose or add them to _LOCAL_ONLY_SERVICES with a "
        "comment explaining why they should never deploy."
    )


@pytest.mark.parametrize(
    "compose_label,compose_path",
    [
        ("docker-compose.yml", _LOCAL_COMPOSE_PATH),
        ("docker-compose.dokploy.yml", _DOKPLOY_COMPOSE_PATH),
    ],
)
def test_no_generic_container_names(compose_label: str, compose_path: Path) -> None:
    """Reject container_name values that still carry the template's generic prefix.

    Generic names like ``app-backend`` collide across Dokploy stacks deployed to
    the same host. Derived projects must specialize the prefix (or drop
    ``container_name`` entirely and let Compose auto-name).
    """
    parsed_compose_doc = _load_compose(compose_path)
    offending_service_to_container_name: dict[str, str] = {}
    for service_name, service_def in _service_definitions(parsed_compose_doc).items():
        declared_container_name = service_def.get("container_name")
        if not isinstance(declared_container_name, str):
            continue
        if any(
            declared_container_name.startswith(generic_prefix_str)
            for generic_prefix_str in _GENERIC_CONTAINER_NAME_PREFIXES
        ):
            offending_service_to_container_name[service_name] = declared_container_name

    assert not offending_service_to_container_name, (
        f"{compose_label} declares container_name values with a generic prefix "
        f"({_GENERIC_CONTAINER_NAME_PREFIXES}): "
        f"{offending_service_to_container_name}. Either replace the prefix "
        "with a project-specific slug or remove container_name and let "
        "Compose auto-name (recommended)."
    )


def test_shared_services_have_matching_environment_keys(
    local_compose_doc: dict[str, Any],
    dokploy_compose_doc: dict[str, Any],
) -> None:
    """For services declared in both files, explicit environment keys must match.

    Catches drift such as ``DOCUMENT_RECOGNITION_TEXT_MODEL`` being added to
    one compose file but not the other, which would make the variable silently
    unset in whichever environment lacks it.

    ``env_file:`` entries are deliberately ignored — this asserts parity of
    explicit declarations, not effective runtime environment.
    """
    local_service_def_by_name = _service_definitions(local_compose_doc)
    dokploy_service_def_by_name = _service_definitions(dokploy_compose_doc)

    shared_service_name_set = set(local_service_def_by_name.keys()) & set(
        dokploy_service_def_by_name.keys()
    )

    mismatch_report_by_service: dict[str, dict[str, list[str]]] = {}
    for shared_service_name in sorted(shared_service_name_set):
        local_env_var_name_set = _environment_var_names(
            local_service_def_by_name[shared_service_name]
        )
        dokploy_env_var_name_set = _environment_var_names(
            dokploy_service_def_by_name[shared_service_name]
        )
        only_in_local_set = local_env_var_name_set - dokploy_env_var_name_set
        only_in_dokploy_set = dokploy_env_var_name_set - local_env_var_name_set
        if only_in_local_set or only_in_dokploy_set:
            mismatch_report_by_service[shared_service_name] = {
                "only_in_local": sorted(only_in_local_set),
                "only_in_dokploy": sorted(only_in_dokploy_set),
            }

    assert not mismatch_report_by_service, (
        "Explicit environment keys diverge between docker-compose.yml and "
        f"docker-compose.dokploy.yml for shared services: "
        f"{mismatch_report_by_service}. Align the environment blocks so the "
        "same variables are declared on both sides."
    )


def test_compose_environment_vars_declared_in_env_example(
    local_compose_doc: dict[str, Any],
) -> None:
    """``docker-compose.yml`` 引用的外部变量必须在 ``.env.example`` 中声明。

    保证本地开发不会出现 compose 里用了某个变量、但开发者拿到仓库后不知道要
    在 ``.env`` 里填什么。密钥值可以留空或注释掉，但变量名和说明必须存在。
    """
    required_env_var_name_set = _extract_required_env_vars(local_compose_doc)
    declared_env_var_name_set = _load_env_example_var_names(_PROJECT_ROOT_PATH / ".env.example")
    missing_env_var_name_set = required_env_var_name_set - declared_env_var_name_set

    assert not missing_env_var_name_set, (
        "Environment variables referenced in docker-compose.yml but missing from "
        f".env.example: {sorted(missing_env_var_name_set)}. Add them to .env.example "
        "(secret values may be left empty or commented out)."
    )
