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
