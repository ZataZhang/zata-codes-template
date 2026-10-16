"""Pytest 全局配置：本地导入路径、跨目录共享夹具、真实库残留哨兵与本地核心档。

``_realdb_residue_sentinel`` 对所有测试生效：前后对比哨兵覆盖表的主键集合，
任何测试泄漏或误删真实数据库数据都会当场 fail 并列出泄漏的表与 ID。写真实
数据库的测试（打 ``@pytest.mark.realdb``）会被 xdist 串行调度，避免并行
worker 互相污染快照。

``_guard_shared_database_external_writer`` 是哨兵的前置防线：dev server
（``just run``）与测试共用 ``.env.local`` 的 ``DATABASE_URL`` 时，外部写入既会让
哨兵误报残留，也可能被测试里的整库收敛操作改坏。故在有 realdb 测试被选中时先探测
外部写者，命中即 fail-fast。

``--core-tier`` 把本次收集收窄到本地核心档，口径见 ``docs/ai-standards/testing.md``。
"""

from __future__ import annotations

import importlib.util
import os
import re
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import pytest

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter


def _ensure_project_root_on_path() -> None:
    """Ensure project root is on sys.path for local package imports."""
    project_root_path = Path(__file__).resolve().parents[1]
    if str(project_root_path) not in sys.path:
        sys.path.insert(0, str(project_root_path))


# backend 包的导入依赖上面这行先把项目根放进 sys.path，因此不能提到文件顶部。
_ensure_project_root_on_path()

from tests.realdb_test_support import has_realdb_marker  # noqa: E402

_REALDB_SCOPE: str = "realdb"

# 写真实数据库的测试文件（整个文件打 ``pytestmark = pytest.mark.realdb``）。
# controller 端 xdist 调度器只有 nodeid、拿不到 item，无法按 marker 判断；
# 而文件是 realdb 测试的天然串行单元（整文件同标记），故按文件路径分组，
# 让同文件的 realdb 测试在同一 worker 串行，哨兵快照不被其他 worker 干扰。
_REALDB_TEST_FILES: frozenset[str] = frozenset(
    {
        "tests/backend/test_admin_user_management.py",
        "tests/backend/test_auth_domains.py",
        "tests/backend/test_admin_run_trace_api.py",
    }
)


class _RealDbLoadScopeScheduling:
    """把 ``_REALDB_TEST_FILES`` 里的测试固定进同一 scope 的 loadgroup 调度器。

    xdist 自带的 ``LoadGroupScheduling`` 只按 nodeid 里的 ``@<组名>`` 后缀
    分组。realdb 测试写入由 ``DATABASE_URL`` 指向的真实数据库，哨兵依赖前后
    主键快照，若 realdb 测试跨 worker 并行，快照会把其他 worker 的写入误判为
    残留。因此把 realdb 文件收进单一 scope（同 worker 串行），其余测试回退到
    xdist 默认的文件级 loadgroup 分组，保住并行度。
    """

    def __new__(cls, config, log=None):
        """惰性继承 xdist 的 LoadScopeScheduling，避免无 xdist 时导入失败。"""
        from xdist.scheduler.loadscope import LoadScopeScheduling

        class _Scheduling(LoadScopeScheduling):
            def _split_scope(self_inner, nodeid: str) -> str:  # noqa: N805
                scope_name = nodeid.split("::")[0]
                if scope_name in _REALDB_TEST_FILES:
                    return _REALDB_SCOPE
                if nodeid.rfind("@") > nodeid.rfind("]"):
                    return nodeid.split("@")[-1]
                return nodeid

        return _Scheduling(config, log)


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_make_scheduler(config, log) -> "_RealDbLoadScopeScheduling | None":
    """把 ``--dist=loadgroup`` 替换为按 realdb 文件分组的调度器。"""
    if config.getoption("dist") != "loadgroup":
        return None
    return _RealDbLoadScopeScheduling(config, log)


