"""验证 PRD skill 归档 checker 的证据链约束。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

CHECKER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "prd"
    / "scripts"
    / "check_prd_acceptance_checklist.py"
)
CHECKER_SPEC = importlib.util.spec_from_file_location("prd_skill_checker", CHECKER_PATH)
assert CHECKER_SPEC is not None
assert CHECKER_SPEC.loader is not None
PRD_CHECKER = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(PRD_CHECKER)


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

# Part A · 人审层 (Review Layer)

## 1. Introduction & Goals

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
  real_entry: just e2e share
  expected: 匿名浏览器看到分享内容
  mock_boundary: 仅 mock 邮件发送
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
