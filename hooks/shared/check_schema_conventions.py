#!/usr/bin/env python3
"""数据库 schema 约定检查。

当前仅覆盖 Alembic 迁移脚本约定：

- ``alembic/versions/`` 下 ``.py`` 迁移脚本的 ``revision`` 变量长度不得超过
  Alembic 默认 ``alembic_version.version_num`` 列宽（32 字符）。

SQLAlchemy 模型表/列备注检查已拆分到独立的
``hooks/shared/check_sqlalchemy_model_comments.py``，由 pre-commit hook
``check-sqlalchemy-model-comments`` 执行。这样每个检查项都是自包含脚本，便于
分发到不同目录结构的下游仓库。

通过 pre-commit 在本地提交前强制执行。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ALEMBIC_VERSIONS_DIR_RELPATH: Path = Path("alembic/versions")
"""被检查的 Alembic 迁移脚本目录相对项目根路径。"""

ALEMBIC_REVISION_PATTERN = re.compile(
    r'^\s*revision\s*(?::\s*\w+\s*)?=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)
"""匹配迁移文件中 ``revision = "..."`` / ``revision: str = "..."`` 的正则。"""


# ==========================================
# 1. 数据结构
# ==========================================


@dataclass(frozen=True)
class MigrationViolation:
    """单条迁移脚本违规记录。

    Attributes:
        file_path: 发生违规的文件路径。
        target: 违规的 revision ID。
        reason: 人类可读的违规原因描述。
    """

    file_path: Path
    target: str
    reason: str


@dataclass
class CheckResult:
    """检查汇总结果。

    Attributes:
        violations: 所有发现的违规列表。
        checked_files_count: 实际检查的文件数量。
    """

    violations: list[MigrationViolation] = field(default_factory=list)
    checked_files_count: int = 0

    @property
    def passed(self) -> bool:
        """是否全部通过（无违规）。"""
        return len(self.violations) == 0


# ==========================================
# 2. Alembic 迁移脚本检查
# ==========================================


def extract_revision_ids(file_path: Path) -> list[str]:
    """从单个 Alembic 迁移文件中提取所有 revision ID。

    Args:
        file_path: 迁移文件路径。

    Returns:
        提取到的 revision ID 列表。
    """
    content = file_path.read_text(encoding="utf-8")
    return ALEMBIC_REVISION_PATTERN.findall(content)


def check_alembic_migration_file(
    migration_file: Path,
    max_length: int = 32,
) -> list[MigrationViolation]:
    """检查单个 Alembic 迁移文件的 revision ID 长度。

    Args:
        migration_file: 迁移文件路径。
        max_length: revision ID 最大允许长度（默认 32）。

    Returns:
        违规记录列表。
    """
    file_violations: list[MigrationViolation] = []
    for revision_id in extract_revision_ids(migration_file):
        if len(revision_id) > max_length:
            file_violations.append(
                MigrationViolation(
                    file_path=migration_file,
                    target=revision_id,
                    reason=(
                        f"revision ID 长度为 {len(revision_id)}，"
                        f"超过 alembic_version.version_num 默认上限 {max_length}。"
                    ),
                )
            )
    return file_violations


def run_alembic_revision_check(
    versions_dir: Path,
    max_length: int = 32,
) -> CheckResult:
    """对整个 Alembic versions 目录执行 revision ID 长度检查。

    Args:
        versions_dir: Alembic versions 目录路径。
        max_length: revision ID 最大允许长度（默认 32）。

    Returns:
        检查汇总结果。
    """
    aggregated_result = CheckResult()
    if not versions_dir.exists():
        return aggregated_result

    for migration_file in sorted(versions_dir.glob("*.py")):
        aggregated_result.checked_files_count += 1
        file_violations = check_alembic_migration_file(migration_file, max_length)
        aggregated_result.violations.extend(file_violations)

    return aggregated_result


# ==========================================
# 3. 输出与入口
# ==========================================


def _format_report(check_result: CheckResult) -> str:
    """将检查结果格式化为可读报告。

    Args:
        check_result: 检查汇总结果。

    Returns:
        格式化后的报告字符串。
    """
    report_lines: list[str] = [
        f"\nAlembic 迁移约定检查 — 共扫描 {check_result.checked_files_count} 个文件\n"
    ]

    if check_result.passed:
        report_lines.append("✅ 无违规。")
        return "\n".join(report_lines)

    report_lines.append(f"❌ 发现 {len(check_result.violations)} 处违规：\n")
    for violation in check_result.violations:
        report_lines.append(
            f"  [alembic_revision] {violation.file_path.name} ({violation.target})\n"
            f"    {violation.reason}\n"
        )
    return "\n".join(report_lines)


def _resolve_dir(arg_value: Path) -> Path:
    """将命令行传入的目录解析为绝对路径。

    兼容 ``pre-commit`` 默认从仓库根目录运行以及直接在工作子树目录运行的两种场景。

    Args:
        arg_value: 命令行传入的目录路径（可能为相对路径）。

    Returns:
        解析后的绝对路径。
    """
    if arg_value.is_absolute():
        return arg_value

    candidate_paths: list[Path] = [Path.cwd() / arg_value]
    if Path.cwd().name == arg_value.name:
        candidate_paths.append(Path.cwd())
    for candidate in candidate_paths:
        if candidate.exists():
            return candidate
    return candidate_paths[0]


def _classify_migration_file(file_path: Path, versions_dir: Path) -> bool:
    """判断文件是否位于 Alembic versions 目录内。

    Args:
        file_path: 待判断文件路径。
        versions_dir: Alembic versions 目录绝对路径。

    Returns:
        文件属于 versions 目录则为 True。
    """
    try:
        file_path.resolve().relative_to(versions_dir.resolve())
        return True
    except ValueError:
        return False


def main(argv: Optional[list[str]] = None) -> int:
    """主入口：扫描 Alembic versions 目录或检查指定文件，返回退出码。"""
    parser = argparse.ArgumentParser(
        description="检查 Alembic 迁移脚本 schema 约定。",
    )
    parser.add_argument(
        "--alembic-versions-dir",
        type=Path,
        default=ALEMBIC_VERSIONS_DIR_RELPATH,
        help="Alembic versions 目录路径（默认：alembic/versions）。",
    )
    parser.add_argument(
        "--max-revision-length",
        type=int,
        default=32,
        help="revision ID 最大长度（默认：32）。",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="待检查的迁移文件路径；为空时扫描整个目录。",
    )
    args = parser.parse_args(argv)

    versions_dir = _resolve_dir(args.alembic_versions_dir)
    result = CheckResult()

    if args.files:
        for file_str in args.files:
            file_path = Path(file_str).resolve()
            if not file_path.is_file():
                continue
            if not _classify_migration_file(file_path, versions_dir):
                continue
            result.checked_files_count += 1
            result.violations.extend(
                check_alembic_migration_file(file_path, args.max_revision_length)
            )
    else:
        result = run_alembic_revision_check(versions_dir, args.max_revision_length)

    print(_format_report(result))

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
