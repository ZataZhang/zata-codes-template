---
name: prd
description: "[Updated 2026-08-21] Generate an architecture-aware technical PRD split into two altitudes — a human review layer (Part A) and an executor build layer (Part B) — with a decision-oriented human review map, a front-loaded interpretation lock, and a risk-ordered acceptance evidence package for a single end-of-flow human review. Triggers on: create a prd, write prd for, plan this feature. Prioritizes reuse, minimal-change plans, evidence-chain integrity, required output compliance, realistic validation, and conditional web research."
---

# PRD Generator (Architecture-First)

> **Maintenance note:** The `[Updated YYYY-MM-DD]` tag in the frontmatter reflects the date of the last **substantive** change to this SKILL.md (core rules, workflow phases, output contract, or templates). When committing a change to this file or any template under `skills/prd/`, bump the date to match the commit day so it never lags behind git history.

Create technical PRDs that fit the existing codebase instead of expanding it unnecessarily.
The default recommendation must be the smallest change that cleanly solves the problem.

---

## Core Rules

1. **Repository First:** Treat the current codebase as the primary source of truth.
2. **Architecture Before Output:** Do not jump to sections, diagrams, or prototype work before identifying existing boundaries, extension points, and reusable modules.
3. **Minimal Change Bias:** Prefer extending an existing path over adding a new layer, service, hook, table, page, or dependency.
4. **No Redundant Abstractions:** Every newly proposed abstraction must be justified against the current codebase.
5. **Target-State Bias:** Default to a complete end-state plan. Do not split required work into `Phase 1` / `Phase 2`, temporary facades, or deferred cleanup unless a real constraint makes single-stage delivery unsafe or impossible.
6. **Conditional Web Research:** Browse only when the answer depends on external facts that are not stable in the repository.
7. **Output Contract:** Treat the required PRD structure as mandatory. Do not omit, rename, or bury required sections unless the user explicitly requests a different format.
8. **Realistic Validation:** Every PRD must identify the highest-fidelity validation needed to prove the behavior works through real project entry points, not only isolated unit or integration tests.
9. **Executor-Resilient Detail:** Write implementation detail for a less capable executor: be concrete, but prefer semantic anchors and repository searches over brittle coordinates such as line numbers.
10. **Full-Stack Surface:** Treat the user-visible frontend as first-class. Discover the repo's actual frontend app(s) (don't assume a framework or directory) and plan any user-facing change with backend-level rigor; a genuinely backend-only PRD must state `No frontend impact` with a one-line reason rather than omit it silently. (Detailed gate: Phase 1.5.)
11. **Two-Altitude Output:** Structure every PRD as **Part A · Review Layer** (problem, user-facing value, human review map, requirement shape) and **Part B · Build Layer** (mechanism, change tree, validation commands, dependency metadata). Part A must let a human accept or reject the work *without* reading implementation mechanism, file paths, commands, or scheduling metadata; all executor detail lives in Part B. Do not front-load Part A with mechanism — the historical failure mode was a first section so full of code/test/scheduling detail that human review was hard.
12. **Decision-Oriented Human Review Map:** Internally classify every meaningful change point with the deterministic `R0`–`R3` model in Phase 3.6, recording the result in Part B. Do not expose the classification machinery as a menu or compliance table in Part A. Present only the concrete decisions that require **human confirmation**, written as questions a reviewer can answer. Summarize everything else under **executor + automated gates**. Keep the human-confirm set short and principled; over-flagging defeats the map.
13. **Two-Touch Autonomy + Evidence Package:** The operating model is two batched human touches with autonomous execution between them — up front the human approves the Agent's interpretation (Section 1) and the human-facing decisions plus acceptance outcomes (Section 2); at the end the human reads a risk-ordered **Acceptance Evidence Package** (Section 9). There is no mid-flow human gate: the Agent self-verifies as deeply as needed (many rounds, adversarial checks — tokens are cheaper than human attention). So "human confirmation" means **high evidence burden** (the item tops the end package with an executable oracle), not an interruption; every human decision and automated gate must map to evidence in Part B that would fail if the change were wrong.
14. **Tiered Evidence-Chain Integrity:** A passing nearby path is not delivery evidence — but provenance rigor is a cost, so spend it by risk tier. `R2`/`R3` oracles must identify the exact critical-value source, runtime boundaries that must be crossed, forbidden bypasses, a fresh-state postcondition probe, and how evidence is tied to the final implementation tree; `R0`/`R1` oracles need one assertion that genuinely discriminates their own failure and nothing more. More than three `R2`/`R3` oracles in one PRD is a scope signal — revisit Phase 3.4 before adding a fourth. Never modify production code to make an oracle able to fail. Read [references/validation-evidence-integrity.md](references/validation-evidence-integrity.md) whenever `R2`/`R3` executable behavior changes or a PRD is prepared for archive.
15. **Information-Preserving Plain Language:** Part A must reduce the background knowledge needed to understand the PRD without weakening its meaning. Translate technical constraints; do not delete them. Preserve anything that changes required processing order, supported modes, forbidden legacy or bypass paths, required data completeness, failure or unresolved behavior, compatibility promises, or acceptance conclusions. Introduce a necessary internal term as `plain-language meaning (internal name)`, then prefer the plain-language term afterward.

---

## Workflow

### Phase 0: Rewrite The Request As An Implementable Claim

State in plain language:
- who wants what behavior
- under which conditions
- what changes in system state, API, UI, or workflow

