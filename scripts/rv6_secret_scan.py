"""rv-6 静态包密钥探针：递归扫描目录中的所有文件（含二进制），查找密钥标记。

用法::

    RV6_MARKER=<marker> python3 rv6_secret_scan.py <label>=<dir> [<label>=<dir> ...]

标记值只从环境变量读取，输出里只显示掩码。任一文件含标记即退出 1。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def mask_marker(marker_text: str) -> str:
    """返回标记的掩码形式，避免把完整值写入证据。"""
    return f"{marker_text[:6]}***({len(marker_text)} chars)"


def scan_directory(scan_root: Path, marker_bytes: bytes) -> tuple[int, list[str]]:
    """扫描目录，返回（文件数, 命中文件相对路径列表）。"""
    scanned_file_count = 0
    hit_paths: list[str] = []
    for file_path in sorted(scan_root.rglob("*")):
        if not file_path.is_file() or file_path.is_symlink():
            continue
        scanned_file_count += 1
        if marker_bytes in file_path.read_bytes():
            hit_paths.append(str(file_path.relative_to(scan_root)))
    return scanned_file_count, hit_paths


def main() -> int:
    """扫描所有参数目录并打印结果。"""
    marker_text = os.environ.get("RV6_MARKER", "")
    if len(marker_text) < 16:
        print("ERROR: RV6_MARKER missing or too short")
        return 2
    marker_bytes = marker_text.encode("utf-8")
    print(f"marker={mask_marker(marker_text)}")
    total_hits = 0
    for scan_arg in sys.argv[1:]:
        scan_label, _, scan_dir = scan_arg.partition("=")
        scan_root = Path(scan_dir)
        if not scan_root.is_dir():
            print(f"ERROR: {scan_label}: not a directory")
            return 2
        scanned_file_count, hit_paths = scan_directory(scan_root, marker_bytes)
        if scanned_file_count == 0:
            print(f"ERROR: {scan_label}: no files scanned")
            return 2
        print(f"scan {scan_label}: files={scanned_file_count} marker_hits={len(hit_paths)}")
        for hit_path in hit_paths:
            print(f"  HIT {scan_label}:{hit_path}")
        total_hits += len(hit_paths)
    if total_hits:
        print(f"SECRET_SCAN FAIL: marker found in {total_hits} file(s)")
        return 1
    print("SECRET_SCAN PASS: marker absent from all scanned files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
