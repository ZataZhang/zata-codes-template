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

## Codex Session Workflow

在新的 Codex CLI 会话开始时：

1. 运行 `bash scripts/hooks/session-start.sh`
2. 把返回 JSON 中的 `result` 当作补充上下文
3. 这个动作每个 CLI 会话只做一次

如果需要显式跑开始/结束 hook，优先使用：

```bash
bash scripts/codex_session.sh
```

## Platform Notes

- Windows 下优先使用 PowerShell 语法
- 文本文件读写显式指定 UTF-8

## Playwright Exception

`tests/playwright-e2e/` 是 Node/TypeScript 包：

- 使用 `npm`
- 不使用 `uv`
- 运行方式遵循该目录自己的 `README.md`
