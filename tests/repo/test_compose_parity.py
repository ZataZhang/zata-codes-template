"""Repository-convention checks for Docker Compose files.

Guards against two failure modes seen in derived projects:

1. A service exists in `docker-compose.yml` but is missing from
   `docker-compose.dokploy.yml` (e.g. an async worker that never deploys to
   production).
2. Generic container names such as ``app-backend`` leak from the template into
   shared deployment hosts, causing name collisions across projects.

Pure YAML parsing — no ``docker`` CLI required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]
_LOCAL_COMPOSE_PATH = _PROJECT_ROOT_PATH / "docker-compose.yml"
_DOKPLOY_COMPOSE_PATH = _PROJECT_ROOT_PATH / "docker-compose.dokploy.yml"

# Services that intentionally exist only in `docker-compose.yml` because they
# are local-development-only (e.g. a bundled Postgres container that production
# replaces with a managed database).
_LOCAL_ONLY_SERVICES: frozenset[str] = frozenset({"db"})

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
