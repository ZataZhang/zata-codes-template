# 文档一致性维护指南

## 概述

本项目使用多个配置文件来指导不同的AI工具使用。为了保证一致性，需要遵循以下维护规则。

## 相关文件

1. **`AGENTS.md`** - AI代理通用指南（中文）
2. **`CLAUDE.md`** - Claude Code专用指导（英文）
3. **`.cursor/commands/cursor.md`** - Cursor IDE配置

## 维护规则

### 1. 共同内容同步
以下内容在所有文件中必须保持一致：
- Python包管理规则（使用uv）
- 代码规范（Google Style文档字符串）
- Windows平台特定说明
- 开发优先级

### 2. 更新流程
当需要更新项目指导时：

1. **确定影响范围**：判断哪些文件需要更新
2. **同时更新所有相关文件**：不要只更新一个文件
3. **检查引用**：确保文件间的交叉引用仍然有效
4. **测试验证**：运行相关工具验证配置正确性

### 3. 文件特定内容
- **AGENTS.md**：保持通用性，避免工具特定内容
- **CLAUDE.md**：包含Claude Code特定的技术细节和已知问题
- **.cursor/commands/cursor.md**：只包含Cursor IDE相关配置

## 自动化检查

### 建议的检查脚本

可以创建一个简单的脚本来验证一致性：

```python
# scripts/check_guidelines_consistency.py
def check_consistency():
    """检查指导文件的一致性"""
    files = ['AGENTS.md', 'CLAUDE.md', '.cursor/commands/cursor.md']

    # 检查共同的关键短语是否存在
    required_phrases = [
        'uv', 'Google Style', 'Python 包管理', 'Package Management'
    ]

    for file in files:
        # 检查逻辑
        pass
```

### Pre-commit Hook
考虑添加pre-commit hook来检查文档一致性：

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-guidelines-consistency
        name: Check guidelines consistency
        entry: python scripts/check_guidelines_consistency.py
        language: system
        files: ^(AGENTS\.md|CLAUDE\.md|\.cursor/commands/cursor\.md)$
```

## 常见问题

### Q: 什么时候需要更新所有文件？
A: 当修改核心规则（如包管理方式、代码规范）时

### Q: 什么时候可以只更新一个文件？
A: 当添加工具特定的配置或示例时

### Q: 如何验证更新是否完整？
A: 运行 `uv run pre-commit run --all-files` 并检查所有相关文件

## 贡献指南

- 更新文档时，请在commit消息中明确说明更新的文件
- 如果不确定是否需要更新所有文件，请更新所有相关文件
- 新增AI工具支持时，请相应添加新的配置文件