_RUN_STATE_FILE_PATH = Path(__file__).resolve().parents[1] / ".env.run-state"
_DEV_SERVER_PROBE_TIMEOUT_SECONDS = 0.5
# 故意与 dev server 共用 DATABASE_URL 时的手动逃生口，见 docs/ai-standards/testing.md。
_ALLOW_SHARED_DATABASE_ENV_VAR = "ALLOW_SHARED_DATABASE"


def _read_run_state_value(key: str) -> str | None:
    """读取 ``just run`` 记录在 ``.env.run-state`` 的某一项。

    Args:
        key: 要读取的键名。

    Returns:
        str | None: 去空白后的值；文件缺失或未记录该键时返回 ``None``。
    """
    try:
        run_state_lines = _RUN_STATE_FILE_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for run_state_line in run_state_lines:
        line_key, separator, value = run_state_line.partition("=")
        if separator and line_key.strip() == key:
            return value.strip()
    return None


def _dev_server_backend_port() -> int | None:
    """读取 ``just run`` 记录在 ``.env.run-state`` 的后端端口。

    Returns:
        int | None: 后端端口；文件缺失或未记录时返回 ``None``。
    """
    raw_port = _read_run_state_value("BACKEND_PORT")
    if raw_port is None:
        return None
    try:
        return int(raw_port)
    except ValueError:
        return None


def _current_database_name() -> str | None:
    """取当前测试要写的数据库名（``DATABASE_URL`` 去掉驱动/凭据/查询串后的库名）。

    Returns:
        str | None: 数据库名；解析不出时返回 ``None``。
    """
    from backend.infrastructure.persistence.database import DATABASE_URL  # noqa: PLC0415

    database_name = DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
    return database_name or None


