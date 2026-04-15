---
name: prd
description: "[Updated 2026-04-09] Generate an architecture-aware technical PRD. Triggers on: create a prd, write prd for, plan this feature. Prioritizes reuse, minimal-change plans, and conditional web research."
---

# PRD Generator (Architecture-First)

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

---

## Workflow

### Phase 0: Rewrite The Request As An Implementable Claim

State in plain language:
- who wants what behavior
- under which conditions
- what changes in system state, API, UI, or workflow

If you cannot rewrite the request concretely, call that out before generating a PRD.

### Phase 1: Repository Context And Architecture Gate

Before asking questions or proposing changes, inspect the repository for:
- tech stack and runtime constraints
- current module boundaries and dependency direction
- existing extension points and reusable code paths
- current data model and state ownership
- existing docs, tests, and workflows relevant to the request

You must explicitly identify:
- **Existing Path:** the current code path that is closest to the requested change
- **Reuse Candidates:** files/modules that can be extended directly
- **Architecture Constraints:** boundaries that should not be broken
- **Potential Redundancy Risks:** likely sources of duplicated logic or parallel abstractions

Do not ask questions that can be answered by reading the repository.

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

Visual artifacts should clarify the change, not pad the PRD.

Always include:
- a **Change Matrix**
- at least one **flow or architecture diagram**

Include a **low-fidelity prototype** only when:
- the request is UI-heavy, or
- behavior depends on multi-step user interaction, or
- layout is necessary to resolve scope ambiguity

Include an **ER diagram** only when data model or persistent state changes.

Create or modify interactive prototype files under `docs/prototypes/` only when:
- the user explicitly asks for a prototype, wireframe, or interactive demo, or
- static diagrams cannot adequately express the behavior under review

Do not create prototype files merely because the feature touches UI.

### Phase 6: Generate And Save The PRD

Write the PRD to:
- `tasks/[YYYYMMDD-HHMMSS]-prd-[feature-name].md`

Feature slug must be lowercase with hyphens.
Timestamp must use local current time in `YYYYMMDD-HHMMSS` format.

---

## Required PRD Structure

### 1. Introduction & Goals

Brief problem statement plus measurable objectives.

### 2. Requirement Shape

- actor
- trigger
- expected behavior
- explicit scope boundary

### 3. Repository Context And Architecture Fit

Must include:
- current relevant modules/files
- existing architecture pattern to follow
- ownership and dependency boundaries
- constraints from runtime, docs, tests, or workflows

### 4. Recommendation

Must include:
- **Recommended Approach**
- why this is the best fit for the current architecture
- rationale for rejecting redundant abstractions
- **Alternatives Considered** only when a plausible non-trivial alternative exists

### 5. Implementation Guide

Must include:
- **Core Logic:** how data and control move through the existing system
- **Affected Files:** predicted file paths
- **Change Matrix**
- **Flow or Architecture Diagram**
- **Low-Fidelity Prototype** when required
- **ER Diagram** when required
- **Interactive Prototype Change Log** when prototype files changed
- **External Validation** when web research was used

### 6. Definition Of Done

Include:
- implementation validation
- docs updates
- no regression checks
- architecture-fit checks
- overall delivery/readiness gates only; do not use this section as a substitute for the Acceptance Checklist

### 7. Acceptance Checklist

Include:
- a dedicated section named `Acceptance Checklist`
- grouped checklist headings such as `Architecture Acceptance`, `Dependency Acceptance`, `Behavior Acceptance`, `Documentation Acceptance`, and `Validation Acceptance` when relevant
- concrete, repository-verifiable checkbox items
- exact paths, API contracts, commands, or search assertions where applicable
- no checklist item may be replaced by a `Definition Of Done` bullet or by per-story acceptance criteria

### 8. User Stories

Focus on business logic unique to this change.

### 9. Functional Requirements

Use numbered requirements such as `FR-1`, `FR-2`.

### 10. Non-Goals

List explicit out-of-scope items.

### 11. Risks And Follow-Ups

List only unavoidable migration risk, rollout risk, or explicitly approved non-blocking follow-up.
Do not use this section to park work that is actually required for the recommended target state.

### 12. Decision Log

Record every key decision made during this PRD as a permanent reference that survives archival.

