"""守护新 worktree 初始化 git submodule 的守卫测试（guard test）。

本文件位于 ``tests/guards/shared/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

被测对象：``scripts/shared/worktree/create.sh`` 的 ``init_worktree_submodules``。核心不变量：

1. **含 ``.gitmodules`` 的仓库，新 worktree 必须检出 submodule。** ``git worktree add``
   不会检出 submodule；目录为空时前端包管理器会把 ``file:`` 依赖当成空包并改写锁文件，
   构建也会失败。
2. **没有 ``.gitmodules`` 时是无操作**，不得因此让 worktree 创建失败。
3. **``WORKTREE_SKIP_SUBMODULES=true`` 跳过初始化并成功返回。**
4. **初始化失败必须返回非零并给出可操作的提示**，不得静默继续安装依赖。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_CREATE_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "shared" / "worktree" / "create.sh"
)
# 本地 file:// submodule 默认被 git 安全策略禁止，测试内显式放行。
_ALLOW_FILE_PROTOCOL_ENV = {
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
}


def _run_git(repo_path: Path, *git_args: str) -> subprocess.CompletedProcess[str]:
    """在指定目录执行 git 命令并返回结果。"""
    return subprocess.run(
        ["git", *git_args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **_ALLOW_FILE_PROTOCOL_ENV},
    )


def _init_repo(repo_path: Path, file_name: str) -> Path:
    """初始化一个含单个文件与一次提交的真实 git 仓库。"""
    repo_path.mkdir(parents=True, exist_ok=True)
    _run_git(repo_path, "init", "-b", "main")
    _run_git(repo_path, "config", "user.email", "guard@example.com")
    _run_git(repo_path, "config", "user.name", "guard-test")
    (repo_path / file_name).write_text("fixture\n", encoding="utf-8")
    _run_git(repo_path, "add", ".")
    _run_git(repo_path, "commit", "-m", "init")
    return repo_path


def _init_main_repo_with_submodule(tmp_path: Path) -> Path:
    """初始化带一个 submodule 的主仓库。"""
    submodule_source_path = _init_repo(tmp_path / "design-system", "package.json")
    main_repo_path = _init_repo(tmp_path / "app", "README.md")
    _run_git(main_repo_path, "submodule", "add", str(submodule_source_path), "vendor/design-system")
    _run_git(main_repo_path, "add", ".")
    _run_git(main_repo_path, "commit", "-m", "add submodule")
    return main_repo_path


def _add_worktree(main_repo_path: Path) -> Path:
    """按普通 ``git worktree add`` 创建 worktree，此时 submodule 目录为空。"""
    worktree_path = main_repo_path.parent / "app-worktrees" / "feature"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _run_git(main_repo_path, "worktree", "add", "-b", "feature", str(worktree_path))
    return worktree_path


def _run_init_submodules(
    worktree_path: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """在子 shell 中 source ``create.sh`` 后调用 ``init_worktree_submodules``。"""
    return subprocess.run(
        [
            "/bin/bash",
            "-c",
            'source "$1" && init_worktree_submodules "$2"',
            "guard",
            str(_CREATE_SCRIPT_PATH),
            str(worktree_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **_ALLOW_FILE_PROTOCOL_ENV, **(extra_env or {})},
    )


def test_new_worktree_checks_out_submodules(tmp_path: Path) -> None:
    """含 .gitmodules 时，新 worktree 的 submodule 目录被检出。"""
    worktree_path = _add_worktree(_init_main_repo_with_submodule(tmp_path))
    submodule_file_path = worktree_path / "vendor" / "design-system" / "package.json"
    assert not submodule_file_path.exists()

    init_result = _run_init_submodules(worktree_path)

    assert init_result.returncode == 0, init_result.stdout + init_result.stderr
    assert submodule_file_path.exists()


def test_repo_without_gitmodules_is_noop(tmp_path: Path) -> None:
    """没有 .gitmodules 的仓库直接成功返回，不输出初始化提示。"""
    main_repo_path = _init_repo(tmp_path / "app", "README.md")
    worktree_path = _add_worktree(main_repo_path)

    init_result = _run_init_submodules(worktree_path)

    assert init_result.returncode == 0
    assert "submodule" not in init_result.stdout


def test_skip_env_leaves_submodule_empty(tmp_path: Path) -> None:
    """WORKTREE_SKIP_SUBMODULES=true 时跳过初始化并成功返回。"""
    worktree_path = _add_worktree(_init_main_repo_with_submodule(tmp_path))

    init_result = _run_init_submodules(worktree_path, {"WORKTREE_SKIP_SUBMODULES": "true"})

    assert init_result.returncode == 0
    assert "WORKTREE_SKIP_SUBMODULES=true" in init_result.stdout
    assert not (worktree_path / "vendor" / "design-system" / "package.json").exists()


def test_unreachable_submodule_fails_with_hint(tmp_path: Path) -> None:
    """submodule 无法获取时返回非零，并提示检查权限或跳过。"""
    worktree_path = _add_worktree(_init_main_repo_with_submodule(tmp_path))
    # 删除 submodule 源仓库，模拟远端不可达或无访问权限。
    shutil.rmtree(tmp_path / "design-system")

    init_result = _run_init_submodules(worktree_path)

    assert init_result.returncode != 0
    assert "WORKTREE_SKIP_SUBMODULES=true" in init_result.stdout
