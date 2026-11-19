"""为 RV-6 生成并校验使用可达镜像的临时锁文件。"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
WORKTREE = SCRIPT_DIRECTORY.parents[3]
MIRROR_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
MIRROR_LOCK = SCRIPT_DIRECTORY / "uv.lock.rv6-mirror"


def _lock_fingerprints(lock_path: Path) -> list[tuple[str, str, tuple[str, ...]]]:
    """读取锁文件中每个包的版本和所有分发文件哈希。"""
    with lock_path.open("rb") as lock_file:
        lock_document = tomllib.load(lock_file)
    fingerprints = []
    for package in lock_document["package"]:
        artifact_hashes = []
        source_distribution = package.get("sdist")
        if source_distribution is not None:
            artifact_hashes.append(source_distribution["hash"])
        artifact_hashes.extend(wheel["hash"] for wheel in package.get("wheels", []))
        fingerprints.append(
            (
                package["name"],
                package["version"],
                tuple(sorted(artifact_hashes)),
            )
        )
    return sorted(fingerprints)


def prepare_mirror_lock(timeout_seconds: int) -> Path:
    """生成临时镜像锁，并拒绝任何版本或分发哈希变化。"""
    original_lock = WORKTREE / "uv.lock"
    temporary_directory = tempfile.TemporaryDirectory(
        prefix="rv6-lock-", dir=SCRIPT_DIRECTORY
    )
    temporary_project = Path(temporary_directory.name)
    try:
        shutil.copy2(WORKTREE / "pyproject.toml", temporary_project / "pyproject.toml")
        shutil.copy2(original_lock, temporary_project / "uv.lock")
        package_directory = temporary_project / "packages" / "oidc-client"
        package_directory.mkdir(parents=True)
        shutil.copy2(
            WORKTREE / "packages" / "oidc-client" / "pyproject.toml",
            package_directory / "pyproject.toml",
        )
        shutil.copy2(
            WORKTREE / "packages" / "oidc-client" / "README.md",
            package_directory / "README.md",
        )
        shutil.copy2(WORKTREE / "README.md", temporary_project / "README.md")
        completed = subprocess.run(
            [
                "uv",
                "lock",
                "--project",
                str(temporary_project),
                "--default-index",
                MIRROR_INDEX,
            ],
            cwd=WORKTREE,
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
            timeout=timeout_seconds,
        )
        original_fingerprints = _lock_fingerprints(original_lock)
        mirror_lock = temporary_project / "uv.lock"
        mirror_fingerprints = _lock_fingerprints(mirror_lock)
        if original_fingerprints != mirror_fingerprints:
            raise RuntimeError(
                "mirror lock changed package versions or artifact hashes"
            )
        shutil.copy2(mirror_lock, MIRROR_LOCK)
        print(completed.stdout.strip())
        print(
            "Mirror lock verified: package versions and all distribution SHA-256 "
            f"hashes match ({len(original_fingerprints)} packages)."
        )
        return MIRROR_LOCK
    finally:
        temporary_directory.cleanup()

