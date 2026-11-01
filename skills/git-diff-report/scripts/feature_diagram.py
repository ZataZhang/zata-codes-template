#!/usr/bin/env python3
"""渲染自包含、可跳转到代码 diff 的功能 SVG 图。"""

from __future__ import annotations

import html
import textwrap
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class DiagramNode:
    """功能图中的模块节点。"""

    node_id: str
    kind: str
    label: str
    detail: str
    column: int
    row: int
    href: str | None


@dataclass(frozen=True)
class DiagramEdge:
    """功能图中的有向连接。"""

    source_id: str
    target_id: str
    label: str


def render_feature_diagram(
    raw_diagram: Any,
    step_core_indexes: Sequence[Sequence[int]],
    feature_index: int,
) -> str:
    """渲染可选的功能图；摘要无效时返回空字符串以使用流程图回退。"""
    if not isinstance(raw_diagram, dict):
        return ""

    raw_nodes = raw_diagram.get("nodes")
    raw_edges = raw_diagram.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        return ""
    if not 2 <= len(raw_nodes) <= 12 or not 1 <= len(raw_edges) <= 20:
        return ""

    nodes: list[DiagramNode] = []
    node_ids: set[str] = set()
    occupied_positions: set[tuple[int, int]] = set()
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            return ""
        node_id = str(raw_node.get("id", "")).strip()
        label = str(raw_node.get("label", "")).strip()
        column = raw_node.get("column")
        row = raw_node.get("row")
        if (
            not node_id
            or node_id in node_ids
            or not label
            or not _is_grid_coordinate(column, 1)
            or not _is_grid_coordinate(row, 5)
            or (column, row) in occupied_positions
        ):
            return ""

        raw_step = raw_node.get("step")
        href = None
        if isinstance(raw_step, int) and not isinstance(raw_step, bool):
            if 1 <= raw_step <= len(step_core_indexes):
                core_indexes = step_core_indexes[raw_step - 1]
                if core_indexes:
                    href = f"#f{core_indexes[0]}"
        nodes.append(
            DiagramNode(
                node_id=node_id,
                kind=_text_field(raw_node.get("kind")),
                label=label,
                detail=_text_field(raw_node.get("detail")),
                column=column,
                row=row,
                href=href,
            )
        )
        node_ids.add(node_id)
        occupied_positions.add((column, row))

    edges: list[DiagramEdge] = []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            return ""
        source_id = str(raw_edge.get("from", "")).strip()
        target_id = str(raw_edge.get("to", "")).strip()
        if source_id not in node_ids or target_id not in node_ids or source_id == target_id:
            return ""
        edges.append(
            DiagramEdge(
                source_id=source_id,
                target_id=target_id,
                label=_text_field(raw_edge.get("label")),
            )
        )

    diagram_title = _text_field(raw_diagram.get("title"))
    if not diagram_title:
        return ""

    node_by_id = {node.node_id: node for node in nodes}
    column_count = max(node.column for node in nodes) + 1
    row_count = max(node.row for node in nodes) + 1
    node_width = 170 if column_count > 1 else 342
    node_height = 98
    column_gap = 32
    row_gap = 42
    padding = 14
    svg_width = padding * 2 + column_count * node_width + (column_count - 1) * column_gap
    svg_height = padding * 2 + row_count * node_height + (row_count - 1) * row_gap
    node_positions = {
        node.node_id: (
            padding + node.column * (node_width + column_gap),
            padding + node.row * (node_height + row_gap),
        )
        for node in nodes
    }
    title_id = f"feature-diagram-title-{feature_index}"
    marker_id = f"feature-diagram-arrow-{feature_index}"
    escaped_diagram_title = html.escape(diagram_title, quote=True)
    diagram_svg = [
        f'<figure class="feature-svg-figure" ' f'aria-label="{escaped_diagram_title}">',
        "<figcaption><strong>功能结构图</strong>"
        "<span>点击模块查看关联核心 diff</span></figcaption>",
        f'<svg class="feature-svg-diagram" viewBox="0 0 {svg_width} {svg_height}" '
        f'role="group" aria-labelledby="{title_id}">',
        f'<title id="{title_id}">{html.escape(diagram_title)}</title>',
        "<defs>",
        f'<marker id="{marker_id}" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto" markerUnits="strokeWidth"><path d="M0 0 L8 4 L0 8 z" /></marker>',
        "</defs>",
        '<g class="feature-svg-edges" aria-hidden="true">',
    ]
    for edge in edges:
        diagram_svg.append(
            _render_edge(edge, node_by_id, node_positions, node_width, node_height, marker_id)
        )
    diagram_svg.append('</g><g class="feature-svg-nodes">')
    for node in nodes:
        node_x, node_y = node_positions[node.node_id]
        node_accessible_name = f"查看 {node.label} 对应的核心代码 diff"
        tag_start = (
            f'<a class="feature-svg-node-link" href="{node.href}" '
            f'aria-label="{html.escape(node_accessible_name, quote=True)}">'
            if node.href
            else '<g class="feature-svg-node">'
        )
        tag_end = "</a>" if node.href else "</g>"
        label_lines = _wrap_lines(node.label, 22 if column_count > 1 else 44, 2)
        detail_lines = _wrap_lines(node.detail, 26 if column_count > 1 else 50, 2)
        diagram_svg.extend(
            [
                tag_start,
                f'<g class="feature-svg-node" transform="translate({node_x} {node_y})">',
                f"<title>{html.escape(node_accessible_name if node.href else node.label)}</title>",
                f'<rect width="{node_width}" height="{node_height}" rx="10" />',
                '<rect class="feature-svg-node-accent" width="4" height="50" rx="2" />',
                f'<text class="feature-svg-kind" x="13" y="20">{html.escape(node.kind)}</text>',
                _render_text_lines("feature-svg-label", label_lines, 13, 44, 15),
                _render_text_lines("feature-svg-detail", detail_lines, 13, 72, 13),
                "</g>",
                tag_end,
            ]
        )
    diagram_svg.append("</g></svg></figure>")
    return "".join(diagram_svg)


