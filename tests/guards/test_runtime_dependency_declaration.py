"""守护「模块级 import 必须由依赖声明覆盖」的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

为什么需要这个守卫：这套模板与其下游项目已经被同一类缺陷咬过三次，形态都是
"环境里恰好有、声明里根本没有"——

1. ``httpx[socks]``：``starlette.testclient`` 的硬依赖漏声明，靠 ``.venv``
   残留才跑绿（见 ``pyproject.toml`` 的 ``[dependency-groups] dev`` 注释）。
2. ``cryptography``：被 ``create_app()`` 装配路径上的模块（模型密钥加密工具）
   顶层 import，却只经某个可选 extra 的附属包传递安装。裸 ``uv sync`` 的新克
   隆必然在 collection 阶段就 ``ModuleNotFoundError``，几百个测试全灭。
3. 同一个 ``httpx`` 缺口，第二次以"守卫抓不到"的形态复现：它的 import 在
   ``tests/`` 里，而本守卫最初只扫 ``src/backend/``，于是这条约定虽然写着
   "httpx 是教训之一"，实现上却结构性地不可能抓到它。CI 因此红了一个多月。

这类缺陷的共同点是**本地环境掩盖了声明缺口**：开发机装过 extra 或留有旧
venv，测试全绿；CI 或新克隆做对应的 ``uv sync`` 才炸。普通测试抓不到它——测
试自己就跑在那个被污染的环境里。所以只能拿"声明"而不是"环境"当事实来源：本
守卫完全基于 ``pyproject.toml`` 与 ``uv.lock`` 静态推算，不 import 任何被检
查的包，也不关心当前 venv 里装了什么。

## 两个维度

守卫按"谁装它、怎么装"分两个维度，判定逻辑同一份，差别只在允许的依赖集：

| 扫描范围 | 允许的依赖集 | 对应现实 |
|---|---|---|
| ``src/backend/`` | 裸 ``uv sync``（不带 extra 与 group） | 生产镜像、新克隆 |
| ``tests/`` | ``uv sync --all-extras --all-groups --frozen`` | CI 的安装口径 |

第二个维度是第 3 条教训的直接产物：测试依赖的声明缺口只会在 CI 里炸，而 CI
装的正是这条全量命令，所以"测试能不能在 CI 里 import 成功"必须拿它当尺子。
``tests/playwright-e2e/`` 是独立的 TypeScript/Node 包，不受 Python 依赖声明约
束，扫描时按"是不是 Node 包"剪掉（见 ``_iter_python_source_files``）。

在当前没有缺口的仓库里，本守卫是**预防性**的：它挡的是将来有人往装配路径或
测试树上加一个只靠残留环境才装得出来的顶层 import。

判定口径：
- 只统计**模块级且无保护**的 import。``try: import x / except ImportError``
  或函数体内的延迟 import 属于合法的可选依赖（extra 能力按需安装），不在
  约束范围内。
- 允许的依赖集从 ``uv.lock`` 的根 package 出发展开硬依赖闭包，也就是对应那条
  ``uv sync`` 实际会装进 venv 的包集合。

本文件设计为在模板仓库与各下游项目之间共用**同一份**实现：项目名从
``pyproject.toml`` 读取，一方包名从仓库自身的目录结构推断，别名表允许包含本
项目用不到的条目，因此不含任何仓库专属常量。改动时请同步两边，勿单边分叉。
"""

from __future__ import annotations

import ast
import importlib.metadata
import os
import sys
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]
_BACKEND_SOURCE_PATH = _PROJECT_ROOT_PATH / "src" / "backend"
# 测试树根目录 = 本文件所在 guards 目录的父目录，刻意不写 "tests" 字面量。
_TESTS_ROOT_PATH = Path(__file__).resolve().parents[1]
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

# 前端依赖目录名与 Node 包清单名：扫描 Python 源码时用来剪掉非 Python 子树。
_VENDORED_DEPENDENCY_DIRECTORY_NAME = "node_modules"
_NODE_PACKAGE_MANIFEST_NAME = "package.json"


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