def _has_local_listener(port: int) -> bool:
    """探测本机 ``port`` 是否有进程在监听。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.settimeout(_DEV_SERVER_PROBE_TIMEOUT_SECONDS)
        return probe_socket.connect_ex(("127.0.0.1", port)) == 0


def _realdb_tests_in_scope(config: pytest.Config) -> bool:
    """粗判本次会话是否会选中 realdb 测试。

    xdist 的 controller 进程不做 collection、拿不到 item，只能按 ``-m`` 表达式与
    命令行目标路径推断：显式排除 realdb 判否；显式包含 realdb、或目标路径可能覆盖
    ``_REALDB_TEST_FILES`` 时判是；未给目标路径（默认全量）判是。

    Args:
        config: 当前 pytest 配置对象。

    Returns:
        bool: 本次会话是否需要检查外部写者。
    """
    mark_expression = (config.getoption("markexpr", None) or "").replace(" ", "").lower()
    if "notrealdb" in mark_expression:
        return False
    if "realdb" in mark_expression:
        return True
    raw_targets = list(config.args or [])
    if not raw_targets:
        return True
    project_root_path = Path(config.rootpath)
    for raw_target in raw_targets:
        target_path = Path(raw_target.split("::", 1)[0])
        if not target_path.is_absolute():
            target_path = project_root_path / target_path
        for realdb_file in _REALDB_TEST_FILES:
            realdb_path = project_root_path / realdb_file
            if realdb_path == target_path or realdb_path.is_relative_to(target_path):
                return True
    return False


def _listener_shares_database() -> bool:
    """端口有监听者时，判断它是否与本次测试写的是同一个库。

    端口有监听者只说明「本机有个 dev server」，不说明它连的是本库：run-state 记录的
    库名与当前测试的库名不同，就是别处（主仓 / 其他 worktree）占了同一端口而与本库
    无关，不拦。旧 run-state 无库名或库名解析不出时保持保守拦截。

    Returns:
        bool: 监听者可能与本次测试共用同一个库时为 ``True``。
    """
    run_state_database_name = _read_run_state_value("DATABASE_NAME")
    current_database_name = _current_database_name()
    return (
        run_state_database_name is None
        or current_database_name is None
        or run_state_database_name == current_database_name
    )


def _find_project_active_runs() -> list[tuple[str, str]]:
    """调用项目可选提供的「库内活跃运行探测」，未提供时返回空列表。

    该钩子依赖业务表结构，所以不进通用守卫：项目需要时在
    ``tests/realdb_test_support.py`` 定义 ``find_live_nonterminal_runs()``，返回
    ``(运行标识, 状态)`` 列表。没有定义时本信号关闭，守卫只看端口 + 库名。

    Returns:
        list[tuple[str, str]]: 仍在执行的运行；钩子缺失、库不可用或表未建立时为空。
    """
    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415

    from tests import realdb_test_support  # noqa: PLC0415

    probe_active_runs = getattr(realdb_test_support, "find_live_nonterminal_runs", None)
    if probe_active_runs is None:
        return []
    try:
        return list(probe_active_runs())
    except SQLAlchemyError:
        # 表尚未建立（全新库）或库暂不可用：交给测试自身暴露问题，守卫不越权。
        return []


def _guard_shared_database_external_writer(config: pytest.Config) -> None:
    """选中 realdb 测试时，若外部进程正在用同一个库则终止本次会话。

    ``just run``（dev server）与 ``just test`` 都从 ``.env.local`` 读同一个
    ``DATABASE_URL``。dev server 的写入会让残留哨兵把外部写入误判成测试残留，
    也可能被测试里的整库收敛操作改坏——报假错的同时真的改坏数据。因此在收集测试前
    探测外部写者，命中即 fail-fast。

    通用信号：``just run`` 记录的后端端口有监听者**且该 run-state 指向同一个数据库**。
    只看端口会把「别处进程占了同名端口、但连的是另一个库」误判成外部写者（worktree
    与主仓很常见），故以 run-state 记录的 ``DATABASE_NAME`` 区分；旧 run-state 未记录
    库名时保持保守拦截。项目可再通过 ``find_live_nonterminal_runs`` 钩子叠加「库内
    有活跃运行」信号。确实需要共用数据库时设 ``ALLOW_SHARED_DATABASE=1`` 跳过本守卫。

    Args:
        config: 当前 pytest 配置对象。
    """
    if os.environ.get(_ALLOW_SHARED_DATABASE_ENV_VAR) == "1":
        return
    if not _realdb_tests_in_scope(config):
        return

    blocking_reasons: list[str] = []
    backend_port = _dev_server_backend_port()
    if backend_port is not None and _has_local_listener(backend_port):
        if _listener_shares_database():
            run_state_database_name = _read_run_state_value("DATABASE_NAME")
            blocking_reasons.append(
                f"`just run` 的后端仍在监听 {backend_port} 端口"
                + (
                    f"（run-state 记录的库：{run_state_database_name}）"
                    if run_state_database_name
                    else ""
                )
            )
    active_runs = _find_project_active_runs()
    if active_runs:
        blocking_reasons.append(
            "数据库中存在仍在执行的运行："
            + ", ".join(f"{run_id}({status})" for run_id, status in active_runs[:3])
        )
    if not blocking_reasons:
        return
    pytest.exit(
        "检测到外部进程正在使用测试要写的真实数据库（"
        + "；".join(blocking_reasons)
        + f"）。\n`just test` 与 `just run` 共用同一个库（库名：{_current_database_name()}），"
        "继续跑会：\n"
        "  1) 让 realdb 残留哨兵把 dev server 写入的行误判为测试残留；\n"
        "  2) 让测试里的整库收敛操作改坏你正在使用的数据。\n"
        "请先停掉 `just run` 与前端活跃会话；"
        f"确实需要共用时设 {_ALLOW_SHARED_DATABASE_ENV_VAR}=1。"
    )


_CORE_TIER_LIST_PATH = Path(__file__).resolve().parent / "core_set.txt"


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册 ``--core-tier``：把本次收集收窄到本地核心档。

    Args:
        parser: pytest 选项解析器。
    """
    parser.addoption(
        "--core-tier",
        action="store_true",
        default=False,
        help="只跑 tests/core_set.txt 列出的文件与显式 core 标记的用例（本地档口径，全量交 CI）",
    )


