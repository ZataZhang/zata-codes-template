"""守卫：``src/backend/`` 的模块级 import 必须由 ``[project.dependencies]`` 覆盖。

为什么需要这个守卫：这套模板与其下游项目已经被同一类缺陷咬过两次，形态都是
"环境里恰好有、声明里根本没有"——

1. ``httpx[socks]``：``starlette.testclient`` 的硬依赖漏声明，靠 ``.venv``
   残留才跑绿（见 ``pyproject.toml`` 的 ``[dependency-groups] dev`` 注释）。
2. ``cryptography``：被 ``create_app()`` 装配路径上的模块（模型密钥加密工具）
   顶层 import，却只经某个可选 extra 的附属包传递安装。裸 ``uv sync`` 的新克
   隆必然在 collection 阶段就 ``ModuleNotFoundError``，几百个测试全灭。

这类缺陷的共同点是**本地环境掩盖了声明缺口**：开发机装过 extra 或留有旧
venv，测试全绿；CI 或新克隆做裸 ``uv sync`` 才炸。普通测试抓不到它——测试
自己就跑在那个被污染的环境里。所以只能拿"声明"而不是"环境"当事实来源：本
守卫完全基于 ``pyproject.toml`` 与 ``uv.lock`` 静态推算，不 import 任何被检
查的包，也不关心当前 venv 里装了什么。

在当前没有缺口的仓库里，本守卫是**预防性**的：它挡的是将来有人往装配路径上
加一个只靠 extra 传递安装的顶层 import。

判定口径：
- 只统计**模块级且无保护**的 import。``try: import x / except ImportError``
  或函数体内的延迟 import 属于合法的可选依赖（extra 能力按需安装），不在
  约束范围内。
- 允许的依赖集 = ``uv.lock`` 中本项目根 package 的 ``dependencies`` 硬依赖闭
  包，即裸 ``uv sync``（不带任何 ``--extra``）实际会装进 venv 的包。extra 与
  dev 组刻意排除在外。

本文件设计为在模板仓库与各下游项目之间共用**同一份**实现：项目名从
``pyproject.toml`` 读取，一方包名从 ``src/`` 推断，别名表允许包含本项目用不到
的条目，因此不含任何仓库专属常量。改动时请同步两边，勿单边分叉。
"""

from __future__ import annotations

import ast
import importlib.metadata
import sys
import tomllib
from pathlib import Path

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]
_BACKEND_SOURCE_PATH = _PROJECT_ROOT_PATH / "src" / "backend"
_LOCK_FILE_PATH = _PROJECT_ROOT_PATH / "uv.lock"
_PYPROJECT_FILE_PATH = _PROJECT_ROOT_PATH / "pyproject.toml"

# import 名与发行包名不一致的映射。仅覆盖 import root ≠ distribution name 的
# 少数情况；其余按 ``下划线 -> 连字符`` 规范化后即为发行包名。
#
# 这张表刻意允许包含本项目当前用不到的条目：本文件在模板仓库与各下游项目之间
# 共用同一份实现，各仓库的依赖集不同，若要求"每条别名都必须被用到"，同一份文
# 件就无法跨仓库复用。表的正确性由
# ``test_import_root_aliases_match_installed_metadata`` 用已安装包的真实元数据
# 校验，而不是靠"是否被用到"来间接推断。
_IMPORT_ROOT_TO_DISTRIBUTION_NAME: dict[str, str] = {
    "PIL": "pillow",
    "dotenv": "python-dotenv",
    "fitz": "pymupdf",
    "pythonjsonlogger": "python-json-logger",
    "yaml": "pyyaml",
}

_SOURCE_ROOT_PATH = _PROJECT_ROOT_PATH / "src"


def _normalize_distribution_name(raw_name: str) -> str:
    """把发行包名规范化为 PEP 503 形式（小写、下划线转连字符）。

    Args:
        raw_name (str): 原始发行包名。

    Returns:
        str: 规范化后的发行包名。
    """
    return raw_name.strip().lower().replace("_", "-")