Rules:
- Each row answers one decision question (e.g. "which architecture pattern", "which storage backend").
- **Chosen** must match the recommendation in Section 4.
- **Rejected** must name the concrete alternative from Section 4 when one is documented, not a vague "other approaches".
- **Rationale** must be one concrete sentence — not "fits the architecture" but why specifically.
- Assign sequential IDs: D-01, D-02, …
- Minimum one row per PRD. Add rows for major trade-offs or alternatives explicitly resolved in Section 4.

---

## PRD Content Rules

### A. Change Matrix

Use this structure:

| Change Target | Current State | Target State | How to Modify | Why This Fits Existing Architecture | Affected Files |
|---|---|---|---|---|---|
| Example: user profile validation | Validation split across route handlers | Validation consolidated in existing service | Move validation into `UserService` and update call sites | Reuses existing service boundary instead of adding a parallel validator layer | `src/services/user.py`, `src/routes/user.py` |

### B. Flow / Architecture Diagram

At least one Mermaid diagram is required.
Prefer a diagram that shows where the requested change lands inside the existing system.

Mermaid label safety rule:
- If a node label contains special characters such as `/`, `{}`, `[]`, `()`, `:`, or `-`, wrap the label with double quotes.

### C. Low-Fidelity Prototype

Include only when required by Phase 5.
Use ASCII wireframe or Mermaid layout.

### D. ER Diagram

Include only when:
- a new entity/table/model is added
- fields or relationships change
- persistent structured state changes

If not required, state:
- `No data model changes in this PRD.`

### E. Interactive Prototype Change Log

Include only when prototype files were actually changed.

| File Path | Change Type | Before | After | Why |
|---|---|---|---|---|
| `docs/prototypes/<feature>-demo.html` | Modify | Static layout only | Added state transition controls | Clarify behavior that static diagrams could not show |

If no prototype files changed, state:
- `No interactive prototype file changes in this PRD.`

### F. External Validation

Include only when web research was used.

Use this structure:

| Topic | Source | Checked On | Relevant Finding | Impact On Recommendation |
|---|---|---|---|---|
| [Vendor/API/standard] | [URL or document title] | [YYYY-MM-DD] | [Fact] | [Constraint, risk, or compatibility note] |

If no web research was needed, state:
- `No external validation required; repository evidence was sufficient.`

### G. Acceptance Checklist

This section is required even when User Stories already include acceptance criteria.
Do not merge it into `Definition Of Done`.

Use grouped subsections.
For architecture-heavy or refactor work, prefer:
- `Architecture Acceptance`
- `Dependency Acceptance`
- `Behavior Acceptance`
- `Documentation Acceptance`
- `Validation Acceptance`

Each checkbox must describe a concrete, verifiable end state.
Prefer exact file paths, commands, API paths/contracts, dependency boundaries, or repository search assertions over vague quality statements.
If a default group does not fit the task, rename or replace it with a more precise group instead of dropping the section entirely.
The checklist must validate the final target state, not merely the completion of an interim first phase.

---

## Checklist

* [ ] Rewrote the request into a concrete behavior change
* [ ] Inspected the repository before asking questions
* [ ] Identified the closest existing code path
* [ ] Handled critical unresolved questions correctly: asked the user only when repository evidence was insufficient and the answer would materially affect the PRD
* [ ] Compared a minimal-change option against a heavier option
* [ ] Justified every new abstraction, dependency, or file path
* [ ] Rejected redundant layers where reuse was sufficient
* [ ] Included a Change Matrix with architecture-fit reasoning
* [ ] Included at least one flow or architecture diagram
* [ ] Added low-fidelity prototype only when actually needed
* [ ] Added ER diagram only when data model changes are present
* [ ] Used web research only when external facts were required
* [ ] Cited sources and dates for any web-derived claims
* [ ] Saved to `tasks/[YYYYMMDD-HHMMSS]-prd-[feature-name].md`
* [ ] Included a dedicated `Acceptance Checklist` section and did not collapse it into `Definition Of Done` or User Story acceptance criteria
* [ ] Recommended a full target state rather than leaving required work in `Phase 2`, `follow-up`, or temporary compatibility layers unless a hard constraint was explicitly documented
* [ ] Decision Log has at least one row for each major trade-off or documented alternative resolved in Section 4
* [ ] Each Decision Log row names a concrete rejected alternative (not a vague "other approaches")
