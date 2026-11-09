# -*- coding: utf-8 -*-
"""给人看的 HTML 说明页：SVG 图表组件、CSS 设计令牌与页面外壳。

提供分层带（band）、方框（box）、箭头（arrow）、泳道（swimlane）、时间线（timeline）
等内联 SVG 组件、带动画的流程图（flow），以及一套随主题切换的 CSS 设计令牌和页面外壳。生成脚本只负责组织内容，
所有颜色都经由 CSS 类引用令牌，因此浅色与深色主题下的图表都能保持可读。

用法::

    import sys; sys.path.insert(0, "<skill>/scripts")
    from svg_kit import box, band, arrow, label, svg, swimlane, timeline, legend, page
    from svg_kit import FlowNode, flow  # 动态流程图

    body = svg(1200, 400, box(20, 20, 200, 80, "标题", ["说明"], "agent"), "示例图")
    html = page(title="示例", eyebrow="Demo", h1="示例页面", thesis="一句话定位", sections=[...])

命令行::

    python svg_kit.py --demo /tmp/readable-demo.html   # 生成示例页
"""

# 内联 CSS 与 SVG 片段是整行数据，按行宽拆分会降低可读性。
# ruff: noqa: E501
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# 方框种类 → 语义。颜色按"数据或职责的形态"编码，而不是按装饰需要随意取色。
KINDS: dict[str, str] = {
    "plain": "中性：人、通用组件、存储",
    "ghost": "虚线：占位、暂不参与、未来扩展",
    "start": "强调：当前起点或焦点（每张图最多一处）",
    "agent": "Agent、运行时、AI 产出",
    "files": "工作态资料、草稿",
    "fileslite": "工作态的附属动作（虚线描边）",
    "kn": "发布态知识、正式资产",
    "knstrong": "被写入的正式资产（粗描边，强调沉淀点）",
    "biz": "外部业务系统、实时事实",
    "gate": "深色：权限、闸门、关键决策点（文字自动反白）",
    "gatebox": "放在 gateband 里的子框（文字自动反白）",
    "gatelite": "浅色闸门：确认、审核类步骤",
}

_INVERTED_KINDS: frozenset[str] = frozenset({"gate", "gatebox"})


def esc(raw_text: str) -> str:
    """转义 SVG 文本中的特殊字符。

    Args:
        raw_text (str): 原始文本。

    Returns:
        str: 可安全放入 SVG 的文本。
    """
    return raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subs: Sequence[str] = (),
    kind: str = "plain",
) -> str:
    """绘制带标题与说明行的圆角方框，文字整体垂直居中。

    Args:
        x (float): 左上角横坐标。
        y (float): 左上角纵坐标。
        w (float): 宽度。中文 13.5px 标题约 14px/字，留足左右边距。
        h (float): 高度。标题行 18px，每条说明行 16px。
        title (str): 标题。
        subs (Sequence[str]): 说明行，每行一条，不自动换行。
        kind (str): 方框种类，见 ``KINDS``。

    Returns:
        str: SVG 片段。
    """
    total_height = 18 + 16 * len(subs)
    title_y = y + h / 2 - total_height / 2 + 13
    inv = " inv" if kind in _INVERTED_KINDS else ""
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="f-{kind}"/>']
    parts.append(
        f'<text x="{x + w / 2}" y="{title_y}" class="t-l{inv}" text-anchor="middle">{esc(title)}</text>'
    )
    for index, sub_text in enumerate(subs):
        parts.append(
            f'<text x="{x + w / 2}" y="{title_y + 19 + index * 16}" class="t-s{inv}" '
            f'text-anchor="middle">{esc(sub_text)}</text>'
        )
    return "".join(parts)


def band(
    x: float, y: float, w: float, h: float, title: str, subs: Sequence[str] = (), kind: str = "band"
) -> str:
    """绘制分层架构中的一层：左侧写层名与说明，右侧留给子框。

    子框建议从 ``x + 180`` 开始，给层名留出约 160px。

    Args:
        x (float): 左上角横坐标。
        y (float): 左上角纵坐标。
        w (float): 宽度。
        h (float): 高度。
        title (str): 层名。
        subs (Sequence[str]): 层说明，每行约 10 个中文字以内。
        kind (str): ``band``（中性）、``agentband``（Agent 层）或 ``gateband``（深色关键层）。

    Returns:
        str: SVG 片段。
    """
    inv = " inv" if kind == "gateband" else ""
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" class="f-{kind}"/>']
    parts.append(f'<text x="{x + 20}" y="{y + 32}" class="t-h{inv}">{esc(title)}</text>')
    for index, sub_text in enumerate(subs):
        parts.append(
            f'<text x="{x + 20}" y="{y + 54 + index * 16}" class="t-s{inv}">{esc(sub_text)}</text>'
        )
    return "".join(parts)


def arrow(path_d: str, accent: bool = True, dash: bool = False) -> str:
    """绘制带箭头的连线。

    Args:
        path_d (str): SVG path 的 ``d``，例如 ``"M100 50H200"`` 或三次曲线。
        accent (bool): 主流程用强调色；次要关系用中性色。
        dash (bool): 虚线表示引用、回流或可选关系。

    Returns:
        str: SVG 片段。
    """
    css_class = "ar" + (" ar-acc" if accent else "") + (" ar-dash" if dash else "")
    marker_id = "mk-acc" if accent else "mk"
    return f'<path d="{path_d}" class="{css_class}" marker-end="url(#{marker_id})"/>'


def fan(x1: float, y1: float, x2: float, ys: Sequence[float], accent: bool = True) -> str:
    """从一点向多个目标纵坐标扇出曲线箭头（一对多）。

    Args:
        x1 (float): 起点横坐标。
        y1 (float): 起点纵坐标。
        x2 (float): 终点横坐标（各目标左边缘）。
        ys (Sequence[float]): 各目标的纵坐标。
        accent (bool): 是否使用强调色。

    Returns:
        str: SVG 片段。
    """
    mid_x = (x1 + x2) / 2
    return "".join(
        arrow(f"M{x1} {y1}C{mid_x} {y1} {mid_x} {target_y} {x2 - 3} {target_y}", accent)
        for target_y in ys
    )


