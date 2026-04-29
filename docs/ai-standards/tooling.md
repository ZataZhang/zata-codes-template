# Tooling Standards

## Preferred Tools

### Python

- 包管理：`uv`
- 任务入口：`just`
- 文档：`mkdocs`

优先顺序：

- 用 `uv` 代替 `pip` / `conda`
- 用 `just` 代替手工记忆零散命令

## Common Commands

| Command | Purpose |
|---|---|
| `just sync` | 同步开发依赖 |
| `just run` | 运行主应用 |
| `just test` | 运行本地测试 |
| `uv run mkdocs build` | 验证文档站点 |
| `just docs-serve` | 本地预览文档 |

## PRD Workflow Hooks

本仓库通过 `pre-commit` 维护 PRD 交付状态：

- `tasks/pending/` 下的 PRD 可以保留未完成验收项
- `tasks/` 根目录下的 active PRD 必须完成 `Acceptance Checklist`
- 新增、复制或重命名进入 `tasks/archive/` 的 PRD 也必须完成验收清单
- 已存在的历史 archive PRD 不会因为普通修改被重新套用新规则
- 验收清单标题支持英文 `Acceptance Checklist`、中文 `验收清单` 和双语标题

这条规则的目标是让“归档”代表交付完成，同时避免历史归档文档被新标准批量翻旧账。

## Codex Session Workflow

在新的 Codex CLI 会话开始时：

1. 运行 `bash scripts/hooks/session-start.sh`
2. 把返回 JSON 中的 `result` 当作补充上下文
3. 这个动作每个 CLI 会话只做一次

如果需要显式跑开始/结束 hook，优先使用：

```bash
bash scripts/codex_session.sh
```

### Codex macOS 通知

macOS 用户可以把 Codex CLI 的 `notify` 事件转发到系统快捷指令：

```bash
just codex-notify install codex通知
just codex-notify test codex通知
```

该能力会把顶层 `notify` 写入 `~/.codex/config.toml`，并在 Codex 完成 `agent-turn-complete` 事件时调用 macOS 快捷指令，快捷指令输入中包含当前任务仓库名和当前 Git 分支。详细步骤见 `docs/guides/codex-notifications.md`。

## Platform Notes

- Windows 下优先使用 PowerShell 语法
- 文本文件读写显式指定 UTF-8

## Playwright Exception

`tests/playwright-e2e/` 是 Node/TypeScript 包：

- 使用 `npm`
- 不使用 `uv`
- 运行方式遵循该目录自己的 `README.md`
