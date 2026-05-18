# PRD: Add .dockerignore, code-reuse consistency check, and CI max-file-lines sync

## Description

从 vanta-dev 模板项目同步缺失项到当前模板：

1. `.dockerignore` — 生产 Docker 构建时应排除的非代码文件列表（git、venv、cache、docs、tests 等），当前模板完全缺失。
2. `hooks/check_guidelines_consistency.py` 中的 `code_reuse` 校验 — 当前校验字典缺少对 `docs/ai-standards/code-reuse.md` 的关键词覆盖检查，导致该规范页的内容变化不会被一致性检查发现。
3. `cd.yml` 中添加 `check_max_file_lines.py` hard limit 步骤 — ci.yml 已有该步骤，cd.yml 缺失，导致 release 构建路径缺少文件行数硬限制检查。

## Acceptance Checklist

- [x] 在模板根目录创建 `.dockerignore`，内容从 vanta-dev 拷贝并适配路径（无路径需要修改）
- [x] `hooks/check_guidelines_consistency.py` 的 `hub_files` 字典中添加 `code_reuse` 条目指向 `docs/ai-standards/code-reuse.md`
- [x] `check_hub_content` 的 `required_phrases` 中添加 `code_reuse` 关键词检查：`["复用优先", "参数游行", "AI 编码自检清单"]`
- [x] `check_hub_content` 的 index 关键词列表中追加 `"code-reuse.md"`，确保 index.md 也引用该标准页
- [x] 在 `cd.yml` 的 pre-commit checks 之后、test suite 之前添加 `Check max file lines (hard limit)` 步骤
- [x] 运行 `uv run python hooks/check_guidelines_consistency.py` 验证全部检查通过
- [x] 运行 `just lint` 验证 pre-commit 无报错（`check-test-flag` 失败是已有过期标记，非本次改动引入）