def merge(x1: float, ys: Sequence[float], x2: float, y2: float, accent: bool = True) -> str:
    """从多个来源汇聚到一点的曲线箭头（多对一）。

    Args:
        x1 (float): 各来源右边缘横坐标。
        ys (Sequence[float]): 各来源纵坐标。
        x2 (float): 终点横坐标。
        y2 (float): 终点纵坐标。
        accent (bool): 是否使用强调色。

    Returns:
        str: SVG 片段。
    """
    mid_x = (x1 + x2) / 2
    return "".join(
        arrow(f"M{x1} {source_y}C{mid_x} {source_y} {mid_x} {y2} {x2 - 3} {y2}", accent)
        for source_y in ys
    )


def label(x: float, y: float, text: str, anchor: str = "middle", css_class: str = "t-s") -> str:
    """在连线旁放一段说明文字。

    Args:
        x (float): 横坐标。
        y (float): 基线纵坐标。
        text (str): 文字。
        anchor (str): ``start`` / ``middle`` / ``end``。
        css_class (str): ``t-s``（说明）、``t-l``（标签）或 ``t-h``（大号，如 ∩ 符号）。

    Returns:
        str: SVG 片段。
    """
    return f'<text x="{x}" y="{y}" class="{css_class}" text-anchor="{anchor}">{esc(text)}</text>'


DEFS: str = (
    '<defs><marker id="mk" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
    '<path d="M0 0L9 4.5L0 9z" class="mk"/></marker>'
    '<marker id="mk-acc" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
    '<path d="M0 0L9 4.5L0 9z" class="mk-acc"/></marker></defs>'
)


def svg(width: int, height: int, body: str, aria_label: str) -> str:
    """把 SVG 片段包成完整图，宽图在窄屏下横向滚动而不挤压文字。

    Args:
        width (int): viewBox 宽度，常用 1200；泳道图常用 1300。
        height (int): viewBox 高度。
        body (str): 由组件函数拼出的片段。
        aria_label (str): 图的无障碍名称。

    Returns:
        str: ``<svg>`` 元素。
    """
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}" '
        f'style="min-width:{min(width, 1040)}px">{DEFS}{body}</svg>'
    )


@dataclass(frozen=True)
class Lane:
    """泳道图中的一条泳道。

    Attributes:
        name (str): 泳道名，例如角色、系统或数据层。
        sub (str): 泳道说明。
        kind (str): 该泳道单元格的默认方框种类。
        cells (Sequence[tuple[str, Sequence[str]]]): 每个阶段一格：``(标题, 说明行)``；
            标题写 ``"—"`` 表示该阶段不参与，渲染为虚线占位。
        flow (bool): 是否在相邻单元格之间画横向主流程箭头（通常只给主角泳道）。
        highlight (Sequence[int]): 需要强调的阶段下标，使用该种类的强调样式（如 ``knstrong``）。
    """

    name: str
    sub: str
    kind: str
    cells: Sequence[tuple[str, Sequence[str]]]
    flow: bool = False
    highlight: Sequence[int] = field(default_factory=tuple)


def swimlane(stages: Sequence[str], lanes: Sequence[Lane], footnote: str = "") -> str:
    """绘制"阶段 × 角色/数据层"泳道图：横向看流程，纵向看每个阶段谁在做什么、数据落在哪里。

    Args:
        stages (Sequence[str]): 阶段名，建议 4-6 个，带序号（如 ``"① 接收"``）。
        lanes (Sequence[Lane]): 泳道，建议把人放上面、Agent 居中、数据与外部系统放下面。
        footnote (str): 图底部的阅读提示。

    Returns:
        str: 完整 ``<svg>`` 元素。
    """
    left, column_step, cell_width, top, lane_height = 168, 188, 176, 60, 100
    width = left + column_step * len(stages) + 12
    parts: list[str] = []
    for index, stage_name in enumerate(stages):
        stage_x = left + index * column_step
        parts.append(
            f'<rect x="{stage_x}" y="10" width="{cell_width}" height="38" rx="8" class="f-stage"/>'
        )
        parts.append(
            f'<text x="{stage_x + cell_width / 2}" y="35" class="t-l inv" text-anchor="middle">{esc(stage_name)}</text>'
        )
    for lane_index, lane in enumerate(lanes):
        lane_y = top + lane_index * lane_height
        parts.append(
            f'<rect x="6" y="{lane_y}" width="{width - 12}" height="{lane_height - 6}" rx="10" class="f-lane{lane_index % 2}"/>'
        )
        parts.append(f'<text x="20" y="{lane_y + 40}" class="t-l">{esc(lane.name)}</text>')
        parts.append(f'<text x="20" y="{lane_y + 60}" class="t-s">{esc(lane.sub)}</text>')
        for cell_index, (cell_title, cell_subs) in enumerate(lane.cells):
            cell_kind = lane.kind
            if cell_index in lane.highlight:
                cell_kind = {"kn": "knstrong", "agent": "start"}.get(lane.kind, lane.kind)
            if cell_title == "—":
                cell_kind = "ghost"
            parts.append(
                box(
                    left + cell_index * column_step,
                    lane_y + 12,
                    cell_width,
                    70,
                    cell_title,
                    cell_subs,
                    cell_kind,
                )
            )
            if lane.flow and cell_index < len(lane.cells) - 1:
                start_x = left + cell_index * column_step + cell_width
                parts.append(
                    arrow(f"M{start_x} {lane_y + 47}H{left + (cell_index + 1) * column_step - 2}")
                )
    height = top + len(lanes) * lane_height + (36 if footnote else 10)
    if footnote:
        parts.append(label(width / 2, top + len(lanes) * lane_height + 22, footnote))
    return svg(width, height, "".join(parts), "泳道图")


def timeline(
    items: Sequence[tuple[str, str, Sequence[str], str]], aria_label: str = "时间线"
) -> str:
    """绘制横向时间线：用于复盘的事件经过、汇报的里程碑、路线图的阶段。

    Args:
        items (Sequence[tuple[str, str, Sequence[str], str]]): 每项 ``(时间, 标题, 说明行, 种类)``；
            种类同 ``box``，异常节点可用 ``biz``，当前节点用 ``start``。建议 3-7 项。
        aria_label (str): 图的无障碍名称。

    Returns:
        str: 完整 ``<svg>`` 元素。
    """
    step, card_width, left = 190, 172, 20
    width = max(left * 2 + step * len(items) - (step - card_width), 600)
    axis_y = 56
    parts: list[str] = [f'<path d="M{left} {axis_y}H{width - left}" class="ar"/>']
    for index, (when, item_title, item_subs, item_kind) in enumerate(items):
        card_x = left + index * step
        center_x = card_x + card_width / 2
        parts.append(
            f'<circle cx="{center_x}" cy="{axis_y}" r="6" class="f-{item_kind if item_kind != "plain" else "start"}"/>'
        )
        parts.append(label(center_x, axis_y - 18, when, css_class="t-l"))
        parts.append(arrow(f"M{center_x} {axis_y + 7}V{axis_y + 26}", accent=False))
        parts.append(box(card_x, axis_y + 30, card_width, 78, item_title, item_subs, item_kind))
    return svg(width, axis_y + 122, "".join(parts), aria_label)


