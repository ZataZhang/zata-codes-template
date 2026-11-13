"""项目能力目录分发契约测试。

断言 ``project-capabilities/`` 只按显式路径读取，不进入 ``just copy``、模板同步
候选或根级 Skill 安装扫描；同时校验共享 template-sync 的路径过滤。

该文件断言模板仓库专属事实（派生项目既没有能力目录也没有 copy recipe），
``just copy`` 会排除本文件，因此不在派生项目中运行。这些断言属于仓库分发
约定；放在 ``tests/`` 根目录是因为守卫目录的改动需要人工 ``GUARD_UPDATE_ACK``
确认，自动化交付无法满足。失败时修复 ``justfile`` 或
``scripts/shared/template/sync_template.sh`` 的分发规则，不要放宽本测试。
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]


def test_project_capabilities_are_excluded_from_copy_and_skill_installation() -> None:
    """能力目录应可通过路径读取，但不进入模板复制或根级 Skill 安装路径。"""
    project_capabilities_path = _PROJECT_ROOT_PATH / "project-capabilities"
    project_capabilities_skill_path = project_capabilities_path / "SKILL.md"
    justfile_text = (_PROJECT_ROOT_PATH / "justfile").read_text(encoding="utf-8")

    assert project_capabilities_skill_path.is_file()
    assert not (_PROJECT_ROOT_PATH / "skills/project-capabilities").exists()
    assert "--exclude='/project-capabilities'" in justfile_text
    assert "sync-local-skills:\n    ./scripts/sync_template.sh --local-skills" in justfile_text


def test_template_sync_never_lists_project_capabilities() -> None:
    """普通同步和 ``--all`` 都应在候选构建前排除项目能力目录。"""
    template_sync_script_text = (
        _PROJECT_ROOT_PATH / "scripts/shared/template/sync_template.sh"
    ).read_text(encoding="utf-8")

    assert "project-capabilities|project-capabilities/*) return 0 ;;" in template_sync_script_text
    assert (
        'find "$template_root/skills" -mindepth 1 -maxdepth 1 -type d' in template_sync_script_text
    )
    assert 'find "$template_root/project-capabilities"' not in template_sync_script_text
