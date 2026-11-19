"""验证临时 Linux Chromium 服务可由本机 Playwright 客户端连接。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_ui  # noqa: E402
import rv_stack as stack  # noqa: E402


def main() -> None:
    browser_setup_started_at = time.monotonic()
    container_name, _port, endpoint = rv_ui.start_remote_chromium(
        stack.free_port(),
        stack.free_port(),
        started_at=browser_setup_started_at,
    )
    try:
        completed = subprocess.run(
            ["node", str(stack.EVIDENCE_DIR / "scripts" / "remote-browser-client-smoke.mjs")],
            cwd=stack.WORKTREE,
            env={**os.environ, "PLAYWRIGHT_REMOTE_BROWSER_WS": endpoint},
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(completed.stdout.strip())
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr[-2000:])
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)
        (stack.EVIDENCE_DIR / "scripts" / ".rv58-browser-endpoint").unlink(missing_ok=True)


if __name__ == "__main__":
    stack.main_guard(main)
