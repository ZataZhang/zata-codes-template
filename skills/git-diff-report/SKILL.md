---
name: git-diff-report
description: "[Updated 2026-09-24] Render git changes into a self-contained HTML report: a collapsible file tree on the left with per-file summaries and +/− counts, a dedicated panel for renamed/moved files, and a highlighted diff viewer with sticky collapsible file headers, click-to-jump, and scroll sync. Use when the user asks to 展示当前改动, 看改了什么, 生成改动预览页, 改动可视化, diff 报告, or wants a reviewable HTML overview of a working tree, branch diff, or staged changes."
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Write
---

# Git Diff Report

## Overview

把「当前代码改了什么」变成一份可以直接看、可以直接发出去的 HTML 报告：

- **顶部**：摘要 JSON 提供 `overview` 或 `reading_path` 时，出现可折叠的「改动总览」面板——功能级叙述 + 建议阅读顺序 + 按角色分组的重点文件清单；正文里的文件路径 / `路径:行号` 自动变跳转链接，点了直达下方对应文件甚至那一行；
- **左侧**：可折叠的改动文件树，每个文件带 `+N -M` 统计与一句话中文总结，点击跳转、滚动联动高亮；
- **左侧顶部**：有重命名（`git mv`）时自动出现「文件移动」汇总面板，逐条列出 `← 旧路径` / `→ 新路径` 与相似度，可点击跳转——纯搬迁类改动一眼能看清搬了什么；
- **右侧**：全部文件的完整 diff，逐 hunk 展开（长文件只默认展开关键 hunk，超大 hunk 可按 `focus_ranges` 只展开聚焦区间，其余折成一行占位、点开即见），可一路下滑；逐行带新旧行号双列（增行只显示新侧号、删行只显示旧侧号、上下文行两侧都显示），长行折行不横滚，浅色主题的设计令牌与 `just view` 同源；每个文件标题栏可点击折叠，滚动时吸附在当前文件顶部并在文件内容结束时自然离开；重命名文件在 diff 顶部显示移动横幅，而不是原来那行低对比度的灰色元信息；
- 单文件、无外部依赖（CSS/JS 全内联），可直接发给他人或用浏览器打开。

