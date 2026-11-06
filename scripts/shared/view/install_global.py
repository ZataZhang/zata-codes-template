"""把 ``zview`` 安装为当前用户可从任意目录调用的命令。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    """在用户 PATH 目录中创建指向模板查看器入口的符号链接。

    Returns:
        int: 安装成功或已安装时返回 0，目标路径冲突或平台不支持时返回 1。
    """
    if os.name == "nt":
        print("全局 zview 安装目前支持 macOS 和 Linux。", file=sys.stderr)
        return 1

    viewer_script_path = Path(__file__).resolve().with_name("zview")
    user_bin_directory = Path.home() / ".local" / "bin"
    installed_command_path = user_bin_directory / "zview"
    user_bin_directory.mkdir(parents=True, exist_ok=True)

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
    if str(user_bin_directory) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"请将 {user_bin_directory} 加入 PATH 后再调用 zview。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
