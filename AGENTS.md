# AI Agent Entry Guide

本文件是仓库的**跨工具 AI 入口适配层**。

统一规范源在：

- `docs/ai-standards/index.md`
- `docs/ai-standards/architecture.md`
- `docs/ai-standards/naming.md`
- `docs/ai-standards/comments-docstrings.md`
- `docs/ai-standards/documentation.md`
- `docs/ai-standards/testing.md`
- `docs/ai-standards/tooling.md`

详细后端架构权威文档仍在：

- `docs/architecture/system-design.md`

## Read Order

1. 先读 `docs/ai-standards/index.md`
2. 若涉及后端新功能，再读 `docs/architecture/system-design.md`
3. 根据任务类型补读对应标准页

## Critical Summary

- 后端必须遵守四层依赖方向：
  `src/backend/api/ -> src/backend/core/ -> src/backend/engines/ -> src/backend/infrastructure/`
- Python 项目优先使用 `uv` 和 `just`
- 公共 Python API 使用 Google Style Docstrings
- Python 文本文件 I/O 必须显式写 `encoding="utf-8"`
- 变量命名必须具有来源、类型或状态语义，避免 `data`、`item`、`res`
- 新增或修改代码前先搜索现有实现；禁止复制粘贴后微调，参数超过 4 个时收敛到对象
- 除非用户明确要求，否则不要自动执行 `git add`、`git commit`、`git push` 等 Git 变更操作
- 单代码文件非空行不超过 1000 行；`just lint` 会对此发出警告
- PRD 对应任务全部完成后：将已完成项打勾，所有 Acceptance Checklist 条目达到完成态后，再将 PRD 从 `tasks/pending/` 归档到 `tasks/archive/`
- PRD 必须包含 Realistic Validation Plan，验收清单需覆盖最高可行保真度的真实入口验证，或说明无可执行行为变更
- 变更代码时同步更新 `docs/` 与 `mkdocs.yml`
- `tests/playwright-e2e/` 是独立 TypeScript/Node 包，使用 `npm`，不强制套用 Python SSA 命名规范

## Maintenance Rule

共享规范优先写入 `docs/ai-standards/`，不要把长篇规则重新复制回本文件。
