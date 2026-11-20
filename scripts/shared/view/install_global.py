"""把 ``zview`` 安装为当前用户可从任意目录调用的命令。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Windows 没有免管理员权限的符号链接，也不认 ``zview`` 这份 POSIX shell 入口，因此改为
#: 生成一份等价的 ``zview.cmd``：项目 venv 可用时以 ``-S`` 直接启动入口，否则退回 ``uv run``。
_WINDOWS_COMMAND_TEMPLATE = """@echo off
setlocal
if exist "{project_python}" (
  "{project_python}" -S "{launch_script}" --global %*
) else (
  uv run --project "{project_directory}" --no-sync python "{launch_script}" --global %*
)
"""


def main() -> int:
    """在用户 PATH 目录中安装指向模板查看器入口的 ``zview`` 命令。

    macOS 与 Linux 创建符号链接，Windows 生成 ``zview.cmd``。

    Returns:
        int: 安装成功或已安装时返回 0，目标路径冲突时返回 1。
    """
    user_bin_directory = Path.home() / ".local" / "bin"
    user_bin_directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        exit_code = _install_windows_command(user_bin_directory)
    else:
        exit_code = _install_symlink(user_bin_directory)
    if exit_code == 0 and str(user_bin_directory) not in os.environ.get("PATH", "").split(
        os.pathsep
    ):
        print(f"请将 {user_bin_directory} 加入 PATH 后再调用 zview。")
    return exit_code


def _install_windows_command(user_bin_directory: Path) -> int:
    """在 Windows 上生成转发到 ``launch.py`` 的 ``zview.cmd``。

    Args:
        user_bin_directory (Path): 用户级命令目录。

    Returns:
        int: 安装成功或已安装时返回 0，已有其他同名文件时返回 1。
    """
    view_scripts_directory = Path(__file__).resolve().parent
    project_directory = view_scripts_directory.parents[2]
    # cmd.exe 按 OEM 代码页解析批处理文件；用 UTF-8 写入会让含非 ASCII 字符的路径失效。
    command_file_bytes = (
        _WINDOWS_COMMAND_TEMPLATE.format(
            project_python=project_directory / ".venv" / "Scripts" / "python.exe",
            launch_script=view_scripts_directory / "launch.py",
            project_directory=project_directory,
        )
        .replace("\n", "\r\n")
        .encode("oem")
    )
    installed_command_path = user_bin_directory / "zview.cmd"

    if installed_command_path.exists():
        if installed_command_path.read_bytes() == command_file_bytes:
            print(f"zview 已安装：{installed_command_path}")
            return 0
        print(f"拒绝覆盖已有文件：{installed_command_path}", file=sys.stderr)
        return 1

    installed_command_path.write_bytes(command_file_bytes)
    print(f"已安装 zview：{installed_command_path}")
    return 0


def _install_symlink(user_bin_directory: Path) -> int:
    """在 macOS 与 Linux 上创建指向 ``zview`` 入口脚本的符号链接。

    Args:
        user_bin_directory (Path): 用户级命令目录。

    Returns:
        int: 安装成功或已安装时返回 0，目标路径冲突时返回 1。
    """
    viewer_script_path = Path(__file__).resolve().with_name("zview")
    installed_command_path = user_bin_directory / "zview"

    if installed_command_path.is_symlink():
        if installed_command_path.resolve() == viewer_script_path:
            print(f"zview 已安装：{installed_command_path}")
            return 0
        print(
            f"拒绝覆盖已有的 zview 符号链接：{installed_command_path}",
            file=sys.stderr,
        )
        return 1
    if installed_command_path.exists():
        print(f"拒绝覆盖已有文件：{installed_command_path}", file=sys.stderr)
        return 1

    installed_command_path.symlink_to(viewer_script_path)
    print(f"已安装 zview：{installed_command_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
