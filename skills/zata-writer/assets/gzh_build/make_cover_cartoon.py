#!/usr/bin/env python3
"""卡通插画封面合成：AI 生成底图 → 修补生成水印 → 裁切 2.35:1 → 左侧叠加标题文字。

底图由生图模型按「画面无文字」要求生成（模型渲染中文不可靠，文字一律后叠）。
品牌人物设定见 assets/brand/人物设定.png，人物描述片段写进生图 prompt，
流程和 prompt 模板见 references/gongzhong-publish.md「卡通插画封面」。

用法:
  python3 make_cover_cartoon.py 底图.png 输出.png "标题行1|标题行2" \
      [副标题] [角标] [--watermark X0,Y0,X1,Y1] [--light]

  --watermark  底图上的生成水印区域（通常在右下角），用其左侧同行背景平移覆盖 + 高斯模糊抹除
  --light      底图整体偏深时用浅色文字（默认按浅色底配深色字）
"""

import argparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 900, 383

FONT_PATHS = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]


def font(size, bold=True):
    """从 macOS 系统字体列表中取第一个可用字体，全部失败时退回 PIL 默认字体。"""
    for font_path in FONT_PATHS:
        try:
            return ImageFont.truetype(font_path, size, index=1 if bold else 0)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    """解析命令行参数，合成封面并保存到输出路径。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="AI 生成的底图（建议 2560×1080，画面无文字）")
    ap.add_argument("out", help="输出路径，命名 封面.png 可被 push_draft.py 优先采用")
    ap.add_argument("title", help="封面标题，最多两行，用 | 分隔")
    ap.add_argument("subtitle", nargs="?", default="", help="副标题，可省略")
    ap.add_argument("tag", nargs="?", default="", help="左上角标（如「产业推演」），可省略")
    ap.add_argument("--watermark", default="", help="底图水印区域 X0,Y0,X1,Y1（原图坐标）")
    ap.add_argument("--light", action="store_true", help="深色底图用浅色文字")
    args = ap.parse_args()

    lines = args.title.split("|")
    if len(lines) > 2:
        ap.error("标题最多两行，用 | 分隔")
    wm = None
    if args.watermark:
        wm = tuple(int(v) for v in args.watermark.split(","))
        if len(wm) != 4:
            ap.error("--watermark 需要 4 个数字：X0,Y0,X1,Y1")

    if args.light:
        ink, sub_c, mute, rule = (255, 255, 255), (214, 228, 220), (168, 180, 174), (255, 255, 255)
        green, green_d = (7, 193, 96), (82, 209, 128)
    else:
        ink, sub_c, mute, rule = (31, 41, 51), (74, 90, 100), (140, 152, 160), (210, 216, 214)
        green, green_d = (7, 193, 96), (10, 143, 71)

    img = Image.open(args.base).convert("RGB")

    if wm:
        wx0, wy0, wx1, wy1 = wm
        patch = img.crop((wx0 - (wx1 - wx0), wy0, wx0, wy1)).filter(ImageFilter.GaussianBlur(2))
        img.paste(patch, (wx0, wy0))

    target_w = int(img.height * W / H)
    x0 = (img.width - target_w) // 2
    img = img.crop((x0, 0, x0 + target_w, img.height)).resize((W, H), Image.LANCZOS)

    draw = ImageDraw.Draw(img)

    if args.tag:
        f_tag = font(16)
        tw = draw.textlength(args.tag, font=f_tag)
        draw.rounded_rectangle((52, 44, 52 + tw + 32, 78), radius=17, outline=green_d, width=2)
        draw.text((68, 51), args.tag, font=f_tag, fill=green_d)

    f_title = font(33)
    title_ys = [102, 152] if len(lines) == 2 else [127]
    for line, y in zip(lines, title_ys):
        draw.text((52, y), line, font=f_title, fill=ink)

    if args.subtitle:
        draw.text((54, 212), args.subtitle, font=font(15, bold=False), fill=sub_c)

    draw.line((54, 322, 240, 322), fill=rule, width=1)
    draw.ellipse((50, 316, 62, 328), outline=green, width=2)
    draw.text((74, 336), "Zata山外志", font=font(14, bold=False), fill=mute)

    img.save(args.out)
    print(f"已生成 {args.out}（{W}×{H}）")


if __name__ == "__main__":
    main()