When repository evidence is available, record at least one concrete current-state fact behind the request: a duplicate call, legacy dependency, observed failure, measured waste, or blocked extension path. Architectural smells such as "boundaries are unclear" or "maintenance is difficult" are insufficient by themselves.

If you cannot rewrite the request concretely, call that out before generating a PRD.

This restatement is the **Interpretation Echo** recorded in Section 1 and is the human's first of two touches — they approve it (and the Section 2 acceptance oracles) before autonomous implementation begins. A wrong-but-unconfirmed interpretation is the one failure downstream evidence cannot catch: the oracles and the implementation are both products of this reading, so if the reading is wrong they agree with each other and every check goes green on the wrong behavior. No amount of verification rigor downstream detects that. This phase is the only place it can be caught.

Prose cannot be red-lined. A reader skims a dense paragraph, finds it plausible, and approves. So the echo must be **concrete enough to correct one cell of**, in three blocks:

1. **Behavior examples** — a table of 3-7 rows: a concrete input/action in the reader's own domain language, and the exact observable result expected. Include at least one edge case and one failure case. These rows are transcribed verbatim into the Section 7.6 oracles, so correcting a cell corrects the acceptance criteria; say so in the PRD, because it is what makes reviewing the table worth the reader's time.
2. **Decisions taken silently** — every ambiguity resolved without asking, one line each, with the answer chosen. Phase 2 deliberately does not ask about these; that is exactly why they must be visible. Expectation gaps live in the decisions the Agent judged obvious, and a reader spots the wrong one in seconds when it is a scannable list rather than buried in a paragraph.
3. **Read as out of scope** — 2-3 things the reader might plausibly have wanted that this PRD reads as excluded. Scope read too narrowly is the other half of the expectation gap, and it is invisible in a description of what *will* be built.

Then the falsifiable prose reading ("read as X, not Y"), covering boundaries whose omission would permit a materially different implementation, and explicit non-goals.

### Phase 1: Repository Context And Architecture Gate

Before asking questions or proposing changes, inspect the repository for:
- tech stack and runtime constraints
- current module boundaries and dependency direction
- existing extension points and reusable code paths
- current data model and state ownership
- existing docs, tests, and workflows relevant to the request
- user-facing surface: which frontend app(s) the repository ships (discover from top-level app directories, `package.json`, and framework configs) and whether the request touches them, including the closest routes/components/state
- existing PRDs under `tasks/pending/` and related archived PRDs under `tasks/archive/`

You must inspect existing PRDs before creating a new one:
- search `tasks/pending/` first for duplicate, overlapping, prerequisite, or downstream work
- search `tasks/archive/` when a completed PRD may define context, prior decisions, or reusable acceptance criteria
- reuse or update an existing pending PRD when it clearly represents the same work instead of creating a duplicate
- populate `Delivery Dependencies` from explicit pending PRD relationships when a task must wait for another task or group
- use `none` only after checking pending PRDs and finding no sequencing dependency
- do not infer hard dependencies from vague topic similarity; record uncertain relationships as `soft` or ask the user when dependency choice changes scope or execution order

You must explicitly identify:
- **Existing Path:** the current code path that is closest to the requested change
- **Reuse Candidates:** files/modules that can be extended directly
- **Architecture Constraints:** boundaries that should not be broken
- **Frontend Impact:** which of the repository's frontend app(s) change, or none with a reason
- **Existing PRD Relationship:** whether the request duplicates, depends on, blocks, or is independent from current pending PRDs
- **Potential Redundancy Risks:** likely sources of duplicated logic or parallel abstractions

Do not ask questions that can be answered by reading the repository.

### Phase 1.5: Frontend Impact Gate

Decide the user-facing surface before designing the backend. First discover what frontend(s) the repository actually ships — do not assume a fixed framework or directory name. Inspect:
- top-level application directories and the repository's architecture docs
- each candidate's `package.json` (framework, and the dev/build/test/e2e scripts) and framework config files
- how each frontend is run and tested in this repo (its dev command, app-run command, and e2e/UI test command)

Record each frontend app's path, stack, run command, and e2e/UI test command from what you find, and reuse those concrete values in the Change Impact Tree and validation.

Then classify the request as exactly one of:

- **Full-stack:** backend behavior plus a user-visible change. Plan the affected frontend app(s) as first-class: components, routes/pages, state, the API client call that hits the new/changed backend endpoint, and type/contract sync. These must appear in the Change Impact Tree and in validation.
- **Frontend-only:** UI/UX change with no backend contract change. Plan the frontend with full concreteness; note that no backend layer changes.
- **Backend-only:** no user-visible surface (internal CLI, worker job, migration, infra). The PRD must state `No frontend impact` with a one-line reason, so omission is a documented decision rather than a silent default.

**Hard rule:** if the request changes anything a user sees or interacts with, the PRD MUST plan the frontend with the same concreteness as the backend. A lone "update UI" line is not acceptable — name the app, the components/routes, and the API wiring. If more than one frontend could plausibly host the surface, ask the user which one in Phase 2 instead of guessing.

### Phase 2: Clarify Only What The Code Cannot Answer

Ask only the critical questions that remain unresolved after repository analysis.
If an unresolved item would materially change scope, behavior, trust boundaries, rollout, or architecture, you must ask the user to confirm it before finalizing the PRD.
Do not silently pick a default for a requirement-level ambiguity that the repository cannot answer.

Question categories:
- business rule ambiguity
- permission or trust-boundary ambiguity
- scope boundaries
- rollout or migration decisions

