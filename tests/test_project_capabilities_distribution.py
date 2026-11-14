"""项目能力目录的模板分发契约测试。

这些断言只覆盖当前模板仓库的 ``project-capabilities/`` 与 copy/sync 入口；
派生项目没有这些模板维护内容，因此 ``just copy`` 与 template-sync 会排除此文件。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("relative_path", "expected_exit_code"),
    [
        ("project-capabilities", 0),
        ("project-capabilities/components/object-storage-delivery/README.md", 0),
        ("tests/test_project_capabilities_distribution.py", 0),
        ("scripts/shared/template/sync_template.sh", 1),
    ],
)
def test_template_sync_filter_excludes_only_template_private_paths(
    relative_path: str, expected_exit_code: int
) -> None:
    """执行当前脚本的共享过滤器，同时验证排除项与正常共享路径。"""
    sync_script_path = _PROJECT_ROOT_PATH / "scripts/shared/template/sync_template.sh"
    sync_script_text = sync_script_path.read_text(encoding="utf-8")
    filter_function_match = re.search(
        r"^_is_always_skipped\(\) \{\n.*?^\}", sync_script_text, re.MULTILINE | re.DOTALL
    )
    assert filter_function_match is not None
    filter_command = filter_function_match.group(0) + '\n_is_always_skipped "$1"'
    completed_process = subprocess.run(
        ["bash", "-c", filter_command, "sync-filter-test", relative_path],
        cwd=_PROJECT_ROOT_PATH,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        timeout=5,
    )

    assert completed_process.returncode == expected_exit_code, completed_process.stderr
