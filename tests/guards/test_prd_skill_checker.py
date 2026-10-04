"""守护 PRD 归档 checker 证据链约束的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

被测对象：``skills/prd/scripts/`` 下的 checker 与契约解析器。核心不变量：

1. **证据链与格式单一来源。** oracle 必须写清值来源、必经边界与 fresh-state；契约版本
   标记必须等于解析器的实现版本，checker 只复用 ``prd_contract`` 的解析。
2. **归档只代表执行侧交付完成。** 归档门禁只数 ``Human-Confirmed`` 之外的空框：人的
   确认是归档**之后**的验收记录，不拦归档；"还欠人一个确认"改由验收状态横幅承接，
   所以归档时横幅必须存在、可识别，且与 §9 对得上（``🧍 待人工验收`` ⟺ 人属组还有
   空框，``✅ 已验收`` ⟺ 一个不剩，``⬜ 未开工`` 永不可归档）。横幅一旦漂掉，一条
   已归档却仍待人确认的 PRD 就会从所有看板里消失。
3. **三份解析器逐例等价。** 随模板同步的 hook（``hooks/shared``）与状态看板的读取副本
   （``scripts/shared/just/prd_acceptance.py``，看板与执行锁共用）不能 import 可选安装
   的 skill，只能各自带一份轻量实现；等价性只能由这里（模板仓库内部、能同时看到三者）
   来锁。除"哪些空框是执行侧欠的"与横幅三态之外，看板的勾选进度计数（``checked/total``）
   也锁在这里：改分组、横幅或计数口径时三处必须一起改，否则这里变红。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = REPO_ROOT / "skills" / "prd" / "scripts" / "check_prd_acceptance_checklist.py"
CHECKER_SPEC = importlib.util.spec_from_file_location("prd_skill_checker", CHECKER_PATH)
assert CHECKER_SPEC is not None
assert CHECKER_SPEC.loader is not None
PRD_CHECKER = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(PRD_CHECKER)

CONTRACT_MODULE_PATH = CHECKER_PATH.parent / "prd_contract.py"
SKILL_MD_PATH = CHECKER_PATH.parents[1] / "SKILL.md"
PRD_TEMPLATE_PATH = CHECKER_PATH.parents[1] / "templates" / "prd-visual-template.md"
# 取的正是 checker 运行时加载的那一份（它按脚本所在目录 import 兄弟模块），
# 而不是再加载一次——同一个文件加载两遍会得到两个不同的模块对象。
PRD_CONTRACT = sys.modules.get("prd_contract")
assert PRD_CONTRACT is not None, "checker 未能加载兄弟模块 prd_contract"

# 另两份随模板同步的解析实现，与 skill 的契约解析互为镜像（见模块 docstring 第 3 条）。
HOOK_PATH = REPO_ROOT / "hooks" / "shared" / "check_prd_acceptance_checklist.py"
HOOK_SPEC = importlib.util.spec_from_file_location("prd_acceptance_hook", HOOK_PATH)
assert HOOK_SPEC is not None
assert HOOK_SPEC.loader is not None
PRD_HOOK = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(PRD_HOOK)

# prd_acceptance.py 不是包的一部分，import 前需把它所在目录放到 sys.path。
_JUST_SCRIPTS_PATH = REPO_ROOT / "scripts" / "shared" / "just"
if str(_JUST_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(_JUST_SCRIPTS_PATH))

import prd_acceptance  # noqa: E402

# 清单作用域的用例表与 hook 的守卫测试共用一份（见该模块 docstring），同样按路径放进 sys.path。
_SHARED_GUARDS_PATH = REPO_ROOT / "tests" / "guards" / "shared"
if str(_SHARED_GUARDS_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_GUARDS_PATH))

from prd_checklist_scope_cases import (  # noqa: E402
    CHECKLIST_SCOPE_PARAMS,
    open_item_labels,
    prd_with_checklist_body,
)


def test_machine_contract_version_matches_the_parser() -> None:
    """SKILL.md 的契约版本标记必须与 prd_contract 的实现版本一致。

    两侧各写各的版本号正是这个仓库踩过的坑：契约文本说的形式与真正执行的解析器
    不一致，于是"照着模板写却过不了门禁"。改契约必须同时改实现，本测试就是那道锁。
    """

    marker = re.search(
        r"Machine-Contract-Version:\s*(\d+)", SKILL_MD_PATH.read_text(encoding="utf-8")
    )
    assert marker is not None, "SKILL.md 缺少 Machine-Contract-Version 标记"
    assert int(marker.group(1)) == PRD_CONTRACT.CONTRACT_VERSION


def test_checker_reuses_the_shared_contract_parser() -> None:
    """checker 必须复用 prd_contract 的解析，不得自带第二份实现。

    同目录安装是硬要求：checker 通过脚本所在目录 import 兄弟模块，拆开安装会
    ImportError（而不是静默用一份陈旧的内联实现）。
    """

    assert CONTRACT_MODULE_PATH.exists(), "prd_contract.py 必须与 checker 同目录安装"
    assert PRD_CHECKER.parse_checklist is PRD_CONTRACT.parse_checklist


def _complete_prd(*, include_reconciliation: bool = False) -> str:
    """构造覆盖 checker 结构要求的最小完整 PRD。"""

    reconciliation = ""
    if include_reconciliation:
        reconciliation = """