def _is_grid_coordinate(value: Any, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= maximum


def _text_field(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _wrap_lines(value: str, width: int, max_lines: int) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        textwrap.wrap(
            value,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            max_lines=max_lines,
            placeholder="…",
        )
    )


def _render_text_lines(
    class_name: str,
    lines: Sequence[str],
    x: int,
    y: int,
    line_height: int,
) -> str:
    if not lines:
        return ""
    tspans = "".join(
        f'<tspan x="{x}" dy="{0 if line_index == 0 else line_height}">'
        f"{html.escape(line)}</tspan>"
        for line_index, line in enumerate(lines)
    )
    return f'<text class="{class_name}" y="{y}">{tspans}</text>'


def _render_edge(
    edge: DiagramEdge,
    node_by_id: dict[str, DiagramNode],
    node_positions: dict[str, tuple[int, int]],
    node_width: int,
    node_height: int,
    marker_id: str,
) -> str:
    source_node = node_by_id[edge.source_id]
    target_node = node_by_id[edge.target_id]
    source_x, source_y = node_positions[edge.source_id]
    target_x, target_y = node_positions[edge.target_id]

    if source_node.row == target_node.row:
        if source_node.column < target_node.column:
            start_x, end_x = source_x + node_width, target_x
        else:
            start_x, end_x = source_x, target_x + node_width
        start_y = source_y + node_height / 2
        end_y = target_y + node_height / 2
        curve_x = abs(end_x - start_x) * 0.45
        path_data = (
            f"M {start_x} {start_y} C {start_x + curve_x} {start_y}, "
            f"{end_x - curve_x} {end_y}, {end_x} {end_y}"
        )
    elif source_node.row < target_node.row:
        start_x = source_x + node_width / 2
        end_x = target_x + node_width / 2
        start_y = source_y + node_height
        end_y = target_y
        curve_y = max(16, (end_y - start_y) * 0.45)
        path_data = (
            f"M {start_x} {start_y} C {start_x} {start_y + curve_y}, "
            f"{end_x} {end_y - curve_y}, {end_x} {end_y}"
        )
    else:
        start_x = source_x + node_width / 2
        end_x = target_x + node_width / 2
        start_y = source_y
        end_y = target_y + node_height
        curve_y = max(16, (start_y - end_y) * 0.45)
        path_data = (
            f"M {start_x} {start_y} C {start_x} {start_y - curve_y}, "
            f"{end_x} {end_y + curve_y}, {end_x} {end_y}"
        )

    edge_html = f'<path class="feature-svg-edge" d="{path_data}" marker-end="url(#{marker_id})" />'
    if not edge.label:
        return edge_html
    label_x = (start_x + end_x) / 2
    label_y = (start_y + end_y) / 2 - 3
    return (
        f'{edge_html}<text class="feature-svg-edge-label" x="{label_x:g}" '
        f'y="{label_y:g}" text-anchor="middle">{html.escape(edge.label)}</text>'
    )