def _iter_python_source_files(scan_root_path: Path) -> Iterator[Path]:
    """遍历目录下属于本仓库 Python 源码的 ``*.py`` 文件。

    剪掉三类子树，它们都不受本仓库 Python 依赖声明的约束：

    - 点开头目录：``.venv``、``.git``、``.claude/worktrees/`` 里的仓库副本等；
    - ``node_modules``：前端依赖里夹带的 Python 脚本会造成大量假阳性；
    - 自带 ``package.json`` 的目录：那是独立的 Node/TS 包，本仓库的
      ``tests/playwright-e2e/`` 正属此类。这里按"是不是 Node 包"判定而不是写死
      目录名，本文件才能跨仓库复用。

    Args:
        scan_root_path (Path): 扫描起点目录。

    Yields:
        Path: 该目录树下的 Python 源文件，同层按路径名排序，顺序稳定可复现。
    """
    for child_path in sorted(scan_root_path.iterdir()):
        if child_path.is_dir():
            if child_path.name.startswith("."):
                continue
            if child_path.name == _VENDORED_DEPENDENCY_DIRECTORY_NAME:
                continue
            if (child_path / _NODE_PACKAGE_MANIFEST_NAME).exists():
                continue
            yield from _iter_python_source_files(child_path)
        elif child_path.suffix == ".py":
            yield child_path


def _describe_repository_relative_path(target_path: Path) -> str:
    """把路径渲染成相对仓库根的可读形式，用于失败信息。

    仓库外的路径（负控用的 ``tmp_path`` 合成源码树）也要能渲染，因此用
    ``os.path.relpath`` 而不是 ``Path.relative_to``——后者遇到仓库外路径会抛
    ``ValueError``。

    Args:
        target_path (Path): 待渲染的路径。

    Returns:
        str: 相对仓库根的路径字符串。
    """
    return os.path.relpath(target_path, _PROJECT_ROOT_PATH)


def _resolve_repository_module_import_roots() -> frozenset[str]:
    """列出本仓库自己提供的顶层可导入名，它们是一方代码而不是外部发行包。

    两类来源：

    - ``src/`` 下的包目录，即后端一方代码；
    - 仓库内**非包目录**（没有 ``__init__.py``）里的模块，例如 ``hooks/shared/``
      的 hook 脚本——测试会先把这类目录插进 ``sys.path`` 再 import 它们，写法上
      和第三方 import 一模一样；隐式命名空间包下的模块也走这条分支，同样是一方
      代码。

    判定依据是"仓库里是否真的存在同名模块"，而不是写死一份名单——写死名单的
    话，同一份文件一到下游项目就会把它们的 hook 与脚本模块误判成未声明的第三
    方包。代价是仓库里若真有个 ``httpx.py`` 会掩盖同名缺口；相比"跨仓库直接不
    可用"，这个代价可以接受。

    Returns:
        frozenset[str]: 一方顶层可导入名集合。
    """
    first_party_import_roots = {
        child_path.name
        for child_path in _SOURCE_ROOT_PATH.iterdir()
        if child_path.is_dir() and (child_path / "__init__.py").exists()
    }
    for source_path in _iter_python_source_files(_PROJECT_ROOT_PATH):
        if not (source_path.parent / "__init__.py").exists():
            first_party_import_roots.add(source_path.stem)
    return frozenset(first_party_import_roots)


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


def _collect_third_party_imports_by_distribution(scan_root_path: Path) -> dict[str, list[Path]]:
    """扫描给定源码树，按发行包名归集模块级第三方 import 及其来源文件。

    Args:
        scan_root_path (Path): 待扫描的源码树根目录。

    Returns:
        dict[str, list[Path]]: 发行包名 -> 出现该 import 的源文件列表。
    """
    # 被扫描目录自身的名字也算一方包名：``tests`` 就是靠项目根在 ``sys.path`` 上
    # 被当作命名空间包 import 的（``from tests.realdb_test_support import ...``）。
    first_party_import_roots = _resolve_repository_module_import_roots() | {scan_root_path.name}
    imports_by_distribution: dict[str, list[Path]] = {}
    for source_path in _iter_python_source_files(scan_root_path):
        for import_root_name in sorted(_collect_module_level_import_roots(source_path)):
            if import_root_name in sys.stdlib_module_names:
                continue
            if import_root_name in first_party_import_roots:
                continue
            distribution_name = _IMPORT_ROOT_TO_DISTRIBUTION_NAME.get(
                import_root_name, _normalize_distribution_name(import_root_name)
            )
            imports_by_distribution.setdefault(distribution_name, []).append(source_path)
    return imports_by_distribution


def _read_lock_package_index() -> dict[str, dict]:
    """读取 ``uv.lock``，按规范化发行包名索引全部 package 条目。

    Returns:
        dict[str, dict]: 规范化发行包名 -> ``uv.lock`` 中的 package 条目。
    """
    lock_document = tomllib.loads(_LOCK_FILE_PATH.read_text(encoding="utf-8"))
    return {
        _normalize_distribution_name(package_entry["name"]): package_entry
        for package_entry in lock_document["package"]
    }


