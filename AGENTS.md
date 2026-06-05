# AI Agent Entry Guide

本文件是仓库的**跨工具 AI 入口适配层**，不是规范正文。
统一规范源在 `docs/ai-standards/`，详细后端架构权威文档仍在 `docs/architecture/system-design.md`。

## Read Order

任何任务都先读：

1. `docs/ai-standards/index.md` — 规范地图与权威关系

然后根据任务类型按需补读下表对应的页面，**不要无差别地一次性读完所有标准页**。

## When To Read Which Standard

| 标准页 | 何时必须读 | 何时可以跳过 |
|---|---|---|
| `docs/ai-standards/index.md` | 任何任务开始时 | 永远不跳过 |
| `docs/ai-standards/architecture.md` | 新增/修改 `src/backend/` 下的模块、调整跨层依赖、新增 engine 或 infrastructure 实现、新增对外 HTTP/CLI 入口 | 只改 `frontend/`、文档、测试、构建脚本时 |
| `docs/architecture/system-design.md` | 开始**任何**新的后端功能、新增四层之间的契约、改动 composition root、新增独立服务边界 | 已经只是小范围 bugfix 或参数调整，不动层间契约时 |
| `docs/ai-standards/code-reuse.md` | **任何**新增或修改代码前；考虑提取 helper、判断是否复制粘贴、函数参数 ≥4 个、文件接近 500 行、运行 `just lint --reuse` 之前；交付前必须完成其中的 **AI 编码自检清单** | 纯文档排版或纯配置改动且无任何代码逻辑变更 |
| `docs/ai-standards/naming.md` | 新增 Python 变量、函数、类、模块；命名风格不确定时 | `tests/playwright-e2e/` 内的 TypeScript 改动 |
| `docs/ai-standards/comments-docstrings.md` | 新增/修改公共 Python API；写模块/类/函数 docstring；做文件 I/O 涉及编码问题 | 仅改私有实现细节且不涉及公共 docstring 时 |
| `docs/ai-standards/documentation.md` | 改动公共函数签名、配置项、业务流程；新增长期文档页；更新 `mkdocs.yml` 导航 | 纯内部重构且无对外行为或文档变化 |
| `docs/ai-standards/testing.md` | 准备验证策略；改动 API/CLI/前端流程/后台任务/持久化/启动或部署；写 PRD 的 Realistic Validation Plan | 仅改注释或纯文档排版 |
| `docs/ai-standards/tooling.md` | 选择运行命令；改 `justfile` / `pre-commit` / `mkdocs` / Docker 配置；处理 PRD 归档流程；处理 lint flag 或重复检测 hooks | 在已熟悉常用 `just` 命令、且本次不动工具链配置时 |

`tests/playwright-e2e/` 是独立 TypeScript/Node 包，遵循该目录自己的 `README.md`，不强制套用 Python 规范。

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

- 共享规范优先写入 `docs/ai-standards/`，不要把长篇规则重新复制回本文件
- 新增标准页时，同时在上方 **When To Read Which Standard** 表中加一行触发条件，保持入口可路由