_CORE_TIER_PATHS_CACHE: set[str] | None = None
_CORE_MARKER_PATTERN = re.compile(r"\bpytest\.mark\.core\b")


def _load_core_tier_paths() -> set[str]:
    """读取本地核心档名单（进程内缓存一次）。

    Returns:
        名单内测试文件的绝对路径集合；名单文件缺失时为空集合。
    """
    global _CORE_TIER_PATHS_CACHE  # noqa: PLW0603
    if _CORE_TIER_PATHS_CACHE is not None:
        return _CORE_TIER_PATHS_CACHE
    listed_paths: set[str] = set()
    if _CORE_TIER_LIST_PATH.is_file():
        # 名单里的路径相对仓库根，而名单文件本身在 tests/ 下，必须以仓库根为基准解析。
        project_root_path = _CORE_TIER_LIST_PATH.resolve().parents[1]
        for raw_line in _CORE_TIER_LIST_PATH.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            listed_paths.add(str((project_root_path / stripped).resolve()))
    _CORE_TIER_PATHS_CACHE = listed_paths
    return listed_paths


def _declares_core_marker(module_path: Path) -> bool:
    """测试模块源码里是否显式声明了 ``core`` 标记。

    例外通道直接读源码而不是等 ``just test-core-refresh`` 把它写进名单，否则新加的
    ``@pytest.mark.core`` 要跑一次几分钟的全量才生效，等于没有例外。

    Args:
        module_path: 测试模块的绝对路径。

    Returns:
        源码出现 ``pytest.mark.core`` 时为 True。
    """
    try:
        return bool(_CORE_MARKER_PATTERN.search(module_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError):
        return False


_WORKING_TREE_PLAN_CACHE: "tuple[set[str], set[str], list[str], bool] | None" = None


def _working_tree_test_plan() -> "tuple[set[str], set[str], list[str], bool]":
    """本地档本次要额外覆盖的测试：改动/新增的测试、预算内的 src 映射测试。

    把"改了代码就把覆盖它的测试临时放开"做成机制，而不是写进提示词指望 agent 记得：
    最该验证的那批用例往往正是被耗时规则请出本地档的贵文件，回归最容易漏的就是这里；
    而且 ``check-test-flag`` 把标记绑在整份有效树上，本地档若不含这些测试，门禁就会给
    一条从未执行过的用例盖章。

    "什么算改动"与"改动映射到哪些测试"的判断只有一份实现：``scripts/shared/testing/test_tiers.py``。
    这里按文件路径动态加载它并缓存，非本地档会话（CI 全量、单跑某个文件）不付这份成本；
    conftest 自己不再写一遍 git 采集——那正是仓库重复检测 hook 要拦的东西。

    Returns:
        ``(改动测试绝对路径集合, 预算内 src 映射测试绝对路径集合, 超预算的映射测试相对路径,
        影响面是否无法收窄)``。脚本不可用时集合为空，本地档退化成只读名单，不会误放大成全量。
    """
    global _WORKING_TREE_PLAN_CACHE  # noqa: PLW0603
    if _WORKING_TREE_PLAN_CACHE is not None:
        return _WORKING_TREE_PLAN_CACHE
    project_root_path = _CORE_TIER_LIST_PATH.resolve().parents[1]
    tiers_script_path = project_root_path / "scripts" / "shared" / "testing" / "test_tiers.py"
    empty_plan: "tuple[set[str], set[str], list[str], bool]" = (set(), set(), [], False)
    if not tiers_script_path.is_file():
        _WORKING_TREE_PLAN_CACHE = empty_plan
        return _WORKING_TREE_PLAN_CACHE
    module_spec = importlib.util.spec_from_file_location("zata_test_tiers", tiers_script_path)
    if module_spec is None or module_spec.loader is None:
        _WORKING_TREE_PLAN_CACHE = empty_plan
        return _WORKING_TREE_PLAN_CACHE
    tiers_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(tiers_module)
    changed_tests, mapped_within, mapped_over, prefer_full_run = (
        tiers_module.working_tree_test_plan()
    )

    def _to_absolute(relative_paths: list[str]) -> set[str]:
        """把脚本返回的相对路径转成绝对路径集合。

        Args:
            relative_paths: 相对仓库根的路径列表。

        Returns:
            对应的绝对路径字符串集合。
        """
        return {
            str((project_root_path / relative_path).resolve()) for relative_path in relative_paths
        }

    _WORKING_TREE_PLAN_CACHE = (
        _to_absolute(list(changed_tests)),
        _to_absolute(list(mapped_within)),
        list(mapped_over),
        bool(prefer_full_run),
    )
    return _WORKING_TREE_PLAN_CACHE


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """``--core-tier`` 生效时，跳过本地档之外的测试模块，连 import 都不做。

    本地档 = ``core_set.txt`` ∪ 改动/新增的测试 ∪ 改动 src 映射到的测试 ∪ 显式 ``core``
    标记。前两条保证"改过的东西一定被验证"，第三条补上"改了产品代码后，覆盖它的贵用例
    即使被耗时规则请出了名单，这一次也要跑"。

    过滤放在 collection 之前而不是 ``pytest_collection_modifyitems``：本仓 1300+ 条用例
    分布在 150+ 个模块里，光把全部模块 import 一遍再 deselect 就要好几秒，而本地档整个
    预算只有 30s。也不走 ``-m`` 表达式，是为了让 ``pytest.ini`` 的 ``addopts`` 保持唯一
    口径——本地档与全量档共用同一套 marker 排除（slow / real_api / redis），本地档只是
    在其上再按文件切一刀，两边不存在"本地跑过但语义不同"的第二套规则。

    Args:
        collection_path: 待判断的文件路径。
        config: 当前 pytest 配置对象。

    Returns:
        需要跳过该模块时返回 True，否则返回 None 交给其他插件判断。
    """
    if not config.getoption("core_tier", False):
        return None
    if collection_path.suffix != ".py" or not collection_path.name.startswith("test_"):
        return None
    resolved_key = str(collection_path.resolve())
    changed_tests, mapped_tests, _mapped_over, _prefer_full = _working_tree_test_plan()
    if resolved_key in _load_core_tier_paths():
        return None
    if resolved_key in changed_tests or resolved_key in mapped_tests:
        return None
    return not _declares_core_marker(collection_path.resolve())


def pytest_terminal_summary(terminalreporter: TerminalReporter, config: pytest.Config) -> None:
    """``--core-tier`` 结束时打印本地档口径，让超支可见。

    Args:
        terminalreporter: 终端报告器。
        config: 当前 pytest 配置对象。
    """
    if not config.getoption("core_tier", False):
        return
    terminalreporter.write_sep("=", "local core tier")
    changed_tests, mapped_tests, mapped_over, prefer_full_run = _working_tree_test_plan()
    terminalreporter.write_line(
        f"本地档 = 名单 {len(_load_core_tier_paths())} 个文件 ∪ 改动的 "
        f"{len(changed_tests)} 个测试 ∪ src 映射补跑 {len(mapped_tests)} 个"
        "（超出补跑预算的会点名）∪ core 标记。"
        "墙钟超过 30s 预算时执行 `just test-core-refresh` 重算名单，"
        "全量口径见 `just test all`，含 slow 的真·全量见 CI。"
    )
    if mapped_over:
        terminalreporter.write_line(
            f"⚠️  与本次改动相关但超出补跑预算、这次没跑的 {len(mapped_over)} 个文件："
        )
        for over_path in mapped_over:
            terminalreporter.write_line(f"      {over_path}")
        terminalreporter.write_line(
            "   这些仍在 CI 全量档里；想现在就验掉它们：`just test-changed`（不设预算、不写提交"
            "标记），或 `JUST_MAPPED_BUDGET_SECONDS=<秒> just test` 临时抬高预算。"
        )
    if prefer_full_run:
        terminalreporter.write_line(
            "⚠️  本次改动影响面无法收窄（tests/conftest.py、pytest.ini、src/backend/shared/、"
            "依赖锁等），本地档只能给局部信号——收尾请跑 `just test all`。"
        )


def pytest_configure(config: pytest.Config) -> None:
    """在 controller 进程执行外部写者防呆。

    放在 ``pytest_configure`` 而不是 fixture 里：xdist worker 内调用
    ``pytest.exit`` 会被报成 "worker crashed / keyboard-interrupt"，守卫给的
    可操作提示会整段丢失；controller 的 ``pytest_configure`` 早于 worker 启动，
    提示能干净打印。

    Args:
        config: 当前 pytest 配置对象。
    """
    if hasattr(config, "workerinput"):
        return
    if config.getoption("core_tier", False) and not _load_core_tier_paths():
        # 名单缺失时 --core-tier 会把每个模块都 ignore 掉，pytest 只留一个
        # "no tests collected"（退出码 5）作为报错，看不出是没名单；在这里提前
        # 退出才能给出可操作提示。放在 pytest_configure（controller 进程、早于
        # worker）而不是 ignore_collect，避免 worker 内 exit 被报成 crashed。
        pytest.exit(
            "`--core-tier` 没有可用名单：`tests/core_set.txt` 缺失或为空。"
            "请执行 `just test-core-refresh` 生成后再跑 `just test`。"
        )
    if config.getoption("collectonly", False):
        return
    _guard_shared_database_external_writer(config)


@pytest.fixture(autouse=True)
def _disable_otlp_trace_export(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认关闭 Run 轨迹的 OTLP 导出，避免测试向真实接收端发送轨迹。

    导出失败被设计成静默，其他用例不会因外发而变红，因此必须有一条会失败的守卫：
    ``tests/backend/test_run_otlp_exporter.py`` 断言进程内配置单例处于关闭态。
    开发机 ``.env.local`` 里若配了 ``OTEL_EXPORTER_OTLP_ENDPOINT``，删掉本 fixture
    会让该用例变红；否则「测试不外发」只是一个无法失败的说法。
    """
    from backend.infrastructure.config.settings import config

    monkeypatch.setattr(config.observability, "otlp_endpoint", "")
    monkeypatch.setattr(config.observability, "otlp_base_endpoint", "")


@pytest.fixture(autouse=True)
def _realdb_residue_sentinel(request: pytest.FixtureRequest) -> Iterator[None]:
    """真实数据库测试的前后主键快照对比，净变化即 fail。

    只对带 ``realdb`` 标记的测试生效。realdb 文件已由
    ``pytest_xdist_make_scheduler`` 定制的调度器收进同一 scope，
    ``--dist=loadgroup`` 下整组在同一 worker 串行执行，快照不被其他
    worker 的写入干扰。哨兵覆盖表见
    ``tests.realdb_test_support.residue_table_models``。快照前先预建一次
    应用，确保 ``create_app()`` 装配期种子的净新增不会误报。
    """
    if not has_realdb_marker(request):
        yield
        return
    from backend.main import create_app

    create_app()
    from tests.realdb_test_support import (  # noqa: PLC0415
        diff_residue_tables,
        snapshot_residue_tables,
    )

    snapshot_before = snapshot_residue_tables()
    yield
    residue_diff = diff_residue_tables(snapshot_before, snapshot_residue_tables())
    assert not residue_diff, "真实数据库测试泄漏或误删数据：" + ", ".join(
        f"{table_name} {direction}={sorted(primary_keys)[:5]}"
        for table_name, directions in residue_diff.items()
        for direction, primary_keys in directions.items()
        if primary_keys
    )