def _read_lock_root_package() -> dict:
    """取 ``uv.lock`` 中本项目自身的根 package 条目。

    Returns:
        dict: 根 package 条目，含 ``dependencies`` 与（若有）
            ``optional-dependencies`` / ``dev-dependencies`` 边集。
    """
    return _read_lock_package_index()[_read_project_distribution_name()]


def _resolve_distribution_closure(root_dependency_edges: list[dict]) -> set[str]:
    """从给定的根依赖边集出发，沿 ``uv.lock`` 的硬依赖展开出发行包闭包。

    根边集决定这个闭包对应哪条 ``uv sync``，因此刻意由调用方传入而不是写死在
    这里：只给根 package 的 ``dependencies`` 就是裸 ``uv sync``；额外并入
    ``optional-dependencies`` 与 ``dev-dependencies`` 就是
    ``uv sync --all-extras --all-groups``。展开时对边上显式请求的 extra 追加其
    ``optional-dependencies``。

    Args:
        root_dependency_edges (list[dict]): ``uv.lock`` 形态的根依赖边列表。

    Returns:
        set[str]: 规范化后的发行包名闭包。
    """
    package_by_name = _read_lock_package_index()
    pending_edges: list[dict] = list(root_dependency_edges)
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


def _resolve_bare_sync_distribution_closure() -> set[str]:
    """推算裸 ``uv sync``（不带 extra 与 group）会安装的发行包闭包。

    以 ``uv.lock`` 中本项目根 package 的 ``dependencies`` 为起点——该字段已是
    解析后的非可选根依赖集，天然排除只挂在 extra 或 dev group 上的包。

    Returns:
        set[str]: 规范化后的发行包名闭包。
    """
    return _resolve_distribution_closure(_read_lock_root_package().get("dependencies", []))


def _resolve_full_sync_distribution_closure() -> set[str]:
    """推算 ``uv sync --all-extras --all-groups`` 会安装的发行包闭包。

    这是 CI 实际执行的安装口径（``--frozen`` 只是禁止重解析，不改变包集合），
    因此也是"测试能不能在 CI 里 import 成功"的唯一事实来源。除根 package 的硬
    依赖外，并入它全部 extra 与全部 dependency group 的边。

    Returns:
        set[str]: 规范化后的发行包名闭包。
    """
    root_package = _read_lock_root_package()
    root_dependency_edges: list[dict] = list(root_package.get("dependencies", []))
    for extra_dependency_edges in root_package.get("optional-dependencies", {}).values():
        root_dependency_edges.extend(extra_dependency_edges)
    for group_dependency_edges in root_package.get("dev-dependencies", {}).values():
        root_dependency_edges.extend(group_dependency_edges)
    return _resolve_distribution_closure(root_dependency_edges)


@dataclass(frozen=True)
class _DependencyDeclarationScope:
    """一条 ``uv sync`` 口径：它装出哪些包、缺依赖该补到哪、失败信息怎么称呼它。

    把三个总是一起出现的值收敛成对象，让两个扫描维度和负控用例共享同一段断言
    逻辑，而不是各自复制一份判定与提示文案。

    Attributes:
        sync_command_description (str): 安装口径的人类可读描述，写进失败信息。
        declaration_target_description (str): 缺失依赖应补进 ``pyproject.toml``
            的哪个声明段。
        resolve_installable_distribution_names (Callable[[], set[str]]): 惰性推算
            该口径下可安装的发行包闭包；惰性是为了不在模块 import 阶段读锁文件。
    """

    sync_command_description: str
    declaration_target_description: str
    resolve_installable_distribution_names: Callable[[], set[str]]


_BARE_SYNC_DECLARATION_SCOPE = _DependencyDeclarationScope(
    sync_command_description="裸 `uv sync`（不带任何 --extra / --group）",
    declaration_target_description="[project.dependencies]",
    resolve_installable_distribution_names=_resolve_bare_sync_distribution_closure,
)

_FULL_SYNC_DECLARATION_SCOPE = _DependencyDeclarationScope(
    sync_command_description="`uv sync --all-extras --all-groups --frozen`（CI 的安装口径）",
    declaration_target_description="[dependency-groups] dev",
    resolve_installable_distribution_names=_resolve_full_sync_distribution_closure,
)