### Final Reconciliation

- Interpretation: confirmed — 最终行为与批准解读一致
- Public behavior and contracts: corrected — 已按真实 API 修正文案
- Related PRD status: confirmed — 依赖状态已复核
- Requirements and risks: confirmed — 最终需求与风险已复核
"""

    return f"""# PRD: 测试任务

> ✅ **交付前置**：无，可立即开工。
> 结构化声明见 §8 Delivery Dependencies，**那里是唯一事实源**。

# Part A · 人审层 (Review Layer)

## 1. Introduction & Goals

### Interpretation (解读回显)

| 输入 / 操作 | 期望观察到的结果 |
|---|---|
| 执行最小操作 | 观察到最小结果 |
| 重复执行同一操作 | 结果保持一致 |
| 输入越界值 | 明确报错而不是静默通过 |

以上每一行会被逐字转成验收 oracle。

**我默默定了这些**

- 沿用现有默认配置，不新增开关。

**我理解为不做**

- 不改动对外契约。

## 2. Human Review Map (介入与风险地图)

## 3. Usage And Impact After Implementation

## 4. Requirement Shape

# Part B · 执行器层 (Build Layer)

## 5. Repository Context And Architecture Fit

## 6. Recommendation

## 7. Implementation Guide

### 7.6 Realistic Validation Plan (Oracle 块)

- No executable behavior changes; realistic validation is limited to documentation/build checks.

## 8. Delivery Dependencies

## 9. Acceptance Checklist

- [x] 最小验收项已完成

## 10. Functional Requirements

- FR-1: 保持最小行为
- FR-2: 保持兼容行为

## 11. Non-Goals

## 12. Risks And Follow-Ups

## 13. Decision Log
{reconciliation}
"""


def test_executable_oracle_requires_complete_evidence_chain() -> None:
    """缺少旁路、fresh-state 等字段时必须拒绝归档。"""

    incomplete_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 分享链接可由匿名用户打开
  reviewer: verifier
  real_entry: just e2e share
  expected: 匿名浏览器看到分享内容
  mock_boundary: 仅 mock 邮件发送
  negative_control: 破坏 canonical route
  expected_fail: 实际请求返回 404
  test_layer: e2e
  required_for_acceptance: true
```
"""

    oracle_issues = PRD_CHECKER._oracle_schema_issues(incomplete_prd)

    assert len(oracle_issues) == 1
    assert "critical_value_source" in oracle_issues[0][1]
    assert "fresh_state_probe" in oracle_issues[0][1]
    assert "final_tree_evidence" in oracle_issues[0][1]


def test_executable_oracle_accepts_complete_evidence_chain() -> None:
    """完整记录值来源、边界、旁路和 fresh-state 时允许验收。"""

    complete_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 分享链接可由匿名用户打开
  reviewer: human
  presentation: 真实入口截图 share-anon-open.png + 无痕窗口自验 URL
  real_entry: just e2e share
  expected: 匿名浏览器看到分享内容
  mock_boundary: 仅 mock 邮件发送
  tier: R3
  critical_value_source: 页面渲染的分享链接
  must_cross: browser -> proxy -> canonical API -> commit -> anonymous read
  forbidden_bypasses: 硬编码路由、直接 service 调用、writer session
  fresh_state_probe: 新匿名 browser context 打开页面原样链接
  final_tree_evidence: 最后相关 diff 后重跑并记录 tree hash
  negative_control: 破坏 canonical route
  expected_fail: 实际请求返回 404
  test_layer: e2e
  required_for_acceptance: true
```
"""

    assert PRD_CHECKER._oracle_schema_issues(complete_prd) == []


def test_low_tier_oracle_does_not_require_evidence_chain() -> None:
    """R0/R1 条目只需可区分失败的断言，不必背完整证据链。"""

    low_tier_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 导航栏显示语言切换器
  reviewer: human
  presentation: 切换前后截图 switch-before.png / switch-after.png
  real_entry: pnpm --filter frontend-admin test:e2e -g language-switcher
  expected: 切换后可见文案由中文变为英文
  mock_boundary: 不 mock 前端渲染，仅 mock 后端列表接口
  tier: R1
  test_layer: e2e
  required_for_acceptance: true
```
"""

    assert PRD_CHECKER._oracle_schema_issues(low_tier_prd) == []


def test_high_tier_oracle_still_requires_evidence_chain() -> None:
    """显式声明 R2 时仍必须补齐证据链字段。"""

    high_tier_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 同步写入对新会话可见
  reviewer: verifier
  real_entry: just e2e sync
  expected: 新会话读到已提交记录
  mock_boundary: 仅 mock 邮件发送
  tier: R2
  test_layer: e2e
  required_for_acceptance: true
```
"""

    oracle_issues = PRD_CHECKER._oracle_schema_issues(high_tier_prd)

    assert len(oracle_issues) == 1
    assert "must_cross" in oracle_issues[0][1]
    assert "fresh_state_probe" in oracle_issues[0][1]


