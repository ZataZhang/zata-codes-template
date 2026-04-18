"""Environment management utilities for DwCrawler.

This module centralizes loading logic for environment variables so that global
settings (shared by the entire package) and local overrides (used by scripts or
tests) can be handled independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

EnvPath = Union[str, Path]

# Package directory that now hosts the dotenv files.
PACKAGE_DIR = Path(__file__).resolve().parent

# Default file names for global and local configuration.
GLOBAL_ENV_NAME = ".env"
LOCAL_ENV_NAME = ".env.local"


def _resolve(candidate: EnvPath) -> Path:
    """Resolve a candidate path relative to the package directory."""
    path = Path(candidate)
    if not path.is_absolute():
        path = PACKAGE_DIR / path
    return path


def load_global_settings(
    env_file: Optional[EnvPath] = None, override: bool = False
) -> Optional[Path]:
    """Load shared settings that should apply across every module.

    Args:
        env_file (Optional[EnvPath]): Custom file to use instead of the package
            default.
        override (bool): Whether to override already defined environment
            variables.

    Returns:
        Optional[Path]: The file that was successfully loaded.
    """
    target = _resolve(env_file or GLOBAL_ENV_NAME)
    if target.exists():
        load_dotenv(target, override=override)
        return target
    return None


def load_local_settings(
    env_file: Optional[EnvPath] = None, override: bool = True
) -> Optional[Path]:
    """Load local overrides for scripts or tests.

    Args:
        env_file (Optional[EnvPath]): Custom file that stores overrides.
        override (bool): Whether to override already defined environment
            variables.

    Returns:
        Optional[Path]: The file that was successfully loaded.
    """
    target = _resolve(env_file or LOCAL_ENV_NAME)
    if target.exists():
        load_dotenv(target, override=override)
        return target
    return None


# Load global settings once when the package is imported.
GLOBAL_ENV_FILE = load_global_settings()
if GLOBAL_ENV_FILE:
    print(f"已加载全局环境变量文件: {GLOBAL_ENV_FILE}")
