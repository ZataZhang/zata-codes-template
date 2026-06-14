---
name: idea-inbox
description: "[Updated 2026-06-14] Capture raw ideas verbatim and maintain an AI summary in the current project's tasks/inbox/. Appends untouched original wording to tasks/inbox/ideas.md (append-only, never edited) and regenerates tasks/inbox/summary.md on demand. Triggers on: 记一下, 记录想法, 帮我记下来, 把这个想法记下来, capture this idea, 总结想法, 整理 inbox, summarize my ideas."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# Idea Inbox

## Overview

Capture fleeting ideas as **verbatim original wording**, then let AI maintain a rolling summary — without ever rewriting the raw record. This is stage 0 of the task lifecycle: `tasks/inbox/` → `tasks/pending/` (PRD) → `tasks/archive/`.

Two files in the current project's `tasks/inbox/`, with strictly separated roles:

| File | Role | Who writes | Mutability |
|---|---|---|---|
| `tasks/inbox/ideas.md` | Raw log（原话） | Human (AI transcribes verbatim) | **Append-only, never edited** |
| `tasks/inbox/summary.md` | AI digest（总结） | AI | Rewritable anytime |

The single source of truth is `ideas.md`. `summary.md` is derived and may be regenerated from it at any time. When the project ships `docs/guides/idea-inbox.md`, that page is the canonical convention; this skill is its executable form and stays self-contained.

## Resolve the inbox location

1. Find the repo root: `git rev-parse --show-toplevel` (fallback: current working directory).
2. Inbox dir = `<root>/tasks/inbox/`; create it if missing.
3. Raw log = `<root>/tasks/inbox/ideas.md`; summary = `<root>/tasks/inbox/summary.md`.

## Detect intent from the invocation

- **Summarize** when the input matches `总结`, `整理`, `汇总`, `summary`, `summarize`, `digest`, or "整理 inbox".
- **Promote** when the input asks to turn an idea into a PRD/task (`开 PRD`, `变成任务`, `promote ... to prd`).
- Otherwise treat the input as **a thought to capture** (the default).
- When there is no input text at all, run **Status** and ask whether to capture or summarize.

## Mode: Capture (default)

Append one new entry to the END of `ideas.md`. Never touch existing entries.

1. If `ideas.md` does not exist, create it with this header:
   ```markdown
   # Idea Inbox — 原话日志

   > 追加式、逐字保留。AI 只在末尾追加，永不改写已有条目。事实来源是本文件。
   ```
2. Get the timestamp: `date "+%Y-%m-%d %H:%M"`.
3. Append a blank line, then:
   ```markdown
   ## <timestamp> · <optional short tag>

   > <the user's idea, transcribed VERBATIM>
   ```
4. Preserve the original wording exactly — do **not** fix typos, translate, rephrase, shorten, or "improve" it. If the idea contains code or multi-line structure, keep it as-is (use a fenced code block instead of a blockquote when a blockquote would mangle it).
5. Confirm briefly what was appended (timestamp + first line). Do **not** regenerate the summary automatically.

### Hard rules
- **Append only.** Never edit, merge, delete, reorder, or polish existing entries in `ideas.md`. The raw wording is evidence, not a draft.
- Any interpretation, grouping, or commentary belongs in `summary.md`, never in `ideas.md`.

## Mode: Summarize

1. Read the entire `ideas.md`.
2. Regenerate `summary.md` (rewrite, do not append) with this structure:
   ```markdown
   # Idea Inbox — 总结（AI 派生，可重写；事实以 ideas.md 为准）

   _最后更新：<date "+%Y-%m-%d %H:%M">_

   ## 主题聚类
   - **<主题>** — <归纳>（来源：<timestamp>, <timestamp>）

   ## 可执行候选
   - <想法> → 建议 PRD：<P?>-<TYPE>，理由 …（来源：<timestamp>）

   ## 待澄清问题
   - <需要用户拍板的点>（来源：<timestamp>）

   ## 已升级
   - <想法> → `tasks/pending/<prd-file>.md`
   ```
3. Every cluster and item cites the source timestamp(s) so it traces back to the raw entry.
4. Do **not** modify `ideas.md` while summarizing.

## Mode: Promote to PRD

1. Use the `prd` skill to create a PRD under `tasks/pending/` (naming and structure per `docs/guides/prd-standard.md`).
2. Record the idea under "已升级" in `summary.md` with the PRD path.
3. Leave the original entry in `ideas.md` untouched — it remains the requirement trace.

## Mode: Status (no input)

Report: the inbox path, whether `ideas.md` / `summary.md` exist, the entry count in `ideas.md`, the latest 1–3 entry timestamps, and whether `summary.md` is stale (older than the newest idea). Then ask whether to capture a new idea or summarize.

## Encoding

All file I/O uses UTF-8. Timestamps use local time via `date`.
