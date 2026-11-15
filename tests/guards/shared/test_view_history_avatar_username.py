"""守护 Git Log 作者头像的 GitHub 登录名解析（guard test）。

本文件位于 ``tests/guards/shared/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

被测对象：``scripts/shared/view/history.py``。核心不变量：

1. **只能从 GitHub 的 noreply 地址取登录名。** 普通邮箱里没有可验证的账号信息，
   猜一个名字会把头像指向别人。
2. **新旧两种 noreply 格式都要认。** ``1234+login@users.noreply.github.com`` 与
   ``login@users.noreply.github.com`` 都还在被使用。
3. **域名必须整段匹配。** ``login@users.noreply.github.com.evil.example`` 这类相似域名
   不能通过，否则一条恶意提交就能让查看器去请求任意主机。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VIEW_DIRECTORY = PROJECT_ROOT / "scripts" / "shared" / "view"
if str(VIEW_DIRECTORY) not in sys.path:
    # history.py 以同级模块方式导入 workspace，需要先把查看器目录放进导入路径。
    sys.path.insert(0, str(VIEW_DIRECTORY))

import history  # noqa: E402  （必须在上面的 sys.path 调整之后导入）


@pytest.mark.parametrize(
    ("author_email", "expected_username"),
    [
        ("57862134+ZataZhang@users.noreply.github.com", "ZataZhang"),
        ("ZataZhang@users.noreply.github.com", "ZataZhang"),
        ("57862134+some-user@users.noreply.github.com", "some-user"),
        ("ZataZhang@USERS.NOREPLY.GITHUB.COM", "ZataZhang"),
    ],
)
def test_noreply_email_yields_github_username(author_email: str, expected_username: str) -> None:
    """新旧两种 noreply 格式都必须解出登录名，域名大小写不影响结果。"""
    assert history._read_author_github_username(author_email) == expected_username


@pytest.mark.parametrize(
    "author_email",
    [
        "",
        "zata@example.com",
        "zata@users.noreply.github.com.evil.example",
        "zata@notusers.noreply.github.com",
        "zata",
    ],
)
def test_non_noreply_email_yields_empty_username(author_email: str) -> None:
    """没有可信登录名时返回空串，让界面退回按名字生成的方块头像。"""
    assert history._read_author_github_username(author_email) == ""