For each unresolved question:
1. state the decision that must be made
2. ask the user to confirm the answer before finalizing the PRD
3. give the single answer you recommend by default
4. justify the recommendation using existing repository patterns where possible
5. include alternative options only when the trade-off is real and material

If there are no critical unresolved questions, proceed without asking.

### Phase 3: Redundancy Gate And Recommendation Check

Before writing the final PRD, stress-test your recommendation against the closest heavier alternative:

1. **Minimal-Change Path**
   Extend the closest existing path with the fewest new moving parts.
2. **Heavier Alternative**
   Introduce a new abstraction, module, service, table, page, or dependency only if warranted.

The PRD should present a single recommended path by default.
Recommend the minimal-change path unless the heavier alternative is clearly necessary.
Mention the heavier alternative in the PRD only when it materially affects scope, risk, or architecture.

For every proposed new item, answer:
- why the existing path is insufficient
- why this does not duplicate an existing responsibility
- what complexity it adds
- whether an existing path can be removed or consolidated as part of the change

If you cannot justify the new item, do not recommend it.

### Phase 3.4: Scope Cohesion Gate

List the independently approvable decisions discovered for Part A. If three or more decisions can be implemented, rolled back, or validated independently, explicitly assess whether they should become separate PRDs. Keep them together only when they form one indivisible target state and splitting them would require a temporary compatibility layer, duplicated migration, or another concrete delivery hazard. The count triggers review; it is not an automatic split rule.

### Phase 3.5: Realistic Validation Gate

Identify the highest-fidelity validation that proves the behavior through a real project entry point, and record it in the Section 7 **Realistic Validation Plan** (content rule F defines the table columns, mock boundary, opt-in live, and fallback rules). Mirror the relevant outcome in plain language as the short **验收** line under each human-facing decision; keep commands and `rv-id` references in Part B.

Assign each oracle the `R0`–`R3` tier of its change point, and let the tier set the evidence depth (content rule F defines the field split). For `R2`/`R3` behavior, read [references/validation-evidence-integrity.md](references/validation-evidence-integrity.md) and lock the full evidence chain before handoff: values displayed or copied by a UI must be extracted from that UI and used unchanged; successful writes must be observed from a fresh consumer after the durability boundary; frontend flows must assert their actual canonical request path and reject known compatibility/duplicate paths. For `R0`/`R1` behavior, stop at one failure-discriminating assertion — a provenance chain on a contained change buys nothing and costs authoring and collection time on every run.

