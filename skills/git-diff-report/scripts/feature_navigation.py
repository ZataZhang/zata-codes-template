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
    """渲染按功能组织的文件树，以及改动总览中的 SVG 图。"""
    if not groups:
        return "", ""

    feature_tree: list[str] = []
    overview_diagrams: list[str] = []
    for group in groups:
        is_initial_group = group.index == 0
        group_tree: dict[str, Any] = {"dirs": {}, "leaves": []}
        for file_index in group.file_indexes:
            file_entry = files[file_index]
            path = str(file_entry["path"])
            path_parts = path.split("/")
            node = group_tree
            for part in path_parts[:-1]:
                node = node["dirs"].setdefault(part, {"dirs": {}, "leaves": []})
            added, removed = count_changes(file_entry)
            file_summary = (summaries.get("files", {}).get(path) or {}).get("summary", "")
            node["leaves"].append(
                {
                    "name": path_parts[-1],
                    "index": file_index,
                    "added": added,
                    "removed": removed,
                    "path": path,
                    "core": file_index in group.core_file_indexes,
                    "summary": file_summary if isinstance(file_summary, str) else "",
                }
            )

        def render_group_tree(node: dict[str, Any], *, open_directories: bool) -> str:
            rows: list[str] = []
            for directory_name, child in sorted(node["dirs"].items()):
                directory_label = directory_name
                while not child["leaves"] and len(child["dirs"]) == 1:
                    next_name, next_node = next(iter(child["dirs"].items()))
                    directory_label = f"{directory_label}/{next_name}"
                    child = next_node
                child_html = render_group_tree(child, open_directories=open_directories)
                child_count = count_tree_files(child)
                opened = " open" if open_directories else ""
                rows.append(
                    f'<details class="node dir"{opened}>'
                    f'<summary class="dir-row"><span class="dir-name">'
                    f"{html.escape(directory_label)}</span>"
                    f'<span class="dir-count">{child_count}</span></summary>'
                    f'<div class="children">{child_html}</div></details>'
                )
            for leaf in sorted(node["leaves"], key=lambda entry: entry["name"]):
                path = leaf["path"]
                search_index = f"{path} {leaf['summary']}"
                core_class = " core-file" if leaf["core"] else ""
                summary_html = (
                    f'<span class="file-summary">{html.escape(leaf["summary"])}</span>'
                    if leaf["summary"]
                    else ""
                )
                moved_from = ""
                file_entry = files[leaf["index"]]
                if file_entry.get("is_rename"):
                    old_path = str(file_entry.get("old_path") or "")
                    moved_from = (
                        f'<span class="file-move-path">← {html.escape(old_path)}</span>'
                        if old_path
                        else ""
                    )
                must_read_badge = (
                    '<span class="role-badge must tree-must">必读</span>'
                    if (summaries.get("files", {}).get(path) or {}).get("must_read") is True
                    else ""
                )
                rows.append(
                    f'<a class="node file-row{core_class}" href="#f{leaf["index"]}" '
                    f'data-index="{leaf["index"]}" data-feature-index="{group.index}" '
                    f'data-search="{html.escape(search_index, quote=True)}" '
                    f'title="{html.escape(path, quote=True)}">'
                    f'<span class="file-name">{html.escape(leaf["name"])}{must_read_badge}</span>'
                    f'<span class="file-hit"><span class="add-stat">+{leaf["added"]}</span>'
                    f'<span class="del-stat">-{leaf["removed"]}</span></span>'
                    f'{summary_html}{moved_from}</a>'
                )
            return "".join(rows)

        def count_tree_files(node: dict[str, Any]) -> int:
            return len(node["leaves"]) + sum(
                count_tree_files(child) for child in node["dirs"].values()
            )

        group_added = sum(count_changes(files[index])[0] for index in group.file_indexes)
        group_removed = sum(count_changes(files[index])[1] for index in group.file_indexes)
        support_count = len(group.file_indexes) - len(group.core_file_indexes)
        opened = " open" if is_initial_group else ""
        feature_tree.append(
            f'<details class="node dir feature-tree-group"{opened} '
            f'data-feature-index="{group.index}" data-feature-title="'
            f'{html.escape(group.title, quote=True)}" data-feature-summary="'
            f'{html.escape(group.summary, quote=True)}" '
            f'data-file-count="{len(group.file_indexes)}" '
            f'data-core-count="{len(group.core_file_indexes)}" '
            f'data-support-count="{support_count}" data-added="{group_added}" '
            f'data-removed="{group_removed}">'
            f'<summary class="feature-group-head"><span class="feature-group-copy">'
            f"<strong>{html.escape(group.title)}</strong>"
            f"<span>核心 {len(group.core_file_indexes)} · 相关 "
            f"{len(group.file_indexes)} 个文件</span>"
            f'</span><span class="group-count">{len(group.file_indexes)}</span></summary>'
            '<div class="children">'
            f"{render_group_tree(group_tree, open_directories=is_initial_group)}"
            "</div></details>"
        )

        diagram_html = render_feature_diagram(
            group.diagram,
            tuple(step.core_file_indexes for step in group.steps),
            group.index,
        )
        if diagram_html:
            overview_diagrams.append(
                f'<section class="ov-feature-diagram" data-feature-index="{group.index}">'
                f"<h3>{html.escape(group.title)}</h3>{diagram_html}</section>"
            )
    return '<div class="feature-tree">' + "".join(feature_tree) + "</div>", "".join(
        overview_diagrams
    )
