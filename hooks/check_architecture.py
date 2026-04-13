#!/usr/bin/env python3
"""架构依赖方向检查脚本。

基于 docs/architecture/system-design.md 定义的四层规则，
检查项目内部模块的 import 方向是否合法。

层次（由外到内）：
    apps/ → core/ → capabilities/ → infrastructure/

依赖规则（只允许向内依赖）：
    - apps/           可以依赖: core
    - core/           可以依赖: （仅 core 内部的 shared/interfaces）
    - capabilities/       可以依赖: core, infrastructure
    - infrastructure/ 可以依赖: （仅外部第三方包）

禁止的方向：
    - infrastructure/ 不得 import core, capabilities, apps
    - core/           不得 import capabilities, infrastructure, apps
    - apps/           不得 import infrastructure, capabilities（直接依赖）
    - 任意层          不得反向依赖外层
"""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ==========================================
# 1. 架构规则定义
# ==========================================

LAYER_ORDER: list[str] = ["infrastructure", "capabilities", "core", "apps"]
"""层次从内到外的顺序，index 越大表示越外层。"""

FORBIDDEN_IMPORTS: dict[str, list[str]] = {
    "infrastructure": ["core", "capabilities", "apps"],
    "core": ["capabilities", "infrastructure", "apps"],
    "apps": ["infrastructure", "capabilities"],
    "capabilities": ["apps"],
}
"""每个层禁止 import 的其他层列表。"""

LEGACY_MODULES: set[str] = set()
"""迁移期兼容模块，不参与架构检查（见 system-design.md 迁移策略）。"""


@dataclass
class ArchitectureViolation:
    """单条架构违规记录。

    Attributes:
        file_path: 发生违规的文件路径。
        line_number: 违规 import 所在行号。
        source_layer: 来源层名称。
        forbidden_layer: 被禁止依赖的目标层名称。
        import_statement: 原始 import 语句文本。
    """

    file_path: Path
    line_number: int
    source_layer: str
    forbidden_layer: str
    import_statement: str


@dataclass
class CheckResult:
    """架构检查的汇总结果。

    Attributes:
        violations: 所有发现的违规列表。
        checked_files_count: 实际检查的文件数量。
    """

    violations: list[ArchitectureViolation] = field(default_factory=list)
    checked_files_count: int = 0

    @property
    def passed(self) -> bool:
        """是否全部通过（无违规）。"""
        return len(self.violations) == 0


# ==========================================
# 2. 核心检查逻辑
# ==========================================


def _resolve_layer(file_path: Path, project_root: Path) -> Optional[str]:
    """从文件路径推断所属的架构层名称。

    Args:
        file_path: 待检查的 Python 文件绝对路径。
        project_root: 项目根目录绝对路径。

    Returns:
        层名称字符串（如 "core"），或 None（不属于任何受管层）。
    """
    relative_path_str: str = str(file_path.relative_to(project_root))
    top_level_dir: str = relative_path_str.split("/")[0]

    if top_level_dir in LAYER_ORDER:
        return top_level_dir
    return None


def _extract_imported_modules(source_code: str) -> list[tuple[int, str]]:
    """从 Python 源码中提取所有 import 的顶层模块名。

    Args:
        source_code: Python 文件的完整源码文本。

    Returns:
        (行号, 顶层模块名) 的列表。
    """
    imported_module_entries: list[tuple[int, str]] = []

    try:
        parsed_ast_tree: ast.Module = ast.parse(source_code)
    except SyntaxError:
        return imported_module_entries

    for ast_node in ast.walk(parsed_ast_tree):
        if isinstance(ast_node, ast.Import):
            for alias in ast_node.names:
                top_level_module_name: str = alias.name.split(".")[0]
                imported_module_entries.append((ast_node.lineno, top_level_module_name))

        elif isinstance(ast_node, ast.ImportFrom):
            if ast_node.module and ast_node.level == 0:
                top_level_module_name = ast_node.module.split(".")[0]
                imported_module_entries.append((ast_node.lineno, top_level_module_name))

    return imported_module_entries