def test_invalid_oracle_tier_is_rejected() -> None:
    """tier 只接受 R0-R3，拼错必须报错而不是静默降级。"""

    bad_tier_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 导航栏显示语言切换器
  reviewer: verifier
  real_entry: pnpm --filter frontend-admin test:e2e
  expected: 切换后文案变化
  mock_boundary: 不 mock 前端渲染
  tier: low
  test_layer: e2e
  required_for_acceptance: true
```
"""

    oracle_issues = PRD_CHECKER._oracle_schema_issues(bad_tier_prd)

    assert len(oracle_issues) == 1
    assert "invalid tier" in oracle_issues[0][1]


def test_not_feasible_negative_control_waives_expected_fail() -> None:
    """负控不可行时记录原因即可，不逼作者为可测性造失败开关。"""

    documented_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 供应商超时时同步标记为失败
  reviewer: verifier
  real_entry: just e2e sync
  expected: attempt 状态为 failed 且无 remote_reference
  mock_boundary: 供应商 HTTP 边界由测试 fake 替换
  tier: R3
  critical_value_source: 真实上传接口返回的 run id
  must_cross: API -> connector 边界 -> commit -> fresh read
  forbidden_bypasses: 直接构造 attempt、复用 writer session
  fresh_state_probe: 新 DB session 读取 attempt 状态
  final_tree_evidence: 最后相关 diff 后重跑并记录 tree hash
  negative_control: not feasible — 制造该失败需要在生产 connector 注入故障开关
  test_layer: e2e
  required_for_acceptance: true
```
"""

    assert PRD_CHECKER._oracle_schema_issues(documented_prd) == []


def test_interpretation_echo_requires_correctable_blocks() -> None:
    """只有散文的解读回显必须拒绝：读者无法逐条否证。"""

    prose_only_prd = """### Interpretation (解读回显)

本次需求被理解为在现有列表页补充双语切换能力，不改动后端契约。
"""

    echo_issues = PRD_CHECKER._interpretation_echo_issues(prose_only_prd)
    issue_messages = " ".join(message for _, message in echo_issues)

    assert "behavior-example table" in issue_messages
    assert "我默默定了这些" in issue_messages
    assert "我理解为不做" in issue_messages


def test_interpretation_echo_accepts_example_table_and_blocks() -> None:
    """样例表加上默认决策与排除范围时通过。"""

    correctable_prd = """### Interpretation (解读回显)

| 输入 / 操作 | 期望观察到的结果 |
|---|---|
| 在后台顶栏切到 English | 当前页可见文案全部变英文 |
| 切换后刷新页面 | 仍保持 English |
| 浏览器语言为 ja | 回落到 English 而不是报错 |

以上每一行会被逐字转成验收 oracle，改一格就等于改验收标准。

**我默默定了这些**

- 未迁移页面保留中文硬编码，不视为缺陷。

**我理解为不做**

- 不做 URL 语言前缀路由。
- 不做后端返回文案的多语言化。

解读为「前端展示层双语」，不是「全链路国际化」。
"""

    assert PRD_CHECKER._interpretation_echo_issues(correctable_prd) == []


def test_non_executable_prd_keeps_documentation_build_exception() -> None:
    """无可执行行为时保留明确的文档构建豁免。"""

    documentation_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

- No executable behavior changes; realistic validation is limited to documentation/build checks.
"""

    assert PRD_CHECKER._oracle_schema_issues(documentation_prd) == []


def test_required_sections_reject_missing_or_out_of_order_headings() -> None:
    """缺少章节或章节乱序时必须明确失败。"""

    incomplete_prd = _complete_prd().replace("## 6. Recommendation\n", "")
    missing_issues = PRD_CHECKER._required_section_issues(incomplete_prd)
    assert any("Recommendation" in issue_text for _, issue_text in missing_issues)

    out_of_order_prd = _complete_prd().replace(
        "## 5. Repository Context And Architecture Fit\n\n## 6. Recommendation",
        "## 6. Recommendation\n\n## 5. Repository Context And Architecture Fit",
    )
    order_issues = PRD_CHECKER._required_section_issues(out_of_order_prd)
    assert any("must appear after" in issue_text for _, issue_text in order_issues)


def test_part_a_rejects_executor_evidence_metadata() -> None:
    """Part A 不得泄漏 rv-id 或证据链字段。"""

    prd_with_metadata = _complete_prd().replace(
        "## 4. Requirement Shape",
        "执行追踪：rv-1\n\ncritical_value_source: response\n\n## 4. Requirement Shape",
    )

    metadata_issues = PRD_CHECKER._part_a_metadata_issues(prd_with_metadata)

    assert len(metadata_issues) == 2
    assert all("executor-only metadata" in issue_text for _, issue_text in metadata_issues)


def test_functional_requirement_ids_must_be_sequential() -> None:
    """FR 编号重复、跳号或乱序时必须失败。"""

    unordered_prd = _complete_prd().replace(
        "- FR-1: 保持最小行为\n- FR-2: 保持兼容行为",
        "- FR-1: 保持最小行为\n- FR-3: 保持兼容行为\n- FR-2: 恢复旧行为",
    )

    requirement_issues = PRD_CHECKER._functional_requirement_issues(unordered_prd)

    assert len(requirement_issues) == 1
    assert "found [1, 3, 2]" in requirement_issues[0][1]