def _read_project_distribution_name() -> str:
    """从 ``pyproject.toml`` 读取本项目自身的发行包名。

    刻意不写死项目名：本文件在模板仓库与各下游项目之间共用，写死会让它一到别的
    仓库就 KeyError。

    Returns:
        str: 规范化后的本项目发行包名，对应 ``uv.lock`` 中的根 package。
    """
    pyproject_document = tomllib.loads(_PYPROJECT_FILE_PATH.read_text(encoding="utf-8"))
    return _normalize_distribution_name(pyproject_document["project"]["name"])


def _resolve_first_party_import_roots() -> frozenset[str]:
    """列出本仓库自己的顶层包名，它们不是外部依赖。

    直接看 ``src/`` 下有哪些包目录，而不是写死包名——这既是"一方代码"的定义
    本身，也让本文件不带任何仓库专属常量。

    Returns:
        frozenset[str]: ``src/`` 下的顶层包名集合。
    """
    return frozenset(
        child_path.name
        for child_path in _SOURCE_ROOT_PATH.iterdir()
        if child_path.is_dir() and (child_path / "__init__.py").exists()
    )


def _collect_module_level_import_roots(source_path: Path) -> set[str]:
    """收集单个文件中模块级、无保护 import 的顶层包名。

    只遍历模块 body 的直接子语句，因此 ``try``/``if`` 包裹的 import 与函数、
    类体内的延迟 import 都不会被计入——那些正是可选依赖的合法写法。

    Args:
        source_path (Path): 待扫描的 Python 源文件。

    Returns:
        set[str]: 模块级 import 的顶层包名集合（含标准库与一方包）。
    """
    parsed_module = ast.parse(source_path.read_text(encoding="utf-8"))
    import_root_names: set[str] = set()
    for statement in parsed_module.body:
        if isinstance(statement, ast.Import):
            import_root_names.update(alias.name.split(".")[0] for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom):
            # level > 0 是包内相对 import；module 为 None 只可能出现在相对 import。
            if statement.level == 0 and statement.module is not None:
                import_root_names.add(statement.module.split(".")[0])
    return import_root_names


def _collect_third_party_imports_by_distribution() -> dict[str, list[Path]]:
    """扫描后端源码，按发行包名归集模块级第三方 import 及其来源文件。

    Returns:
        dict[str, list[Path]]: 发行包名 -> 出现该 import 的源文件列表。
    """
    first_party_import_roots = _resolve_first_party_import_roots()
    imports_by_distribution: dict[str, list[Path]] = {}
    for source_path in sorted(_BACKEND_SOURCE_PATH.rglob("*.py")):
        for import_root_name in _collect_module_level_import_roots(source_path):
            if import_root_name in sys.stdlib_module_names:
                continue
            if import_root_name in first_party_import_roots:
                continue
            distribution_name = _IMPORT_ROOT_TO_DISTRIBUTION_NAME.get(
                import_root_name, _normalize_distribution_name(import_root_name)
            )
            imports_by_distribution.setdefault(distribution_name, []).append(
                source_path.relative_to(_PROJECT_ROOT_PATH)
            )
    return imports_by_distribution


