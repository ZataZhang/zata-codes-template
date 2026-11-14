"""项目能力目录的模板分发契约测试。

这些断言只覆盖当前模板仓库的 ``project-capabilities/`` 与 copy/sync 入口；
派生项目没有这些模板维护内容，因此 ``just copy`` 与 template-sync 会排除此文件。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]


def test_project_capabilities_are_excluded_from_copy_and_skill_installation() -> None:
    """能力目录应能按路径读取，但不进入复制产物或根级 Skill 安装候选。"""
    project_capabilities_path = _PROJECT_ROOT_PATH / "project-capabilities"
    project_capabilities_skill_path = project_capabilities_path / "SKILL.md"
    justfile_text = (_PROJECT_ROOT_PATH / "justfile").read_text(encoding="utf-8")

    assert project_capabilities_skill_path.is_file()
    assert not (_PROJECT_ROOT_PATH / "skills/project-capabilities").exists()
    assert "--exclude='/project-capabilities'" in justfile_text
    assert "--exclude='/tests/test_project_capabilities_distribution.py'" in justfile_text
    assert "sync-local-skills:\n    ./scripts/sync_template.sh --local-skills" in justfile_text


def test_template_sync_list_excludes_project_capabilities() -> None:
    """template-sync 普通候选与 ``--all`` 均不得列出模板专用能力目录。"""
    sync_script_path = _PROJECT_ROOT_PATH / "scripts/sync_template.sh"
    completed_process = subprocess.run(
        [str(sync_script_path), "--list-all"],
        cwd=_PROJECT_ROOT_PATH,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )

    assert "project-capabilities" not in completed_process.stdout
    assert "tests/test_project_capabilities_distribution.py" not in completed_process.stdout
