"""守护 git-diff-report 技能路径解析与输出转义的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

被测对象：``skills/git-diff-report/scripts/render_diff_report.py``。它把 ``git diff``
的输出渲染成一份**会发给别人**的静态 HTML，因此下面每条不变量都直接决定报告
是否可信：

1. **路径不能被截断。** git 只为特殊字符加引号，只有空格的路径在 ``diff --git``
   头里是裸写的（``diff --git a/with space.txt b/with space.txt``），按空格切分
   token 会把路径截成最后一个词。
2. **引号里的八进制转义是 UTF-8 字节。** ``"\\346\\226\\207"`` 要还原成 ``文``；
   把 ``\\346`` 当码点解释会让中文路径变成乱码。
3. **路径出现在 HTML 属性位时必须转义引号。** 路径来自被检查的仓库（可能是别人
   的分支），``title="…"`` 被引号提前闭合就等于把任意属性——包括事件处理器——
   注进报告，收件人一打开就执行。
4. **解析出的路径必须能与 ``--summaries`` 的键对上。** 逐文件总结按路径查表，
   路径错一个字符，总结就静默消失，而那是这份报告相对查看器的主要价值。
5. **没有 HEAD 的仓库也要能出报告。** ``git init`` 之后、首次提交之前是最常见的
   「看改了什么」场景，任何 scope 都不能直接以 git 报错退出。
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

REPORT_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "git-diff-report"
    / "scripts"
    / "render_diff_report.py"
)

#: 文件名里的引号会尝试闭合 ``title="…"`` 并挂上一个事件处理器。
ATTRIBUTE_INJECTION_PATH = 'evil" onmouseover="alert(1)" .txt'


def _init_empty_repository(repository_root: Path) -> None:
    """初始化一个临时 git 仓库（默认分支名与身份都显式给足）。"""
    repository_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "guard-test@example.com"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "guard test"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def _init_repository_with_baseline(repository_root: Path) -> None:
    """初始化临时仓库并提交一个基线文件。

    基线提交让用例面对「已有 HEAD」的常态——「尚无提交」本身是单独一条用例的被测
    对象，不能顺手混进其它用例的失败原因里。
    """
    _init_empty_repository(repository_root)
    (repository_root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _stage_paths(repository_root, "baseline.txt")
    _commit_staged(repository_root, "add baseline")


def _stage_paths(repository_root: Path, *relative_paths: str) -> None:
    """把给定路径加进索引（``git add``）。"""
    subprocess.run(
        ["git", "add", "--", *relative_paths],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def _commit_staged(repository_root: Path, message: str) -> None:
    """提交当前索引内容（供重命名与模式变更用例准备基线）。"""
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )


def _render_report(
    repository_root: Path,
    report_path: Path,
    *report_arguments: str,
) -> subprocess.CompletedProcess[str]:
    """按真实入口（命令行）生成一份报告。"""
    return subprocess.run(
        [
            sys.executable,
            str(REPORT_SCRIPT_PATH),
            "--repo",
            str(repository_root),
            "--out",
            str(report_path),
            *report_arguments,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_space_in_path_is_kept_whole(tmp_path: Path) -> None:
    """含空格的路径必须整条出现在报告里，而不是只剩最后一个词。"""
    repository_root = tmp_path / "repository"
    _init_repository_with_baseline(repository_root)
    (repository_root / "with space.txt").write_text("sp\n", encoding="utf-8")
    _stage_paths(repository_root, "with space.txt")

    report_path = tmp_path / "report.html"
    result = _render_report(repository_root, report_path, "--scope", "staged")
    assert result.returncode == 0, result.stderr

    report_page = report_path.read_text(encoding="utf-8")
    assert "<h2>with space.txt</h2>" in report_page
    assert "<h2>space.txt</h2>" not in report_page


def test_utf8_path_is_decoded_and_matches_summary(tmp_path: Path) -> None:
    """非 ASCII 路径要还原成原字符，且能对上 ``--summaries`` 里的键。"""
    repository_root = tmp_path / "repository"
    _init_repository_with_baseline(repository_root)
    (repository_root / "文档-中文名.md").write_text("zh\n", encoding="utf-8")
    _stage_paths(repository_root, "文档-中文名.md")

    summaries_path = tmp_path / "summaries.json"
    summaries_path.write_text(
        json.dumps(
            {"files": {"文档-中文名.md": {"summary": "这条总结必须出现"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report_path = tmp_path / "report.html"
    result = _render_report(
        repository_root,
        report_path,
        "--scope",
        "staged",
        "--summaries",
        str(summaries_path),
    )
    assert result.returncode == 0, result.stderr

    report_page = report_path.read_text(encoding="utf-8")
    assert "<h2>文档-中文名.md</h2>" in report_page
    assert "这条总结必须出现" in report_page


def test_path_quote_cannot_break_out_of_title_attribute(tmp_path: Path) -> None:
    """路径里的引号不得闭合属性位，注入的事件处理器不能出现在页面里。"""
    repository_root = tmp_path / "repository"
    _init_repository_with_baseline(repository_root)
    (repository_root / ATTRIBUTE_INJECTION_PATH).write_text("x\n", encoding="utf-8")
    _stage_paths(repository_root, ATTRIBUTE_INJECTION_PATH)

    report_path = tmp_path / "report.html"
    result = _render_report(repository_root, report_path, "--scope", "staged")
    assert result.returncode == 0, result.stderr

    report_page = report_path.read_text(encoding="utf-8")
    assert 'onmouseover="alert(1)"' not in report_page

    title_attribute = re.search(r'title="([^"]*)"', report_page)
    assert title_attribute is not None
    assert title_attribute.group(1) == html.escape(ATTRIBUTE_INJECTION_PATH, quote=True)


def test_report_renders_before_first_commit(tmp_path: Path) -> None:
    """仓库尚无提交时，``staged`` 与 ``head`` 都要能出报告。"""
    repository_root = tmp_path / "fresh-repository"
    _init_empty_repository(repository_root)
    (repository_root / "first.txt").write_text("x\n", encoding="utf-8")
    _stage_paths(repository_root, "first.txt")

    staged_report_path = tmp_path / "staged-report.html"
    staged_result = _render_report(repository_root, staged_report_path, "--scope", "staged")
    assert staged_result.returncode == 0, staged_result.stderr
    assert "<h2>first.txt</h2>" in staged_report_path.read_text(encoding="utf-8")

    head_report_path = tmp_path / "head-report.html"
    head_result = _render_report(repository_root, head_report_path, "--scope", "head")
    assert head_result.returncode == 0, head_result.stderr
    head_report_page = head_report_path.read_text(encoding="utf-8")
    assert "<h2>first.txt</h2>" in head_report_page
    assert "尚无提交" in head_report_page


def test_rename_with_space_is_reported_as_move(tmp_path: Path) -> None:
    """含空格的纯重命名仍要认成「文件移动」，并给出完整的新路径。"""
    repository_root = tmp_path / "repository"
    _init_empty_repository(repository_root)
    (repository_root / "old name.txt").write_text("content\n", encoding="utf-8")
    _stage_paths(repository_root, "old name.txt")
    _commit_staged(repository_root, "add file")
    subprocess.run(
        ["git", "mv", "old name.txt", "new name.txt"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )

    report_path = tmp_path / "report.html"
    result = _render_report(repository_root, report_path, "--scope", "staged")
    assert result.returncode == 0, result.stderr

    report_page = report_path.read_text(encoding="utf-8")
    assert "文件移动" in report_page
    assert 'title="new name.txt"' in report_page


def test_mode_only_change_keeps_whole_path(tmp_path: Path) -> None:
    """只有模式变更（没有 hunk、没有 ``+++`` 行）时也要拿到完整路径。"""
    repository_root = tmp_path / "repository"
    _init_empty_repository(repository_root)
    executable_path = repository_root / "run me.sh"
    executable_path.write_text("echo hi\n", encoding="utf-8")
    _stage_paths(repository_root, "run me.sh")
    _commit_staged(repository_root, "add script")
    executable_path.chmod(0o755)
    _stage_paths(repository_root, "run me.sh")

    report_path = tmp_path / "report.html"
    result = _render_report(repository_root, report_path, "--scope", "staged")
    assert result.returncode == 0, result.stderr

    report_page = report_path.read_text(encoding="utf-8")
    assert 'title="run me.sh"' in report_page
    assert 'title="me.sh"' not in report_page
