"""守护 Dokploy 部署栈可真正构建与路由的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

这里钉的两条约定都来自真实线上事故，共同点是**本地全绿、构建也许能过，直到
部署当天才炸**，且症状都指不到根因：

1. Traefik 的 router / service / middleware 名使用 ``${COMPOSE_PROJECT_NAME}``
   前缀。Dokploy 上所有项目共用一个 Traefik 实例，这三类名字是全局命名空间。
   Docker Compose 会把实际项目名提供给文件插值；用该值拼接路由名称可避免复用
   模板部署多个应用时发生同名冲突。

2. Dockerfile 的 COPY 源必须落在自己声明的构建上下文里。``pnpm-workspace.yaml``
   与 ``pnpm-lock.yaml`` 在仓库根，而两个前端的 context 是 ``./frontend-*``，
   COPY 直接失败，镜像根本构建不出来。同类的还有 file: 依赖的 vendor tarball。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parents[2]
DOKPLOY_COMPOSE_PATH: Path = PROJECT_ROOT_PATH / "docker-compose.dokploy.yml"
LOCAL_COMPOSE_PATH: Path = PROJECT_ROOT_PATH / "docker-compose.yml"

_TRAEFIK_NAME_PATTERN = re.compile(r"traefik\.http\.(?:routers|services|middlewares)\.([^.=]+)\.")

_COMPOSE_PROJECT_NAME_PREFIX: str = "${COMPOSE_PROJECT_NAME}-"


def _load_compose_services(compose_path: Path) -> dict[str, dict]:
    """读取 compose 文件的 services 段。"""
    compose_doc = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    return compose_doc.get("services", {}) or {}


def _collect_traefik_names(service_definition: dict) -> set[str]:
    """从一个服务的 labels 里收集 Traefik 的 router/service/middleware 名。"""
    raw_labels = service_definition.get("labels", []) or []
    label_lines = (
        raw_labels
        if isinstance(raw_labels, list)
        else [f"{key}={value}" for key, value in raw_labels.items()]
    )
    return {
        match.group(1)
        for label_line in label_lines
        for match in [_TRAEFIK_NAME_PATTERN.search(str(label_line))]
        if match
    }


def _iter_dockerfile_copy_sources(dockerfile_path: Path) -> list[tuple[int, str]]:
    """列出 Dockerfile 里所有从构建上下文复制的 COPY 源。

    跳过 ``COPY --from=<stage>``：那是从前一个构建阶段复制，不经过上下文。

    Args:
        dockerfile_path (Path): Dockerfile 路径。

    Returns:
        list[tuple[int, str]]: ``(行号, 源路径)`` 列表。
    """
    copy_sources: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(
        dockerfile_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped_line = raw_line.strip()
        if not stripped_line.upper().startswith("COPY "):
            continue
        arguments = stripped_line[len("COPY ") :].split()
        if any(argument.startswith("--from=") for argument in arguments):
            continue
        positional_arguments = [argument for argument in arguments if not argument.startswith("--")]
        # 最后一个位置参数是镜像内目标路径，其余都是上下文内的源。
        copy_sources.extend((line_number, source) for source in positional_arguments[:-1])
    return copy_sources


def _context_contains(context_path: Path, copy_source: str) -> bool:
    """判断一条 COPY 的源在构建上下文里是否存在（支持通配符）。

    ``COPY . .`` 这类以上下文根为源的写法恒成立；其余按相对 glob 匹配，
    只去掉一个前导 ``./``，避免把 ``.env`` 之类的前导点一并削掉。

    Args:
        context_path (Path): 构建上下文绝对路径。
        copy_source (str): Dockerfile 里写的源路径，可能带通配符。

    Returns:
        bool: 上下文中是否存在匹配项。
    """
    normalized_source = copy_source[2:] if copy_source.startswith("./") else copy_source
    normalized_source = normalized_source.rstrip("/")
    if normalized_source in {"", "."}:
        return True
    return bool(list(context_path.glob(normalized_source)))


@pytest.mark.parametrize("compose_path", [DOKPLOY_COMPOSE_PATH, LOCAL_COMPOSE_PATH])
def test_traefik_names_use_compose_project_name(compose_path: Path) -> None:
    """Traefik 的 router/service/middleware 名必须以 Compose 项目名插值开头。

    Dokploy 单实例 Traefik 下这三类名字是全局的；固定名称会让同机部署互相撞名。
    Compose 项目名由部署平台提供，按该变量拼接名称可随每个应用自动隔离。
    """
    if not compose_path.is_file():
        pytest.skip(f"{compose_path.name} 不存在")
    offending_names: dict[str, set[str]] = {}
    for service_name, service_definition in _load_compose_services(compose_path).items():
        generic_names = {
            traefik_name
            for traefik_name in _collect_traefik_names(service_definition)
            if not traefik_name.startswith(_COMPOSE_PROJECT_NAME_PREFIX)
        }
        if generic_names:
            offending_names[service_name] = generic_names

    assert not offending_names, (
        f"{compose_path.name} 的 Traefik 名未以 Compose 项目名变量前缀开头: "
        f"{offending_names}。"
        "Dokploy 上所有项目共用一个 Traefik，这些名字是全局的；"
        "通用名会与同机其他派生项目撞车，导致某个域名失去路由并返回 404。"
    )


@pytest.mark.parametrize("compose_path", [DOKPLOY_COMPOSE_PATH, LOCAL_COMPOSE_PATH])
def test_dockerfile_copy_sources_exist_in_build_context(compose_path: Path) -> None:
    """每个服务 Dockerfile 的 COPY 源都必须存在于它声明的构建上下文内。

    这条抓的是"镜像根本构建不出来"，而且只在部署当天才暴露：本地 `just run`
    不走 Docker，测试也不构建镜像。典型是 pnpm workspace 文件在仓库根、而前端
    的 context 却是 ``./frontend-*``，以及 ``file:`` 依赖的 vendor tarball 晚于
    ``npm ci`` 才进入镜像。
    """
    if not compose_path.is_file():
        pytest.skip(f"{compose_path.name} 不存在")
    missing_sources: dict[str, list[str]] = {}
    for service_name, service_definition in _load_compose_services(compose_path).items():
        build_definition = service_definition.get("build")
        if not isinstance(build_definition, dict):
            continue
        context_path = (PROJECT_ROOT_PATH / build_definition.get("context", ".")).resolve()
        dockerfile_path = context_path / build_definition.get("dockerfile", "Dockerfile")
        if (
            build_definition.get("dockerfile", "").startswith(("/", "./", "../"))
            or (PROJECT_ROOT_PATH / build_definition.get("dockerfile", "")).is_file()
        ):
            dockerfile_path = PROJECT_ROOT_PATH / build_definition["dockerfile"]
        if not dockerfile_path.is_file():
            missing_sources[service_name] = [f"Dockerfile 不存在: {dockerfile_path}"]
            continue

        unresolved: list[str] = []
        for line_number, copy_source in _iter_dockerfile_copy_sources(dockerfile_path):
            if not _context_contains(context_path, copy_source):
                unresolved.append(
                    f"{dockerfile_path.name}:{line_number} COPY {copy_source}"
                    f"（context={build_definition.get('context', '.')}）"
                )
        if unresolved:
            missing_sources[service_name] = unresolved

    assert not missing_sources, (
        f"{compose_path.name} 中以下 COPY 源不在自己的构建上下文里，镜像会构建失败:\n"
        + "\n".join(
            f"  {service_name}: {', '.join(entries)}"
            for service_name, entries in missing_sources.items()
        )
    )
