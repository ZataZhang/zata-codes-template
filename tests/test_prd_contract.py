"""``skills/prd/scripts/prd_contract.py`` 的行为测试。

这些覆盖原先散落在下游执行工具（agent runner）里的解析器测试。解析实现已经
收敛到本模板的 skill，覆盖就必须跟着走——否则"测试留在下游、实现搬到上游"
会让下游不得不再造一份替身解析器，等于把刚消掉的重复实现搬回来。

**本文件是模板内部测试**：被测对象 ``skills/prd/`` 不同步进派生项目（见
``scripts/shared/template/sync_template.sh`` 的排除清单），因此本文件也已列入
该清单，不会随同步外流。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "skills" / "prd" / "scripts" / "prd_contract.py"
)
_SPEC = importlib.util.spec_from_file_location("prd_contract_under_test", CONTRACT_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
prd_contract = importlib.util.module_from_spec(_SPEC)
# dataclass 在解析注解时要回查 sys.modules[cls.__module__]，因此必须先登记再执行。
sys.modules[_SPEC.name] = prd_contract
_SPEC.loader.exec_module(prd_contract)


# ---------------------------------------------------------------------------
# Acceptance Checklist：章节边界
# ---------------------------------------------------------------------------


class TestChecklistSectionBounds:
    """章节定位、围栏忽略与行号。"""

    def test_missing_section_is_reported(self) -> None:
        """没有清单标题时不报 section_found，也不产出条目。"""
        state = prd_contract.parse_checklist("# PRD\n\n## Other\n\n- [ ] item\n")
        assert state.section_found is False
        assert state.items == ()

    def test_empty_content_has_no_section(self) -> None:
        """空文档同样不报 section_found。"""
        assert prd_contract.parse_checklist("").section_found is False

    def test_unchecked_items_carry_one_based_line_numbers(self) -> None:
        """未勾项按 1-based 行号报告。"""
        content = "\n".join(
            ["# PRD", "", "## Acceptance Checklist", "", "- [x] done", "- [ ] undone"]
        )
        state = prd_contract.parse_checklist(content)
        assert [(item.line, item.text) for item in state.unchecked_items] == [(6, "- [ ] undone")]

    def test_checkboxes_outside_the_section_are_ignored(self) -> None:
        """章节前后的复选框不计入。"""
        content = "\n".join(
            [
                "# PRD",
                "- [ ] before",
                "## Acceptance Checklist",
                "- [x] done",
                "## Notes",
                "- [ ] after",
            ]
        )
        state = prd_contract.parse_checklist(content)
        assert state.unchecked_items == ()

    @pytest.mark.parametrize("fence", ["```markdown", "~~~python"])
    def test_checkboxes_inside_code_fences_are_ignored(self, fence: str) -> None:
        """围栏代码块内的复选框不计入（反引号与波浪号两种围栏都认）。"""
        content = "\n".join(
            [
                "## Acceptance Checklist",
                fence,
                "- [ ] inside fence",
                fence,
                "- [ ] real unchecked",
            ]
        )
        state = prd_contract.parse_checklist(content)
        assert [item.text for item in state.unchecked_items] == ["- [ ] real unchecked"]

    def test_numbered_and_bilingual_headings_are_recognized(self) -> None:
        """编号前缀与中英双语标题都要能识别。"""
        numbered = prd_contract.parse_checklist("## 7. Acceptance Checklist\n- [ ] a\n")
        bilingual = prd_contract.parse_checklist(
            "## 7. Acceptance Checklist（验收清单）\n- [ ] a\n"
        )
        assert numbered.section_found is True
        assert bilingual.section_found is True
        assert numbered.unchecked_items[0].line == 2
        assert bilingual.unchecked_items[0].line == 2


# ---------------------------------------------------------------------------
# Acceptance Checklist：标记语义
# ---------------------------------------------------------------------------


class TestChecklistMarks:
    """``[ ]`` / ``[x]`` / ``[~]`` 的区分，以及"章节内无条目"。"""

    def test_all_checked_has_no_unchecked_items(self) -> None:
        """全勾时未勾集合为空。"""
        state = prd_contract.parse_checklist("## Acceptance Checklist\n- [x] a\n- [X] b\n")
        assert state.unchecked_items == ()
        assert len(state.checked_items) == 2

    def test_tilde_is_resolved_and_not_unchecked(self) -> None:
        """``[~]`` 是 runner 门禁豁免，既不算勾也不算未勾。

        归档门禁依赖这个语义：``- [~] … — runner-owned gate: …`` 必须放行，
        否则「等独立 verifier PASS」这类条目会让 attempt 死循环。
        """
        content = "\n".join(
            [
                "## Acceptance Checklist",
                "- [x] 真实入口证据已产出",
                "- [~] 独立 verifier PASS — runner-owned gate: Phase 3.6",
            ]
        )
        state = prd_contract.parse_checklist(content)
        assert state.unchecked_items == ()
        assert len(state.resolved_items) == 1

    def test_empty_section_yields_no_items(self) -> None:
        """章节存在但没有任何条目的情况是合法的。"""
        state = prd_contract.parse_checklist("## Acceptance Checklist\n\n只有文字。\n")
        assert state.section_found is True
        assert state.items == ()


# ---------------------------------------------------------------------------
# Acceptance Checklist：Human-Confirmed 分组
# ---------------------------------------------------------------------------


class TestHumanConfirmedGroup:
    """人属分组的识别、边界与诊断信号。

    背景：``**Human-Confirmed**`` 这种整行加粗写法曾让分组彻底不被识别，人属项
    落入执行项集合，交付门禁报 checklist_unchecked 并触发 closeout/repair 死循环
    （实证：ai-assistant Issue #53）。
    """

    def test_heading_group_separates_human_from_execution(self) -> None:
        """人属组内的空框归人；组外的空框才是执行项。"""
        content = "\n".join(
            [
                "## 9. Acceptance Checklist",
                "### Human-Confirmed",
                "- [ ] 人属项",
                "### Validation Acceptance",
                "- [ ] rv-1 PASS",
            ]
        )
        state = prd_contract.parse_checklist(content)
        assert [item.text for item in state.human_items] == ["- [ ] 人属项"]
        assert [item.text for item in state.execution_unchecked_items] == ["- [ ] rv-1 PASS"]
        assert state.human_group_found is True

    def test_group_label_with_suffix_is_recognized(self) -> None:
        """带说明后缀的分组标题（模板自带写法）必须被识别。

        这是分组标签用**前缀**而非精确相等匹配的原因：``### Human-Confirmed
        (来自 Part A 风险地图)`` 曾是"照着模板写却过不了门禁"的根因。
        """
        content = "\n".join(
            [
                "### Human-Confirmed (来自 Part A 风险地图)",
                "- [ ] 人属项",
                "### Behavior Acceptance",
                "- [ ] 执行项",
            ]
        )
        state = prd_contract.parse_checklist(f"## Acceptance Checklist\n{content}")
        assert state.human_group_found is True
        assert [item.text for item in state.human_items] == ["- [ ] 人属项"]
        assert [item.text for item in state.execution_unchecked_items] == ["- [ ] 执行项"]

    def test_bold_group_label_opens_and_a_sibling_bold_label_closes_it(self) -> None:
        """整行加粗的分组标签按三级处理，被下一个同级加粗标签关闭。"""
        content = "\n".join(
            [
                "## 9. Acceptance Checklist",
                "### 9.2 Acceptance Evidence Package",
                "**Human-Confirmed**",
                "- [ ] 决定一：人属项",
                "**Behavior Acceptance**",
                "- [ ] rv-1 PASS：待独立 verifier",
            ]
        )
        state = prd_contract.parse_checklist(content)
        assert [item.text for item in state.human_items] == ["- [ ] 决定一：人属项"]
        assert [item.text for item in state.execution_unchecked_items] == [
            "- [ ] rv-1 PASS：待独立 verifier"
        ]

    def test_inline_bold_is_not_a_group_marker(self) -> None:
        """行内强调（加粗后还有正文）不得被当作分组标签。"""
        content = "\n".join(
            [
                "## 9. Acceptance Checklist",
                "**Human-Confirmed（2026-09-23）：** 用户确认了该决定。",
                "- [ ] 执行项",
            ]
        )
        state = prd_contract.parse_checklist(content)
        assert state.human_items == ()
        assert state.human_group_found is False
        assert state.human_confirmed_mentioned is True
        assert [item.text for item in state.execution_unchecked_items] == ["- [ ] 执行项"]

    def test_mention_without_group_is_diagnosable(self) -> None:
        """提到 Human-Confirmed 但没识别出分组时，两个信号可区分。

        消费方据此给出可行动的诊断（"分组写法有问题"），而不是让 agent 在
        "人属项必须留空"与"门禁说它未勾"之间空转。
        """
        state = prd_contract.parse_checklist(
            "## Acceptance Checklist\nHuman-Confirmed:\n- [ ] 人属项\n"
        )
        assert state.human_group_found is False
        assert state.human_confirmed_mentioned is True


# ---------------------------------------------------------------------------
# Change Log（Machine Contract §1）
# ---------------------------------------------------------------------------


class TestChangeLog:
    """条目数、六字段完整性与缺章节。"""

    COMPLETE_ENTRY = "\n".join(
        [
            "# PRD",
            "## Change Log",
            "### 2026-07-14 · Agent proposal",
            "- 类型：验证方案调整",
            "- 原文：真实应用截图",
            "- 变更后：真实 Playwright 截图",
            "- 原因：使步骤可重复执行",
            "- 影响：用户可见目标不变",
            "- 审核：待独立 reviewer 确认",
        ]
    )

    def test_complete_entry_is_complete(self) -> None:
        """六个字段齐备的条目让整个章节完整。"""
        state = prd_contract.parse_change_log(self.COMPLETE_ENTRY)
        assert state.section_found is True
        assert state.entry_count == 1
        assert state.entries[0].missing_fields == ()
        assert state.is_complete is True

    def test_missing_fields_are_named_in_contract_order(self) -> None:
        """缺字段的条目要点名缺失项，顺序按契约定义的字段顺序。"""
        content = "\n".join(
            [
                "# PRD",
                "## Change Log",
                "### 2026-07-14 · Agent proposal",
                "- 类型：范围调整",
                "- 原文：原始范围",
            ]
        )
        state = prd_contract.parse_change_log(content)
        assert state.entries[0].missing_fields == ("变更后", "原因", "影响", "审核")
        assert state.is_complete is False

    def test_no_section_reports_zero_entries(self) -> None:
        """没有 Change Log 章节时条目数为 0。"""
        state = prd_contract.parse_change_log("# PRD\n")
        assert state.section_found is False
        assert state.entry_count == 0

    def test_multiple_entries_are_counted_in_order(self) -> None:
        """多条记录按出现顺序计入。"""
        tail = "\n".join(
            [
                "### 2026-07-15 · 第二条",
                "- 类型：范围调整",
                "- 原文：a",
                "- 变更后：b",
                "- 原因：c",
                "- 影响：d",
                "- 审核：e",
            ]
        )
        state = prd_contract.parse_change_log(f"{self.COMPLETE_ENTRY}\n{tail}\n")
        assert state.entry_count == 2
        assert [entry.title for entry in state.entries] == [
            "2026-07-14 · Agent proposal",
            "2026-07-15 · 第二条",
        ]