def test_pending_validation_does_not_require_final_reconciliation(tmp_path: Path) -> None:
    """普通 pending 校验不应提前要求归档校正记录。"""

    prd_path = tmp_path / "pending-prd.md"
    prd_path.write_text(_complete_prd(), encoding="utf-8")

    assert PRD_CHECKER._validate_file(prd_path) == []
    archive_ready_issues = PRD_CHECKER._validate_file(prd_path, require_archive_reconciliation=True)
    assert any(
        "Missing Final Reconciliation" in issue_text for _, issue_text in archive_ready_issues
    )


def test_archive_validation_requires_complete_final_reconciliation() -> None:
    """归档校验必须包含完整的最终叙事对账。"""

    missing_issues = PRD_CHECKER._archive_reconciliation_issues(_complete_prd())
    assert any("Missing Final Reconciliation" in issue_text for _, issue_text in missing_issues)

    incomplete_prd = _complete_prd(include_reconciliation=True).replace(
        "Public behavior and contracts: corrected — 已按真实 API 修正文案",
        "Public behavior and contracts: [confirmed / corrected — summary]",
    )
    incomplete_issues = PRD_CHECKER._archive_reconciliation_issues(incomplete_prd)
    assert any("is incomplete" in issue_text for _, issue_text in incomplete_issues)

    assert (
        PRD_CHECKER._archive_reconciliation_issues(_complete_prd(include_reconciliation=True)) == []
    )


_NOT_STARTED_BANNER_LINE = "> ⬜ **验收状态**：未开工。"
_AWAITING_BANNER_LINE = "> 🧍 **验收状态**：待人工验收 — 仅剩 Human-Confirmed 项未确认。"
_ACCEPTED_BANNER_LINE = "> ✅ **验收状态**：已验收 — Human-Confirmed 项均已确认。"
_HUMAN_ITEM_LABEL = "人工确认：切换后的文案读起来通顺"
_EXECUTION_ITEM_LABEL = "最小验收项已完成"


def _archive_candidate_prd(
    banner_line: str | None,
    *,
    human_item_mark: str = " ",
    execution_item_mark: str = "x",
) -> str:
    """构造只有验收清单与横幅可变、其余都满足归档校验的 PRD。

    §9 拆成执行侧一项与 ``Human-Confirmed`` 分组一项；横幅插在交付前置横幅之后，与
    模板同形。

    Args:
        banner_line: 横幅首行（含行首 ``> ``）；``None`` 表示不写横幅。
        human_item_mark: ``Human-Confirmed`` 组内那一项的勾选标记。
        execution_item_mark: 执行侧那一项的勾选标记。
    """

    prd_text = _complete_prd(include_reconciliation=True).replace(
        f"- [x] {_EXECUTION_ITEM_LABEL}\n",
        f"- [{execution_item_mark}] {_EXECUTION_ITEM_LABEL}\n"
        "\n"
        "### Human-Confirmed\n"
        "\n"
        f"- [{human_item_mark}] {_HUMAN_ITEM_LABEL}\n",
        1,
    )
    if banner_line is None:
        return prd_text
    return prd_text.replace(
        "> 结构化声明见 §8 Delivery Dependencies，**那里是唯一事实源**。\n",
        "> 结构化声明见 §8 Delivery Dependencies，**那里是唯一事实源**。\n"
        "\n"
        f"{banner_line}\n"
        "> 本行是 §9 Acceptance Checklist 的投影，**那里是唯一事实源**。\n",
        1,
    )


def _archive_gate_issues(tmp_path: Path, prd_text: str) -> list[tuple[int, str]]:
    """把 PRD 落盘后按"准备归档"的口径校验，返回全部问题。"""

    prd_path = tmp_path / "archive-candidate.md"
    prd_path.write_text(prd_text, encoding="utf-8")
    return PRD_CHECKER._validate_file(prd_path, require_archive_reconciliation=True)


def test_archive_gate_lets_open_human_confirmed_items_through(tmp_path: Path) -> None:
    """归档只代表执行侧交付完成：Human-Confirmed 组里的空框不拦归档。

    这是语义变更的核心。以前归档要等人工验收做完；现在人的确认是归档**之后**的
    验收记录，由横幅 ``🧍 待人工验收`` 承接，不再借"清单没勾完"来拦提交。
    """

    prd_text = _archive_candidate_prd(_AWAITING_BANNER_LINE)
    assert PRD_CONTRACT.parse_checklist(
        prd_text
    ).human_unchecked_items, "夹具必须真的留着人属空框，否则下面的断言是假通过"

    assert _archive_gate_issues(tmp_path, prd_text) == []


def test_archive_gate_accepts_accepted_banner_once_every_human_item_is_ticked(
    tmp_path: Path,
) -> None:
    """人确认完（回填验收记录）之后的终态：全勾 + ``✅ 已验收`` 照样合法。"""

    prd_text = _archive_candidate_prd(_ACCEPTED_BANNER_LINE, human_item_mark="x")

    assert _archive_gate_issues(tmp_path, prd_text) == []


def test_archive_gate_reads_legacy_ready_to_archive_banner_as_accepted(tmp_path: Path) -> None:
    """v4 及以前的 ``✅ 可归档`` 就是现在的 ``✅ 已验收``：存量 PRD 不必回头改文件。"""

    legacy_banner_line = "> ✅ **验收状态**：可归档 — 验收清单已全部完成。"
    prd_text = _archive_candidate_prd(legacy_banner_line, human_item_mark="x")

    assert _archive_gate_issues(tmp_path, prd_text) == []


