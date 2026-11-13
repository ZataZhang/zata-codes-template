"""``skills/desktop-app-demo-recording/scripts/stitch.sh`` 录屏剪辑脚本的行为测试。

用 ffmpeg 现场生成测试片段，验证多段拼接后中段按倍数快进、头尾保持原速，
以及总长放不下头尾时原样输出；产物必须是 H.264 + yuv420p。机器上没有
ffmpeg 时整体跳过。

**本文件是模板内部测试**：被测对象 ``skills/`` 不同步进派生项目，本文件已列入
``scripts/shared/template/sync_template.sh`` 的排除清单。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

STITCH_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "desktop-app-demo-recording"
    / "scripts"
    / "stitch.sh"
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


def make_clip(path: Path, seconds: int) -> Path:
    """生成一段纯色测试视频。"""
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=320x200:rate=30:duration={seconds}",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return path


def probe(path: Path, entries: str, stream: bool = False) -> str:
    """读取视频的时长或首个视频流的编码信息。"""
    selector = ["-select_streams", "v:0"] if stream else []
    return subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            *selector,
            "-show_entries",
            entries,
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run_stitch(output: Path, head: int, tail: int, *segments: Path) -> None:
    subprocess.run(
        ["bash", str(STITCH_SCRIPT), str(output), str(head), str(tail), *map(str, segments)],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "WIDTH": "320"},
    )


def test_segments_are_joined_and_middle_is_fast_forwarded(tmp_path: Path) -> None:
    first = make_clip(tmp_path / "a.mp4", 20)
    second = make_clip(tmp_path / "b.mp4", 12)
    output = tmp_path / "out.mp4"

    run_stitch(output, 4, 4, first, second)

    # 32 秒原片：头 4 秒 + 尾 4 秒原速，中间 24 秒按 8 倍快进成 3 秒。
    assert float(probe(output, "format=duration")) == pytest.approx(11, abs=0.5)
    assert probe(output, "stream=codec_name,pix_fmt", stream=True) == "h264,yuv420p"


def test_short_recording_is_kept_at_normal_speed(tmp_path: Path) -> None:
    clip = make_clip(tmp_path / "short.mp4", 6)
    output = tmp_path / "out.mp4"

    run_stitch(output, 4, 4, clip)

    assert float(probe(output, "format=duration")) == pytest.approx(6, abs=0.5)


def test_missing_arguments_exit_with_usage(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(STITCH_SCRIPT), str(tmp_path / "out.mp4")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "用法" in result.stderr