**Hard rule:** if the PRD introduces or changes executable behavior (CLI, API, jobs, file output, external integrations, or user-visible frontend), the plan MUST contain at least one row exercising a real entry point; user-visible changes need at least one real frontend entry point (the repo's e2e/UI test command or a manual app run), not only a unit test. "Unit tests are sufficient" is acceptable only for pure internal refactoring with no executable surface. Do not require live external services by default — gate them behind opt-in env vars and document the no-credential fallback.

For delivery/archive readiness, run the bundled checker when a Python runtime is available (resolve `scripts/check_prd_acceptance_checklist.py` relative to this skill directory, do not hard-code a path):

```bash
python scripts/check_prd_acceptance_checklist.py --repo-root <repo-root> --all
```

Pending PRDs may keep unchecked acceptance items, so this completion checker is not a blocker for a normal newly generated PRD; for a pending PRD about to be archived, validate it with `--check-provided --archive-ready tasks/pending/<prd-file>.md`. The checker also rejects executable oracle entries missing the evidence-chain fields defined below.

Before archive, perform a **Final Narrative Reconciliation** against the final implementation and fresh evidence. Correct earlier sections when implementation disproved an assumption; do not leave a false statement in the body merely because a later validation record explains it. Reconcile at least Part A interpretation and compatibility claims, public API/UI/CLI fields and entry points, supported modes and failure semantics, related PRD status, Functional Requirements, Risks, and the Decision Log. Record the outcome in Section 13 under `Final Reconciliation`.

### Phase 3.6: Human Review Map Gate

Once the change surface is known (from the architecture analysis, recommendation, and Change Impact Tree), classify it internally before writing the Part A **Human Review Map** (Section 2). For each meaningful change point:

1. **Layer:** which architecture layer it lands in (`api` / `core` / `engines` / `infrastructure` / a frontend app). The layer sets the default intervention: `core` business logic leans human; `api` adapters and `infrastructure` plumbing lean executor + automated gate.
2. **Risk tier:** evaluate the dimensions below and assign `R0`–`R3` using the highest applicable dimension or override; never average risks down.
3. **Intervention:** route to **human confirmation** or **executor + automated gate**, and name the concrete gate (a specific hook, test, or architecture check) when it is the latter. This classification guides what appears in Part A; it is not itself the human-facing format.

#### Internal Risk Classification

Use these tiers consistently:

| Tier | Definition | Typical consequence if wrong | Default intervention |
|---|---|---|---|
| `R0 · Trivial` | Mechanical or presentation-only change with no behavioral contract change | Local, immediately visible, and fully reversible | Executor + targeted automated gate |
| `R1 · Contained` | Behavioral change confined to one component or adapter, with a proven rollback and no fixed-zone boundary | Limited users or one workflow; recovery is routine | Executor + failure-discriminating test |
| `R2 · Material` | Cross-component behavior, compatibility, persistent state handling, or operational behavior where failure has meaningful blast radius | Multiple workflows/users affected, difficult diagnosis, or non-trivial recovery | Human confirmation when a product/contract trade-off remains; otherwise executor + strong oracle |
| `R3 · Critical` | Security, money, destructive/irreversible data effects, breaking external contracts, or correctness-critical concurrency/transaction behavior | Unauthorized access, financial loss, unrecoverable corruption, or broad outage | Human confirmation + executable negative control |

Evaluate these dimensions independently:

- **Reversibility:** immediate clean rollback (`R0/R1`); rollback needs coordinated repair, migration, or replay (`R2`); effects cannot be reliably undone (`R3`).
- **Blast radius:** one local surface (`R0/R1`); multiple components, tenants, workflows, or deployments (`R2`); system-wide or externally propagated impact (`R3`).
- **Security / money:** no trust or financial boundary (`R0/R1`); indirect quota, permission, sensitive-data, or cost impact (`R2`); authorization, credential exposure, billing correctness, or direct financial movement (`R3`).
- **Correctness criticality:** cosmetic or mechanically detectable (`R0`); ordinary behavior with a clear test oracle (`R1`); persistent-state, compatibility, ordering, or recovery correctness (`R2`); corruption, double execution, privilege failure, or safety-critical invariant (`R3`).

Classification rules:

1. Assign the tier from the **highest** dimension reached. Do not lower it because other dimensions are benign.
2. When evidence is incomplete, classify one tier higher until the uncertainty is resolved; record the missing evidence. Mere implementation complexity does not increase risk unless it increases consequence or uncertainty.
3. The fixed zones and cross-cutting triggers below override the calculated intervention. A fixed-zone item still receives an `R0`–`R3` tier; the override explains why human confirmation is required despite that tier.
4. Merge change points only when they share one human decision and one acceptance oracle. Do not inflate risk merely because several low-risk edits implement the same decision.
5. Record the internal result in Section 7 under `Risk Classification Register` with: `change point | tier | decisive dimension/override | intervention | oracle/gate`. Part A receives only the resulting human decisions, not this register.

Always flag these for human confirmation regardless of where the code lands:

- **Fixed zones:** core business logic / orchestration (`core/`); database structure / schema / migration (even under `infrastructure/`); security / auth / trust boundaries; external API contracts / breaking changes.
- **Cross-cutting triggers** (escalate any layer): money / billing / quota (when applicable); irreversible or destructive data operations (bulk delete, backfill, down-migration); concurrency / transaction / idempotency.

**Hard rule:** keep the human-confirm set short and justified — if everything is flagged, the map adds no signal. Anything not in a fixed zone and not hitting a trigger defaults to executor + automated gate. Do not show the full zone/trigger menu, hit/miss bookkeeping, architecture-layer classification table, or `rv-id` references in Part A; those are executor metadata, not human decisions. Instead, turn each human-confirm point into a concrete decision with a plain-language recommendation, material risk, an explicit `请确认：` question, and a short `验收：` statement. Prefer one or two natural paragraphs over repeated `建议 / 原因 / 风险 / 如何证明` micro-headings. When a schema change is present, surface the relevant ER diagram in the decision that asks the human to approve the schema. Every human-confirm decision must get a matching item under the `Human-Confirmed` group in the Section 9 Acceptance Checklist.

A concise decision must still retain every material forbidden behavior, failure behavior, compatibility boundary, data-completeness requirement, and supported-mode distinction. If the rewrite would let an executor restore a forbidden legacy path or change failure semantics while still claiming compliance, it is too vague.

**Acceptance Oracle Lock (up front):** For every human-confirm decision, define the executable oracle that locks its correct behavior — characterization/golden test for core logic; round-trip + migration up/down for schema; an actual unauthorized-access test for auth; contract/snapshot test for an external API. Keep the oracle ID, commands, boundary detail, and negative controls in Section 7.6; Part A states only what observable result will prove the decision. For executor + automated-gate work, name a gate that genuinely discriminates *this* change's failure (a generic `build`/`lint` that would pass even if the change were wrong is not valid). These oracles are agreed up front, run continuously during autonomous implementation, and presented as the Section 9 Acceptance Evidence Package. A high-risk decision with no definable oracle is flagged, not marked done.

Oracles are written before the implementation and run red first — the red run is the honest negative control, and writing them first keeps harness failures (wrong response shape, missing fixture, collection markers, colliding test data) cheap instead of paying for them under end-of-flow pressure. Never buy a `negative_control` by adding a fault-injection switch, failure mode, test-only config key, counter, or observation hook to production code; if no legitimate route to red exists, record `negative_control: not feasible — <reason>`.

### Phase 4: Conditional Web Research

Use web search only when the decision depends on external facts that may have changed, such as:
- third-party APIs, SDKs, or vendor capabilities
- security guidance, standards, or regulations
- framework, library, or platform version behavior
- ecosystem best practices that materially affect safety or operability
- explicit user requests for competitive or external-pattern research

When browsing:
- prefer official documentation and primary sources
- use search to inform constraints, compatibility, and risks, not to override repository patterns
- include sources and dates in the PRD
- clearly mark what is sourced fact versus your inference

Do not use web results as a reason to add abstractions by default.

### Phase 5: Prototype And Visual Artifact Gate

Always include a **Change Impact Tree** and at least one **flow/architecture diagram** (content rules A, B). Add a **low-fidelity prototype** (rule C) only when the request is UI-heavy, depends on multi-step interaction, or layout is needed to resolve scope; add an **ER diagram** (rule D) only when the data model or persistent state changes.

Create or modify interactive prototype files under `docs/prototypes/` only when the user explicitly asks for a prototype/wireframe/demo, or static diagrams cannot express the behavior. Skipping a prototype file does not waive the Frontend Impact Gate — the frontend must still be planned in the Change Impact Tree and validation when the user-visible surface changes.

### Phase 5.5: Executor Resilience Gate

Implementation detail may be thorough, but must survive normal repository drift. Anchor fragile edits to file paths, symbol/recipe/route names, config keys, or headings — never to line numbers or line ranges. Include `rg` searches for legacy, new-target, and likely-hidden references when repo-wide references exist, and state that the listed files are a starting point, not an exhaustive set. Keep every shell command copy-paste executable (prefer `rg`; if `grep` alternation is used, use `grep -E 'a|b'`), add a short failure-triage note for risky commands (build context, CI working dir, cache/artifact path, route, env var, composition root), and mark live/credential-dependent validation as opt-in or post-merge unless truly required.

### Phase 6: Generate And Save The PRD

Write the PRD to:
- `tasks/pending/<PRIORITY>-<TYPE>-<YYYYMMDD-HHMMSS>-<slug>.md`

| Segment | Description |
|---------|-------------|
| `PRIORITY` | `P0` (urgent) / `P1` (high) / `P2` (normal) / `P3` (low) |
| `TYPE` | `BUG` / `FEAT` / `REFACTOR` / `PERF` / `DOCS` / `CHORE` / `SECURITY` |
| `YYYYMMDD-HHMMSS` | Local current time |
| `slug` | Lowercase with hyphens |

Feature slug must be lowercase with hyphens.
Timestamp must use local current time in `YYYYMMDD-HHMMSS` format.

The PRD document itself must start with `# PRD: <descriptive feature title>` as its first Markdown H1 heading. This title is used to derive the GitHub Issue title and roadmap display name; it must describe the feature, not repeat the Part A/Part B section headings.

### Phase 7: PRD Compliance Gate

Before handing off, verify the document against the **Checklist** at the end of this skill — that list is the single source of truth for required sections, blocks, and blockers. Use `rg -n "^## " <prd-file>` for a quick section-header check.

When updating an existing PRD, run the Checklist against the entire file. If the existing file is non-compliant, preserve valid context and decisions but reorganize the document into the required structure instead of appending a compliant fragment to a non-compliant PRD.

**If the PRD changes executable behavior and the Realistic Validation Plan contains only unit/integration test entries with no real entry point, or the Validation Acceptance lacks a real entry-point item without a justified internal-refactoring exception, this gate FAILS. Do not hand off the PRD.**

---

## Required PRD Structure

This structure is the output contract for generated and updated PRDs. PRDs are organized into two altitudes, read top-down:

- **Part A · Review Layer** (Sections 1-4): what a human reads to accept or reject the work and to see where they must personally confirm. No implementation mechanism, file paths, commands, or scheduling metadata.
- **Part B · Build Layer** (Sections 5-13): what the executor (human or Agent) reads to implement. The human drills in only where the Part A Human Review Map points.

The PRD opens with `# PRD: <descriptive feature title>` as the very first heading, followed by a short two-altitude orientation note, then the heading `# Part A · 人审层 (Review Layer)`. The `<title>` must be a human-readable feature name, not the literal text "Part A · 人审层 (Review Layer)".

### 1. Introduction & Goals

Review-altitude only. Must include, in order:
- `### Problem Statement` — the pain, who feels it, why the current behavior is insufficient, and at least one concrete repository-observable current-state fact when available. Problem only; no solution, mechanism, files, or commands.
- `### Interpretation (解读回显)` — the Agent's reading of the request (from Phase 0), in a form the human can correct rather than merely nod at. This is the up-front approval target, the first of the two human touches, and the only gate that can catch a wrong interpretation. It must contain, in order:

  1. a **行为样例** table of 3-7 rows, including at least one edge case and one failure case:

     ```markdown
     | 输入 / 操作 | 期望观察到的结果 |
     |---|---|
     | [concrete action in the reader's domain language] | [exact observable result] |
     ```

     Follow the table with one line stating that these rows become the acceptance oracles verbatim, so correcting a cell corrects the acceptance criteria.

  2. **我默默定了这些** — a scannable list of every ambiguity resolved without asking, one line each, each naming the answer chosen.
  3. **我理解为不做** — 2-3 things the reader might plausibly have wanted that this PRD reads as excluded.
  4. the falsifiable prose reading ("read as X, not Y"): target behavior, key boundaries whose omission would permit a materially different implementation, and explicit non-goals. Preserve formal mode/config names only when the human is approving them.
- `### What The User Gets` — plain-language description of the capability/behavior the consumer (end user / caller / operator) receives, from the consumer's point of view. No implementation mechanism or module paths — mechanism belongs in Section 6.
- `### Measurable Objectives` — success criteria with an obvious pass/fail oracle through a test, runtime observation, static boundary check, or human-visible result. Do not use unqualified goals such as "clearer responsibilities", "more maintainable", "better extensibility", or "can be described as".

Do not place a proposed solution summary, validation commands, or delivery-dependency metadata here — those live in Sections 6, 7, and 8 respectively. The first section must stay reviewable without implementation detail.

### 2. Human Review Map (介入与风险地图)

The heart of the review layer: it tells a human exactly what they need to decide. It must be written for decision-making, not as a visible risk-classification worksheet.

For each human-confirm item, include:

- a descriptive decision heading phrased in domain language rather than internal layer names;
- one or two natural paragraphs explaining the recommendation, why it matters, and the material risk;
- an explicit `**请确认：**` question that can be answered directly;
- a short `**验收：**` statement describing the observable proof in plain language.

Do not force simple decisions into separate `建议` / `为什么需要确认` / `主要风险` / `如何证明` subsections. Expand only genuinely complex decisions with real alternatives. Avoid unexplained internal jargon in Part A; translate terms such as `semantic adapter`, `canonical contract`, `bbox`, and `provenance` into reader-facing language, retaining the code term in parentheses only when needed for precision.

After the decisions, include a compact **自动门禁，不需要逐项人工审阅** summary for ordinary work and a **本次明确不涉及** scope sentence. Do not list `rv-id` values, commands, file paths, the full fixed-zone menu, or hit/miss bookkeeping in Part A. Those details belong in Sections 5-9.

If no item requires human confirmation, state that once and show only the automated-gate summary and explicit non-scope. When a schema change requires approval, place the relevant ER diagram with that decision; otherwise the non-scope sentence may simply say there is no database structure change.

Keep the human-confirm set short and principled (see Core Rules 12-13 and Phase 3.6). "人工确认" means **high evidence burden** — the decision tops the Section 9 evidence package with an executable oracle for the single end-of-flow review — not a mid-flow interruption.

### 3. Usage And Impact After Implementation

Part of the review layer so reviewers see the concrete delivered outcome before requirement and implementation detail. Write it at PRD time as a target end state — a usage script to build toward and verify against — not a post-hoc log.

Required when the change is user-visible or has executable behavior (API/CLI/UI/job/startup/migration). For a purely internal change with no user-facing or executable surface, keep the section and state `No user-facing usage change; internal-only change.`

A role is affected when its existing entry point crosses the changed system flow, even if its UI and actions remain unchanged. Before writing this section, identify direct end users, reviewers/admins, operators, API/CLI callers, and developers/integrators. For every applicable role, state what changes or explicitly state what remains unchanged; do not silently omit direct users because the task has no frontend changes. Section 4 `actor` must cover the same affected roles.

See the `Usage And Impact After Implementation` content rule for the per-role walkthrough, entry-point description, backward-compatibility impact, and anti-duplication rules. Complete `curl`, CLI scripts, test commands, and evidence collection belong in Section 7.6, except that a normal end-user command may appear here when the product itself is a CLI.

### 4. Requirement Shape

- actor
- trigger
- expected behavior
- explicit scope boundary

The PRD then begins the build layer with the heading `# Part B · 执行器层 (Build Layer)`.

### 5. Repository Context And Architecture Fit

Must include:
- current relevant modules/files
- existing architecture pattern to follow
- ownership and dependency boundaries
- frontend impact: the affected frontend app(s) and the closest existing routes/components, or `No frontend impact` with a reason
- constraints from runtime, docs, tests, or workflows
- matching or related PRDs found in `tasks/pending/` and relevant prior PRDs from `tasks/archive/`

If no related PRDs are found, state that explicitly.
If related PRDs are found, identify whether this PRD:

- duplicates existing pending work and should update that PRD instead
- depends on another pending PRD
- blocks another pending PRD
- can run independently

Reflect dependency decisions in the Section 8 `Delivery Dependencies` block.

### 6. Recommendation

Must include:
- **Recommended Approach**
- why this is the best fit for the current architecture
- rationale for rejecting redundant abstractions
- a `### Proposed Solution Summary (实现机制)` that hands the implementer the mechanism: name the core mechanism or architecture path; state who supplies any required declaration/configuration/input and whether the system infers it or only consumes explicit data; identify the existing entry point, module boundary, API, workflow, or UI surface it plugs into; state the main system state/output/user-visible behavior change; and state the complexity intentionally avoided (new storage, parallel abstraction, changed state machine)
- **Alternatives Considered** only when a plausible non-trivial alternative exists

### 7. Implementation Guide

This section must start with this sentence or a close equivalent:

> This section is a living implementation guide based on current repository analysis. If implementation discovers additional affected files, hidden dependencies, edge cases, or a better path, update this PRD before proceeding.

Must include:
- **Core Logic:** how data and control move through the existing system
- **Change Impact Tree**
- **Risk Classification Register:** the internal `R0`–`R3` classification required by Phase 3.6; keep it in Part B, not the Human Review Map
- **Executor Drift Guard** when hidden references or repository drift could affect implementation
- **Flow or Architecture Diagram**
- **ER Diagram** when the data model changes (this is the detail figure linked from the Section 2 schema-review note)
- **Realistic Validation Plan** (a structured YAML oracle block — see content rule F)
- **Low-Fidelity Prototype** when required
- **Interactive Prototype Change Log** when prototype files changed
- **External Validation** when web research was used

### 8. Delivery Dependencies

Tool-neutral sequencing metadata, not a tool-specific queue syntax. Use `none` explicitly when the task has no dependency.

Use this shape:

```markdown
### Delivery Dependencies

- Group: [logical-delivery-group-or-none]
- Depends on tasks/issues:
  - none
- Gate type: none
- Notes: [Use tool-neutral dependency names. Do not put tool-specific hidden markers here.]
```

Rules:
- `Group` names the logical delivery group for this PRD, or `none`.
- `Depends on tasks/issues` lists upstream task names, PRD slugs, issue numbers, or `none`.
- `Gate type` must be `none`, `soft`, or `hard`.
- `hard` means an execution tool may treat the dependency as a blocking gate when that repository has a deterministic adapter.
- `soft` documents sequencing context but must not be treated as a blocking gate unless a repository-specific PRD explicitly defines that behavior.
- Do not place tool-specific hidden markers, labels, or queue syntax in this block. Repository-specific publish tooling may translate the block into its own markers or labels.

### 9. Acceptance Checklist

Include:
- a dedicated section named `Acceptance Checklist`
- this section is the **single human-facing acceptance artifact** ("look once at the end"): organize it as an **Acceptance Evidence Package** ordered by the Section 7 risk classification — human-confirmed and `R3` oracle results first, then `R2` results and decision reconciliation, then contract diffs and folded `R1`/`R0` gate results
- every checkbox must be **evidence-bearing**: name the command output, observation, or artifact that proves it, not a bare claim
- a `Human-Confirmed` group whose checkbox items correspond one-to-one to the human-confirm change points in the Section 2 Human Review Map
- grouped checklist headings such as `Architecture Acceptance`, `Dependency Acceptance`, `Behavior Acceptance`, `Frontend Acceptance` (when a frontend app changes), `Documentation Acceptance`, `Validation Acceptance`, and `Delivery Readiness` (the overall delivery gate formerly in Definition Of Done) when relevant
- concrete, repository-verifiable checkbox items
- exact paths, API contracts, commands, or search assertions where applicable
- at least one `Validation Acceptance` item that exercises the changed behavior through the highest feasible real entry point; if no real entry-point validation is included, the PRD must explicitly document that the change is pure internal refactoring with no executable surface, and this justification must be reviewed in the Decision Log
- this checklist is the single completion gate; do not replace any item with a vague summary bullet or local requirement acceptance notes

### 10. Functional Requirements

Use numbered requirements such as `FR-1`, `FR-2`.

### 11. Non-Goals

List explicit out-of-scope items.

### 12. Risks And Follow-Ups

List only unavoidable migration risk, rollout risk, or explicitly approved non-blocking follow-up.
Do not use this section to park work that is actually required for the recommended target state.

### 13. Decision Log

Record every key decision made during this PRD as a permanent reference that survives archival.

Rules:
- Each row answers one decision question (e.g. "which architecture pattern", "which storage backend").
- **Chosen** must match the recommendation in Section 6.
- **Rejected** must name the concrete alternative from Section 6 when one is documented, not a vague "other approaches".
- **Rationale** must be one concrete sentence — not "fits the architecture" but why specifically.
- Assign sequential IDs: D-01, D-02, …
- Minimum one row per PRD. Add rows for major trade-offs or alternatives explicitly resolved in Section 6.

---

## PRD Content Rules

Read [references/prd-content-rules.md](references/prd-content-rules.md) before generating the final PRD. It defines the required Change Impact Tree, diagrams/prototypes, structured validation oracle, external validation, post-implementation usage, and evidence-bearing Acceptance Checklist without duplicating those details in the main workflow.

---

## Checklist

**BLOCKER items must be satisfied before the PRD can be handed off. Non-blocker items should be satisfied but do not stop delivery.**

* [ ] Rewrote the request into a concrete behavior change
* [ ] Inspected the repository before asking questions
* [ ] Searched existing `tasks/pending/` PRDs for duplicate, prerequisite, blocking, or downstream work before creating/updating this PRD
* [ ] Checked relevant `tasks/archive/` PRDs when prior decisions or completed related work could affect the plan
* [ ] Identified the closest existing code path
* [ ] Documented the Existing PRD Relationship in Section 5 and reflected sequencing decisions in the Section 8 Delivery Dependencies block
* [ ] Handled critical unresolved questions correctly: asked the user only when repository evidence was insufficient and the answer would materially affect the PRD
* [ ] Compared a minimal-change option against a heavier option
* [ ] Justified every new abstraction, dependency, or file path
* [ ] Rejected redundant layers where reuse was sufficient
* [ ] Assessed whether independently approvable decisions should be split; documented why the remaining scope is one cohesive target state
* [ ] **BLOCKER:** The PRD starts with `# PRD: <descriptive feature title>` as its first Markdown H1 heading; the title describes the feature and is not the literal Part A/Part B heading text
* [ ] **BLOCKER:** Structured as Part A (Review Layer, Sections 1-4) and Part B (Build Layer, Sections 5-13); Part A contains no implementation mechanism, file paths, commands, or scheduling metadata
* [ ] Section 1 stays review-altitude: Problem Statement, `Interpretation (解读回显)`, What The User Gets, and Measurable Objectives only — no proposed solution summary, validation commands, or delivery-dependency metadata
* [ ] **BLOCKER:** The `Interpretation (解读回显)` is correctable, not just readable — a behavior-example table of ≥3 rows (with an edge case and a failure case) whose rows become the Section 7.6 oracles verbatim, a `我默默定了这些` list of ambiguities resolved without asking, a `我理解为不做` list of plausibly-wanted excluded scope, and the falsifiable prose reading. Enforced by `scripts/check_prd_acceptance_checklist.py`
* [ ] Problem Statement includes a concrete repository-observable current-state fact when available; Measurable Objectives are pass/fail outcomes rather than unqualified maintainability claims
* [ ] **BLOCKER:** Section 2 Human Review Map presents only concrete human decisions, each with a plain-language recommendation/risk explanation, an explicit `请确认：` question, and a short observable `验收：` statement; it does not expose the fixed-zone menu, hit/miss bookkeeping, classification tables, commands, file paths, or `rv-id` values
* [ ] Section 2 ends with a compact automated-gate summary and explicit non-scope; schema changes surface the relevant ER diagram with the decision that approves them
* [ ] Every Section 2 human decision maps to ≥1 executable oracle in Section 7.6 and one evidence-bearing `Human-Confirmed` item in Section 9, without requiring the reader to follow IDs from Part A
* [ ] Part A translated rather than deleted required paths, supported modes, forbidden legacy/bypass paths, data-completeness requirements, failure semantics, compatibility promises, and acceptance conclusions
* [ ] **BLOCKER:** Section 7 contains a complete `Risk Classification Register`; every meaningful change point has an `R0`–`R3` tier derived from its highest applicable dimension, a decisive reason or override, an intervention, and a failure-discriminating oracle/gate
* [ ] Human-confirm set is short and principled (fixed-zone overrides, cross-cutting triggers, `R3`, or unresolved material `R2` decisions only); ordinary `R0`/`R1` changes are routed to executor + automated gate
* [ ] Section 6 Recommendation includes the `Proposed Solution Summary (实现机制)` carrying the mechanism that moved out of Section 1
* [ ] Section 8 includes a tool-neutral Delivery Dependencies block, using explicit `none` values when no sequencing dependency exists
* [ ] Section 9 Acceptance Checklist includes a `Human-Confirmed` group whose items map one-to-one to the Section 2 human-confirm change points
* [ ] **BLOCKER:** Section 9 is organized as a risk-ordered Acceptance Evidence Package using the Section 7 classification (human-confirmed and `R3` evidence first, then `R2`, then folded `R1`/`R0` gates), with evidence-bearing items suitable for a single end-of-flow human review
* [ ] Included a Change Impact Tree with architecture-fit reasoning
* [ ] **BLOCKER:** Stated frontend impact explicitly — for user-visible features named the affected frontend app(s) and their changes (components, routes, API wiring) in the Change Impact Tree; for backend-only work recorded `No frontend impact` with a reason; never omitted the frontend silently
* [ ] For user-visible changes, the Realistic Validation Plan includes a real frontend entry point (the repo's e2e/UI test command or a manual app run), not only component unit tests
* [ ] For user-visible or executable-behavior changes, included a `Usage And Impact After Implementation` section covering every role whose existing entry point crosses the changed flow, including unchanged end-user behavior; for purely internal changes recorded `No user-facing usage change`
* [ ] Section 3 roles and Section 4 Actor are consistent; What The User Gets, Section 3, Functional Requirements, and Non-Goals do not contradict one another
* [ ] **BLOCKER:** Did not include line-number-dependent edit instructions; all fragile edits use semantic anchors and/or `rg` search commands
* [ ] Included at least one flow or architecture diagram
* [ ] Implementation Guide includes the required living implementation guide statement
* [ ] Included an Executor Drift Guard when hidden references, moved paths, config rewires, or repository-wide updates are likely
* [ ] **BLOCKER:** Included a Realistic Validation Plan as a structured YAML oracle block parseable by deterministic tooling, with `id` / `behavior` / `real_entry` / `expected` / `mock_boundary` / `tier` / `test_layer` / `required_for_acceptance` on every entry; `R2`/`R3` entries add the provenance chain (`critical_value_source` / `must_cross` / `forbidden_bypasses` / `fresh_state_probe` / `final_tree_evidence`) and `R3` / human-confirm entries add `negative_control` + `expected_fail`; no `negative_control` was bought by adding a failure switch to production code
* [ ] Added low-fidelity prototype only when actually needed
* [ ] Added ER diagram only when data model changes are present
* [ ] Used web research only when external facts were required
* [ ] Cited sources and dates for any web-derived claims
* [ ] Saved new PRDs to `tasks/pending/<PRIORITY>-<TYPE>-<YYYYMMDD-HHMMSS>-<slug>.md`
* [ ] Did not require acceptance-completion checks for normal pending PRDs; for archive readiness, ran the bundled `scripts/check_prd_acceptance_checklist.py` checker when available
* [ ] For existing PRD updates, restructured the whole PRD to the required shape instead of appending to a non-compliant file
* [ ] Ran a section compliance check, manually or with `rg -n "^## " <prd-file>`; all required sections are present in order
* [ ] Functional Requirements use `FR-1`, `FR-2`, … identifiers, and Non-Goals + Risks And Follow-Ups sections are present
* [ ] Included a dedicated `Acceptance Checklist` section (the single completion gate; no separate Definition Of Done) and did not collapse it into local requirement notes
* [ ] **BLOCKER:** All validation/search commands are copy-paste executable; repository searches prefer `rg`, and any `grep` alternation uses an explicit compatible mode
* [ ] **BLOCKER:** Validation Acceptance includes the highest feasible real entry-point validation or explicitly documents why the change is pure internal refactoring with no executable surface
* [ ] **BLOCKER:** Required evidence comes from the exact producer/UI value, crosses every named boundary without a listed bypass, proves the postcondition from fresh state, and was recollected after the last relevant final-tree change; contradictory field evidence reopens acceptance
* [ ] Recommended a full target state rather than leaving required work in `Phase 2`, `follow-up`, or temporary compatibility layers unless a hard constraint was explicitly documented
* [ ] Decision Log has at least one row for each major trade-off or documented alternative resolved in Section 6
* [ ] Each Decision Log row names a concrete rejected alternative (not a vague "other approaches")
* [ ] Before archive, completed Final Reconciliation and corrected any earlier narrative contradicted by the final implementation or evidence