def test_archive_gate_still_blocks_open_execution_items(tmp_path: Path) -> None:
    """执行侧欠的活照旧拦归档；同一份 PRD 里的人属空框不跟着被报。"""

    prd_text = _archive_candidate_prd(_AWAITING_BANNER_LINE, execution_item_mark=" ")

    issues = _archive_gate_issues(tmp_path, prd_text)

    assert len(issues) == 1
    assert _EXECUTION_ITEM_LABEL in issues[0][1]
    assert _HUMAN_ITEM_LABEL not in issues[0][1]


def test_archive_gate_requires_the_acceptance_status_banner(tmp_path: Path) -> None:
    """没有横幅就不能归档：人工验收的交接点缺了，待确认项会从看板里消失。"""

    issues = _archive_gate_issues(tmp_path, _archive_candidate_prd(None))

    assert len(issues) == 1
    assert "Missing Acceptance Status Banner" in issues[0][1]


@pytest.mark.parametrize(
    ("banner_line", "human_item_mark", "expected_message"),
    [
        pytest.param(
            _NOT_STARTED_BANNER_LINE,
            " ",
            "still says ⬜ 未开工",
            id="not-started-with-open-human-item",
        ),
        pytest.param(
            _NOT_STARTED_BANNER_LINE,
            "x",
            "still says ⬜ 未开工",
            id="not-started-even-when-every-human-item-is-ticked",
        ),
        pytest.param(
            "> 🔶 **验收状态**：已完成。",
            " ",
            "not recognised",
            id="unrecognised-state-word",
        ),
        pytest.param(
            _AWAITING_BANNER_LINE,
            "x",
            "no open Human-Confirmed",
            id="awaiting-human-with-nothing-left-to-confirm",
        ),
        pytest.param(
            _ACCEPTED_BANNER_LINE,
            " ",
            "still unchecked",
            id="accepted-while-human-items-are-open",
        ),
    ],
)
def test_archive_gate_rejects_a_banner_that_disagrees_with_the_checklist(
    tmp_path: Path, banner_line: str, human_item_mark: str, expected_message: str
) -> None:
    """横幅是 §9 的投影：缺、认不出、停在未开工或与人属空框对不上都必须拒收。

    每种错位只报一条，且锚在横幅所在行，作者能直接定位。
    """

    prd_text = _archive_candidate_prd(banner_line, human_item_mark=human_item_mark)

    issues = _archive_gate_issues(tmp_path, prd_text)

    assert len(issues) == 1
    assert expected_message in issues[0][1]
    assert issues[0][0] == prd_text.splitlines().index(banner_line) + 1


def _write_prd(repo_root: Path, relative_path: str, prd_text: str) -> None:
    """把 PRD 写到仓库内的相对路径（按需建目录）。"""

    prd_path = repo_root / relative_path
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(prd_text, encoding="utf-8")


def test_archived_path_is_held_to_the_archive_gate_without_a_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """已在 ``tasks/archive/`` 下的 PRD 自动按归档口径校验，不靠 ``--archive-ready``。"""

    archived_path = "tasks/archive/P2-FEAT-20260101-000000-sample.md"
    _write_prd(tmp_path, archived_path, _archive_candidate_prd(None))

    exit_code = PRD_CHECKER.main(["--repo-root", str(tmp_path), "--check-provided", archived_path])

    assert exit_code == 1
    assert "Missing Acceptance Status Banner" in capsys.readouterr().out


