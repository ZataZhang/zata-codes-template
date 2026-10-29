---
name: idea-inbox
description: "[Updated 2026-10-29] Capture and manage ideas in the current project's tasks/inbox/. ideas.md preserves original wording and AI context while storing lifecycle status in mutable heading metadata linked to PRDs. Only captures at idea boundaries, never every message. Triggers on: 记一下, 记录想法, 帮我记下来, 把这个想法记下来, capture this idea, 总结想法, 整理 inbox, summarize my ideas."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# Idea Inbox

## Overview

Capture ideas at **idea boundaries** — not every message — as one entry each. An entry pairs the user's load-bearing wording, **quoted verbatim** (the evidence), with an explicitly labeled, AI-derived context block (motivation, boundaries, what was already ruled out). This is stage 0 of the task lifecycle: `tasks/inbox/` → `tasks/pending/` (PRD) → `tasks/archive/`.

Files in the current project's `tasks/inbox/` have strictly separated roles:

| File | Role | Who writes | Mutability |
|---|---|---|---|
| `tasks/inbox/ideas.md` | Raw log（原话引用 + 标注的 AI 背景 + 状态标记） | Human wording + AI context + lifecycle metadata | Wording/context append-only; heading metadata may be updated |
| `tasks/inbox/summary.md` | AI digest（总结） | AI | Rewritable anytime |

`ideas.md` is the source of truth for both the original wording and lifecycle markers: the verbatim quote is what the user actually said, and the AI block is clearly marked so the two can never be confused. Effective lifecycle status is derived from linked PRD locations, with explicit `completed` and `abandoned` markers for manual decisions. Snapshot reads may update only the H2 heading metadata; the quote and AI context remain unchanged. `summary.md` is derived and may be regenerated at any time. When the project ships `docs/guides/idea-inbox.md`, that page is the canonical convention; this skill is its executable form and stays self-contained.

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

Append one new entry to the END of `ideas.md`. Do not edit existing wording or AI context; the lifecycle system may update only heading metadata.

1. If `ideas.md` does not exist, create it with this header:
   ```markdown
   # Idea Inbox — 原话日志

   > 想法原话与 AI 背景只追加、不改写；标题中的 ID 与生命周期状态标记可更新。`>` 引用为用户原话（证据），`AI 派生` 块为 AI 归纳（非用户原话）。事实来源是本文件。
   ```
2. Get the timestamp: `date "+%Y-%m-%d %H:%M"`.
3. Generate a stable ID `idea-<YYYYMMDDHHMMSS>-<6 hex characters>` for the entry. Use `python -c 'import secrets; print(secrets.token_hex(3))'` for the random suffix so entries created in the same second remain distinct.
4. Append a blank line, then:
   ```markdown
   ## <timestamp> · <short tag> (idea-<YYYYMMDDHHMMSS>-<random>) <!-- idea-status: pending -->

   > <用户关键原话，逐字引用；长想法可多行/多段>

   **AI 派生（非用户原话）**
   - 背景/动机：…
   - 边界/约束：…
   - 已否定：…（可选，讨论中被排除的方案）
   - 收敛结论：…（可选，话题若已收敛）
   ```
5. The `>` block must be the user's **own wording, exactly** — do not fix typos, translate, rephrase, shorten, or "improve" it. If the idea spans several messages, quote the load-bearing sentences verbatim; anything that is synthesis goes in the AI block. **Never fabricate a quote** — if there is no clear user sentence to quote, do not create the entry.
6. Keep the AI block grounded: only record what the discussion actually established. Mark uncertain points as `待澄清：…`.
7. Confirm briefly what was appended (timestamp + tag + one-line gist). Do **not** regenerate the summary automatically.

### Hard rules
- **Preserve content.** Never rewrite, merge, delete, reorder, or polish an existing quote or AI context block. Lifecycle changes update only the `idea-status` HTML comment in the H2 heading; assigning a stable ID to a legacy entry may also update that heading. The quote is evidence, not a draft.
- The `>` quote and the `AI 派生` block are strictly separate: never move AI interpretation into the quote, and never let the AI block read as if the user said it.
- If an idea later evolves, **append a new entry** that references the earlier timestamp; do not rewrite the old one.
- Cross-idea grouping and commentary belong in `summary.md`, not in `ideas.md`.
- Do not infer `abandoned` from age or lack of recent activity. Mark it only after an explicit user decision by changing the heading marker to `<!-- idea-status: abandoned -->`.

## Idea lifecycle status

The `/ideas` page returns one effective status for each entry:

- `pending`（待处理）: no linked draft or PRD and no abandoned marker. New entries start here.
- `in_progress`（进行中）: a linked draft awaits review, or a linked PRD exists under `tasks/`, `tasks/pending/`, or `tasks/hold/`.
- `completed`（已完成）: a linked PRD exists under `tasks/archive/`, or the user explicitly marked the idea complete (useful for legacy entries without PRD references).
- `abandoned`（已放弃）: the user explicitly chose to stop pursuing the idea, recorded in the heading.

The H2 heading stores the ID and status as metadata:

```markdown
## 2026-10-29 12:30 · short-tag (idea-20261029123000-a1b2c3) <!-- idea-status: pending -->
```

The system may reconcile the status marker when reading the inbox: linked drafts and PRD locations drive `in_progress` and `completed`; explicit `completed` and `abandoned` markers stay in effect until the user changes the lifecycle decision. This reconciliation changes only the heading line, never the quoted wording or AI context. A linked PRD uses a header line such as `- Source Idea Refs: idea-20261029123000-a1b2c3`; retain that reference so lifecycle status can be derived. On projects with the `/ideas` UI, use its status action; otherwise edit only the heading's status marker after an explicit user decision.

## Mode: Summarize

1. Read the entire `ideas.md`.
2. Read heading status markers and linked PRD references when available. Keep `completed` and `abandoned` ideas out of active candidates; preserve them in a lifecycle/history section when useful.
3. Regenerate `summary.md` (rewrite, do not append) with this structure:
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

   ## 生命周期盘点
   - **进行中**：<想法> → <关联 PRD 路径>
   - **已完成**：<想法> → `tasks/archive/<prd-file>.md`
   - **已放弃**：<想法>（来源：<timestamp>）
   ```
4. Every cluster and item cites the source timestamp(s) so it traces back to the raw entry.
5. Do **not** modify `ideas.md` while summarizing.
6. A new entry makes `summary.md` stale; a status change makes its lifecycle section stale. Mention this when useful and regenerate on request, but do not regenerate automatically while capturing.

## Mode: Promote to PRD

1. Use the `prd` skill to create a PRD under `tasks/pending/` (naming and structure per `skills/prd/SKILL.md`).
2. Add `- Source Idea Refs: <idea-id>` to the PRD metadata when the idea has a stable ID, so its lifecycle stays linked to the PRD.
3. Record the idea under "已升级" in `summary.md` with the PRD path.
4. Leave the original quote and AI context untouched — they remain the requirement trace. The heading status updates to `in_progress` from the new PRD reference.

## Mode: Status (no input)

Report: the inbox path, whether `ideas.md` / `summary.md` exist, total entries, latest 1–3 timestamps, and whether `summary.md` is stale. When a project exposes the `/ideas` snapshot, use its effective status counts; otherwise derive statuses from heading markers and PRD `Source Idea Refs` where possible. Treat legacy entries without a usable ID or PRD reference as pending; never guess from age. Then ask whether to capture, summarize, or update an idea's status.

## Encoding

All file I/O uses UTF-8. Timestamps use local time via `date`.
