"""守护本地测试分层配置的守卫测试（guard test）。

本文件位于 ``tests/guards/``，守护的是项目自有的四处分层配置：
``tests/core_set.txt``（``just test`` 本地档跑什么）、``.test_durations.json``
（耗时基线）、``.github/workflows/ci.yml``（移出本地档后由谁兜住）与
``test-budget.json``（全量档成本上限，即"套件膨胀必须被显式承认"的棘轮）。

失败意味着有人删了 CI 的全量档步骤、把核心档名单撑爆、改掉了 ``justfile`` 里的
``--core-tier`` 接线、让 CI 的成本棘轮漏传 ``--enforce-seconds``、或把上限拧成了
自相矛盾的值——这些都不会让任何测试变红，只会让"本地 30 秒、全量交 CI、总量有上限"
这套契约悄悄失效，所以必须用守卫测试钉住。
正确做法是修配置，而不是修改本文件让守卫通过；仅当分层约定本身需要变更时才改本文件，
并同步更新 ``docs/ai-standards/testing.md`` 的测试分层小节。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

# 守分层配置的测试自己必须每次本地都跑到，否则名单被撑爆时恰好没人报警；
# 显式 core 标记让它不依赖耗时规则就能留在本地档。
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_SET_PATH = REPO_ROOT / "tests" / "core_set.txt"
BASELINE_PATH = REPO_ROOT / ".test_durations.json"
JUSTFILE_PATH = REPO_ROOT / "justfile"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
BUDGET_PATH = REPO_ROOT / "test-budget.json"
CONFTEST_PATH = REPO_ROOT / "tests" / "conftest.py"


# 串行预算只有一个事实源：scripts/shared/testing/test_tiers.py 里的 DEFAULT_SERIAL_BUDGET_SECONDS
# （读同一个环境变量）。守卫直接 import 它，避免两处默认值各自漂移。
def _script_serial_budget_seconds() -> float:
    """从选集脚本取它实际使用的串行预算默认值。

    Returns:
        脚本内的 `DEFAULT_SERIAL_BUDGET_SECONDS` 数值。
    """
    module_spec = importlib.util.spec_from_file_location(
        "test_tiers_under_guard",
        REPO_ROOT / "scripts" / "shared" / "testing" / "test_tiers.py",
    )
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return float(module.DEFAULT_SERIAL_BUDGET_SECONDS)


SERIAL_BUDGET_SECONDS = _script_serial_budget_seconds()

CORE_MARKER_PATTERN = re.compile(r"\bpytest\.mark\.core\b")


def _listed_core_files() -> list[str]:
    """读取本地核心档名单里的测试文件路径。

    Returns:
        相对仓库根的路径列表（已去掉注释与空行）。

    Raises:
        AssertionError: 名单文件不存在或为空。
    """
    assert (
        CORE_SET_PATH.is_file()
    ), "tests/core_set.txt 缺失：本地档没有名单可跑，请执行 `just test-core-refresh`。"
    listed_files = [
        line.strip()
        for line in CORE_SET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert listed_files, "tests/core_set.txt 里一个文件都没有，本地档等于不跑测试。"
    return listed_files


def test_core_set_files_exist_on_disk() -> None:
    """名单里的每个文件都必须还在仓库里，防止重命名后本地档静默少跑。"""
    missing_files = [
        listed_file
        for listed_file in _listed_core_files()
        if not (REPO_ROOT / listed_file).is_file()
    ]
    assert not missing_files, (
        "core_set.txt 指向了不存在的测试文件，跑 `just test-core-refresh` 重算名单："
        f"{', '.join(missing_files)}"
    )


def test_core_set_stays_inside_serial_budget() -> None:
    """名单在耗时基线里的串行耗时之和不得超过预算，否则本地档会突破 30 秒墙钟目标。

    只对 ``.test_durations.json`` 里**上次 refresh 时记录**的秒数求和：名单之后才变慢的
    用例、以及基线里没有记录的文件它都看不见，所以它只能防"名单被手工撑大"，
    防不住"墙钟悄悄漂过 30s"——后者要靠 ``just bench-test`` 在本机手动量。
    """
    listed_files = set(_listed_core_files())
    assert (
        BASELINE_PATH.is_file()
    ), ".test_durations.json 缺失：没有耗时基线就无法判断预算，请执行 `just test-core-refresh`。"
    baseline_payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    measured_files = baseline_payload.get("files", {})
    spent_seconds = sum(
        float(cost.get("seconds", 0.0))
        for file_name, cost in measured_files.items()
        if file_name in listed_files
    )
    assert spent_seconds <= SERIAL_BUDGET_SECONDS, (
        f"按基线记录，本地档串行 {spent_seconds:.1f}s 已超过 {SERIAL_BUDGET_SECONDS}s 预算，"
        "跑 `just test-core-refresh` 让最慢的文件退出本地档（CI 仍会跑它们）。"
    )


def test_every_core_marked_module_is_listed() -> None:
    """显式打了 ``core`` 标记的模块必须在名单里，否则例外通道形同虚设。"""
    listed_files = set(_listed_core_files())
    unlisted_marked_files = [
        str(test_module.relative_to(REPO_ROOT))
        for test_module in (REPO_ROOT / "tests").rglob("test_*.py")
        if CORE_MARKER_PATTERN.search(test_module.read_text(encoding="utf-8"))
        and str(test_module.relative_to(REPO_ROOT)) not in listed_files
    ]
    assert not unlisted_marked_files, (
        "这些模块声明了 pytest.mark.core 却不在本地档名单里，"
        f"请执行 `just test-core-refresh` 收编：{', '.join(sorted(unlisted_marked_files))}"
    )


def test_justfile_wires_core_tier_into_local_run() -> None:
    """``just test`` 的本地档必须真的带上 ``--core-tier``，否则会退回全量。"""
    justfile_text = JUSTFILE_PATH.read_text(encoding="utf-8")
    assert "--core-tier" in justfile_text, (
        "justfile 里的 JUST_LOCAL_TEST_FLAGS 不再带 --core-tier：本地档会退回全量 `tests/`，"
        "`just test` 将不再是 30 秒口径。"
    )


def test_ci_runs_the_full_tier_and_produces_the_budget_junit() -> None:
    """CI 必须跑非 slow 的全量档并产出 junit：本地核心档只是子集，全量由 CI 兜底。"""
    ci_text = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'pytest tests/ -v -m "not slow and not real_api and not redis"' in ci_text, (
        "ci.yml 缺少全量步骤：本地核心档只跑名单子集，删掉这一步就等于把其余用例"
        "彻底关掉不测。详见 docs/ai-standards/testing.md 的「本地核心档」小节。"
    )
    assert "--junit-xml=.test-budget-junit.xml" in ci_text, (
        "ci.yml 的全量档步骤不再产出 junit，成本棘轮 check_test_budget.py 就没有输入，"
        "套件膨胀会重新变成没人看得见的事。"
    )


def test_ci_enforces_full_tier_budget_including_seconds() -> None:
    """CI 必须真的调用成本棘轮，并显式带 ``--enforce-seconds``。

    ``test-budget.json`` 的秒数上限按 CI 口径校准，脚本默认只强制条数（本机同一条命令
    慢得多，不可互比）。漏传开关不会让任何测试变红，只会让墙钟棘轮悄悄退化成只出报告。
    这里解析 YAML 取步骤的 ``run`` 命令，而不是在全文里搜字符串——注释里写着
    ``--enforce-seconds`` 不等于命令里真的传了它。
    """
    workflow_definition = yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))
    run_commands = [
        str(step_definition["run"])
        for step_definition in workflow_definition["jobs"]["validate-template"]["steps"]
        if "run" in step_definition
    ]
    budget_commands = [
        run_command
        for run_command in run_commands
        if "scripts/shared/testing/check_test_budget.py" in run_command
    ]
    assert len(budget_commands) == 1, (
        "validate-template job 必须恰好有一个步骤调用 scripts/shared/testing/check_test_budget.py，"
        f"实际找到 {len(budget_commands)} 个：删掉它，全量档的成本上限就没人比对了。"
    )
    assert "--enforce-seconds" in budget_commands[0], (
        "CI 里的成本棘轮没带 --enforce-seconds：墙钟上限只剩报告，不再强制。"
        "本机才应该省略它（本机慢得多，数字不可互比）。"
    )


def test_core_tier_covers_changed_and_mapped_tests() -> None:
    """本地档必须包含"改动的测试"与"改动 src 映射到的测试"两条并集。

    `check-test-flag` 把通过标记绑在整份有效树上。如果本地档只读 `core_set.txt`，
    刚写的测试、或改了产品代码后本该验证它的那批（往往正是被耗时规则请出名单的贵用例）
    会一次都不执行，而门禁照样放行。这两条并集是门禁成立的前提，所以接线被简化掉时
    必须报警。
    """
    conftest_text = CONFTEST_PATH.read_text(encoding="utf-8")
    hook_body = conftest_text.split("def pytest_ignore_collect", 1)
    assert len(hook_body) == 2, "tests/conftest.py 里找不到 pytest_ignore_collect，本地档无从收窄。"
    ignore_collect_body = hook_body[-1].split("\ndef ", 1)[0]
    assert "_working_tree_test_plan()" in ignore_collect_body, (
        "本地档不再读取工作区测试计划：改动的测试与改动 src 映射到的测试都不会被跑，"
        "而 check-test-flag 依然会给这份工作树盖章。"
    )
    assert "working_tree_test_plan" in conftest_text, (
        "conftest 与 scripts/shared/testing/test_tiers.py 的接线断了；"
        '"什么算改动"必须只有一份实现，不能两处各写一遍 git 采集。'
    )


def test_full_tier_budget_ceilings_are_coherent() -> None:
    """``test-budget.json`` 的上限必须是可用且自洽的，否则棘轮形同虚设。"""
    assert BUDGET_PATH.is_file(), (
        "test-budget.json 缺失：全量档成本上限（棘轮）没了依据，CI 的 "
        "check_test_budget.py 会直接报错。"
    )
    budget_payload = json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
    ceilings = budget_payload.get("ceilings", {})
    baseline = budget_payload.get("baseline", {})
    assert {"seconds", "tests"} <= set(ceilings), "test-budget.json 的 ceilings 缺少字段。"
    ceiling_seconds = float(ceilings["seconds"])
    ceiling_tests = float(ceilings["tests"])
    assert ceiling_seconds >= 60 and ceiling_tests >= 100, (
        f"上限明显不合理（seconds={ceiling_seconds}, tests={ceiling_tests}），" "会把 CI 永久锁红。"
    )
    assert ceiling_seconds >= float(baseline.get("seconds", 0)), (
        "ceilings.seconds 低于 baseline.seconds：上限被设成了已经达不到的值，"
        "等于把棘轮反着拧。抬高成本时两项要一起改。"
    )
    assert ceiling_tests >= float(
        baseline.get("tests", 0)
    ), "ceilings.tests 低于 baseline.tests：同上，条数上限不能低于已记录的基线条数。"
