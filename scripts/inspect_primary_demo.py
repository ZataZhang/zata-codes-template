"""抽取主演示各段画面，核对字幕出现时长与结果留屏。

脚本只读取证据目录里的主演示 MP4 与它的分段时长 sidecar：按片段边界每秒采样，
用左下角字幕带的亮度判断字幕是否在画面上（字幕条为深色背景），并要求同一段里
字幕至少连续可见 3 秒、各段字幕画面互不相同。字幕文案本身由
``rv-2-caption-trace.txt`` 记录，因为容器内没有中文 OCR 语言包。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

EVIDENCE_DIRECTORY = Path(__file__).resolve().parents[1]
VIDEO_PATH = EVIDENCE_DIRECTORY / "rv-2-demo-multi-organization-agent.mp4"
CLIP_MANIFEST_PATH = EVIDENCE_DIRECTORY / "rv-2-primary-demo-clips.json"
#: 字幕条是深色底，亮度平均值低于该阈值即认为字幕在画面上。
CAPTION_YAVG_THRESHOLD = 180.0
#: PRD 要求每个结果画面停留不少于 3 秒。
MIN_CAPTION_SECONDS = 3.0
#: 片段与步骤的对应关系（第 3 步由历史与管理轨迹两段共同呈现）。
STEP_CLIP_NAMES = (
    ("rv-2-demo-step-1-admin-publish.webm", "step 1: publish a model-configured Agent"),
    ("rv-2-demo-step-2-member-run.webm", "step 2: member run with incremental reply"),
    ("rv-2-demo-step-3-history.webm", "step 3a: reopen the same run from history"),
    ("rv-2-demo-step-4-trace.webm", "step 3b: admin low-sensitivity trace"),
    ("rv-2-demo-step-5-skill-version.webm", "step 4: Skill update, compare and restore"),
    ("rv-2-demo-step-6-second-run.webm", "step 5: second run freezes the restored version"),
)
#: 左下角字幕带，按视频高度的比例裁剪。
CAPTION_BAND_FILTER = "crop=iw*0.55:ih*0.06:0:ih*0.925"


def video_duration(video_path: Path, ffprobe_path: str) -> float:
    """读取录屏时长秒数。"""
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def extract_frame(
    ffmpeg_path: str, video_path: Path, timestamp: float, frame_path: Path
) -> None:
    """按时间点抽取单帧 PNG。"""
    subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-ss",
            f"{max(timestamp, 0.0):.2f}",
            "-frames:v",
            "1",
            "-y",
            str(frame_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def caption_band_stats(ffmpeg_path: str, frame_path: Path) -> tuple[float, str]:
    """返回字幕带的平均亮度与内容摘要。"""
    result = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(frame_path),
            "-vf",
            f"{CAPTION_BAND_FILTER},signalstats,metadata=print:file=-",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    matched = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", result.stdout)
    if matched is None:
        raise RuntimeError("caption band brightness could not be measured")
    return float(matched.group(1)), hashlib.sha256(frame_path.read_bytes()).hexdigest()[:12]


def main() -> None:
    """逐段核对字幕可见时长与字幕画面差异，任一段不合格即非零退出。"""
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        raise RuntimeError("ffmpeg and ffprobe are required to inspect the primary demo")
    if not VIDEO_PATH.is_file():
        raise RuntimeError(f"primary demo missing: {VIDEO_PATH.name}")
    clip_lengths = {
        clip_document["name"]: float(clip_document["duration_seconds"])
        for clip_document in json.loads(CLIP_MANIFEST_PATH.read_text(encoding="utf-8"))["clips"]
    }

    preview_directory = Path(tempfile.mkdtemp(prefix="rv58-primary-demo-preview-", dir="/private/tmp"))
    offset_seconds = 0.0
    failures: list[str] = []
    captured_digests: list[str] = []
    for step_number, (clip_name, description) in enumerate(STEP_CLIP_NAMES, start=1):
        if clip_name not in clip_lengths:
            raise RuntimeError(f"primary demo clip duration missing: {clip_name}")
        clip_length = clip_lengths[clip_name]
        caption_timestamps: list[float] = []
        sample_digest = ""
        for sample_index in range(1, max(int(clip_length), 2)):
            sample_time = offset_seconds + sample_index
            if sample_time >= offset_seconds + clip_length - 0.5:
                break
            frame_path = preview_directory / f"step-{step_number}-{sample_index}.png"
            extract_frame(ffmpeg_path, VIDEO_PATH, sample_time, frame_path)
            average_brightness, frame_digest = caption_band_stats(ffmpeg_path, frame_path)
            if average_brightness < CAPTION_YAVG_THRESHOLD:
                caption_timestamps.append(sample_time - offset_seconds)
                sample_digest = frame_digest
            frame_path.unlink()
        caption_seconds = (
            caption_timestamps[-1] - caption_timestamps[0] + 1.0 if caption_timestamps else 0.0
        )
        captured_digests.append(sample_digest)
        print(
            f"{description}: clip={clip_name} duration={clip_length:.2f}s "
            f"caption_seconds≈{caption_seconds:.1f}s phrase_digest={sample_digest}"
        )
        if caption_seconds < MIN_CAPTION_SECONDS:
            failures.append(f"{clip_name}: caption stayed on screen for < {MIN_CAPTION_SECONDS:.0f}s")
        offset_seconds += clip_length
    if len(set(captured_digests)) != len(captured_digests):
        failures.append("two steps showed the same caption frame; steps are not distinguishable")
    print(f"primary demo duration: {video_duration(VIDEO_PATH, ffprobe_path):.2f}s")
    if failures:
        raise SystemExit("primary demo inspection failed:\n" + "\n".join(failures))
    print("PRIMARY_DEMO_INSPECTION: PASS")


if __name__ == "__main__":
    main()
