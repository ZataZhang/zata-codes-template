#!/usr/bin/env python3
"""把多张截图合成一张循环 GIF（公众号「任务演示」动图）。

每张截图一帧，统一缩放宽度，底部加深色步骤说明条，末帧停留更久。

用法：
    python3 make_demo_gif.py 输出.gif 图1.png "① 第一步说明" 图2.png "② 第二步说明" ...

选项：
    --width N        输出宽度 px（默认 1400）
    --duration MS    普通帧停留毫秒（默认 2500）
    --last MS        末帧停留毫秒（默认 4200，0 表示与普通帧相同）
    --bar N          底部说明条高度 px（默认 72，0 表示不加说明条）

说明条文字使用「①②③」等编号手动标注步骤；不需要说明文字时 caption 传 ""。
依赖本机 PIL 和中文字体（macOS 优先 Hiragino Sans GB）。
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
]


def load_font(size):
    """按候选字体路径加载指定字号的字体。"""
    for path, index in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=index)
            except OSError:
                continue
    return ImageFont.load_default()


def _pad(im, height):
    canvas = Image.new("RGB", (im.width, height), (31, 41, 55))
    canvas.paste(im, (0, height - im.height))
    return canvas


def main():
    """解析命令行参数，把多张截图合成为循环演示 GIF。"""
    ap = argparse.ArgumentParser(description="多张截图合成循环 GIF，底部加步骤说明条")
    ap.add_argument("output", help="输出 .gif 路径")
    ap.add_argument("frames", nargs="+", help="交替给出：图片路径 说明文字")
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--duration", type=int, default=2500, help="普通帧停留毫秒")
    ap.add_argument("--last", type=int, default=4200, help="末帧停留毫秒，0 表示相同")
    ap.add_argument("--bar", type=int, default=72, help="说明条高度，0 表示不加")
    args = ap.parse_args()

    if len(args.frames) % 2 != 0:
        ap.error("图片路径和说明文字必须成对出现")

    pairs = list(zip(args.frames[::2], args.frames[1::2]))
    bar = args.bar if any(c for _, c in pairs) else 0
    font = load_font(round(args.width * 34 / 1400)) if bar else None

    frames = []
    for path, caption in pairs:
        im = Image.open(path).convert("RGB")
        h = round(im.height * args.width / im.width)
        im = im.resize((args.width, h), Image.LANCZOS)
        if bar:
            canvas = Image.new("RGB", (args.width, h + bar), (31, 41, 55))
            canvas.paste(im, (0, 0))
            if caption:
                d = ImageDraw.Draw(canvas)
                tw = d.textlength(caption, font=font)
                d.text(
                    ((args.width - tw) / 2, h + (bar - 40) / 2),
                    caption,
                    font=font,
                    fill=(255, 255, 255),
                )
            im = canvas
        frames.append(im)

    # GIF 要求所有帧同尺寸：较矮的帧在顶部补齐（说明条颜色），
    # 底部对齐让每帧说明条落在同一位置，避免增量编码留下上一帧残影
    max_h = max(f.height for f in frames)
    frames = [f if f.height == max_h else _pad(f, max_h) for f in frames]
    frames = [
        f.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG) for f in frames
    ]

    durations = [args.duration] * len(frames)
    if args.last:
        durations[-1] = args.last

    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(
        f"{args.output}  {os.path.getsize(args.output) / 1024 / 1024:.2f} MB  "
        f"{frames[0].size}  {len(frames)} 帧"
    )


if __name__ == "__main__":
    sys.exit(main())
