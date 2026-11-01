#!/usr/bin/env python3
"""按用户可读的功能链路组织 diff 报告导航。"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from feature_diagram import render_feature_diagram


@dataclass(frozen=True)
class FeatureStep:
    """功能链路中的一个步骤及其对应文件序号。"""

    label: str
    change: str
    file_indexes: tuple[int, ...]
    core_file_indexes: tuple[int, ...]


@dataclass(frozen=True)
class FeatureGroup:
    """一组按用户功能组织的改动文件。"""

    index: int
    title: str
    summary: str
    core_change: str
    diagram: dict[str, Any] | None
    steps: tuple[FeatureStep, ...]
    file_indexes: tuple[int, ...]
    core_file_indexes: tuple[int, ...]


def normalize_feature_groups(
    summaries: dict[str, Any], files: Sequence[dict[str, Any]]
) -> tuple[FeatureGroup, ...]:
    """解析摘要 JSON 中的功能分组，并将遗漏文件补入「其他改动」。"""
    raw_groups = summaries.get("feature_groups")
    if not isinstance(raw_groups, list):
        return ()

    path_to_index = {str(file_entry["path"]): index for index, file_entry in enumerate(files)}
    groups: list[FeatureGroup] = []
    assigned_indexes: set[int] = set()

    def resolve_paths(raw_paths: Any) -> tuple[int, ...]:
        if not isinstance(raw_paths, list):
            return ()
        result: list[int] = []
        for raw_path in raw_paths:
            if isinstance(raw_path, str) and raw_path in path_to_index:
                index = path_to_index[raw_path]
                if index not in result:
                    result.append(index)
        return tuple(result)

    for raw_group in raw_groups:
        if not isinstance(raw_group, dict):
            continue
        title = str(raw_group.get("title", "")).strip()
        if not title:
            continue

        steps: list[FeatureStep] = []
        step_indexes: list[int] = []
        step_core_indexes: list[int] = []
        raw_steps = raw_group.get("steps")
        if isinstance(raw_steps, list):
            for raw_step in raw_steps:
                if not isinstance(raw_step, dict):
                    continue
                label = str(raw_step.get("label", "")).strip()
                indexes = resolve_paths(raw_step.get("files"))
                if not label or not indexes:
                    continue
                core_indexes = tuple(
                    index for index in resolve_paths(raw_step.get("core_files")) if index in indexes
                )
                steps.append(
                    FeatureStep(
                        label=label,
                        change=str(raw_step.get("change", "")).strip(),
                        file_indexes=indexes,
                        core_file_indexes=core_indexes,
                    )
                )
                step_indexes.extend(index for index in indexes if index not in step_indexes)
                step_core_indexes.extend(
                    index for index in core_indexes if index not in step_core_indexes
                )

        explicit_indexes = resolve_paths(raw_group.get("files"))
        explicit_core_indexes = resolve_paths(raw_group.get("core_files"))
        group_indexes = tuple(
            dict.fromkeys((*step_indexes, *explicit_indexes, *explicit_core_indexes))
        )
        if not group_indexes:
            continue

        core_indexes = tuple(dict.fromkeys((*step_core_indexes, *explicit_core_indexes)))
        if not core_indexes:
            # 老的分组摘要没有核心文件划分时，保留原行为：组内改动都作为核心展示。
            core_indexes = group_indexes

        for step_number, step in enumerate(steps):
            if step.core_file_indexes:
                continue
            inferred_core_indexes = tuple(
                index for index in step.file_indexes if index in core_indexes
            )
            if inferred_core_indexes:
                steps[step_number] = FeatureStep(
                    label=step.label,
                    change=step.change,
                    file_indexes=step.file_indexes,
                    core_file_indexes=inferred_core_indexes,
                )

        displayed_core_indexes = {index for step in steps for index in step.core_file_indexes}
        unplaced_core_indexes = tuple(
            index for index in core_indexes if index not in displayed_core_indexes
        )
        if unplaced_core_indexes:
            steps.append(
                FeatureStep(
                    label="核心实现",
                    change="查看这条功能链路中承担主要行为的实现文件。",
                    file_indexes=unplaced_core_indexes,
                    core_file_indexes=unplaced_core_indexes,
                )
            )

        uncovered_indexes = tuple(index for index in explicit_indexes if index not in step_indexes)
        if uncovered_indexes:
            steps.append(FeatureStep("相关文件", "", uncovered_indexes, ()))
        elif not steps:
            steps.append(FeatureStep("涉及文件", "", group_indexes, core_indexes))

        groups.append(
            FeatureGroup(
                index=len(groups),
                title=title,
                summary=str(raw_group.get("summary", "")).strip(),
                core_change=str(raw_group.get("core_change", "")).strip(),
                diagram=(
                    raw_group.get("diagram") if isinstance(raw_group.get("diagram"), dict) else None
                ),
                steps=tuple(steps),
                file_indexes=group_indexes,
                core_file_indexes=core_indexes,
            )
        )
        assigned_indexes.update(group_indexes)

    unassigned_indexes = tuple(
        index for index in range(len(files)) if index not in assigned_indexes
    )
    if unassigned_indexes:
        groups.append(
            FeatureGroup(
                index=len(groups),
                title="其他改动",
                summary="未被功能链路单独归类的文件仍可从这里逐项查看。",
                core_change="这些文件未归入核心功能链路，可按需展开查看。",
                diagram=None,
                steps=(FeatureStep("相关文件", "", unassigned_indexes, unassigned_indexes),),
                file_indexes=unassigned_indexes,
                core_file_indexes=unassigned_indexes,
            )
        )
    return tuple(groups)


def feature_indexes_for_file(groups: Sequence[FeatureGroup], file_index: int) -> tuple[int, ...]:
    """返回文件所属的所有功能分组序号。"""
    return tuple(group.index for group in groups if file_index in group.file_indexes)


def render_feature_navigation(
    groups: Sequence[FeatureGroup],
    files: Sequence[dict[str, Any]],
    summaries: dict[str, Any],
    count_changes: Callable[[dict[str, Any]], tuple[int, int]],
) -> tuple[str, str]:
    """渲染左侧功能导航与中间的步骤、文件清单。"""
    if not groups:
        return "", ""

    nav_buttons: list[str] = []
    flow_cards: list[str] = []
    for group in groups:
        selected = group.index == 0
        selected_text = "true" if selected else "false"
        hidden = "" if selected else " hidden"
        nav_buttons.append(
            f'<button class="feature-nav-button{" active" if selected else ""}" '
            f'type="button" data-feature-index="{group.index}" '
            f'aria-pressed="{selected_text}">'
            f'<span class="feature-nav-number">{group.index + 1:02}</span>'
            f'<span class="feature-nav-copy"><strong>{html.escape(group.title)}</strong>'
            f'<span>核心 {len(group.core_file_indexes)} / 相关 '
            f'{len(group.file_indexes)} 个文件</span>'
            f'</span></button>'
        )

        step_html: list[str] = []
        for step_index, step in enumerate(group.steps):
            step_number = step_index + 1
            core_file_html: list[str] = []
            for file_index in step.core_file_indexes:
                file_entry = files[file_index]
                path = str(file_entry["path"])
                summary = _summary_for_file(summaries, path)
                core_file_html.append(
                    _render_feature_file_link(
                        file_index,
                        path,
                        summary,
                        count_changes(file_entry),
                    )
                )
            change_html = (
                f'<p class="feature-step-change">{html.escape(step.change)}</p>'
                if step.change
                else ""
            )
            step_html.append(
                f'<article class="feature-step" role="listitem"><div class="feature-step-node">'
                f'<span class="feature-step-number">{step_number:02}</span>'
                f'<div class="feature-step-content"><span class="feature-step-kicker">'
                f'步骤 {step_number}</span><h3>{html.escape(step.label)}</h3>{change_html}'
                f'<div class="feature-step-core-files">{"".join(core_file_html)}</div>'
                f'</div></div></article>'
            )
            if step_index < len(group.steps) - 1:
                step_html.append(
                    '<div class="feature-flow-arrow" aria-hidden="true">'
                    '<svg viewBox="0 0 24 24" focusable="false">'
                    '<path d="M12 2v15m-6-6 6 6 6-6" /></svg></div>'
                )

        summary_html = (
            f'<p class="feature-flow-summary">{html.escape(group.summary)}</p>'
            if group.summary
            else ""
        )
        core_change_html = (
            f'<div class="core-change"><span>核心改动</span>'
            f"<p>{html.escape(group.core_change)}</p></div>"
            if group.core_change
            else ""
        )
        support_indexes = tuple(
            index for index in group.file_indexes if index not in group.core_file_indexes
        )
        support_count = len(support_indexes)
        support_rows: list[str] = []
        for file_index in support_indexes:
            file_entry = files[file_index]
            path = str(file_entry["path"])
            support_rows.append(
                _render_feature_file_link(
                    file_index,
                    path,
                    _summary_for_file(summaries, path),
                    count_changes(file_entry),
                )
            )
        support_html = (
            f'<details class="feature-support"><summary>配套改动 · {support_count} 个文件</summary>'
            f'{"".join(support_rows)}</details>'
            if support_count
            else ""
        )
        core_label = f"只看核心代码（{len(group.core_file_indexes)}）"
        all_label = f"显示全部相关代码（{len(group.file_indexes)}）"
        toggle_html = (
            f'<button class="feature-detail-toggle" type="button" '
            f'data-feature-index="{group.index}" data-core-label="{core_label}" '
            f'data-all-label="{all_label}">{all_label}</button>'
            if support_count
            else ""
        )
        step_count = len(group.steps)
        diagram_html = render_feature_diagram(
            group.diagram,
            tuple(step.core_file_indexes for step in group.steps),
            group.index,
        )
        if diagram_html:
            core_path_html = (
                '<details class="feature-core-paths">'
                f'<summary>展开核心代码阅读路径 · {step_count} 步</summary>'
                f'<div class="feature-core-step-list" role="list">{"".join(step_html)}</div>'
                '</details>'
            )
        else:
            diagram_html = (
                '<figure class="feature-flow-chart" aria-label="核心改动流程图">'
                '<figcaption class="feature-diagram-heading">'
                '<strong>核心改动流程</strong>'
                f'<span>{step_count} 个步骤 · 点击文件直达 diff</span></figcaption>'
                f'<div class="feature-diagram-track" role="list">{"".join(step_html)}</div>'
                '</figure>'
            )
            core_path_html = ""
        flow_cards.append(
            f'<article class="feature-flow-card" data-feature-index="{group.index}"{hidden}>'
            f'<div class="feature-flow-heading"><span>功能链路 {group.index + 1:02}</span>'
            f"<h2>{html.escape(group.title)}</h2>{summary_html}</div>"
            f"{core_change_html}{diagram_html}{core_path_html}"
            f"{support_html}{toggle_html}</article>"
        )

    nav_html = (
        '<nav class="feature-nav surface" aria-label="按功能链路浏览">'
        '<div class="feature-nav-heading"><strong>按功能看改动</strong>'
        f'<span>{len(groups)} 条链路</span></div>{"".join(nav_buttons)}'
        '<button class="feature-nav-button feature-nav-all" type="button" '
        'data-feature-index="all" aria-pressed="false">'
        '<span class="feature-nav-number">≡</span><span class="feature-nav-copy">'
        '<strong>全部改动</strong><span>按文件路径浏览</span></span></button></nav>'
    )
    return nav_html, "".join(flow_cards)


def _render_feature_file_link(
    file_index: int,
    path: str,
    summary: str,
    change_counts: tuple[int, int],
) -> str:
    """渲染步骤图或配套列表中的文件入口。"""
    added, removed = change_counts
    summary_html = (
        f'<span class="feature-file-summary">{html.escape(summary)}</span>' if summary else ""
    )
    return (
        f'<a class="feature-file-row file-row" href="#f{file_index}" '
        f'data-index="{file_index}" title="{html.escape(path, quote=True)}">'
        f'<span class="feature-file-path">{html.escape(path)}</span>'
        f'<span class="feature-file-stats"><i class="add-stat">+{added}</i>'
        f'<i class="del-stat">-{removed}</i></span>{summary_html}</a>'
    )


def _summary_for_file(summaries: dict[str, Any], path: str) -> str:
    """读取文件摘要，并忽略格式不正确的非文本值。"""
    raw_summary = (summaries.get("files", {}).get(path) or {}).get("summary", "")
    return raw_summary if isinstance(raw_summary, str) else ""