def test_archive_ready_flag_holds_a_pending_prd_to_the_archive_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--archive-ready`` 让 pending 下的 PRD 提前过一遍归档门禁，横幅与 §9 对得上才放行。"""

    pending_path = "tasks/pending/P2-FEAT-20260101-000000-sample.md"
    prd_check_argv = [
        "--repo-root",
        str(tmp_path),
        "--check-provided",
        "--archive-ready",
        pending_path,
    ]

    _write_prd(tmp_path, pending_path, _archive_candidate_prd(_ACCEPTED_BANNER_LINE))
    assert PRD_CHECKER.main(prd_check_argv) == 1
    assert "still unchecked" in capsys.readouterr().out

    _write_prd(tmp_path, pending_path, _archive_candidate_prd(_AWAITING_BANNER_LINE))
    assert PRD_CHECKER.main(prd_check_argv) == 0


def test_pending_prd_is_not_held_to_the_banner_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """没提归档的 pending PRD 不要求横幅：横幅只在归档交接时才有"必须对得上"的义务。"""

    pending_path = "tasks/pending/P2-FEAT-20260101-000000-sample.md"
    _write_prd(tmp_path, pending_path, _archive_candidate_prd(None))

    exit_code = PRD_CHECKER.main(["--repo-root", str(tmp_path), "--check-provided", pending_path])

    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_prd_template_default_banner_reads_as_not_started() -> None:
    """模板自带的横幅必须读作 ``未开工``：括号说明里提到的另外两个状态词不得抢占。

    读状态取标记之后**最先出现**的状态词，这条规则只有在模板本身的写法上被证明过才算数。
    """

    template_text = PRD_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert PRD_CONTRACT.parse_acceptance_status(template_text) == "not_started"


def test_describe_prd_payload_exposes_banner_and_the_human_split() -> None:
    """``--json`` 载荷要把横幅状态与"执行 / 人属"两路空框原样给到下游消费方。"""

    payload = PRD_CONTRACT.describe_prd(_archive_candidate_prd(_AWAITING_BANNER_LINE), path="x.md")

    checklist_payload = payload["checklist"]
    assert payload["acceptance_status"] == "awaiting_human"
    assert checklist_payload["execution_unchecked"] == []
    assert [entry["text"] for entry in checklist_payload["human_unchecked"]] == [
        f"- [ ] {_HUMAN_ITEM_LABEL}"
    ]


def _with_delivery_dependencies(prd_text: str, depends_on_line: str) -> str:
    """把结构化依赖字段填进夹具里空着的 §8。

    夹具的 §8 只有标题没有字段，直接对字段做字符串替换不会命中——那样写出来的
    测试会因为 §8 依旧为空而假通过。
    """

    return prd_text.replace(
        "## 8. Delivery Dependencies\n",
        "## 8. Delivery Dependencies\n\n"
        "- Group: none\n"
        "- Depends on tasks/issues:\n"
        f"  - {depends_on_line}\n"
        "- Gate type: none\n"
        "- Notes: none\n",
        1,
    )


def test_delivery_gate_banner_is_required() -> None:
    """缺少交付前置提示时必须报错——空白分不清没有依赖和忘了写。"""

    without_banner = "\n".join(
        line for line in _complete_prd().splitlines() if "交付前置" not in line
    )
    issues = PRD_CHECKER._delivery_gate_banner_issues(without_banner)

    assert any("Missing Delivery Gate Banner" in message for _, message in issues)


def test_delivery_gate_banner_must_name_every_declared_upstream() -> None:
    """banner 与 §8 矛盾时必须报错：§8 是唯一事实源，banner 漂了就是缺陷。"""

    blocked_prd = _with_delivery_dependencies(
        _complete_prd(), "`P1-FEAT-20260101-000000-upstream.md`"
    )
    issues = PRD_CHECKER._delivery_gate_banner_issues(blocked_prd)

    assert any(
        "P1-FEAT-20260101-000000-upstream.md" in message for _, message in issues
    ), "banner 仍写着「无」，却声明了上游，应当判负"


def test_delivery_gate_banner_accepts_matching_upstream() -> None:
    """banner 点全了 §8 声明的上游即通过。"""

    blocked_prd = _with_delivery_dependencies(
        _complete_prd(), "`P1-FEAT-20260101-000000-upstream.md`"
    ).replace(
        "> ✅ **交付前置**：无，可立即开工。",
        "> ⛔ **交付前置**：排在 `P1-FEAT-20260101-000000-upstream.md` 之后开工。",
        1,
    )

    assert PRD_CHECKER._delivery_gate_banner_issues(blocked_prd) == []


def test_delivery_gate_banner_tolerates_none_with_rationale() -> None:
    """`none（中文括号说明）` 是常见写法，不得被当成一个上游依赖名。"""

    with_rationale = _with_delivery_dependencies(
        _complete_prd(), "none（本 PRD 是善后，无未完成上游）"
    )

    assert PRD_CHECKER._delivery_gate_banner_issues(with_rationale) == []


def _with_canonical_delivery_dependencies(prd_text: str, depends_on_line: str) -> str:
    """按 SKILL.md 的规范形状填入 §8 依赖字段。

    规范形状在 ``## 8. Delivery Dependencies`` 之下还会再套一层
    ``### Delivery Dependencies`` 子标题。回归：checker 曾把紧跟在 ``## 8.`` 之后的
    这层子标题当成下一节而提前 ``break``，依赖被读成空、横幅被迫要求写「无」。夹具必须
    带上这层子标题才能锁住它；``_with_delivery_dependencies`` 是扁平形状，覆盖不到。
    """

    return prd_text.replace(
        "## 8. Delivery Dependencies\n",
        "## 8. Delivery Dependencies\n\n"
        "### Delivery Dependencies\n\n"
        "- Group: none\n"
        "- Depends on tasks/issues:\n"
        f"  - {depends_on_line}\n"
        "- Gate type: none\n"
        "- Notes: none\n",
        1,
    )


def test_delivery_dependencies_read_through_canonical_subheading() -> None:
    """§8 下的 ``### Delivery Dependencies`` 子标题不得结束本节的依赖声明。"""

    prd_text = _with_canonical_delivery_dependencies(
        _complete_prd(), "`P1-FEAT-20260101-000000-upstream.md`"
    )

    assert PRD_CHECKER._declared_delivery_dependency_refs(prd_text) == {
        "P1-FEAT-20260101-000000-upstream.md"
    }


