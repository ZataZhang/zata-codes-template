---
name: git-diff-report
description: "[Updated 2026-09-23] Render git changes into a self-contained HTML report: a collapsible file tree on the left with per-file summaries and +/− counts, a dedicated panel for renamed/moved files (old path → new path + similarity), and the full highlighted diff on the right, with click-to-jump and scroll sync. Use when the user asks to 展示当前改动, 看改了什么, 生成改动预览页, 改动可视化, diff 报告, or wants a reviewable HTML overview of a working tree, branch diff, or staged changes."
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
- **左侧顶部**：有重命名（`git mv`）时自动出现「文件移动」汇总面板，逐条列出 `← 旧路径` / `→ 新路径` 与相似度，可点击跳转——纯搬迁类改动一眼能看清搬了什么；
- **右侧**：全部文件的完整高亮 diff，逐 hunk 展开，可一路下滑；重命名文件在 diff 顶部显示移动横幅，而不是原来那行低对比度的灰色元信息；
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

### 4. 渲染并自动打开

报告生成后必须自动调用系统默认浏览器打开，命令始终带 `--open`。生成成功后确认报告路径；打开器不可用或打开失败时，明确告知用户并提供 HTML 文件路径。

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

生成后至少确认三点，别直接甩给用户：

1. **无 JS 报错、无截断**：能用 Playwright 时跑一次裸检查（下面的片段可直接用）；否则至少确认文件非空、`grep -c 'node file-row'` 与改动文件数一致（注意 class 是 `node file-row`，不是 `file-row`）。
2. **数量对齐**：`git diff <同参数> --stat` 的文件数应与报告 `N 个文件` 一致；不一致说明排除规则或 scope 选错了。
3. **移动数量对齐**：有重命名时，报告「文件移动」面板里的条数应与 `git diff <同参数> --name-status -M | grep -c '^R'` 一致；条数为 0 但确实搬过文件，通常是 `--exclude` 排掉了重命名的某一侧路径（见「已知边界」）。

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
| `--open` | 关 | 生成后用系统默认浏览器打开（macOS `open` / Linux `xdg-open`）；本技能每次生成报告都必须传入 |

脚本内部按 `scope` 直接调用 `git diff`，报告里的增删行数、文件树、diff 内容都来自 git 输出，不做二次推断。

## 已知边界

- 路径名含空格、非 ASCII 或引号时都能解析出**完整**的仓库相对路径：git 只为特殊字符加引号，含空格的路径还会在 token 末尾补一个 TAB 终止符，两种写法都按 git 的实际输出处理。`--summaries` 的键要写真实路径（含空格、中文就照原样写），脚本按解析出的路径查表，写错一个字符那条总结就会静默丢失。含换行的极端命名能解析出来，但显示时会折行，不专门支持。
- 仓库尚无提交（`git init` 之后、首次提交之前）也能出报告：`head` 退化为索引口径（等价 `--scope staged`），左上角环境行如实写「尚无提交」。
- 路径与 diff 正文一律经 HTML 转义（含引号）。报告是要发给他人的，而被检查的仓库不是可信输入——文件名里带 `"` 不会截断 `title="…"` 属性，也不会在报告页面里执行任何内容。
- 重命名（`git mv`）由 git 的 `similarity index` / `rename from` / `rename to` 元信息识别，渲染成「移动」：左侧顶部汇总面板 + 树里「移动」徽标与来源路径 + 右侧移动横幅。**纯移动**（相似度 100%、无 hunk）在右侧只显示横幅与一句"纯移动：文件内容未变更"，左侧统计仍是 `+0 -0`；**带内容改动**的移动（相似度 < 100%）横幅之后照常展开 hunk。`--summaries` 的 schema 不需要为移动额外加字段。
- 移动展示依赖 git 的重命名检测：若用 `-c diff.renames=false` 之类配置关掉它，或给 `--exclude` 排掉了重命名的**任一侧路径**，同一文件会退化成「删除 + 新增」或「新增」，报告里就不再显示为移动。
- 模式变更、二进制文件没有 hunk，右侧显示"无内容变更（模式变更或二进制文件）"提示。
- 报告体积随 diff 大小线性增长。改动超过约 5000 行时建议先收窄 `--scope` 或加 `--exclude`，否则浏览器内滚动体验会下降。
