"""在隔离 Linux Chromium 中检查本地人审页及其相对视频资源。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
WORKTREE = SCRIPT_DIRECTORY.parents[4]
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import rv_stack  # noqa: E402
import rv_ui  # noqa: E402


def main() -> None:
    browser_setup_started_at = time.monotonic()
    container_name, _port, endpoint = rv_ui.start_remote_chromium(
        rv_stack.free_port(),
        rv_stack.free_port(),
        started_at=browser_setup_started_at,
    )
    try:
        completed = subprocess.run(
            ["node", str(SCRIPT_DIRECTORY / "human-review-checklist-smoke.mjs")],
            cwd=WORKTREE,
            env={**os.environ, "PLAYWRIGHT_REMOTE_BROWSER_WS": endpoint},
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(completed.stdout.strip())
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr[-3000:])
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)
        (SCRIPT_DIRECTORY / ".rv58-browser-endpoint").unlink(missing_ok=True)


if __name__ == "__main__":
    rv_stack.main_guard(main)
