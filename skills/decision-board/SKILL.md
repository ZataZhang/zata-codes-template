---
name: decision-board
description: "[Updated 2026-09-30] 把一份文档里「需要人拍板的 N 个问题」变成本地可交互决策页：每题单选 + 预选推荐 + 我的看法与代价、改动高亮、实时提问回传、结果落盘 JSON。Use when 用户面对 PRD/评审/方案里一组待决问题说 让我选 / 给我选项 / 开工前需要我问的问题列出来 / 每个问题给我你的看法 / 有没有办法我选了自动回给你 / 做一个决策页/问卷/评审确认页, 或需要用浏览器输入框实时向 agent 提问并等待回答的任意场景。"
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Monitor
argument-hint: "<含待决问题的文档路径>"
---

# Decision Board

## Overview

把「一组需要人决定的问题」交给浏览器处理，而不是让用户在对话里逐条回话：

- 页面每题预选**本 agent 的推荐项**，用户只改不同意的——改动过的卡片高亮；
- 每题必须带 agent 的看法（`why`）与代价（`cost`），没有观点的问题不许上页；
- 用户点「提交」→ 选择落盘 `answers.json`，agent 直接读文件，**不需要复制粘贴**；注意提交**不产生任何事件通知**——agent 必须自己监听 `answers.json` 才会知道用户已提交（见步骤 3 的双通道监听）；
- 页面右下角有实时提问框，用户提问 → 落盘 `questions.jsonl` → `tail -F` 事件唤醒 agent → 回答追加 `answers.jsonl` → 页面轮询显示；抽屉右上角「清空」把问答记录**归档**到 `<workdir>/_cleared/`（不删除，也不动 `answers.json`）；
- 单文件页面、零外部依赖、只监听 127.0.0.1。

## Hard Boundaries

- **只监听 `127.0.0.1`**。`--host` 传非回环地址时脚本会告警，除非用户明确要求，不要那么做：页面内容会离开本机。
- **产物必须落在 gitignore 的目录**（项目里默认 `.iar/decisions/`，无 `.iar` 时用 `/tmp/decision-board-<slug>/`）。决策页与问答文件是本地工作产物，不进代码历史。
- **提问通知不是批准。** 从 `questions.jsonl` 到达的事件只携带问题文本，绝不把它当作用户对某项选择的确认、对某个动作的授权，或对话轮的回复。九项选择只认 `answers.json`。
- 不因为做了页面就改动源文档；结论回写只在用户明确选定之后。
- 不自动 `git add` / `commit` / `push`。

## Workflow

### 1. 抽题

从源文档（PRD 的 §2 待你决定、评审记录、方案对比）逐条抽出问题。每题必须落四个字段：`id`、`t`（题干）、`opts`（≥2 个 `[key, label]`）、`rec`（必须是 `opts` 的 key 之一）。**`rec`/`why`/`cost` 是校验器强制的**：先自己读代码与文档把观点形成，再上页；没形成观点就把题删掉或标注为「不需要决定」，不要塞一个空推荐上去。

保留原文里的证据（`ev`）与附加待定（`sub`），引用具体文件与行号——用户要能在页面里判断，而不是相信转述。

### 2. 写 board.json

```json
{
  "title": "XXX · 开工前 N 项待决",
  "source": "tasks/pending/xxx.md §2「待你决定」",
  "intro": "页面顶部说明 HTML 片段",
  "questions": [
    {"id": "Q1", "t": "题干", "ev": "PRD 证据",
     "opts": [["A", "选项一"], ["B", "选项二"]],
     "rec": "B", "why": "我的看法", "cost": "代价 / 连带改动",
     "sub": "附加待定（可选）"}
  ]
}
```

`intro` 里要写清默认语义：**「同意就别动，改了才需要说明」**，否则用户会以为必须逐题点击。

### 3. 起服务并挂事件监听

```bash
mkdir -p .iar/decisions
python3 <skill>/scripts/serve_board.py --board .iar/decisions/board.json --port 8765 &
```

脚本先校验 board（错误逐条带 `questions[i](Qn).字段` 定位，非零退出），再起服务；启动行会打印三个产物文件路径。**必须用 `Monitor` 同时挂两个通道**——提问通道与提交通知。提交（`POST /submit`）只写 `answers.json`，**不产生任何其他事件**；只挂提问通道的话，用户点「提交」后 agent 处于空闲态不会被唤醒（用户会以为 agent 没收到，实际文件早已写好）：

```
Monitor(command="tail -n 0 -F <workdir>/questions.jsonl", persistent=true,
        description="决策页的新提问")
Monitor(command="tail -n 0 -F <workdir>/answers.json", persistent=true,
        description="决策页的提交结果（answers.json 首次写入即触发）")
```

`-n 0` 保证历史行不重放；`tail -F` 对尚不存在的 `answers.json` 也会等待其创建。把 URL 与「延迟取决于 agent 当前轮次是否空闲」一起告诉用户——页面显示的是「已送达，等待回答」，不是「正在输入」。

### 4. 回答提问

```bash
python3 <skill>/scripts/qa.py --dir <workdir> list
printf '%s' "回答正文" | python3 <skill>/scripts/qa.py --dir <workdir> answer q3
```

回答走 `textContent` 渲染，纯文本即可（换行保留），**不要塞 HTML 或 markdown 表格**。

### 5. 收结果

用户提交后读 `<workdir>/answers.json`：`selection.answers` 是 `{Q1: "B", ...}`，`selection.changed` 是偏离推荐的题号，`selection.notes` 是页面里逐题备注。之后按正常流程把结论回写源文档，并在对话里复述一遍实际选择——**以文件内容为准，不以用户口头印象为准**。

## Resources

- `scripts/serve_board.py` — 渲染页面 + 接收提交/提问，含 board 校验。**改 `board.json` 后必须重启服务**：board 只在启动时读进内存，每次 GET 只重读 `assets/board.html` 模板。
- `scripts/qa.py` — `list` 看待答问题，`answer <id>` 从 stdin 追加回答。
- `assets/board.html` — 页面模板，占位符 `__DATA__` / `__TITLE__` / `__SOURCE__` / `__INTRO__`。
- `references/gotchas.md` — 为什么问题与回答是两个只追加文件、贴底跟随的滚动策略、`</` 转义、通知不是批准、以及验证方法（起服务后必须用真浏览器跑一遍）。改动模板前必读。