@dataclass(frozen=True)
class FlowNode:
    """动态流程图中的一个节点。

    Attributes:
        id (str): 节点标识，只用 ASCII 字母、数字、下划线，在同一张图内唯一。
        col (int): 所在列（从 0 开始）。
        row (int): 所在行（从 0 开始）。
        title (str): 标题。列宽约 148px 时不超过 10 个中文字。
        sub (str): 说明行，不超过 14 个中文字。
        status (str): ``ok``（已具备）、``part``（部分）、``plan``（规划中，琥珀色虚线并缓慢闪烁）
            或 ``gate``（闸门、身份等关键节点，深色底）。
        rowspan (int): 纵向跨几行，用于「身份与授权」这类被多条链路共用的节点。
    """

    id: str
    col: int
    row: int
    title: str
    sub: str = ""
    status: str = "ok"
    rowspan: int = 1


def flow(
    columns: Sequence[str],
    nodes: Sequence[FlowNode],
    edges: Sequence[tuple],
    scenarios: dict[str, tuple[str, str, Sequence[tuple[str, str]]]],
    *,
    uid: str = "fx",
    bus: tuple[str, str] | None = None,
    footer: str = "",
    done_text: str = "",
    aria_label: str = "动态流程图",
) -> str:
    """绘制带动画的流程图：一个光点沿连线移动，经过的节点依次点亮，下方字幕逐步说明。

    适合在架构页里放在静态分层图之后，用 2-5 个真实场景演示「一次请求怎么流过系统」。
    图是深色控制台风格，浅色和深色主题下保持同一外观；``prefers-reduced-motion`` 时不播放动画，
    直接点亮整条路径。返回完整 HTML 片段（场景按钮 + SVG + 字幕 + 图例 + 脚本），一页可以放多张，
    用不同的 ``uid`` 区分。

    Args:
        columns (Sequence[str]): 列标题，从左到右，例如「入口、身份、运行时、能力、上下文、闸门、产出」。建议 4-7 列。
        nodes (Sequence[FlowNode]): 节点。
        edges (Sequence[tuple]): 连线 ``(起点 id, 终点 id)`` 或 ``(起点 id, 终点 id, 选项)``；
            选项为 dict，可含 ``plan=True``（琥珀色，表示规划中的链路）和 ``label="A2A"``（连线旁短标签）。
            同一行相邻节点画直线，同一列画竖线，其他画曲线；连到跨行节点时取对端的纵坐标。
        scenarios (dict): ``{key: (按钮标题, 按钮小字, [(节点 id, 这一步的说明), ...])}``。
            相邻两步之间必须有连线，否则抛出 ``ValueError``。
        uid (str): 元素 id 前缀，一页多张图时各不相同。
        bus (tuple[str, str] | None): 底部总线 ``(标题, 说明)``，例如「全链路 Trace」；最后一行各节点用虚线接入。
            每个场景播完总线会亮一下。
        footer (str): 总线下方的虚线说明框，例如基础设施。
        done_text (str): 每个场景播完后字幕显示的话。
        aria_label (str): 图的无障碍名称。

    Returns:
        str: HTML 片段。
    """
    import json

    gap, top, step, node_h = 22, 56, 90, 64
    node_w = (1200 - 32 - gap * (len(columns) - 1)) / len(columns)
    by_id = {node.id: node for node in nodes}
    rows = max(node.row + node.rowspan for node in nodes)

    def rect(node: FlowNode) -> tuple[float, float, float, float]:
        height = node_h + (node.rowspan - 1) * step
        return 16 + node.col * (node_w + gap), top + node.row * step, node_w, height

    def edge_path(a: str, b: str) -> str:
        ax, ay, aw, ah = rect(by_id[a])
        bx, by_, bw, bh = rect(by_id[b])
        if abs(ax - bx) < 1:
            x = ax + aw / 2
            return f"M{x} {ay + ah}V{by_ - 4}" if by_ > ay else f"M{x} {ay}V{by_ + bh + 4}"
        y1, y2 = ay + ah / 2, by_ + bh / 2
        if by_id[a].rowspan > 1:
            y1 = min(max(y2, ay + 20), ay + ah - 20)
        if by_id[b].rowspan > 1:
            y2 = min(max(y1, by_ + 20), by_ + bh - 20)
        x1, x2 = (ax + aw, bx - 4) if bx > ax else (ax, bx + bw + 4)
        if abs(y1 - y2) < 1:
            return f"M{x1} {y1}H{x2}"
        mid = (x1 + x2) / 2
        return f"M{x1} {y1}C{mid} {y1} {mid} {y2} {x2} {y2}"

    edge_keys: set[tuple[str, str]] = set()
    edge_parts: list[str] = []
    for spec in edges:
        a, b = spec[0], spec[1]
        opts = spec[2] if len(spec) > 2 else {}
        if a not in by_id or b not in by_id:
            raise ValueError(f"连线引用了不存在的节点：{a} → {b}")
        edge_keys.add((a, b))
        path_d = edge_path(a, b)
        css_class = "fx-e" + (" fx-plan-e" if opts.get("plan") else "")
        edge_parts.append(
            f'<path id="{uid}-e-{a}-{b}" d="{path_d}" class="{css_class}" marker-end="url(#{uid}-mk)"/>'
        )
        if opts.get("label"):
            ax, ay, aw, ah = rect(by_id[a])
            bx, by_, _bw, _bh = rect(by_id[b])
            edge_parts.append(
                f'<text x="{(ax + aw / 2 + bx + _bw / 2) / 2 + 8}" y="{(ay + ah + by_) / 2 + 4}" class="fx-tag">{esc(opts["label"])}</text>'
                if abs(ax - bx) < 1
                else f'<text x="{(ax + aw + bx) / 2 + 6}" y="{(ay + ah / 2 + by_ + _bh / 2) / 2 + 4}" class="fx-tag">{esc(opts["label"])}</text>'
            )
    for key, (_title, _sub, steps) in scenarios.items():
        for (a, _), (b, _) in zip(steps, steps[1:]):
            if (a, b) not in edge_keys:
                raise ValueError(f"场景 {key} 的第 {a} → {b} 步没有对应连线")

    height = top + rows * step - (step - node_h) + 24
    parts = [
        f'<defs><filter id="{uid}-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<pattern id="{uid}-dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" class="fx-dotgrid"/></pattern>'
        f'<marker id="{uid}-mk" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8z" class="fx-mk"/></marker></defs>'
    ]
    body_height_placeholder = len(parts)
    parts.append("")
    for index, name in enumerate(columns):
        parts.append(
            f'<text x="{16 + index * (node_w + gap) + node_w / 2}" y="36" class="fx-head" text-anchor="middle">{esc(name)}</text>'
        )
    parts.extend(edge_parts)
    if bus:
        last_row = {node.col: node for node in nodes if node.row + node.rowspan == rows}
        for node in last_row.values():
            x, y, w, h = rect(node)
            parts.append(f'<path d="M{x + w / 2} {y + h}V{height + 2}" class="fx-tap"/>')
    for node in nodes:
        x, y, w, h = rect(node)
        parts.append(
            f'<g id="{uid}-n-{node.id}" class="fx-n fx-{node.status}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="fx-r"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 - 4}" class="fx-t" text-anchor="middle">{esc(node.title)}</text>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 15}" class="fx-s" text-anchor="middle">{esc(node.sub)}</text></g>'
        )
    if bus:
        parts.append(
            f'<g id="{uid}-n-bus" class="fx-n fx-part"><rect x="16" y="{height + 4}" width="1168" height="46" rx="10" class="fx-r"/>'
            f'<text x="600" y="{height + 24}" class="fx-t" text-anchor="middle">{esc(bus[0])}</text>'
            f'<text x="600" y="{height + 41}" class="fx-s" text-anchor="middle">{esc(bus[1])}</text></g>'
        )
        height += 58
    if footer:
        parts.append(
            f'<rect x="16" y="{height + 4}" width="1168" height="36" rx="10" class="fx-infra"/>'
            f'<text x="600" y="{height + 27}" class="fx-s" text-anchor="middle">{esc(footer)}</text>'
        )
        height += 48
    height += 12
    parts[body_height_placeholder] = (
        f'<rect width="1200" height="{height}" rx="16" class="fx-bg"/><rect width="1200" height="{height}" rx="16" fill="url(#{uid}-dots)"/>'
    )
    parts.append(
        f'<circle id="{uid}-dot" r="5.5" class="fx-particle" filter="url(#{uid}-glow)" cx="-20" cy="-20"/>'
    )
    svg_html = (
        f'<svg id="{uid}-svg" viewBox="0 0 1200 {height}" role="img" aria-label="{esc(aria_label)}" '
        f'style="min-width:1040px;display:block">' + "".join(parts) + "</svg>"
    )
    data = json.dumps(
        {
            "done": done_text,
            "bus": bool(bus),
            "s": {
                k: {"title": t, "sys": s, "steps": list(st)} for k, (t, s, st) in scenarios.items()
            },
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return (
        f'<div class="fx-ctl" role="group" aria-label="选择场景" id="{uid}-ctl"></div>'
        f'<div class="fx-box">{svg_html}</div>'
        f'<div class="fx-cap" aria-live="polite"><b id="{uid}-step">准备</b><span id="{uid}-text">选择一个场景，或等待自动轮播。</span></div>'
        '<div class="fx-key"><span><i class="fx-k-ok"></i>已具备</span><span><i class="fx-k-part"></i>部分</span>'
        '<span><i class="fx-k-plan"></i>规划中</span><span><i class="fx-k-on"></i>本次经过</span></div>'
        f"<script>(function(D,U){{{_FLOW_JS}}})({data},{json.dumps(uid)});</script>"
    )


_FLOW_JS: str = r"""
const svg=document.getElementById(U+"-svg"),dot=document.getElementById(U+"-dot");
const stepEl=document.getElementById(U+"-step"),textEl=document.getElementById(U+"-text"),ctl=document.getElementById(U+"-ctl");
const reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const keys=Object.keys(D.s);let mode=keys.length>1?"auto":keys[0],run=0;
function btn(k,label,sub){const b=document.createElement("button");b.type="button";b.className="fx-btn";
  b.textContent=label;if(sub){const s=document.createElement("small");s.textContent=sub;b.appendChild(s);}
  b.setAttribute("aria-pressed",k===mode);
  b.addEventListener("click",function(){mode=k;ctl.querySelectorAll(".fx-btn").forEach(function(x){x.setAttribute("aria-pressed",x===b);});start();});ctl.appendChild(b);}
if(keys.length>1)btn("auto","自动轮播","");keys.forEach(function(k){btn(k,D.s[k].title,D.s[k].sys);});
function clear(){svg.querySelectorAll(".on").forEach(function(e){e.classList.remove("on");});dot.setAttribute("cx",-20);dot.setAttribute("cy",-20);}
function node(id){return document.getElementById(U+"-n-"+id);}
function edge(a,b){return document.getElementById(U+"-e-"+a+"-"+b);}
function wait(ms,id){return new Promise(function(res,rej){setTimeout(function(){id===run?res():rej();},ms);});}
function travel(path,id){return new Promise(function(res,rej){const L=path.getTotalLength(),t0=performance.now(),dur=Math.max(450,L*2.4);
  function f(t){if(id!==run)return rej();const k=Math.min(1,(t-t0)/dur),e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2,pt=path.getPointAtLength(e*L);
    dot.setAttribute("cx",pt.x);dot.setAttribute("cy",pt.y);k<1?requestAnimationFrame(f):res();}requestAnimationFrame(f);});}
async function play(k,id){const S=D.s[k],s=S.steps;clear();
  if(reduce){s.forEach(function(st,i){node(st[0]).classList.add("on");if(i)edge(s[i-1][0],st[0]).classList.add("on");});
    if(D.bus)node("bus").classList.add("on");stepEl.textContent=S.title;textEl.textContent=s.map(function(x){return x[1];}).join(" → ");return;}
  for(let i=0;i<s.length;i++){
    if(i){const e=edge(s[i-1][0],s[i][0]);e.classList.add("on");await travel(e,id);}
    node(s[i][0]).classList.add("on");stepEl.textContent=S.title+" "+(i+1)+"/"+s.length;textEl.textContent=s[i][1];await wait(1500,id);}
  if(D.bus)node("bus").classList.add("on");
  if(D.done){stepEl.textContent=S.title+" 完成";textEl.textContent=D.done;}
  await wait(2600,id);}
async function start(){const id=++run;
  try{if(mode==="auto"){let i=0;while(true){await play(keys[i%keys.length],id);if(reduce)return;i++;}}
      else{while(true){await play(mode,id);if(reduce)return;}}}catch(e){}}
start();
"""


LEGEND_ITEMS: dict[str, str] = {
    "agent": "Agent 与运行时",
    "files": "工作态资料",
    "kn": "发布态资产",
    "biz": "外部业务系统",
    "gate": "权限与闸门",
}


def legend(items: dict[str, str] | None = None) -> str:
    """生成图下方的颜色图例。图例只解释颜色，不放内部进度标记。

    Args:
        items (dict[str, str] | None): ``{种类: 含义}``；为空时使用 ``LEGEND_ITEMS``。

    Returns:
        str: HTML 片段。
    """
    legend_items = items or LEGEND_ITEMS
    spans = "".join(
        f'<span><i class="lg-{kind}"></i>{esc(text)}</span>' for kind, text in legend_items.items()
    )
    return f'<div class="legend">{spans}</div>'


CSS: str = r"""
:root{
  /* 布局：长文档单栏，图表区放宽；颜色按数据形态编码：Agent 蓝、工作态青绿、发布态紫、外部系统橙、闸门深蓝 */
  --bg:#f3f5f8;--surface:#ffffff;--fg:#15253a;--muted:#5b6c81;--line:#d3dce7;--soft:#e9eef4;
  --accent:#1d5fc2;--agent:#2a63c9;--agent-bg:#e8f0fc;
  --files:#14806a;--files-bg:#e3f3ee;--kn:#5b47b6;--kn-bg:#eeebfa;--biz:#b5610e;--biz-bg:#fcefe0;
  --gate:#1b3152;--gate-fg:#f2f6fb;--gate-sub:#b9c9de;
  --ok:#1b7d55;--ok-bg:#dcf2e7;--warn:#a35a00;--warn-bg:#fdebd2;--info:#5a5fb0;--info-bg:#e6e7f8;
  --body:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0e1622;--surface:#152030;--fg:#e3eaf3;--muted:#95a6ba;--line:#2a394d;--soft:#1b2838;
  --accent:#78a8f2;--agent:#7eaaf0;--agent-bg:#1a2b45;
  --files:#55c7a8;--files-bg:#12302a;--kn:#ab9bf2;--kn-bg:#251f40;--biz:#eba35a;--biz-bg:#37260f;
  --gate:#2b4670;--gate-fg:#f2f6fb;--gate-sub:#c3d2e6;
  --ok:#6fd3a4;--ok-bg:#163a2b;--warn:#f2b462;--warn-bg:#3c2a10;--info:#a7abf0;--info-bg:#25284a;color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0e1622;--surface:#152030;--fg:#e3eaf3;--muted:#95a6ba;--line:#2a394d;--soft:#1b2838;
  --accent:#78a8f2;--agent:#7eaaf0;--agent-bg:#1a2b45;
  --files:#55c7a8;--files-bg:#12302a;--kn:#ab9bf2;--kn-bg:#251f40;--biz:#eba35a;--biz-bg:#37260f;
  --gate:#2b4670;--gate-fg:#f2f6fb;--gate-sub:#c3d2e6;
  --ok:#6fd3a4;--ok-bg:#163a2b;--warn:#f2b462;--warn-bg:#3c2a10;--info:#a7abf0;--info-bg:#25284a;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 var(--body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.wrap{max-width:1240px;margin:0 auto;padding-block:28px 60px}
header.hero{padding-block:28px 8px}
.eyebrow{font:600 12px/1 var(--mono);letter-spacing:.12em;color:var(--accent);text-transform:uppercase}
h1{font:700 clamp(26px,3.6vw,38px)/1.3 var(--body);margin:12px 0 10px;text-wrap:balance}
.thesis{font-size:17px;color:var(--muted);max-width:62em;margin:0}
.thesis b{color:var(--fg)}
nav.toc{display:flex;flex-wrap:wrap;gap:6px 8px;margin:22px 0 6px}
nav.toc a{font-size:13px;color:var(--fg);text-decoration:none;padding:5px 11px;border:1px solid var(--line);border-radius:999px;background:var(--surface)}
nav.toc a:hover,nav.toc a:focus-visible{border-color:var(--accent);color:var(--accent);outline:none}
.part{font:600 12px/1 var(--mono);letter-spacing:.14em;color:var(--muted);margin:46px 0 4px;display:flex;align-items:center;gap:12px}
.part::after{content:"";flex:1;height:1px;background:var(--line)}
section{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:28px clamp(18px,3vw,34px);margin-top:18px}
h2{font:700 22px/1.4 var(--body);margin:0 0 6px;text-wrap:balance}
h3{font:700 16px/1.5 var(--body);margin:24px 0 8px}
p{margin:8px 0;max-width:68em}
.lead{color:var(--muted);margin-top:0}
.fig{overflow-x:auto;margin:18px -6px 6px;padding:4px 6px}
.fig svg{display:block;width:100%;height:auto}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:12.5px;color:var(--muted);margin:10px 0 4px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px;border:1px solid}
.lg-agent{background:var(--agent-bg);border-color:var(--agent)!important}.lg-files{background:var(--files-bg);border-color:var(--files)!important}
.lg-kn{background:var(--kn-bg);border-color:var(--kn)!important}.lg-biz{background:var(--biz-bg);border-color:var(--biz)!important}
.lg-gate{background:var(--gate);border-color:var(--gate)!important}
.chip{display:inline-block;font:600 11px/1.6 var(--body);padding:0 8px;border-radius:999px;white-space:nowrap}
.c-ok{color:var(--ok);background:var(--ok-bg)}.c-warn{color:var(--warn);background:var(--warn-bg)}.c-info{color:var(--info);background:var(--info-bg)}
.principles{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:16px}
.principles div{background:var(--soft);border-radius:12px;padding:16px 18px;min-width:0}
.principles b{display:block;font:700 15px/1.5 var(--body);margin-bottom:4px}
.principles p{margin:0;font-size:14px;color:var(--muted)}
.tbl{overflow-x:auto;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13.5px;line-height:1.65}
th{text-align:left;font-weight:700;color:var(--muted);font-size:12.5px;border-bottom:1.5px solid var(--line);padding:9px 12px;white-space:nowrap}
td{border-bottom:1px solid var(--line);padding:10px 12px;vertical-align:top}
td:first-child{font-weight:650;white-space:nowrap}
tr:last-child td{border-bottom:0}
.two{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:22px;align-items:start;margin-top:14px}
.card{border:1px solid var(--kn);border-radius:14px;background:var(--kn-bg);padding:18px 20px;font-size:13.5px}
.card dl{display:grid;grid-template-columns:88px minmax(0,1fr);gap:6px 12px;margin:0}
.card dt{color:var(--muted)}.card dd{margin:0}
code,.mono{font:12.5px/1.6 var(--mono);background:var(--soft);padding:1px 5px;border-radius:4px;overflow-wrap:anywhere}
ol.steps{padding-left:20px;margin:10px 0}ol.steps li{margin:6px 0}
.note{font-size:13px;color:var(--muted);border-left:3px solid var(--accent);padding:4px 0 4px 14px;margin:16px 0}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:12px}
.metrics div{border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:13.5px}
.metrics b{display:block;font-size:14px}
.options{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:14px}
.opt{border:1px solid var(--line);border-radius:14px;padding:18px 20px;background:var(--surface);min-width:0}
.opt.rec{border:2px solid var(--accent);background:var(--agent-bg)}
.opt h3{margin:4px 0 8px}.opt ul{margin:8px 0 0;padding-left:18px;font-size:14px}
.verdict{border-radius:14px;background:var(--gate);color:var(--gate-fg);padding:18px 22px;margin:16px 0}
.verdict b{display:block;font-size:17px;margin-bottom:4px}.verdict p{margin:0;color:var(--gate-sub)}
footer{color:var(--muted);font-size:12.5px;margin-top:30px;line-height:1.8}
@media (max-width:820px){.two{grid-template-columns:1fr}}
svg text{font-family:var(--body)}
.t-h{font-size:16px;font-weight:700;fill:var(--fg)}
.t-l{font-size:13.5px;font-weight:650;fill:var(--fg)}
.t-s{font-size:11.5px;fill:var(--muted)}
.inv.t-l,.inv.t-h{fill:var(--gate-fg)}.inv.t-s{fill:var(--gate-sub)}
.f-plain{fill:var(--surface);stroke:var(--line)}
.f-ghost{fill:var(--soft);stroke:var(--line);stroke-dasharray:4 4}
.f-start{fill:var(--agent-bg);stroke:var(--accent);stroke-width:2}
.f-agent{fill:var(--agent-bg);stroke:var(--agent);stroke-opacity:.55}
.f-files{fill:var(--files-bg);stroke:var(--files);stroke-opacity:.6}
.f-fileslite{fill:var(--surface);stroke:var(--files);stroke-dasharray:4 4}
.f-kn{fill:var(--kn-bg);stroke:var(--kn);stroke-opacity:.6}
.f-knstrong{fill:var(--kn-bg);stroke:var(--kn);stroke-width:2.2}
.f-biz{fill:var(--biz-bg);stroke:var(--biz);stroke-opacity:.6}
.f-gate{fill:var(--gate);stroke:var(--gate)}
.f-gatebox{fill:var(--surface);stroke:var(--surface);fill-opacity:.1;stroke-opacity:.35}
.f-gatelite{fill:var(--surface);stroke:var(--gate);stroke-width:1.6}
.f-band{fill:var(--soft);stroke:var(--line);stroke-opacity:.7}
.f-agentband{fill:var(--agent-bg);fill-opacity:.55;stroke:var(--agent);stroke-opacity:.3}
.f-gateband{fill:var(--gate);stroke:var(--gate)}
.f-stage{fill:var(--gate)}
.f-lane0{fill:var(--soft);fill-opacity:.7}.f-lane1{fill:var(--soft);fill-opacity:.3}
.ar{fill:none;stroke:var(--muted);stroke-width:1.6;stroke-opacity:.7}
.ar-acc{stroke:var(--accent);stroke-opacity:.9}
.ar-dash{stroke-dasharray:5 4}
.mk{fill:var(--muted)}.mk-acc{fill:var(--accent)}
/* 动态流程图（flow）：深色控制台外观，浅色与深色主题下保持一致，令牌只在这里定义一次 */
:root{--fx-bg:#0a1222;--fx-dotc:#1b2a47;--fx-node:#101c33;--fx-line:#2a3f68;--fx-text:#e4ecfb;--fx-sub:#8ea2c8;
--fx-flow:#3d8bff;--fx-hot:#56dcff;--fx-plan:#f0a33a;--fx-part:#a493ff;--fx-gate:#16284a}
.fx-box{border-radius:16px;overflow-x:auto;background:var(--fx-bg)}
.fx-bg{fill:var(--fx-bg)}.fx-dotgrid{fill:var(--fx-dotc)}
.fx-head{font:600 11px/1 var(--mono);letter-spacing:.16em;fill:var(--fx-sub)}
.fx-tag{font:600 10.5px/1 var(--mono);fill:var(--fx-hot)}
.fx-r{fill:var(--fx-node);stroke:var(--fx-line);stroke-width:1.4;transition:stroke .3s}
.fx-gate .fx-r{fill:var(--fx-gate)}
.fx-t{font:600 13px/1 var(--body);fill:var(--fx-text)}
.fx-s{font:400 11px/1 var(--body);fill:var(--fx-sub)}
.fx-part .fx-r{stroke:var(--fx-part)}
.fx-plan .fx-r{stroke:var(--fx-plan);stroke-dasharray:5 4;animation:fx-pulse 2.4s ease-in-out infinite}
.fx-plan .fx-s{fill:var(--fx-plan)}
.fx-n.on .fx-r{stroke:var(--fx-hot);stroke-width:2.2;filter:drop-shadow(0 0 6px var(--fx-hot))}
.fx-n.on.fx-plan .fx-r{stroke:var(--fx-plan);filter:drop-shadow(0 0 6px var(--fx-plan))}
.fx-e{fill:none;stroke:var(--fx-line);stroke-width:1.6;stroke-dasharray:3 7;animation:fx-flow 1.2s linear infinite}
.fx-plan-e{stroke:var(--fx-plan);stroke-opacity:.6}
.fx-e.on{stroke:var(--fx-flow);stroke-width:2.4;stroke-dasharray:none;filter:drop-shadow(0 0 4px var(--fx-flow))}
.fx-plan-e.on{stroke:var(--fx-plan);stroke-opacity:1}
.fx-mk{fill:var(--fx-line)}
.fx-tap{stroke:var(--fx-line);stroke-width:1.2;stroke-dasharray:2 5}
.fx-infra{fill:none;stroke:var(--fx-line);stroke-dasharray:4 4}
.fx-particle{fill:var(--fx-hot)}
@keyframes fx-flow{to{stroke-dashoffset:-20}}
@keyframes fx-pulse{50%{stroke-opacity:.35}}
.fx-ctl{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px}
.fx-btn{font:600 12.5px/1 var(--body);padding:8px 14px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--fg);cursor:pointer}
.fx-btn small{font-weight:400;color:var(--muted);margin-left:6px}
.fx-btn[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--surface)}
.fx-btn[aria-pressed="true"] small{color:inherit;opacity:.8}
.fx-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fx-cap{display:flex;gap:12px;align-items:baseline;margin-top:12px;padding:12px 16px;border-radius:10px;background:var(--soft);font-size:14px}
.fx-cap b{font:600 12px/1 var(--mono);color:var(--accent);white-space:nowrap}
.fx-key{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:var(--muted);margin-top:10px}
.fx-key i{display:inline-block;width:18px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px;border:2px solid var(--fx-line);background:var(--fx-node)}
.fx-key .fx-k-part{border-color:var(--fx-part)}.fx-key .fx-k-plan{border-color:var(--fx-plan);border-style:dashed}.fx-key .fx-k-on{border-color:var(--fx-hot)}
@media (prefers-reduced-motion:reduce){.fx-e,.fx-plan .fx-r{animation:none}}
"""


@dataclass(frozen=True)
class Section:
    """页面中的一节。

    Attributes:
        anchor (str): 锚点 id，同时用于目录。
        nav (str): 目录里的短名。
        html (str): 本节内部 HTML（含 h2、lead、fig、表格等）。
        part (str): 非空时在本节前插入分部标题，如 ``"第一部分 · 架构设计"``。
    """

    anchor: str
    nav: str
    html: str
    part: str = ""


def page(
    *,
    title: str,
    eyebrow: str,
    h1: str,
    thesis: str,
    sections: Sequence[Section],
    footer: str = "",
    standalone: bool = True,
) -> str:
    """拼装完整页面。

    Args:
        title (str): ``<title>``，用 2-4 个词的名字，不加解释性后缀。
        eyebrow (str): 标题上方的小字（项目 · 主题 · 日期）。
        h1 (str): 页面主标题。
        thesis (str): 一段话的定位陈述，可含 ``<b>``。
        sections (Sequence[Section]): 各节。
        footer (str): 页脚：依据与限制说明。
        standalone (bool): ``True`` 输出带 doctype 的完整 HTML（本地打开）；
            ``False`` 只输出片段（发布到会自动包外壳的平台，如 claude.ai Artifact）。

    Returns:
        str: HTML 文本。
    """
    toc = "".join(f'<a href="#{s.anchor}">{esc(s.nav)}</a>' for s in sections)
    body_parts: list[str] = []
    for section in sections:
        if section.part:
            body_parts.append(f'<div class="part">{esc(section.part)}</div>')
        body_parts.append(f'<section id="{section.anchor}">{section.html}</section>')
    fragment = (
        f'<title>{esc(title)}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;600;700'
        '&family=JetBrains+Mono:wght@500;600&display=swap">\n'
        f'<style>{CSS}</style>\n<div class="wrap">\n<header class="hero">'
        f'<div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(h1)}</h1><p class="thesis">{thesis}</p>'
        f'<nav class="toc" aria-label="目录">{toc}</nav></header>\n'
        + "\n".join(body_parts)
        + (f"\n<footer>{footer}</footer>" if footer else "")
        + "\n</div>\n"
    )
    if not standalone:
        return fragment
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n'
        + fragment
        + "</body></html>\n"
    )


def _demo() -> str:
    """生成一个通用题材的示例页（客服工单平台），演示分层图、扇出汇聚、泳道图的用法。"""
    layers: list[str] = []
    layers.append(band(10, 10, 1180, 120, "使用者", ["人与 Agent", "共用一套数据"]))
    for index, (box_title, box_subs, box_kind) in enumerate(
        [
            ("客服 · 工作台", ["接单 · 回复 · 升级"], "plain"),
            ("主管 · 看板", ["质检 · 排班"], "plain"),
            ("对话型 Agent", ["起草回复"], "agent"),
            ("流程型 Agent", ["超时提醒 · 分派"], "agent"),
        ]
    ):
        layers.append(box(190 + index * 248, 44, 236, 66, box_title, box_subs, box_kind))
    layers.append(arrow("M600 130V148"))
    layers.append(band(10, 150, 1180, 120, "权限网关", ["检索前计算范围"], "gateband"))
    for index, (box_title, box_subs) in enumerate(
        [
            ("身份", ["用户 · 团队"]),
            ("范围", ["团队 ∩ 客户 ∩ Agent"]),
            ("装配", ["知识 + 事实 + 附件"]),
            ("留痕", ["来源 · 版本"]),
        ]
    ):
        layers.append(box(190 + index * 248, 184, 236, 66, box_title, box_subs, "gatebox"))
    layers.append(arrow("M600 270V288"))
    layers.append(band(10, 290, 1180, 150, "数据", ["工作态 → 发布态", "+ 外部事实"]))
    layers.append(box(190, 322, 280, 96, "工单附件", ["工作态 · 可编辑"], "files"))
    layers.append(arrow("M470 370H497"))
    layers.append(box(500, 322, 280, 96, "知识库", ["发布态 · 有版本 · 有有效期"], "kn"))
    layers.append(box(810, 322, 360, 96, "订单系统", ["实时事实 · 确认后写回"], "biz"))
    architecture_svg = svg(1200, 455, "".join(layers), "示例分层架构")

    flow_parts: list[str] = [box(20, 110, 170, 90, "收到工单", ["携带客户 ID"], "agent")]
    flow_parts.append(arrow("M190 155H217"))
    flow_parts.append(box(220, 100, 190, 110, "确定范围", ["团队 ∩ 客户 ∩ Agent"], "gate"))
    flow_parts.append(fan(410, 155, 460, [50, 155, 260]))
    flow_parts.append(box(460, 10, 220, 80, "检索知识", ["返回片段 + 版本"], "kn"))
    flow_parts.append(box(460, 115, 220, 80, "查询订单", ["返回记录 ID"], "biz"))
    flow_parts.append(box(460, 220, 220, 80, "读取附件", ["本工单选中的文件"], "files"))
    flow_parts.append(merge(680, [50, 155, 260], 730, 155))
    flow_parts.append(box(730, 100, 200, 110, "上下文包", ["带引用 · 无范围外数据"], "agent"))
    flow_parts.append(arrow("M930 155H967"))
    flow_parts.append(box(970, 110, 210, 90, "回复草稿", ["客服确认后发送"], "start"))
    context_svg = svg(1200, 320, "".join(flow_parts), "示例上下文装配")

    lanes_svg = swimlane(
        ["① 接单", "② 查询", "③ 回复", "④ 复盘"],
        [
            Lane(
                "客服",
                "工单负责人",
                "plain",
                [
                    ("接收工单", ["确认问题"]),
                    ("核对订单", ["必要时追问"]),
                    ("确认并发送", ["按话术规范"]),
                    ("标记解决", ["填写原因"]),
                ],
                flow=True,
            ),
            Lane(
                "Agent",
                "以客服身份运行",
                "agent",
                [
                    ("分类与摘要", ["识别客户"]),
                    ("查订单与知识", ["列出缺失项"]),
                    ("起草回复", ["附引用"]),
                    ("起草复盘", ["提交知识草稿"]),
                ],
            ),
            Lane(
                "知识库",
                "被读取 / 被写入",
                "kn",
                [
                    ("读：客户档案", []),
                    ("读：处理 SOP", []),
                    ("读：话术规范", []),
                    ("写：FAQ 新版本", ["审核后发布"]),
                ],
                highlight=(3,),
            ),
        ],
        footnote="每一列从上往下读：人做什么 → Agent 做什么 → 用到或写入哪些知识",
    )

    sections = [
        Section(
            "arch",
            "分层架构",
            f'<h2>分层架构</h2><p class="lead">先讲谁在用、按什么范围取数据、数据在哪里。</p><div class="fig">{architecture_svg}</div>{legend()}',
            part="第一部分 · 架构设计",
        ),
        Section(
            "ctx",
            "一次调用",
            f'<h2>一次 Agent 调用</h2><p class="lead">范围先算好，再并行取数据，最后装配成带引用的上下文。</p><div class="fig">{context_svg}</div>',
        ),
        Section(
            "flow",
            "业务流程",
            f'<h2>工单流程</h2><p class="lead">横向是阶段，纵向是角色与数据层。</p><div class="fig">{lanes_svg}</div>{legend()}',
            part="第二部分 · 业务流程",
        ),
    ]
    timeline_svg = timeline(
        [
            ("09:10", "告警触发", ["回复超时率升高"], "biz"),
            ("09:25", "定位原因", ["知识检索超时"], "plain"),
            ("09:40", "临时处置", ["切回人工模板"], "gatelite"),
            ("10:30", "恢复", ["超时率回到基线"], "kn"),
        ],
        "示例事件时间线",
    )
    decision_html = (
        '<h2>方案取舍</h2><div class="verdict"><b>建议：先做方案 B</b>'
        "<p>改动最小，两周内能拿到真实数据；方案 A 等数据量证明需要时再做。</p></div>"
        '<div class="options"><div class="opt"><span class="chip c-info">方案 A</span><h3>独立检索服务</h3>'
        "<ul><li>扩展性好</li><li>新增部署与运维成本</li></ul></div>"
        '<div class="opt rec"><span class="chip c-ok">推荐 · 方案 B</span><h3>沿用现有服务加缓存</h3>'
        "<ul><li>改动集中在一个模块</li><li>大流量时需要再评估</li></ul></div></div>"
    )
    flow_html = flow(
        ["入口", "权限", "Agent", "数据", "确认", "产出"],
        [
            FlowNode("mail", 0, 0, "客户邮件", "带客户 ID"),
            FlowNode("chat", 0, 1, "在线会话", "网页 · App"),
            FlowNode("scope", 1, 0, "确定范围", "团队 ∩ 客户", "gate", rowspan=2),
            FlowNode("agent", 2, 0, "对话型 Agent", "起草回复"),
            FlowNode("order", 3, 0, "订单系统", "实时事实"),
            FlowNode("kb", 3, 1, "知识库", "检索 · 引用", "part"),
            FlowNode("review", 4, 0, "客服确认", "规划中", "plan"),
            FlowNode("reply", 5, 0, "回复客户", "附引用"),
        ],
        [
            ("mail", "scope"),
            ("chat", "scope"),
            ("scope", "agent"),
            ("agent", "order"),
            ("agent", "kb", {"label": "检索"}),
            ("order", "review", {"plan": True}),
            ("review", "reply", {"plan": True}),
        ],
        {
            "mail": (
                "邮件工单",
                "",
                [
                    ("mail", "收到客户邮件"),
                    ("scope", "按团队和客户确定能看的数据"),
                    ("agent", "Agent 起草回复"),
                    ("order", "查订单状态"),
                    ("review", "客服确认（规划中）"),
                    ("reply", "发出回复"),
                ],
            ),
            "chat": (
                "知识问答",
                "",
                [
                    ("chat", "客户在线提问"),
                    ("scope", "确定范围"),
                    ("agent", "Agent 判断需要查资料"),
                    ("kb", "检索知识库并引用"),
                ],
            ),
        },
        uid="demo-flow",
        bus=("运行记录", "每一步写入同一条调用链"),
        done_text="每一步都写入运行记录，可回放。",
    )
    sections.append(
        Section(
            "flow",
            "动态流程",
            f'<h2>动态流程</h2><p class="lead">光点沿连线移动，经过的节点依次点亮；琥珀色虚线是规划中的环节。</p>{flow_html}',
        )
    )
    sections.append(Section("decision", "方案取舍", decision_html, part="其他页面类型的组件"))
    sections.append(
        Section("timeline", "时间线", f'<h2>事件经过</h2><div class="fig">{timeline_svg}</div>')
    )
    return page(
        title="工单平台架构示例",
        eyebrow="Demo · Architecture Explainer",
        h1="客服工单平台架构示例",
        thesis="示例页：演示分层图、扇出与汇聚、泳道图、动态流程图、方案卡片与时间线。<b>内容为虚构。</b>",
        sections=sections,
        footer="示例内容，仅用于展示组件用法。",
    )


def main() -> None:
    """命令行入口：``--demo <输出路径>`` 生成示例页。"""
    parser = argparse.ArgumentParser(description="架构说明页 SVG 组件")
    parser.add_argument("--demo", type=Path, help="生成示例页到该路径")
    parsed_args = parser.parse_args()
    if parsed_args.demo:
        parsed_args.demo.write_text(_demo(), encoding="utf-8")
        print(parsed_args.demo)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
