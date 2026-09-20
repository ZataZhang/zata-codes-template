---
name: idea-inbox
description: "[Updated 2026-09-20] Capture ideas into the current project's tasks/inbox/. Each entry = the user's key wording quoted verbatim + an explicitly labeled AI-derived context block; tasks/inbox/ideas.md stays append-only and is the source of truth, and summary.md is a regenerable digest. Only captures at idea boundaries, never every message. Triggers on: 记一下, 记录想法, 帮我记下来, 把这个想法记下来, capture this idea, 总结想法, 整理 inbox, summarize my ideas."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# Idea Inbox

## Overview

Capture ideas at **idea boundaries** — not every message — as one entry each. An entry pairs the user's load-bearing wording, **quoted verbatim** (the evidence), with an explicitly labeled, AI-derived context block (motivation, boundaries, what was already ruled out). This is stage 0 of the task lifecycle: `tasks/inbox/` → `tasks/pending/` (PRD) → `tasks/archive/`.

Two files in the current project's `tasks/inbox/`, with strictly separated roles:

| File | Role | Who writes | Mutability |
|---|---|---|---|
| `tasks/inbox/ideas.md` | Raw log（原话引用 + 标注的 AI 背景） | Human wording + AI context | **Append-only, never edited** |
| `tasks/inbox/summary.md` | AI digest（总结） | AI | Rewritable anytime |

`ideas.md` is the single source of truth: the verbatim quote is what the user actually said, and the AI block is clearly marked so the two can never be confused. `summary.md` is derived and may be regenerated at any time. When the project ships `docs/guides/idea-inbox.md`, that page is the canonical convention; this skill is its executable form and stays self-contained.

## Resolve the inbox location

1. Find the repo root: `git rev-parse --show-toplevel` (fallback: current working directory).
2. Inbox dir = `<root>/tasks/inbox/`; create it if missing.
3. Raw log = `<root>/tasks/inbox/ideas.md`; summary = `<root>/tasks/inbox/summary.md`.

## Detect intent from the invocation

- **Summarize** when the input matches `总结`, `整理`, `汇总`, `summary`, `summarize`, `digest`, or "整理 inbox".
- **Promote** when the input asks to turn an idea into a PRD/task (`开 PRD`, `变成任务`, `promote ... to prd`).
- Otherwise treat the input as **a thought to capture** (the default).
- When there is no input text at all, run **Status** and ask whether to capture or summarize.

## When to capture (触发规则)

Default is **do not capture**. Do not append an entry for every message, and never turn a conversation into a transcript dump.

Capture only when one of these holds:

1. **The user explicitly asks** — matches `记一下`, `记录想法`, `帮我记下来`, `把这个想法记下来`, `capture this idea`, or an equivalent request.
2. **A topic converges into a promotable state** — it has a clear claim, its boundaries, and its motivation, and is close to being PRD-worthy. In this case the AI may append one entry, and **must tell the user** what it recorded (tag + one line) so the user can amend or delete it.

Do **not** capture: mid-discussion fragments, plain Q&A, options that were ruled out, or small talk. If the user says "别记 / 不用记", do not write anything and do not ask again later.

One conversation should usually produce **one entry per idea** — never split a single unfolding thought into several fragment entries.

## Mode: Capture (default)

Append one new entry to the END of `ideas.md`. Never touch existing entries.

1. If `ideas.md` does not exist, create it with this header:
   ```markdown
   # Idea Inbox — 原话日志

   > 追加式、逐字保留引用。AI 只在末尾追加，永不改写已有条目。`>` 引用为用户原话（证据），`AI 派生` 块为 AI 归纳（非用户原话）。事实来源是本文件。
   ```
2. Get the timestamp: `date "+%Y-%m-%d %H:%M"`.
3. Append a blank line, then:
   ```markdown
   ## <timestamp> · <short tag>

   > <用户关键原话，逐字引用；长想法可多行/多段>

   **AI 派生（非用户原话）**
   - 背景/动机：…
   - 边界/约束：…
   - 已否定：…（可选，讨论中被排除的方案）
   - 收敛结论：…（可选，话题若已收敛）
   ```
4. The `>` block must be the user's **own wording, exactly** — do not fix typos, translate, rephrase, shorten, or "improve" it. If the idea spans several messages, quote the load-bearing sentences verbatim; anything that is synthesis goes in the AI block. **Never fabricate a quote** — if there is no clear user sentence to quote, do not create the entry.
5. Keep the AI block grounded: only record what the discussion actually established. Mark uncertain points as `待澄清：…`.
6. Confirm briefly what was appended (timestamp + tag + one-line gist). Do **not** regenerate the summary automatically.

### Hard rules
- **Append only.** Never edit, merge, delete, reorder, or polish existing entries in `ideas.md` — including their AI blocks. The quote is evidence, not a draft.
- The `>` quote and the `AI 派生` block are strictly separate: never move AI interpretation into the quote, and never let the AI block read as if the user said it.
- If an idea later evolves, **append a new entry** that references the earlier timestamp; do not rewrite the old one.
- Cross-idea grouping and commentary belong in `summary.md`, not in `ideas.md`.

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
5. A newly appended entry makes `summary.md` stale — mention that when confirming a capture, and regenerate on request.

## Mode: Promote to PRD

1. Use the `prd` skill to create a PRD under `tasks/pending/` (naming and structure per `skills/prd/SKILL.md`).
2. Record the idea under "已升级" in `summary.md` with the PRD path.
3. Leave the original entry in `ideas.md` untouched — it remains the requirement trace.

## Mode: Status (no input)

Report: the inbox path, whether `ideas.md` / `summary.md` exist, the entry count in `ideas.md`, the latest 1–3 entry timestamps, and whether `summary.md` is stale (older than the newest idea). Then ask whether to capture a new idea or summarize.

## Encoding

All file I/O uses UTF-8. Timestamps use local time via `date`.
