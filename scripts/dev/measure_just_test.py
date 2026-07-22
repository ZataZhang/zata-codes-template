#!/usr/bin/env python3
"""测量 `just test` 端到端耗时，验证 ≤30s 目标。

运行三种场景（默认 warm + after-edit，cold 通过 --include-cold 启用），
输出每段的 wall clock；任一段 >30s 退出码非零。

用法：
    uv run python scripts/dev/measure_just_test.py [--include-cold] [--budget 30]

设计要点：
- 用 subprocess.run + time.monotonic_ns 测 wall clock，不依赖 GNU /usr/bin/time。
- 通过让子进程把 stdout/stderr 透传给本进程，实现"边跑边看"，不需要额外 buffer。
- --include-cold 会删除 .last_linted_commit 和 .last_tested_commit，
  强制走 pre-commit 全套；该路径可能超过 30s（pre-commit 全套时间决定），
  按当前默认不跑，需要时显式 opt-in。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GIT_DIR = PROJECT_ROOT / ".git"
LINT_FLAG = GIT_DIR / ".last_linted_commit"
TEST_FLAG = GIT_DIR / ".last_tested_commit"
EDIT_MARKER = "# measure_just_test.py — temporary marker, safe to remove"

DEFAULT_BUDGET_SECONDS = 30.0


def _run_just_test() -> tuple[int, float]:
    """运行 `just test` 并返回 (exit_code, wall_clock_seconds)。"""
    start = time.monotonic()
    completed = subprocess.run(
        ["just", "test"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    elapsed = time.monotonic() - start
    return completed.returncode, elapsed


def _scenario(label: str, budget_seconds: float, *, include_cold: bool) -> dict:
    """跑一个场景并返回其结果 dict。"""
    print(f"\n=== scenario: {label} ===", flush=True)
    if label == "cold" and not include_cold:
        print("skipped (use --include-cold to enable)", flush=True)
        return {
            "label": label,
            "skipped": True,
            "elapsed": None,
            "exit_code": None,
            "passed": None,
        }
    if label == "cold":
        for flag in (LINT_FLAG, TEST_FLAG):
            if flag.exists():
                flag.unlink()
        print("cleared .last_linted_commit and .last_tested_commit", flush=True)
    elif label == "after-edit":
        pyproject = PROJECT_ROOT / "pyproject.toml"
        original = pyproject.read_text(encoding="utf-8")
        pyproject.write_text(original + "\n" + EDIT_MARKER + "\n", encoding="utf-8")
        try:
            exit_code, elapsed = _run_just_test()
            return {
                "label": label,
                "skipped": False,
                "elapsed": elapsed,
                "exit_code": exit_code,
                "passed": exit_code == 0 and elapsed <= budget_seconds,
            }
        finally:
            pyproject.write_text(original, encoding="utf-8")
            for flag in (LINT_FLAG, TEST_FLAG):
                if flag.exists():
                    flag.unlink()
    exit_code, elapsed = _run_just_test()
    return {
        "label": label,
        "skipped": False,
        "elapsed": elapsed,
        "exit_code": exit_code,
        "passed": exit_code == 0 and elapsed <= budget_seconds,
    }


def _print_summary(results: list[dict], budget_seconds: float) -> None:
    print("\n=== summary ===", flush=True)
    rows = []
    for result in results:
        if result["skipped"]:
            rows.append((result["label"], "skipped", "—", "—"))
        else:
            verdict = "PASS" if result["passed"] else "FAIL"
            rows.append(
                (
                    result["label"],
                    f"{result['elapsed']:.2f}s",
                    f"exit={result['exit_code']}",
                    verdict,
                )
            )
    width = max(len(row[0]) for row in rows)
    for label, elapsed, exit_code, verdict in rows:
        print(f"  {label:<{width}}  {elapsed}  {exit_code}  {verdict}", flush=True)
    if budget_seconds:
        print(f"  budget: ≤{budget_seconds:.1f}s per scenario", flush=True)


def main() -> int:
    """解析参数、跑场景、打印汇总；任一非跳过场景失败返回 1。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-cold",
        action="store_true",
        help="也跑 cold 场景（删 flag 文件强制 pre-commit 全套，可能超时）",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=DEFAULT_BUDGET_SECONDS,
        help=f"每段耗时上限（秒），默认 {DEFAULT_BUDGET_SECONDS}",
    )
    args = parser.parse_args()

    if not shutil.which("just"):
        print("ERROR: `just` not found on PATH", file=sys.stderr, flush=True)
        return 2

    scenarios = ["warm", "after-edit"]
    if args.include_cold:
        scenarios.insert(0, "cold")

    results = [_scenario(label, args.budget, include_cold=args.include_cold) for label in scenarios]
    _print_summary(results, args.budget)

    measured = [r for r in results if not r["skipped"]]
    if not measured:
        return 0
    failed = [r for r in measured if not r["passed"]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