def test_delivery_gate_banner_uses_canonical_subheading_dependencies() -> None:
    """规范形状下横幅仍须点全 §8 声明的上游，而不是被迫写「无」。"""

    blocked_prd = _with_canonical_delivery_dependencies(
        _complete_prd(), "`P1-FEAT-20260101-000000-upstream.md`"
    )

    issues = PRD_CHECKER._delivery_gate_banner_issues(blocked_prd)
    assert any(
        "P1-FEAT-20260101-000000-upstream.md" in message for _, message in issues
    ), "规范形状下的依赖必须被读到；横幅仍写「无」应当判负"

    accepted_prd = blocked_prd.replace(
        "> ✅ **交付前置**：无，可立即开工。",
        "> ⛔ **交付前置**：排在 `P1-FEAT-20260101-000000-upstream.md` 之后开工。",
        1,
    )
    assert PRD_CHECKER._delivery_gate_banner_issues(accepted_prd) == []


def test_oracle_reviewer_is_required() -> None:
    """oracle 必须声明证据受众；缺失时按缺少必填字段拒绝。"""

    no_reviewer_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 构建通过
  real_entry: pnpm build
  expected: 退出码 0
  mock_boundary: 无 mock
  tier: R1
  test_layer: smoke
  required_for_acceptance: true
```
"""

    oracle_issues = PRD_CHECKER._oracle_schema_issues(no_reviewer_prd)

    assert len(oracle_issues) == 1
    assert "reviewer" in oracle_issues[0][1]


def test_invalid_oracle_reviewer_is_rejected() -> None:
    """reviewer 只接受 human / verifier，拼错必须报错而不是静默放过。"""

    bad_reviewer_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 构建通过
  reviewer: robot
  real_entry: pnpm build
  expected: 退出码 0
  mock_boundary: 无 mock
  tier: R1
  test_layer: smoke
  required_for_acceptance: true
```
"""

    oracle_issues = PRD_CHECKER._oracle_schema_issues(bad_reviewer_prd)

    assert len(oracle_issues) == 1
    assert "invalid reviewer" in oracle_issues[0][1]


def test_human_reviewer_requires_presentation() -> None:
    """结果可被人感知的 oracle 必须给出人形态呈递物，否则验收清单无物可呈。"""

    no_presentation_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 导航栏显示语言切换器
  reviewer: human
  real_entry: pnpm --filter frontend-admin test:e2e -g language-switcher
  expected: 切换后可见文案由中文变为英文
  mock_boundary: 不 mock 前端渲染
  tier: R1
  test_layer: e2e
  required_for_acceptance: true
```
"""

    oracle_issues = PRD_CHECKER._oracle_schema_issues(no_presentation_prd)

    assert len(oracle_issues) == 1
    assert "presentation" in oracle_issues[0][1]


def test_verifier_reviewer_does_not_require_presentation() -> None:
    """纯机器验收的 oracle 不背呈递物字段，避免形式主义。"""

    verifier_prd = """### 7.6 Realistic Validation Plan (Oracle 块)

```yaml
- id: rv-1
  behavior: 构建通过
  reviewer: verifier
  real_entry: pnpm build
  expected: 退出码 0
  mock_boundary: 无 mock
  tier: R1
  test_layer: smoke
  required_for_acceptance: true
```
"""

    assert PRD_CHECKER._oracle_schema_issues(verifier_prd) == []


# ---------------------------------------------------------------------------
# 三份解析器的逐例等价（模块 docstring 第 3 条）
# ---------------------------------------------------------------------------

_BANNER_SHAPE_CASES = [
    pytest.param("> ⬜ **验收状态**：未开工。\n", "not_started", id="not-started"),
    pytest.param("> 🧍 **验收状态**：待人工验收 — 仅剩 1 项。\n", "awaiting_human", id="awaiting"),
    pytest.param("> ✅ **验收状态**：已验收 — 全部确认。\n", "accepted", id="accepted"),
    pytest.param("> ✅ **验收状态**：可归档。\n", "accepted", id="legacy-ready-to-archive"),
    pytest.param(
        "> ⬜ **验收状态**：未开工。（归档时与 §9 对齐：Human-Confirmed 仍有空框 → "
        "🧍 待人工验收，全部由人确认后 → ✅ 已验收；⬜ 不可归档）\n",
        "not_started",
        id="template-parenthetical-names-the-other-states",
    ),
    pytest.param(
        "> 🧍 **验收状态**：待人工验收（人确认后改为已验收）\n",
        "awaiting_human",
        id="first-state-word-wins-over-a-later-mention",
    ),
    pytest.param(
        "> ✅ **验收状态**：已验收（此前：未开工）\n",
        "accepted",
        id="first-state-word-wins-over-a-trailing-history-note",
    ),
    pytest.param("> **Acceptance Status**: 已验收\n", "accepted", id="english-marker"),
    pytest.param("> ⬜ **ACCEPTANCE STATUS**：未开工\n", "not_started", id="marker-is-case-blind"),
    pytest.param("  > ⬜ **验收状态**：未开工\n", "not_started", id="indented-quote"),
    pytest.param(
        "> **验收状态**：（待填）\n> ✅ **验收状态**：已验收\n",
        "",
        id="first-banner-line-wins-even-when-unreadable",
    ),
    pytest.param("> 🔶 **验收状态**：已完成。\n", "", id="unrecognised-state-word"),
    pytest.param("**验收状态**：已验收\n", "", id="not-a-quote-line"),
    pytest.param("# PRD: x\n\n## 1. Introduction\n\n正文。\n", "", id="no-banner"),
]


