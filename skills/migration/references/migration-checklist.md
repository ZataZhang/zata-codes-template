# Migration Checklist

Use this checklist selectively. Load only the sections relevant to the current phase. The authoritative workflow is in `../SKILL.md`; this file is the per-phase detail plus the artifact shapes to embed in your planning/PRD files.

## 1. Framing (Phase 0)

- Are source and target named with **pinned versions**?
- Is the **invariant** (behavior that must stay identical) stated as something observable?
- Is "no new features, no behavior changes, no opportunistic refactors" recorded as an explicit non-goal?
- Could any part of this be mistaken for a feature change? If so, split it out into a separate task.

## 2. Discovery (Phase 1)

- Found the project's real **test / lint / type-check / build / run** commands (not assumed)?
- Identified the **real user-facing entry points** (HTTP routes, CLI, UI flows, jobs, public API, migrations)?
- Enumerated the **full surface area** with repo-wide search for old-framework references?
- Decided where durable state lives (planning workspace + migration PRD)?

## 3. Baseline Oracle (Phase 2)

- Is behavior locked at the **highest observable level**, not at old-framework internals?
- Does the baseline cover representative cases, edge cases, and error cases?
- Is the baseline **green on the OLD code** and committed before any migration?
- For untestable behavior, is there a documented **manual verification script**?
- Is the **Baseline Manifest** recorded (shape below)?

Oracle level by surface:

- HTTP API → request→response golden snapshots (status, meaningful headers, body)
- CLI → argv → stdout/stderr/exit code/file side-effects
- UI / user flow → Playwright over user-visible outcomes; visual snapshots only where stable
- Library / public API → characterization tests over public signatures and returns
- Data / schema → round-trip, sample-in→out, migration up/down

## 4. Slicing (Phase 3)

- Is each slice small enough that its diff is reviewable in one sitting?
- Can each slice be **verified and reverted independently**?
- Does the old path stay runnable while the new path is built (coexistence)?
- Is slice ordering recorded with a reason (leaf-first or risk-first)?
- Is the **Slice Tracking Table** on disk (shape below), not in context?

## 5. Per-Slice Loop (Phase 4)

For the current slice:

- Was the executor given the contract + the target's **real idiom/example** (not memory)?
- Was the change **mechanical and migration-only** (no smuggled refactor/feature)?
- Did the discovered test/lint/type-check pass for the affected area?
- Does the **baseline oracle behavior diff come out empty**?
- On green: committed + tracking table updated?
- On red: stopped, fixed/reverted *this slice only*, logged the failure + resolution?

## 6. Final Reconciliation (Phase 5)

- Whole baseline green on fully migrated code?
- Repo-wide search proves **no old references remain** and expected new references exist?
- Shims/adapters/dual paths and replaced old code removed?
- Full test/lint/build + e2e + a real app run executed through actual entry points?
- Migration PRD Acceptance Checklist completed with exact commands and results?

---

## Artifact: Baseline Manifest

Embed in the migration PRD or planning notes. One row per locked behavior.

```markdown
## Baseline Manifest

| Behavior | Surface | Oracle Level | How To Run | Green On Old Code |
|---|---|---|---|---|
| List users returns paginated payload | `GET /api/users` | API golden snapshot | `<discovered test cmd> -k users_snapshot` | yes (commit abc123) |
| Export CSV column order | CLI `export --csv` | argv→file snapshot | `<discovered test cmd> -k export_csv` | yes (commit abc123) |
| Login → dashboard flow | UI | Playwright | `<discovered e2e cmd> login` | yes (commit abc123) |
```

## Artifact: Slice Tracking Table

Embed in the planning workspace. Status flows `pending → in-progress → migrated → verified`.

```markdown
## Slice Tracking

| # | Slice | Status | Baseline Verified | Revert Commit | Notes |
|---|---|---|---|---|---|
| 1 | auth routes | verified | yes | def456 | coexists via adapter |
| 2 | user routes | in-progress | no | — | |
| 3 | reporting jobs | pending | no | — | depends on #2 |
```

---

## AI-Migration Anti-Patterns (smells)

- **Big-bang prompt:** "migrate the whole project" in one shot → unreviewable diff, hidden errors. Slice instead.
- **No oracle:** starting edits before any behavior is captured → "done" can never be proven.
- **Internal-level baseline:** tests bound to the old framework's internals → they get rewritten with the code and prove nothing.
- **Hallucinated target API:** trusting the model's memory of the new framework → migrate against real docs/examples and pinned versions.
- **Smuggled changes:** a feature tweak or refactor hidden inside a migration slice → breaks the "behavior identical" contract and muddies the diff.
- **Lowered assertions:** weakening a baseline check to make a slice pass → silent regression. Stop and escalate instead.
- **Context-only state:** tracking slices in the chat instead of on disk → state lost when context is compacted on a long migration.
- **Skipping the kill step:** leaving shims and old code paths after migration → the strangler never finishes; dead/duplicate code accumulates.
