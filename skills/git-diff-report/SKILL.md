---
name: git-diff-report
description: "[Updated 2026-09-20] Render git changes into a self-contained HTML report: a collapsible file tree on the left with per-file summaries and +/− counts, and the full highlighted diff on the right, with click-to-jump and scroll sync. Use when the user asks to 展示当前改动, 看改了什么, 生成改动预览页, 改动可视化, diff 报告, or wants a reviewable HTML overview of a working tree, branch diff, or staged changes."
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Write
---

# Git Diff Report

## Overview

把「当前代码改了什么」变成一份可以直接看、可以直接发出去的 HTML 报告：

- **左侧**：可折叠的改动文件树，每个文件带 `+N -M` 统计与一句话中文总结，点击跳转、滚动联动高亮；
- **右侧**：全部文件的完整高亮 diff，逐 hunk 展开，可一路下滑；
- 单文件、无外部依赖（CSS/JS 全内联），可直接发给他人或用浏览器打开。

报告只是**只读视图**：它不修改被检查的仓库，也不产生提交。

## Hard Boundaries

未经当前对话明确指示，绝不做：

- `git add` / `git commit` / `git push`，或任何 ref 变更；
- 为了让报告"更好看"而改动、暂存、丢弃仓库里的代码；
- 把报告写进被检查的仓库（默认输出到 `/tmp`）。

## Workflow

### 1. 确定范围

先跑 `git status --porcelain` 和 `git rev-parse --abbrev-ref HEAD`，判断改动落在哪里，再选 `--scope`：

| 场景 | `--scope` | 说明 |
|---|---|---|
| 已 `git add` 的改动 | `staged` | 只看暂存区 |
| 还没暂存的改动 | `unstaged` | 只看工作区 |
| 「当前改了什么」的默认口径 | `head` | 暂存 + 未暂存合并（**默认**） |
| 整条分支相对基线的改动 | `range --base origin/main` | `<base>...HEAD` |

范围有歧义且影响结论时才问用户；否则默认 `head`。

### 2. 确定排除面

默认排除 `tests/**` 与 `**/tests/**`（后者覆盖 `frontend-public/tests/` 这类嵌套测试目录），让报告聚焦生产代码。用户想看测试改动时加 `--include-tests`；还有其他要排除的路径就用 `--exclude '<glob>'` 追加（例如 `--exclude 'docs/**' --exclude '*.lock'`）——`--exclude` 是**追加**，不会顶掉默认的测试排除，`--include-tests` 也只关掉默认那两条。

报告里出现的排除项会写在左上角环境行，不要让读者猜。

### 3. 写摘要（关键步骤）

先渲染一份不带摘要的报告，或先读 diff，然后**自己写**每文件一句话总结与每个 hunk 的短标题，落成一个 JSON：

```json
{
  "title": "keda 工作区改动",
  "meta_line": "分支 main · 已暂存改动 · 已排除 tests/**",
  "files": {
    "src/backend/core/use_cases/repository_registry.py": {
      "summary": "新增 remove_registry_repository()：只删条目并返回被删条目视图；新增 _find_entry_by_path() 校验同一路径不被多个 repo_id 占用。",
      "hunk_notes": ["更新模块不变量说明", "新增 _find_entry_by_path", "add 时增加路径占用校验"]
    }
  }
}
```

写法要求：

- `summary` 一句话讲清「**做了什么 + 对谁有影响/为什么**」，按文件聚合，不要逐 hunk 复述；长度控制在一到三句，保证左侧树里能直接读完。
- `hunk_notes` 与文件中 hunk 的**出现顺序一一对应**，短句（10–20 字）即可；某个 hunk 不值得说就放空字符串。数量不足时后面自动留空，多出的忽略。
- 语言跟随仓库约定（读了 `AGENTS.md` 就照它来），默认中文；专有名词、标识符保持原文。
- 不编造 diff 里没有的动机。看不出来就写事实（"拆出 X 以便复用"→ 只在 diff 确实体现复用时才这么写）。
- 不要给测试文件写摘要（它们通常已被排除）；被排除的文件不出现在报告里，写了也不会生效。

### 4. 渲染

```bash
python3 scripts/render_diff_report.py \
  --repo <repo-root> \
  --scope staged \
  --summaries /tmp/<repo>-summaries.json \
  --title "<仓库名> 改动报告" \
  --open
```

不带 `--summaries` 也能出报告，只是左侧没有总结文字。

### 5. 自检

生成后至少确认两点，别直接甩给用户：

1. **无 JS 报错、无截断**：能用 Playwright 时跑一次裸检查（下面的片段可直接用）；否则至少确认文件非空、`grep -c 'class="file-row"'` 与改动文件数一致。
2. **数量对齐**：`git diff <同参数> --stat` 的文件数应与报告 `N 个文件` 一致；不一致说明排除规则或 scope 选错了。

```javascript
// 在装有 playwright 的目录执行：node check.mjs
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1500, height: 1150 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto('file:///tmp/<repo>-diff-report.html');
await p.waitForTimeout(500);
const clipped = await p.$$eval('.file-row:not(.active) .file-summary',
  els => els.filter(e => e.scrollHeight > e.clientHeight + 1).length);
console.log('errors:', errs, 'clipped:', clipped);
await b.close();
```

`clipped > 0` 说明总结被截断——是总结太长，不是页面坏了，把 `summary` 压短。

## Script Reference

`scripts/render_diff_report.py`（仅用标准库，可直接 `python3` 运行）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--repo PATH` | 当前工作目录回溯 | 仓库根目录 |
| `--scope {staged,unstaged,head,range}` | `head` | diff 范围 |
| `--base REV` | — | `--scope range` 必填，取 `<base>...HEAD` |
| `--exclude GLOB` | `tests/**`、`**/tests/**` | **追加**排除项，可重复；给 glob，脚本自动转成 `:(exclude)` pathspec |
| `--include-tests` | 关 | 只关掉默认的两条测试排除，用户 `--exclude` 仍生效 |
| `--summaries FILE` | — | 摘要 JSON（上面的 schema） |
| `--title TEXT` | `<仓库名> 改动报告` | 页面标题 |
| `--out FILE` | `/tmp/<repo>-diff-report.html` | 输出路径 |
| `--open` | 关 | 生成后用系统默认浏览器打开（macOS `open` / Linux `xdg-open`） |

脚本内部按 `scope` 直接调用 `git diff`，报告里的增删行数、文件树、diff 内容都来自 git 输出，不做二次推断。

## 已知边界

- 路径名含空格/非 ASCII 时依赖 git 的引号转义解析，已在脚本内处理；极端命名（含换行）不支持。
- 纯重命名、模式变更、二进制文件没有 hunk，右侧显示"无内容变更"提示；左侧仍计入文件数与 `+0 -0`。
- 报告体积随 diff 大小线性增长。改动超过约 5000 行时建议先收窄 `--scope` 或加 `--exclude`，否则浏览器内滚动体验会下降。
