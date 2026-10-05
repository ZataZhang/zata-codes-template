#!/usr/bin/env python3
"""人审清单（``human-review-checklist.md`` / ``.html``）的**警告级**结构检查。

只挡「结构性缺失」，不做语义判断——判断一段证据是否真的证明了某个决定，仍归
人和 agent。检查项（全部只产 warning、默认不阻断）：

1. 清单 Markdown 存在。
2. 每个「决定小节」都带证据：可视件内联图（``![...](...)``）**或**逐字引用块
   （blockquote / 代码围栏）——只写文件名或命令视为不合格。
3. 相对图片路径能从清单所在目录解析（绝对本地路径单独告警：它不该出现在会提交
   的产物里，见 SKILL.md §9.1 的路径要求）。
4. 存在交互 companion ``human-review-checklist.html`` 时，决定条目数与 Markdown
   一致（两者内容必须一致，见 SKILL.md 的人审清单条目）。

设计取向与 ``check_prd_acceptance_checklist.py`` 相反：那个是**归档门禁**（阻断），
这个只做提示，默认退出码 0；需要让它在 CI 变红时显式传 ``--fail-on-warning``。

用法::

    python check_human_review_checklist.py <checklist-md | evidence-dir> [--fail-on-warning]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 决定小节之外的收尾小节：它们不是「人的决定」，跳过证据要求。
_NON_DECISION_TITLE_RE = re.compile(r"回复|结果|reply|result", re.IGNORECASE)
# Markdown 二级标题即一个决定小节（模板约定 ``## <标题>``）。
_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
# 内联图 ``![说明](路径)``。
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
# HTML 决定卡的标题（模板固定为 ``<h2>...</h2>``）。
_HTML_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# 视为「证据」的逐字引用块标记。
_QUOTE_MARKERS = (">", "```")


def resolve_checklist_paths(argument_path: Path) -> tuple[Path | None, Path | None]:
    """从命令行参数解析清单 Markdown 与可选交互 HTML 的路径。

    Args:
        argument_path (Path): 传入的清单 ``.md`` 路径，或其所在的证据目录。

    Returns:
        tuple[Path | None, Path | None]: ``(清单 md, 交互 html)``；md 不存在时为
            ``(None, None)``；html 不存在时第二项为 ``None``。
    """
    if argument_path.is_dir():
        evidence_dir_path = argument_path
        markdown_path = evidence_dir_path / "human-review-checklist.md"
    else:
        markdown_path = argument_path
        evidence_dir_path = argument_path.parent
    if not markdown_path.is_file():
        return None, None
    html_path = evidence_dir_path / "human-review-checklist.html"
    return markdown_path, (html_path if html_path.is_file() else None)


def extract_decision_sections(markdown_text: str) -> list[tuple[str, str]]:
    """切出人审清单里的「决定小节」：标题 + 正文。

    二级标题下到下一个二级标题之间为一个小节；标题命中「回复/结果/reply/result」
    的收尾小节不算决定，跳过。

    Args:
        markdown_text (str): 清单 Markdown 文本。

    Returns:
        list[tuple[str, str]]: ``(标题, 正文)``，按出现顺序。
    """
    heading_matches = list(_SECTION_HEADING_RE.finditer(markdown_text))
    sections_list: list[tuple[str, str]] = []
    for index, heading_match in enumerate(heading_matches):
        title_text = heading_match.group(1).strip()
        if _NON_DECISION_TITLE_RE.search(title_text):
            continue
        body_start = heading_match.end()
        body_end = (
            heading_matches[index + 1].start()
            if index + 1 < len(heading_matches)
            else len(markdown_text)
        )
        sections_list.append((title_text, markdown_text[body_start:body_end]))
    return sections_list


def section_has_evidence(section_body: str) -> bool:
    """判断一个小节是否带证据：有内联图，或有逐字引用块。"""
    if _IMAGE_RE.search(section_body):
        return True
    for line_text in section_body.splitlines():
        stripped_line = line_text.strip()
        if stripped_line.startswith(_QUOTE_MARKERS):
            return True
    return False


def extract_image_targets(section_body: str) -> list[str]:
    """取出小节里所有内联图的目标路径（原样，未规范化）。"""
    return [target_text.strip() for target_text in _IMAGE_RE.findall(section_body)]


def _is_remote_target(target_text: str) -> bool:
    """http(s) / data URL 不落本地磁盘，不参与相对路径解析。"""
    lowered_text = target_text.lower()
    return lowered_text.startswith(("http://", "https://", "data:"))


def check_checklist(markdown_path: Path, html_path: Path | None) -> list[str]:
    """对清单做结构性检查，返回人类可读的 warning 列表（可能为空）。

    Args:
        markdown_path (Path): 清单 Markdown 路径。
        html_path (Path | None): 交互 companion 路径；不存在时传 ``None``。

    Returns:
        list[str]: 警告文本；无问题时为空列表。
    """
    warnings_list: list[str] = []
    markdown_text = markdown_path.read_text(encoding="utf-8")
    sections_list = extract_decision_sections(markdown_text)
    if not sections_list:
        warnings_list.append(
            "未识别到任何决定小节（约定为二级标题 ``## <标题>``）——请确认这份文件是不是人审清单。"
        )

    for title_text, section_body in sections_list:
        if not section_has_evidence(section_body):
            warnings_list.append(
                f"决定小节「{title_text}」没有任何证据：需要内联真实图（相对路径）"
                "或逐字引用块（观测值/关键报告行）；只写文件名或命令不合格。"
            )
        for target_text in extract_image_targets(section_body):
            if _is_remote_target(target_text):
                continue
            if target_text.startswith("/"):
                warnings_list.append(
                    f"决定小节「{title_text}」用了绝对图片路径 `{target_text}`："
                    "会提交的产物里应改用仓库相对路径（绝对本地路径会泄漏机器布局）。"
                )
                continue
            resolved_image_path = (markdown_path.parent / target_text).resolve()
            if not resolved_image_path.is_file():
                warnings_list.append(
                    f"决定小节「{title_text}」的图片 `{target_text}` 解析不到文件"
                    f"（期望 {resolved_image_path}）。"
                )

    if html_path is not None:
        html_text = html_path.read_text(encoding="utf-8")
        html_titles_list = [
            _HTML_TAG_RE.sub("", raw_title_text).strip()
            for raw_title_text in _HTML_H2_RE.findall(html_text)
        ]
        html_decision_titles_list = [
            title_text
            for title_text in html_titles_list
            if title_text and not _NON_DECISION_TITLE_RE.search(title_text)
        ]
        if len(html_decision_titles_list) != len(sections_list):
            warnings_list.append(
                "清单 Markdown 与交互 HTML 的决定条目数不一致："
                f"md={len(sections_list)}（{ [title for title, _ in sections_list] }）"
                f" vs html={len(html_decision_titles_list)}（{html_decision_titles_list}）。"
                "两者内容必须一致。"
            )
    return warnings_list


def main(argv: list[str] | None = None) -> int:
    """命令行入口。

    Args:
        argv (list[str] | None): 参数列表；``None`` 时读 ``sys.argv``。

    Returns:
        int: 默认总是 0（警告级）；传 ``--fail-on-warning`` 且存在警告时为 1，
        路径完全解析不到（无清单）时为 1。
    """
    argument_parser = argparse.ArgumentParser(
        description="人审清单结构检查（警告级：只挡结构性缺失，不做语义判断）。"
    )
    argument_parser.add_argument(
        "checklist",
        type=Path,
        help="清单 Markdown 路径，或其所在的证据目录。",
    )
    argument_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="存在警告时以退出码 1 结束（默认仅打印、退出 0）。",
    )
    parsed_arguments = argument_parser.parse_args(argv)

    markdown_path, html_path = resolve_checklist_paths(parsed_arguments.checklist)
    if markdown_path is None:
        print(
            f"ERROR: 找不到人审清单：{parsed_arguments.checklist}"
            "（需要 human-review-checklist.md）"
        )
        return 1

    warnings_list = check_checklist(markdown_path, html_path)
    if not warnings_list:
        print(f"OK: {markdown_path.name} 结构检查通过（警告级，不含语义判断）。")
        return 0
    print(f"WARNING: {markdown_path.name} 有 {len(warnings_list)} 条结构提示（警告级，不阻断）：")
    for warning_text in warnings_list:
        print(f"  - {warning_text}")
    return 1 if parsed_arguments.fail_on_warning else 0


if __name__ == "__main__":
    sys.exit(main())
