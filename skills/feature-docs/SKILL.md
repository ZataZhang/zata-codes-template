---
name: feature-docs
description: "[Created 2026-09-13] Maintain the docs/features/ hub-and-spoke feature documentation directory — per-domain folders with a routing index and per-feature code maps written for AI coding agents. Triggers on: 补功能文档, update feature docs, sync docs/features, document this feature, bootstrap feature docs, 功能文档. Covers creating new domain docs from real code exploration, updating docs after behavior changes, and bootstrapping the convention into a repo that lacks it."
---

# Feature Docs Maintainer

Maintain a `docs/features/` directory whose sole audience is **whoever changes the code** (human or agent). It answers: what features exist, where their entry points are, which files a change will touch, what the data contracts are, and where the traps are.

## Positioning Boundaries

- `docs/features/` = **code map for changers**. Entry points, key code paths, contracts, tests, pitfalls.
- `docs/guides/` = **manual for users**. Installation, configuration, troubleshooting. Do not copy user-manual content into features docs.
- `docs/architecture/` = **cross-layer contracts and design rationale**. Do not duplicate; link.
- `code-reviewer` skill = the docs-synchronization **gate** at pre-merge. This skill = the **how-to** for actually writing the docs. Different roles, do not merge.

When overlap is unavoidable, single-source it: keep the content in one file and replace the other copy with a link. Two files must never both claim authority over the same content.

## Convention Detection

Before anything else, check whether the repo has adopted the convention:

1. Does `docs/features/index.md` (hub with a routing table) exist?
2. Does `docs/features/_template.md` exist?
3. Is the hub referenced from the repo's agent entry file (e.g. `AGENTS.md` routing table)?

If yes to all → follow the **Update Workflow**. If no → run **Bootstrap Mode** first (below).

## Update Workflow

### Step 1: Explore first — never write from memory

Dispatch an exploration pass (subagent or direct search) with this fixed checklist. Every path in the output must be verified to exist:

1. Feature overview: what it is, what problem it solves
2. Entry points: API routes (file + prefix), frontend pages, CLI commands
3. Key code paths: follow the repo's own layering (e.g. api → core → engines → infrastructure), one line of responsibility per file
4. Data contracts: DB tables / ORM models, Pydantic or schema models, config items (note whether they live in config files or env)
5. Tests: which test files cover this feature, how to run them
6. **Pitfalls**: dig code comments, defensive checks, magic numbers, TODOs, ordering constraints — this is the highest-value output

Explicitly ask: "is this directory/mechanism still the primary path, or legacy?" Legacy-looking paths (`data/`, old stores, compat shims) are a common trap.

### Step 2: Write per template

- One domain = one directory with a short `_index.md` whose only job is routing ("changing X → read page Y"). Put the domain's biggest cognitive trap in its first sentence.
- One feature = one file copied from `docs/features/_template.md`. No empty sections — write "无" / "None".
- Value ordering: **pitfalls > code paths > contracts > overview**. The overview is the least important section; anyone can write it, only real exploration produces the pitfalls.
- Match the repo's doc language and heading style.

### Step 3: Wire discoverability (all three, or the page does not exist)

1. Link from the domain's `_index.md`
2. Add/refresh the row in the `docs/features/index.md` routing table (with "when must read / when can skip")
3. Add to the docs site nav (e.g. `mkdocs.yml`) if the repo has one

### Step 4: Verify

1. Run the repo's docs build (`mkdocs build`, or equivalent) — must pass with no new warnings
2. Spot-check 2–3 cited code paths still exist
3. grep that no doc references now-deleted files

## Sync Triggers

Update the matching features doc in the same change as the code when any of these change: user-visible behavior, entry points (routes/commands/pages), data contracts, config items, or the pitfall list (a fixed bug often becomes a documented trap).

Do **not** batch-fill empty domains upfront. Fill on demand: when a PRD or change touches a domain, write that domain's docs in the same pass. Docs filled ahead of code rot immediately.

## Anti-Patterns

- **Design-record dumps**: PRD-numbered "implementation record" sections are not feature docs. If migrating them into `docs/features/`, mark them as design records at the top and rewrite toward the template incrementally.
- **Dual authority**: two pages describing the same mechanism. Single-source and link.
- **Template-forking**: tweaking `_template.md` per domain. The template is the contract; domain knowledge goes in the content.
- **Writing from docs alone**: existing guides describe intent, not current code. Always verify against source.

## Bootstrap Mode (repo lacks the convention)

1. Research how the repo organizes docs and what its agent entry file is (AGENTS.md / CLAUDE.md / none yet).
2. Create `docs/features/index.md` (hub: purpose, how-to-use, empty routing table skeleton seeded with 4–8 real domains from the codebase) and `docs/features/_template.md` (sections: 功能概述 / 入口 / 关键代码路径 / 数据契约 / 测试 / 常见坑 / 相关文档 — adapt names to repo language).
3. Add one routing row to the repo's agent entry file pointing at the hub: "需要了解某个具体业务功能的入口、代码路径、数据契约或常见坑时 → docs/features/index.md".
4. Wire the docs site nav if one exists; run the docs build.
5. Seed **one** real domain end-to-end (pick the repo's main flow) as the living example. Leave the rest as routing-table rows to be filled on demand.
