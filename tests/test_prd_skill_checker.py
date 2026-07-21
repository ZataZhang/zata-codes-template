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
