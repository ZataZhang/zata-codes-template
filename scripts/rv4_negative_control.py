"""RV-4 负控：向真实 just copy 输入注入来源产品标记，验证发布审计会变红。"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402

AUDIT_SCRIPT = Path(__file__).resolve().parent / "rv4_distribution_audit.py"
INJECTED_SOURCE_PATH = (
    stack.WORKTREE / "frontend-admin" / "public" / "CargoX-negative-control.txt"
)


def main() -> None:
    """运行一次真实副本审计并确认来源产品文本会令门禁失败。"""
    report = stack.Report(stack.EVIDENCE_DIR / "rv-4-negative-control.txt")
    if INJECTED_SOURCE_PATH.exists():
        raise RuntimeError("refusing to overwrite a pre-existing negative-control path")
    try:
        INJECTED_SOURCE_PATH.write_bytes(b"CargoX temporary source-product sentinel for RV-4 negative control")
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            cwd=stack.WORKTREE,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=300,
        )
        combined_output = completed.stdout + completed.stderr
        report(f"# rv-4 negative control at {datetime.now(UTC).isoformat()}")
        INJECTED_SOURCE_PATH.unlink(missing_ok=True)
        report("identity:", stack.git_identity())
        report("command:", f"python {AUDIT_SCRIPT.relative_to(stack.WORKTREE)}")
        report("injected fault:", "temporary CargoX text sentinel; `just copy` transfers it into the real output")
        report("audit exit code:", completed.returncode)
        report("auditor response:", "\n".join(line for line in combined_output.splitlines() if "forbidden source-product path/text hits" in line or "AssertionError" in line or "RV_RESULT" in line))
        if completed.returncode == 0 or "forbidden source-product path/text hits" not in combined_output:
            raise AssertionError("distribution audit did not reject the injected source-branded asset")
        if "CargoX-negative-control.txt" not in combined_output:
            raise AssertionError("distribution audit did not report the injected CargoX text sentinel")
        report("expected_fail:", "the copy auditor reports the injected source-product text and exits non-zero")
        report("\nEXPECTED_FAIL: rv-4 distribution assertion detected the injected CargoX sentinel")
        report("RV_RESULT: NEGATIVE CONTROL DETECTED rv-4")
    finally:
        INJECTED_SOURCE_PATH.unlink(missing_ok=True)
        report.save()


if __name__ == "__main__":
    stack.main_guard(main)
