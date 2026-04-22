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
  `backend/apps/ -> backend/core/ -> backend/capabilities/ -> backend/infrastructure/`
- Python 项目优先使用 `uv` 和 `just`
- 公共 Python API 使用 Google Style Docstrings
- Python 文本文件 I/O 必须显式写 `encoding="utf-8"`
- 变量命名必须具有来源、类型或状态语义，避免 `data`、`item`、`res`
- 变更代码时同步更新 `docs/` 与 `mkdocs.yml`
- `tests/playwright-e2e/` 是独立 TypeScript/Node 包，使用 `npm`，不强制套用 Python SSA 命名规范

## Codex Session Workflow

- 新的 Codex CLI 会话开始时，先运行 `bash scripts/hooks/session-start.sh`
- 若需要显式 start/end hook，优先使用 `bash scripts/codex_session.sh`

## Maintenance Rule

共享规范优先写入 `docs/ai-standards/`，不要把长篇规则重新复制回本文件。