def _resolve_bare_sync_distribution_closure() -> set[str]:
    """推算裸 ``uv sync``（不带 extra）会安装的发行包闭包。

    以 ``uv.lock`` 中本项目根 package 的 ``dependencies`` 为起点——该字段已是
    解析后的非可选根依赖集，天然排除只挂在 extra 上的包。随后沿各包的硬
    ``dependencies`` 展开，并对边上显式请求的 extra 追加其
    ``optional-dependencies``。

    Returns:
        set[str]: 规范化后的发行包名闭包。
    """
    lock_document = tomllib.loads(_LOCK_FILE_PATH.read_text(encoding="utf-8"))
    package_by_name = {
        _normalize_distribution_name(package["name"]): package
        for package in lock_document["package"]
    }

    root_package = package_by_name[_read_project_distribution_name()]
    pending_edges: list[dict] = list(root_package.get("dependencies", []))
    # 以 (包名, 请求的 extra) 为访问键：同一个包可能先以裸形式、后以带 extra 的
    # 形式被引入，只按包名去重会漏掉后者的 optional-dependencies。
    visited_edge_identities: set[tuple[str, tuple[str, ...]]] = set()

    while pending_edges:
        edge = pending_edges.pop()
        distribution_name = _normalize_distribution_name(edge["name"])
        requested_extras = tuple(edge.get("extra", ()))
        edge_identity = (distribution_name, requested_extras)
        if edge_identity in visited_edge_identities:
            continue
        visited_edge_identities.add(edge_identity)

        package_entry = package_by_name.get(distribution_name)
        if package_entry is None:
            continue
        pending_edges.extend(package_entry.get("dependencies", []))
        optional_dependencies = package_entry.get("optional-dependencies", {})
        for requested_extra in requested_extras:
            pending_edges.extend(optional_dependencies.get(requested_extra, []))

    return {distribution_name for distribution_name, _ in visited_edge_identities}


def test_module_level_imports_are_covered_by_project_dependencies() -> None:
    """后端模块级 import 的每个第三方包都必须能被裸 ``uv sync`` 装出来。"""
    imports_by_distribution = _collect_third_party_imports_by_distribution()
    installable_distribution_names = _resolve_bare_sync_distribution_closure()

    undeclared_distribution_names = sorted(
        distribution_name
        for distribution_name in imports_by_distribution
        if distribution_name not in installable_distribution_names
    )

    assert not undeclared_distribution_names, (
        "以下发行包在 src/backend/ 中被模块级 import，但裸 `uv sync`（不带任何 --extra）"
        "装不出来。新克隆会在 import 阶段直接 ModuleNotFoundError。\n"
        "修复方式：把它加入 pyproject.toml 的 [project.dependencies] 并 `uv lock`；"
        "若它本就是可选能力，则把 import 改为函数内延迟 import 或 try/except ImportError 保护。\n"
        + "\n".join(
            f"  - {distribution_name}: "
            + ", ".join(str(path) for path in imports_by_distribution[distribution_name][:5])
            for distribution_name in undeclared_distribution_names
        )
    )


def test_import_root_aliases_match_installed_metadata() -> None:
    """别名表的每条映射都必须与已安装包的真实元数据一致。

    别名表是本守卫唯一的人工输入，也是唯一的软肋：一条写错的映射会把未声明的
    包伪装成已声明，等于悄悄把守卫拆掉。这里拿 ``packages_distributions()``
    的真实 import-name -> distribution 关系去核对，而不是靠人肉复核。

    只校验当前环境里装了的包。装不到的条目跳过而非判红——别名表允许包含本项
    目用不到的条目（见表上注释），跳过才能让同一份文件跨项目复用。
    """
    import_root_to_installed_distributions = importlib.metadata.packages_distributions()

    mismatched_alias_descriptions: list[str] = []
    for import_root_name, mapped_distribution_name in sorted(
        _IMPORT_ROOT_TO_DISTRIBUTION_NAME.items()
    ):
        installed_distributions = import_root_to_installed_distributions.get(import_root_name)
        if not installed_distributions:
            continue
        actual_distribution_names = {
            _normalize_distribution_name(name) for name in installed_distributions
        }
        if mapped_distribution_name not in actual_distribution_names:
            mismatched_alias_descriptions.append(
                f"  - {import_root_name}: 表里写的是 {mapped_distribution_name}，"
                f"实际由 {sorted(actual_distribution_names)} 提供"
            )

    assert not mismatched_alias_descriptions, (
        "_IMPORT_ROOT_TO_DISTRIBUTION_NAME 中存在与实际安装元数据不符的映射。"
        "错误的映射会让未声明的包被误判为已声明，请按实际提供方修正：\n"
        + "\n".join(mismatched_alias_descriptions)
    )