def _assert_module_level_imports_are_installable(
    *,
    scan_root_path: Path,
    declaration_scope: _DependencyDeclarationScope,
) -> None:
    """断言某棵源码树的模块级第三方 import 都能被指定的 ``uv sync`` 口径装出来。

    两个扫描维度共用这一条断言，
    ``test_undeclared_module_level_import_fails_the_guard`` 也通过它做负控，因此
    负控跑的确实是真实用例走的同一段判定逻辑，而不是它的复制品。

    Args:
        scan_root_path (Path): 待扫描的源码树根目录。
        declaration_scope (_DependencyDeclarationScope): 允许的依赖集口径。

    Raises:
        AssertionError: 存在未被该口径覆盖的模块级第三方 import。
    """
    imports_by_distribution = _collect_third_party_imports_by_distribution(scan_root_path)
    installable_distribution_names = declaration_scope.resolve_installable_distribution_names()

    undeclared_distribution_names = sorted(
        distribution_name
        for distribution_name in imports_by_distribution
        if distribution_name not in installable_distribution_names
    )

    assert not undeclared_distribution_names, (
        f"以下发行包在 {_describe_repository_relative_path(scan_root_path)}/ 中被模块级 import，"
        f"但 {declaration_scope.sync_command_description} 装不出来。"
        "对应环境会在 import / collection 阶段直接 ModuleNotFoundError。\n"
        "修复方式：把它加入 pyproject.toml 的 "
        f"{declaration_scope.declaration_target_description} 并 `uv lock`；"
        "若它本就是可选能力，则把 import 改为函数内延迟 import 或 try/except ImportError 保护。\n"
        + "\n".join(
            f"  - {distribution_name}: "
            + ", ".join(
                _describe_repository_relative_path(source_path)
                for source_path in imports_by_distribution[distribution_name][:5]
            )
            for distribution_name in undeclared_distribution_names
        )
    )


def test_module_level_imports_are_covered_by_project_dependencies() -> None:
    """后端模块级 import 的每个第三方包都必须能被裸 ``uv sync`` 装出来。"""
    _assert_module_level_imports_are_installable(
        scan_root_path=_BACKEND_SOURCE_PATH,
        declaration_scope=_BARE_SYNC_DECLARATION_SCOPE,
    )


def test_test_suite_module_level_imports_are_covered_by_dev_dependencies() -> None:
    """``tests/`` 的模块级 import 必须能被 CI 的全量 ``uv sync`` 装出来。

    测试依赖的声明缺口只在 CI 里炸：开发机 ``.venv`` 里常年留着早已从声明中摘
    除的包（``httpx`` 就是这么被掩盖了一个多月），而 CI 的
    ``uv sync --all-extras --all-groups --frozen`` 严格按锁文件装，缺一个就在
    collection 阶段全灭。所以这里拿 CI 的安装口径当尺子。
    """
    _assert_module_level_imports_are_installable(
        scan_root_path=_TESTS_ROOT_PATH,
        declaration_scope=_FULL_SYNC_DECLARATION_SCOPE,
    )


def test_undeclared_module_level_import_fails_the_guard(tmp_path: Path) -> None:
    """负控：喂一个未声明的模块级 import，上面那条断言必须变红。

    守卫的全部价值在于"真的会红"，而这一点无法从绿色运行里推出来——旧版守卫在
    ``httpx`` 缺口面前也是一路绿灯。这里在 ``tmp_path`` 造一棵合成源码树（不碰
    任何生产代码，也不碰真实依赖声明），让真实用例走的那段判定逻辑跑一遍并断言
    它变红，同时断言同一棵树里那个**已声明**的 import 不被误报。

    Args:
        tmp_path (Path): pytest 提供的临时目录，充当合成源码树根。
    """
    synthetic_source_path = tmp_path / "test_synthetic_dependency_gap.py"
    synthetic_source_path.write_text(
        "import pytest\nimport zzz_undeclared_probe\n", encoding="utf-8"
    )

    with pytest.raises(AssertionError) as raised_assertion_info:
        _assert_module_level_imports_are_installable(
            scan_root_path=tmp_path,
            declaration_scope=_FULL_SYNC_DECLARATION_SCOPE,
        )

    failure_message = str(raised_assertion_info.value)
    # 匹配清单行而不是裸包名：tmp_path 本身就含 "pytest"（pytest-of-<user>/...），
    # 裸包名匹配会把路径当成命中，误证"已声明的包也被报了"。
    assert "  - zzz-undeclared-probe: " in failure_message
    assert "  - pytest: " not in failure_message


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
