"""重合主演示录屏、核对时长并写回 RV-2 专属输出。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
EVIDENCE_DIRECTORY = SCRIPT_DIRECTORY.parent
MERGER_PATH = SCRIPT_DIRECTORY / "merge_primary_demo.py"
REPORT_PATH = EVIDENCE_DIRECTORY / "rv-2-primary-demo.txt"


def main() -> None:
    """从独立浏览器录制片段重新合成主演示并记录实际结果。"""
    completed = subprocess.run(
        [sys.executable, str(MERGER_PATH)],
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:])
    evidence_section = "\n\n## Final recording assembly\n"
    evidence_section += f"command: {sys.executable} {MERGER_PATH}\n"
    evidence_section += completed.stdout
    with REPORT_PATH.open("a", encoding="utf-8") as report_file:
        report_file.write(evidence_section)
    print(completed.stdout, end="")


if __name__ == "__main__":
    main()
