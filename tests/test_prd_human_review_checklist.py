"""``skills/prd/scripts/check_human_review_checklist.py`` 的行为测试。

警告级结构 checker：只挡「清单里某个决定没有证据 / 相对图解析不到 / 绝对路径进
产物 / md 与 html 条目不一致」这类结构性缺失，不做语义判断。

**本文件是模板内部测试**：被测对象 ``skills/prd/`` 不同步进派生项目（见
``scripts/shared/template/sync_template.sh`` 的排除清单），因此本文件也列在该清单，
不会随同步外流。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CHECKER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "prd"
    / "scripts"
    / "check_human_review_checklist.py"
)
_SPEC = importlib.util.spec_from_file_location("human_review_checklist_checker", CHECKER_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
checker = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = checker
_SPEC.loader.exec_module(checker)


def _write_evidence_dir(tmp_path: Path, markdown_text: str, html_text: str | None = None) -> Path:
    """在临时证据目录写一份清单（可选交互 HTML），返回目录。"""
    evidence_dir_path = tmp_path / "tasks" / "evidence" / "P0-FEAT-20260923-000000-demo"
    evidence_dir_path.mkdir(parents=True)
    (evidence_dir_path / "human-review-checklist.md").write_text(markdown_text, encoding="utf-8")
    if html_text is not None:
        (evidence_dir_path / "human-review-checklist.html").write_text(html_text, encoding="utf-8")
    return evidence_dir_path


def test_decision_sections_skip_reply_section() -> None:
    """决定小节按二级标题切分，收尾的「回复」小节不算决定。"""
    markdown_text = (
        "# 人审清单\n\n"
        "## 1. 决定甲\n\n> 引用\n\n"
        "## 2. 决定乙\n\n> 引用\n\n"
        "## 人审回复格式\n\n怎么答。\n"
    )
    sections = checker.extract_decision_sections(markdown_text)
    assert [title for title, _ in sections] == ["1. 决定甲", "2. 决定乙"]


def test_section_without_evidence_is_warned(tmp_path: Path) -> None:
    """只给文件名/命令、没有图或引用块的小节要告警。"""
    evidence_dir = _write_evidence_dir(
        tmp_path,
        "# 人审清单\n\n## 1. 决定甲\n\n证据文件：`report.md`；复跑 `pytest -q`。\n",
    )
    warnings = checker.check_checklist(evidence_dir / "human-review-checklist.md", None)
    assert any("没有任何证据" in text for text in warnings)


def test_missing_relative_image_is_warned(tmp_path: Path) -> None:
    """相对图片解析不到文件时告警。"""
    evidence_dir = _write_evidence_dir(
        tmp_path,
        "# 人审清单\n\n## 1. 决定甲\n\n![截图](missing.png)\n",
    )
    warnings = checker.check_checklist(evidence_dir / "human-review-checklist.md", None)
    assert any("解析不到文件" in text for text in warnings)


def test_absolute_image_path_is_warned(tmp_path: Path) -> None:
    """绝对本地图片路径要告警（不该进会提交的产物）。"""
    evidence_dir = _write_evidence_dir(
        tmp_path,
        "# 人审清单\n\n## 1. 决定甲\n\n![截图](/Users/someone/secret/shot.png)\n",
    )
    warnings = checker.check_checklist(evidence_dir / "human-review-checklist.md", None)
    assert any("绝对图片路径" in text for text in warnings)


def test_present_relative_image_is_clean(tmp_path: Path) -> None:
    """有可解析的相对图时该小节无告警。"""
    evidence_dir = _write_evidence_dir(
        tmp_path,
        "# 人审清单\n\n## 1. 决定甲\n\n![截图](shot.png)\n\n> 观测值：42。\n",
    )
    (evidence_dir / "shot.png").write_text("x", encoding="utf-8")
    assert checker.check_checklist(evidence_dir / "human-review-checklist.md", None) == []


def test_md_html_decision_count_mismatch_is_warned(tmp_path: Path) -> None:
    """md 与 html 的决定条目数不一致时告警。"""
    markdown_text = "# 人审清单\n\n## 1. 决定甲\n\n> 引用\n\n## 2. 决定乙\n\n> 引用\n"
    html_text = "<h2>决定甲</h2><h2>审查结果</h2>"
    evidence_dir = _write_evidence_dir(tmp_path, markdown_text, html_text)
    warnings = checker.check_checklist(
        evidence_dir / "human-review-checklist.md",
        evidence_dir / "human-review-checklist.html",
    )
    assert any("条目数不一致" in text for text in warnings)


def test_main_warning_level_exit_codes(tmp_path: Path, capsys) -> None:
    """默认警告级退出 0；--fail-on-warning 有告警时退出 1；清单缺失退出 1。"""
    evidence_dir = _write_evidence_dir(tmp_path, "# 人审清单\n\n## 1. 决定甲\n\n无证据。\n")
    checklist_path = evidence_dir / "human-review-checklist.md"

    assert checker.main([str(checklist_path)]) == 0
    assert checker.main([str(checklist_path), "--fail-on-warning"]) == 1
    assert checker.main([str(tmp_path / "nope.md")]) == 1
    capsys.readouterr()
