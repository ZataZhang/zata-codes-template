#!/usr/bin/env python3
"""
检查指导文件一致性的脚本。

此脚本验证AGENTS.md、CLAUDE.md和.cursor/commands/cursor.md
之间的关键内容是否保持一致。
"""

import sys
from pathlib import Path


class GuidelinesChecker:
    """指导文件一致性检查器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.files = {
            "agents": project_root / "AGENTS.md",
            "claude": project_root / "CLAUDE.md",
            "cursor": project_root / ".cursor" / "commands" / "cursor.md",
        }

    def check_files_exist(self) -> bool:
        """检查所有指导文件是否存在"""
        missing_files = []
        for name, path in self.files.items():
            if not path.exists():
                missing_files.append(f"{name}: {path}")

        if missing_files:
            print("❌ 缺少以下文件:")
            for file in missing_files:
                print(f"   {file}")
            return False

        print("✅ 所有指导文件都存在")
        return True

    def check_required_content(self) -> bool:
        """检查必需的内容是否存在"""
        required_phrases = {
            "uv": ["uv", "uv run", "uv add", "uv sync"],
            "google_style": ["Google Style", "Google-style", "文档字符串"],
            "python_package": ["Python 包管理", "Package Management"],
        }

        issues = []

        for file_name, file_path in self.files.items():
            try:
                content = file_path.read_text(encoding="utf-8").lower()

                for category, phrases in required_phrases.items():
                    found = any(phrase.lower() in content for phrase in phrases)
                    if not found:
                        issues.append(f"{file_name} 缺少 {category} 相关内容")

            except Exception as e:
                issues.append(f"读取 {file_name} 时出错: {e}")

        if issues:
            print("❌ 内容一致性问题:")
            for issue in issues:
                print(f"   {issue}")
            return False

        print("✅ 所有文件都包含必需的内容")
        return True

    def check_cross_references(self) -> bool:
        """检查文件间的交叉引用"""
        issues = []

        # 检查AGENTS.md是否被其他文件引用
        claude_content = self.files["claude"].read_text(encoding="utf-8")
        cursor_content = self.files["cursor"].read_text(encoding="utf-8")

        if "AGENTS.md" not in claude_content:
            issues.append("CLAUDE.md 应该引用 AGENTS.md")

        if "AGENTS.md" not in cursor_content and "AGENTS.md" not in cursor_content:
            issues.append("cursor.md 应该引用 AGENTS.md 或 CLAUDE.md")

        if issues:
            print("❌ 交叉引用问题:")
            for issue in issues:
                print(f"   {issue}")
            return False

        print("✅ 交叉引用正确")
        return True

    def run_all_checks(self) -> bool:
        """运行所有检查"""
        print("🔍 检查指导文件一致性...\n")

        checks = [
            self.check_files_exist,
            self.check_required_content,
            self.check_cross_references,
        ]

        all_passed = True
        for check in checks:
            if not check():
                all_passed = False
            print()

        if all_passed:
            print("🎉 所有检查通过！指导文件保持一致。")
        else:
            print("⚠️  发现一致性问题，请根据上述报告修复。")

        return all_passed


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    checker = GuidelinesChecker(project_root)
    success = checker.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