渲染器维护左侧文件树与右侧 diff 的顺序一致：右侧区块必须按文件树递归展示的同一组索引输出。左右两栏是**两个独立滚动面**——右栏是 `.viewer-body`，左栏是 `.tree`（`aside` 只是 flex 外壳，本身 `overflow: hidden`），联动高亮要挂 `.viewer-body` 的 `scroll` 事件。自动高亮需要滚动当前文件时，只调整 `.tree` 的 `scrollTop`，不要对文件行调用 `scrollIntoView()`，否则浏览器可能连页面一起滚动；激活态也不要展开摘要造成侧栏行高突变。

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
  "overview": [
    "## 这个功能改了什么",
    "",
    "一句话：**给 X 加了一道 Y**——...。默认关闭。",
    "",
    "### 1. 基础设施层 — 端点接入",
    "",
    "- `path/to/client.py`（新）：一次请求并行提交多个闭集问题，归一为类型化答案；网络错误与契约错误分开抛，调用方据此 fail-open。"
  ],
  "reading_path": [
    {
      "label": "先认识挂载点：`awrap_tool_call` 是唯一入口，放行恰好调一次原 handler",
      "refs": ["src/backend/engines/decision/tool_risk_gate.py:317"]
    },
    {
      "label": "再看裁决顺序与阈值",
      "refs": ["src/backend/engines/decision/tool_risk_gate.py:272"]
    }
  ],
  "files": {
    "src/backend/core/use_cases/repository_registry.py": {
      "summary": "新增 remove_registry_repository()：只删条目并返回被删条目视图；新增 _find_entry_by_path() 校验同一路径不被多个 repo_id 占用。",
      "hunk_notes": ["更新模块不变量说明", "新增 _find_entry_by_path", "add 时增加路径占用校验"]
    },
    "src/backend/composition/sandbox_wiring.py": {
      "summary": "composition root 新增装配开关：默认关闭或密钥为空时返回 None 并告警。",
      "role": "接入装配",
      "must_read": true,
      "key_hunks": [2],
      "hunk_notes": ["引入依赖", "把 middleware 注入 runner", "新增构建与配置映射"]
    },
    "src/backend/engines/decision/tool_risk_gate.py": {
      "summary": "新增功能主实现：把一次工具调用交给决策模型判定并按阈值裁决。",
      "focus_ranges": [
        {"start": 141, "end": 218, "label": "ToolRiskGate 契约与 evaluate_tool_call（含 fail-open 分支）"},
        {"start": 305, "end": 346, "label": "ToolRiskGateMiddleware：挂 pre-tool-call 边界，拦截即回流"}
      ]
    }
  }
}
```

写法要求：

- `overview`（**可选**）是页面顶部的「改动总览」可折叠面板，用来放不适合塞进单文件 `summary` 的整体叙述：功能做了什么、怎么按层实现、关键设计取舍。字符串或字符串列表（列表项按行拼接）均可；支持极简 Markdown：`##`/`###` 标题、`-` 或 `1.` 列表、空行分段、行内 `**加粗**` 与 `` `代码` ``。**不要**把单文件总结重复一遍——那里已有 `files[*].summary`。
- **正文里的文件路径会自动变成跳转链接**：写到本次确实改动的路径（可带 `:行号`，如 `` `src/.../gate.py:317` ``），渲染后既可点。行号落在 diff 里才精确落行，否则自动降级成文件级跳转（不会产生死链）——所以放心写行号，但**写完要核一遍**，行号漂移会让落点偏移。
- `reading_path`（**可选**）是「建议阅读顺序」：一条 3–5 步的最短理解路径，每步 `{label, refs}`，`refs` 是路径或 `路径:行号`。用来回答「从哪看起、看哪几处就够」，**比让读者自己从总览散文里反推省事得多**。作者给了 overview 或 reading_path 任一项，面板就出。
- `files[<path>]` 除 `summary` / `hunk_notes` 外还支持三个**可选**字段：`role`（角色，用于底部「重点文件清单」分组，缺省按路径推断）、`must_read`（bool，缺省由角色推断）、`key_hunks`（hunk 序号数组，决定长文件默认展开哪几个）。
- 底部「重点文件清单」由 `files` **自动生成**（按角色分组 + 必读/扫一眼徽标 + 点击跳转），不需要手写。角色缺省推断顺序：`__init__.py`→导出、`tests/`→测试、`docs/`/`*.md`→文档、`tasks/`→任务/流程、`src/backend/engines|core`→核心逻辑、`composition|api`→接入装配、`infrastructure`→基础设施、`*.yml|*.toml|.env*`→配置。推断不准时用 `role` 覆盖。
- **hunk 数 ≥ 3 的文件默认只展开关键 hunk**：关键 hunk 依次取 `key_hunks` → 有 `hunk_notes` 的 → 全部（也就是"没给任何线索就不折叠"）。折叠只改默认展开态，读者仍可点开，内容不会丢。
- `focus_ranges`（**可选**）解决 hunk 级折叠够不着的情况——**新建文件整篇就是 1 个 hunk**，`key_hunks` 无从下手。给了区间后：区间内照常展开并在起点打一条 `label` 说明，区间外折成 `⋯ 折叠 N 行（a–b）· 点击展开` 的占位（点开即见原文，跳转命中折叠行也会自动展开）。端点用**新侧行号**、闭区间；写反会自动归正。两个门槛保证不滥用：hunk 少于 60 行不折、连续未聚焦段少于 6 行不折。**这是唯一会默认隐藏代码的能力，用的时候克制**——只圈真正要读者看的几段，别把整篇切碎。
- `summary` 一句话讲清「**做了什么 + 对谁有影响/为什么**」，按文件聚合，不要逐 hunk 复述；长度控制在一到三句，保证左侧树里能直接读完。注意左侧树是 `-webkit-line-clamp: 4`，超过会被截断（`overview` 面板不受此限，可写长）。
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

生成后至少确认五点，别直接甩给用户：

1. **无 JS 报错、无截断**：能用 Playwright 时跑一次裸检查（下面的片段可直接用）；否则至少确认文件非空、`grep -c 'node file-row'` 与改动文件数一致（注意 class 是 `node file-row`，不是 `file-row`）。
2. **数量对齐**：`git diff <同参数> --stat` 的文件数应与报告 `N 个文件` 一致；不一致说明排除规则或 scope 选错了。
3. **移动数量对齐**：有重命名时，报告「文件移动」面板里的条数应与 `git diff <同参数> --name-status -M | grep -c '^R'` 一致；条数为 0 但确实搬过文件，通常是 `--exclude` 排掉了重命名的某一侧路径（见「已知边界」）。
4. **总览链接无死链**：写了 `reading_path` 或带 `:行号` 的路径引用时，确认每个 `.ov-ref` 的 `href` 都能 `getElementById` 到。行号引用只有在 hunk 里才落行锚点，不在这范围会自动降级成文件级跳转——**若你发现落点降级了，多半是行号写错了，回去核对**。
5. **移动面板落点正确**：有重命名时，每条「文件移动」条目的 `href="#f<N>"` 必须等于其 `→ 新路径` 对应树行的锚点 id（可 `grep -o 'href="#f[0-9]*" data-index="[0-9]*" title="<新路径>"'` 对照）。锚点用的是文件在 `files` 里的**原始索引**，不是树中的显示位置；两者只在显示顺序与原始顺序不一致时才不等，所以这一步别省。

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
