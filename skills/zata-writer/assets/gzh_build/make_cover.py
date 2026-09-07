#!/usr/bin/env python3
"""生成公众号头条封面图（900×383）：左侧标题区 + 右侧「三个产品、一个选择」节点图。

用法: python3 make_cover.py 输出.png 标题 [副标题] [角标文字]
"""

import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 900, 383
FONT_TTC = "/System/Library/Fonts/Hiragino Sans GB.ttc"

out = sys.argv[1]
title = sys.argv[2] if len(sys.argv) > 2 else "办公 Agent 怎么选？"
subtitle = sys.argv[3] if len(sys.argv) > 3 else "实测对比与选择建议"
tag = sys.argv[4] if len(sys.argv) > 4 else "选型对比"

# 三个产品节点：名称 + 品牌色
PRODUCTS = [
    ("豆包工作", (66, 103, 245)),
    ("WorkBuddy", (7, 193, 96)),
    ("千问办公", (124, 92, 255)),
]

# 背景：深色竖向渐变
top, bottom = (11, 18, 32), (10, 62, 52)
img = Image.new("RGB", (W, H))
for y in range(H):
    t = y / H
    img.paste(tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3)), (0, y, W, y + 1))

overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)
# 背景光晕
od.ellipse((600, -180, 1060, 260), fill=(7, 193, 96, 20))

# 右侧节点图：三个产品节点连向中心「你」
hub = (720, 200)
chip_pos = [(610, 60), (800, 130), (640, 310)]
f_chip = ImageFont.truetype(FONT_TTC, 19, index=1)

# 连线
for cx, cy in chip_pos:
    od.line((hub[0], hub[1], cx, cy), fill=(255, 255, 255, 70), width=2)
img = Image.alpha_composite(img.convert("RGBA"), overlay)
draw = ImageDraw.Draw(img)

# 产品节点（胶囊）
for (name, color), (cx, cy) in zip(PRODUCTS, chip_pos):
    tw = draw.textlength(name, font=f_chip)
    pw, ph = tw + 40, 44
    box = (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2)
    draw.rounded_rectangle(
        box, radius=22, fill=color + (255,) if len(color) == 3 else color, outline=None
    )
    draw.text((cx - tw / 2, cy - 14), name, font=f_chip, fill=(255, 255, 255))

# 中心节点「你」
overlay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od2 = ImageDraw.Draw(overlay2)
od2.ellipse((hub[0] - 34, hub[1] - 34, hub[0] + 34, hub[1] + 34), fill=(255, 255, 255, 255))
od2.ellipse(
    (hub[0] - 34, hub[1] - 34, hub[0] + 34, hub[1] + 34), outline=(7, 193, 96, 255), width=3
)
img = Image.alpha_composite(img, overlay2)
draw = ImageDraw.Draw(img)
f_hub = ImageFont.truetype(FONT_TTC, 24, index=1)
hub_text = "你"
hw = draw.textlength(hub_text, font=f_hub)
draw.text((hub[0] - hw / 2, hub[1] - 17), hub_text, font=f_hub, fill=(11, 18, 32))

# 左侧文字区
f_tag = ImageFont.truetype(FONT_TTC, 20, index=1)
tw = draw.textlength(tag, font=f_tag)
draw.rounded_rectangle((60, 52, 60 + tw + 36, 96), radius=22, outline=(52, 209, 123), width=2)
draw.text((60 + 18, 60), tag, font=f_tag, fill=(52, 209, 123))

f_title = ImageFont.truetype(FONT_TTC, 56, index=1)
draw.text((58, 122), title, font=f_title, fill=(255, 255, 255))

f_sub = ImageFont.truetype(FONT_TTC, 24, index=0)
draw.text((60, 216), subtitle, font=f_sub, fill=(158, 232, 193))

draw.line((60, 312, 440, 312), fill=(255, 255, 255, 60), width=1)
draw.ellipse((54, 307, 66, 319), outline=(7, 193, 96), width=2)
f_brand = ImageFont.truetype(FONT_TTC, 18, index=0)
draw.text((78, 326), "Zata山外志", font=f_brand, fill=(140, 150, 158))

img.convert("RGB").save(out)
print(f"已生成 {out}")