@pytest.mark.parametrize(("banner_text", "expected_status"), _BANNER_SHAPE_CASES)
def test_banner_parsers_agree_on_every_banner_shape(banner_text: str, expected_status: str) -> None:
    """skill 的契约解析与看板侧的 prd_acceptance 解析必须逐例等价，且都落在期望值上。

    两侧各带一份实现是同步边界逼出来的；这条测试是把它们锁在一起的唯一一把锁——
    只比"二者相等"会放过两边一起漂，所以同时钉死期望值。
    """

    prd_text = f"# PRD: x\n\n{banner_text}\n## 9. Acceptance Checklist\n"

    assert PRD_CONTRACT.parse_acceptance_status(prd_text) == expected_status
    assert prd_acceptance.parse_acceptance_status(prd_text) == expected_status


@pytest.mark.parametrize(("checklist_body", "expected_open_labels"), CHECKLIST_SCOPE_PARAMS)
def test_checklist_scanners_agree_on_which_open_items_the_executor_owes(
    checklist_body: str, expected_open_labels: list[str]
) -> None:
    """hook 的轻量扫描与契约解析逐例等价，且都只报执行侧欠的空框。

    ``Human-Confirmed`` 作用范围的判定（嵌套、同级关闭、前缀匹配、围栏代码块）是两份
    实现最容易悄悄走样的地方，所以每个形态都钉死期望值，而不只比较二者相等。
    """

    prd_text = prd_with_checklist_body(checklist_body)
    contract_state = PRD_CONTRACT.parse_checklist(prd_text)

    hook_items = PRD_HOOK._unchecked_items_in_acceptance_section(prd_text)
    checker_items = PRD_CHECKER._unchecked_items_in_acceptance_section(prd_text)

    assert hook_items == checker_items
    assert open_item_labels(hook_items) == expected_open_labels
    # 执行侧与人属两路合起来恰好是全部空框：不重不漏，横幅才有据可依。
    assert len(contract_state.execution_unchecked_items) + len(
        contract_state.human_unchecked_items
    ) == len(contract_state.unchecked_items)
    assert not set(contract_state.execution_unchecked_items) & set(
        contract_state.human_unchecked_items
    )


@pytest.mark.parametrize(("checklist_body", "_expected_open_labels"), CHECKLIST_SCOPE_PARAMS)
def test_progress_counter_agrees_with_the_contract_on_every_scope_shape(
    checklist_body: str, _expected_open_labels: list[str]
) -> None:
    """看板与执行锁共用的勾选计数和契约解析逐例等价：分组、围栏、``[~]`` 都不改口径。

    进度是"全部复选框里勾了几个"，与分组无关；``[~]`` 既不算已勾也不算未勾，围栏代码块
    内的框不算。两侧各写一份读法时最容易悄悄走样的正是这几处，所以按作用域用例表逐形态
    比对，而不只信任某一份实现。
    """

    prd_text = prd_with_checklist_body(checklist_body)
    contract_state = PRD_CONTRACT.parse_checklist(prd_text)
    checked_count = len(contract_state.checked_items)

    assert prd_acceptance.count_checklist_items(prd_text) == (
        checked_count,
        checked_count + len(contract_state.unchecked_items),
    )


def test_checklist_scanners_agree_when_the_section_is_missing() -> None:
    """缺验收清单章节时两侧给出同一条报告，而不是一边静默通过。"""

    prd_text = "# PRD: x\n\n## 8. Delivery Dependencies\n\n- [ ] not-a-checklist\n"
    expected_issues = [(-1, "Missing Acceptance Checklist section")]

    assert PRD_HOOK._unchecked_items_in_acceptance_section(prd_text) == expected_issues
    assert PRD_CHECKER._unchecked_items_in_acceptance_section(prd_text) == expected_issues


def _real_prd_paths() -> list[Path]:
    """本仓库 ``tasks/`` 下所有真实存在的 PRD / 想法文档（递归）。"""

    return sorted((REPO_ROOT / "tasks").rglob("*.md"))


def test_parsers_agree_on_every_prd_in_the_repository() -> None:
    """在真实语料上做差分：三份解析器对仓库里每一份文档的读法必须一致。

    手写的形态再全也比不过真实 PRD 的写法多样；语料随仓库增长，等价性随之被持续检验。
    只比较、不设期望值，所以语料里有历史写法（旧称横幅、缺章节）也不会误伤。
    """

    prd_paths = _real_prd_paths()
    if not prd_paths:
        pytest.skip("仓库里没有 tasks/ 文档可供差分")

    for prd_path in prd_paths:
        prd_text = prd_path.read_text(encoding="utf-8")
        relative_path = prd_path.relative_to(REPO_ROOT).as_posix()

        assert PRD_HOOK._unchecked_items_in_acceptance_section(
            prd_text
        ) == PRD_CHECKER._unchecked_items_in_acceptance_section(prd_text), relative_path
        assert PRD_CONTRACT.parse_acceptance_status(
            prd_text
        ) == prd_acceptance.parse_acceptance_status(prd_text), relative_path
        contract_state = PRD_CONTRACT.parse_checklist(prd_text)
        checked_count = len(contract_state.checked_items)
        assert prd_acceptance.count_checklist_items(prd_text) == (
            checked_count,
            checked_count + len(contract_state.unchecked_items),
        ), relative_path