def _check_single_file(
    python_file: Path,
    project_root: Path,
) -> list[ArchitectureViolation]:
    """检查单个 Python 文件的 import 是否违反架构规则。

    Args:
        python_file: 待检查的 Python 文件路径。
        project_root: 项目根目录路径。

    Returns:
        该文件中发现的所有 ArchitectureViolation 列表。
    """
    file_violations: list[ArchitectureViolation] = []

    source_layer: Optional[str] = _resolve_layer(python_file, project_root)
    if source_layer is None:
        return file_violations

    forbidden_targets: list[str] = FORBIDDEN_IMPORTS.get(source_layer, [])
    if not forbidden_targets:
        return file_violations

    raw_source_code: str = python_file.read_text(encoding="utf-8")
    imported_module_entries: list[tuple[int, str]] = _extract_imported_modules(
        raw_source_code
    )

    for line_number, imported_module_name in imported_module_entries:
        if imported_module_name in forbidden_targets:
            raw_source_lines: list[str] = raw_source_code.splitlines()
            import_statement_text: str = raw_source_lines[line_number - 1].strip()

            single_violation: ArchitectureViolation = ArchitectureViolation(
                file_path=python_file,
                line_number=line_number,
                source_layer=source_layer,
                forbidden_layer=imported_module_name,
                import_statement=import_statement_text,
            )
            file_violations.append(single_violation)

    return file_violations


def run_architecture_check(project_root: Path) -> CheckResult:
    """对整个项目执行架构依赖方向检查。

    Args:
        project_root: 项目根目录路径。

    Returns:
        CheckResult 汇总对象，包含所有违规信息。
    """
    aggregated_check_result: CheckResult = CheckResult()

    for layer_name in LAYER_ORDER:
        layer_dir_path: Path = project_root / layer_name
        if not layer_dir_path.exists():
            continue

        for python_file_path in layer_dir_path.rglob("*.py"):
            aggregated_check_result.checked_files_count += 1
            file_violations: list[ArchitectureViolation] = _check_single_file(
                python_file_path, project_root
            )
            aggregated_check_result.violations.extend(file_violations)

    return aggregated_check_result


# ==========================================
# 3. 输出与入口
# ==========================================


def _format_report(check_result: CheckResult) -> str:
    """将检查结果格式化为可读报告。

    Args:
        check_result: run_architecture_check 返回的结果对象。

    Returns:
        格式化后的报告字符串。
    """
    report_lines: list[str] = [
        f"\n架构依赖检查 — 共扫描 {check_result.checked_files_count} 个文件\n"
    ]

    if check_result.passed:
        report_lines.append("✅ 架构依赖方向全部合法，无违规。")
        return "\n".join(report_lines)

    report_lines.append(f"❌ 发现 {len(check_result.violations)} 处违规：\n")

    for violation in check_result.violations:
        relative_file_path: str = str(violation.file_path).split("zata_code_template/")[
            -1
        ]
        report_lines.append(
            f"  [{violation.source_layer}] → [{violation.forbidden_layer}]  "
            f"{relative_file_path}:{violation.line_number}\n"
            f"    {violation.import_statement}\n"
        )

    report_lines.append("参考架构规则：docs/architecture/system-design.md")
    return "\n".join(report_lines)


def main() -> None:
    """主入口：执行架构检查并以退出码报告结果。"""
    project_root_path: Path = Path(__file__).parent.parent

    print("🔍 正在检查架构依赖方向...")
    final_check_result: CheckResult = run_architecture_check(project_root_path)
    formatted_report_str: str = _format_report(final_check_result)
    print(formatted_report_str)

    sys.exit(0 if final_check_result.passed else 1)


if __name__ == "__main__":
    main()
