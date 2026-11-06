"""不依赖 Git 的只读目录扫描。"""

from __future__ import annotations

import os
from pathlib import Path

# Git 忽略规则不可用时仍剪掉体积通常很大的依赖与缓存目录。
PRUNED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "coverage",
        "node_modules",
        "site-packages",
        "venv",
    }
)


def collect_viewable_file_paths(workspace_root: Path) -> list[str]:
    """递归列出目录内可读的普通文件，跳过符号链接与缓存目录。

    Args:
        workspace_root (Path): 已解析的浏览目录根路径。

    Returns:
        list[str]: 按路径排序的目录相对路径，统一使用 POSIX 分隔符。
    """
    file_paths: list[str] = []
    for current_directory_name, child_directory_names, file_names in os.walk(
        workspace_root,
        topdown=True,
        followlinks=False,
    ):
        current_directory = Path(current_directory_name)
        child_directory_names[:] = sorted(
            child_directory_name
            for child_directory_name in child_directory_names
            if child_directory_name not in PRUNED_DIRECTORY_NAMES
            and not (current_directory / child_directory_name).is_symlink()
        )
        for file_name in sorted(file_names):
            if file_name == ".git":
                continue
            candidate_file_path = current_directory / file_name
            if candidate_file_path.is_symlink() or not candidate_file_path.is_file():
                continue
            file_paths.append(candidate_file_path.relative_to(workspace_root).as_posix())
    return sorted(file_paths)
