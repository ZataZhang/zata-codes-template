"""把单独主演示流程的真实 Playwright 录屏按页面顺序合成 MP4。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
EVIDENCE_DIRECTORY = SCRIPT_DIRECTORY.parent
OUTPUT_PATH = EVIDENCE_DIRECTORY / "rv-2-demo-multi-organization-agent.mp4"
DEMO_CLIP_NAMES = (
    "rv-2-demo-step-1-admin-publish.webm",
    "rv-2-demo-step-2-member-run.webm",
    "rv-2-demo-step-3-history.webm",
    "rv-2-demo-step-4-trace.webm",
    "rv-2-demo-step-5-skill-version.webm",
    "rv-2-demo-step-6-second-run.webm",
)


def read_video_duration(video_path: Path, ffprobe_path: str) -> float:
    """读取录制片段或主演示的时长。"""
    completed = subprocess.run(
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
    return float(completed.stdout.strip())


def main() -> None:
    """合并独立主演示的六段真实浏览器录屏并记录分段时长。"""
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path is None or ffprobe_path is None:
        raise RuntimeError("ffmpeg and ffprobe are required to assemble the primary demo")
    video_paths = [EVIDENCE_DIRECTORY / file_name for file_name in DEMO_CLIP_NAMES]
    missing_video_paths = [video_path.name for video_path in video_paths if not video_path.is_file()]
    if missing_video_paths:
        raise RuntimeError(f"real demo recordings missing: {', '.join(missing_video_paths)}")
    clip_durations = [read_video_duration(video_path, ffprobe_path) for video_path in video_paths]
    if any(clip_duration < 3.5 for clip_duration in clip_durations):
        raise RuntimeError("a demo recording ended before its required result dwell")

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="rv58-primary-demo-",
        suffix=".txt",
        dir="/private/tmp",
        delete=False,
    ) as list_file:
        concat_list_path = Path(list_file.name)
        for video_path in video_paths:
            list_file.write(f"file '{video_path.as_posix()}'\n")
    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list_path),
                "-map",
                "0:v:0",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "25",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(OUTPUT_PATH),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    finally:
        concat_list_path.unlink(missing_ok=True)

    # 分段边界写进 sidecar，供只读检查脚本在不保留原始 webm 时定位每段末帧。
    clip_manifest_path = EVIDENCE_DIRECTORY / "rv-2-primary-demo-clips.json"
    clip_manifest_path.write_text(
        json.dumps(
            {
                "clips": [
                    {"name": file_name, "duration_seconds": round(clip_duration, 3)}
                    for file_name, clip_duration in zip(DEMO_CLIP_NAMES, clip_durations, strict=True)
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for video_path in video_paths:
        video_path.unlink()

    demo_duration = read_video_duration(OUTPUT_PATH, ffprobe_path)
    print("primary demo: separate real-browser recording, five scripted steps")
    print("clip order: publish Agent, member Run with incremental reply, reopened history,")
    print("admin trace, Skill update/compare/restore, second Run with frozen versions")
    print("six real browser clips (seconds):", ", ".join(f"{duration:.2f}" for duration in clip_durations))
    print("each result step holds for at least 3.5 seconds per the recording workflow")
    print(f"primary demo duration: {demo_duration:.2f} seconds")
    print(f"primary demo file: {OUTPUT_PATH.name} ({OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
