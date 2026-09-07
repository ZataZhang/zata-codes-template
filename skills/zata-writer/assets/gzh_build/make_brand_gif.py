#!/usr/bin/env python3
"""生成公众号开头品牌 GIF：左侧打字机文字 + 闪烁光标，右侧 Agent 节点网络漂移。

用法: python3 make_brand_gif.py 输出路径.gif [左侧文字] [右侧文字]
默认文字: Zata 山外志
"""

import math
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 640, 100
FRAMES = 48
FPS_MS = 70
GREEN = (7, 193, 96)
DARK = (26, 26, 26)
GRAY = (150, 150, 150)

out = sys.argv[1]
left_text = sys.argv[2] if len(sys.argv) > 2 else "Zata"
right_text = sys.argv[3] if len(sys.argv) > 3 else "山外志"

FONT_TTC = "/System/Library/Fonts/Hiragino Sans GB.ttc"
font = ImageFont.truetype(FONT_TTC, 36, index=1)

# 右侧节点网络：固定基准位置 + 正弦漂移
NODES = [(470, 28), (530, 62), (585, 30), (620, 66), (505, 40), (560, 78), (445, 62)]
AMPS = [(6, 4), (5, 6), (7, 3), (4, 5), (5, 5), (6, 4), (4, 6)]
LINK_DIST = 78

probe = ImageDraw.Draw(Image.new("RGB", (W, H)))
wl = probe.textlength(left_text, font=font)
text_x = 44
text_y = H // 2 - 26


def node_pos(k, frame):
    """第 k 个节点在第 frame 帧的坐标：固定基准位置叠加正弦漂移。

    Args:
        k (int): 节点下标。
        frame (int): 当前帧号。

    Returns:
        tuple[float, float]: 节点坐标 (x, y)。
    """
    bx, by = NODES[k]
    ax, ay = AMPS[k]
    return (bx + ax * math.sin(frame * 0.11 + k * 1.7), by + ay * math.cos(frame * 0.09 + k * 2.3))


frames = []
for i in range(FRAMES):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 节点网络：先线后点
    pos = [node_pos(k, i) for k in range(len(NODES))]
    for a in range(len(pos)):
        for b in range(a + 1, len(pos)):
            d = math.dist(pos[a], pos[b])
            if d < LINK_DIST:
                alpha = int(140 * (1 - d / LINK_DIST))
                od.line((*pos[a], *pos[b]), fill=GREEN + (alpha,), width=1)
    for k, (x, y) in enumerate(pos):
        r = 3 if k % 2 else 4
        od.ellipse((x - r, y - r, x + r, y + r), fill=GREEN + (200,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    # 打字机：前 22 帧逐字出现，之后常显
    full = [(left_text, GREEN), (right_text, DARK)]
    chars_total = len(left_text) + len(right_text)
    shown = min(chars_total, max(0, int((i - 2) * chars_total / 20)))
    if shown > 0:
        # 逐字拼接绘制
        acc = ""
        x = text_x
        remaining = shown
        for text, color in full:
            take = min(len(text), remaining)
            if take > 0:
                draw.text((x, text_y), text[:take], font=font, fill=color)
                x += draw.textlength(text[:take], font=font)
            remaining -= take
    else:
        x = text_x
    # 光标：闪烁
    if shown >= chars_total:
        cursor_x = text_x + wl + 8 + probe.textlength(right_text, font=font) + 6
    else:
        # 光标跟在已输入文字后面
        cursor_x = text_x
        remaining = shown
        for text, _ in full:
            take = min(len(text), remaining)
            if take > 0:
                cursor_x += draw.textlength(text[:take], font=font)
            remaining -= take
        cursor_x += 4
    if (i // 6) % 2 == 0:
        draw.rectangle((cursor_x, text_y + 4, cursor_x + 4, text_y + 38), fill=GREEN)

    frames.append(img)

frames[0].save(out, save_all=True, append_images=frames[1:], duration=FPS_MS, loop=0, optimize=True)
print(f"已生成 {out}（{FRAMES} 帧）")
