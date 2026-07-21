# PRD Content Rules

Read this reference before generating the final PRD.

## Contents

- [A. Change Impact Tree](#a-change-impact-tree)
- [B. Flow / Architecture Diagram](#b-flow--architecture-diagram)
- [C. Low-Fidelity Prototype](#c-low-fidelity-prototype)
- [D. ER Diagram](#d-er-diagram)
- [E. Interactive Prototype Change Log](#e-interactive-prototype-change-log)
- [F. Realistic Validation Plan](#f-realistic-validation-plan-oracle-block)
- [G. External Validation](#g-external-validation)
- [H. Usage And Impact After Implementation](#h-usage-and-impact-after-implementation)
- [I. Acceptance Checklist](#i-acceptance-checklist)

## A. Change Impact Tree

Use Tree style, organized by layer:

```text
.
├── xxx/
│   └── xxx.py
│       [新增] / [修改] / [删除]
│       【总结】一句话总结本次修改
│
│       ├── 具体改动 1
│       ├── 具体改动 2
│       └── 具体改动 3
```

**每个文件必须有【总结】**：一句话、高信息密度，直接说明文件改了什么，不重复文件名。

层级的推荐顺序：

```text
Database
Infrastructure
Domain
API
Frontend (per the repo's frontend app(s))
Tests
Docs
```

内容重点覆盖：SQL 变化、字段变化、数据流变化、API 变化、ORM 变化、Domain Logic 变化、前端组件/路由/状态变化、前端调用后端 API 的客户端代码、UI 展示变化、类型同步、测试同步。

当需求触达用户可见界面时，Change Impact Tree 必须包含仓库实际前端 app 的具体改动：组件、路由/页面、状态、调用后端 API 的客户端代码、类型同步。禁止用一行"更新 UI"代替前端规划。

不要包含：import 调整、格式化、lint 修复、无意义 rename、与任务无关的小改动。

For executor handoff quality:

- keep file-level and logical specificity, but do not reference exact line numbers or line ranges
- locate fragile edits by semantic anchors such as function names, recipe names, route names, config keys, or headings
- include the `rg` command an executor can use to find each important anchor when helpful
- if the file list could be incomplete, say so and point to the Executor Drift Guard instead of pretending the tree is exhaustive

## B. Flow / Architecture Diagram

At least one Mermaid diagram is required.
Prefer a diagram that shows where the requested change lands inside the existing system.

Mermaid label safety rule:

- If a node label contains special characters such as `/`, `{}`, `[]`, `()`, `:`, or `-`, wrap the label with double quotes.

## C. Low-Fidelity Prototype

Include only when required by Phase 5.
Use ASCII wireframe or Mermaid layout.

## D. ER Diagram

Include only when:

- a new entity/table/model is added
- fields or relationships change
- persistent structured state changes

If not required, state:

- `No data model changes in this PRD.`

## E. Interactive Prototype Change Log

Include only when prototype files were actually changed.

| File Path | Change Type | Before | After | Why |
|---|---|---|---|---|
| `docs/prototypes/<feature>-demo.html` | Modify | Static layout only | Added state transition controls | Clarify behavior that static diagrams could not show |

If no prototype files changed, state:

- `No interactive prototype file changes in this PRD.`

## F. Realistic Validation Plan (Oracle block)

Every PRD with executable behavior must include this as a **structured YAML block** — the single machine-and-human-readable oracle source. Section 2's evidence column, the Section 9 evidence package, and any deterministic extractor reference/parse the `id`s here. Do not restate oracles as prose tables elsewhere.

Each entry:

```yaml
- id: rv-1
  behavior: <user-visible behavior this proves, plain language>
  real_entry: "<exact command / URL / entry point the real user runs>"   # not a unit test or helper
  expected: "<observable that proves it works>"
  mock_boundary: "<what may be mocked vs must be real>"   # the under-test boundary must NOT be mocked
  critical_value_source: "<exact producer/UI response/clipboard source of URLs, tokens, IDs, commands, or payloads>"
  must_cross: "<ordered real boundaries: UI -> proxy -> canonical API -> commit -> fresh read>"
  forbidden_bypasses: "<helpers, reconstructed values, direct calls, fake adapters, legacy/compatibility paths>"
  fresh_state_probe: "<independent new browser/request/process/DB session observation after the action>"
  final_tree_evidence: "<how evidence is tied to the final relevant code tree and when it must be rerun>"
  negative_control: "<command or seeded break that makes this entry go RED>"   # proves the test can fail
  expected_fail: "<what red looks like>"
  test_layer: unit|integration|e2e|smoke|sandbox|manual
  required_for_acceptance: true
```

Rules:

- One entry per real observable behavior; every Section 2 human-confirm row points to ≥1 `id`.
- `real_entry` is the highest-fidelity real entry point (not pytest/helpers); for user-visible changes at least one entry's `real_entry` is the repo's e2e/UI command or a manual app run.
- `negative_control` + `expected_fail` are **mandatory for human-confirm / high-risk entries** — a test that cannot be shown to fail proves nothing. A purely mechanical low-risk entry may instead name a discriminating gate.
- `critical_value_source`, `must_cross`, `forbidden_bypasses`, `fresh_state_probe`, and `final_tree_evidence` are mandatory for every executable entry. Apply the evidence-integrity reference loaded by Phase 3.5.
- `real_entry` / `negative_control` commands must be copy-paste executable from the documented working directory; prefer `rg`; any `grep` alternation uses `grep -E 'a|b'`.
- Treat production / vendor / credential-dependent entries as `opt-in` / `post-merge`; document the no-credential fallback that still runs.
- Add a short failure-triage note beneath the block (first config/path/boundary to inspect).
- Deterministic tooling parses this block; if a PRD declares executable behavior but the block is missing or unparseable, that is a loud failure — never infer it.

If the change has no executable behavior, state:

- `No executable behavior changes; realistic validation is limited to documentation/build checks.`

## G. External Validation

Include only when web research was used.

Use this structure:

| Topic | Source | Checked On | Relevant Finding | Impact On Recommendation |
|---|---|---|---|---|
| [Vendor/API/standard] | [URL or document title] | [YYYY-MM-DD] | [Fact] | [Constraint, risk, or compatibility note] |

If no web research was needed, state:

- `No external validation required; repository evidence was sufficient.`

## H. Usage And Impact After Implementation

Describe the post-implementation world from the consumer's point of view, written at PRD time as a concrete target end state — not a post-hoc log filled in after delivery. It gives reviewers and the implementer a usage script to build toward and to verify against later.

Include this section when the change is user-visible or has executable behavior (API/CLI/UI/job/startup/migration). When the change is purely internal with no user-facing or executable surface, state instead:

- `No user-facing usage change; internal-only change.`

When included, cover only what the abstract sections cannot:

- **Per-role usage walkthrough:** for each affected role that actually applies (end user, admin, developer, operator), the concrete steps to use the delivered capability — which page/route, which entry point, which fields, and the resulting identifier or output format. Anchor to real paths and entry points, not line numbers.
- **Entry commands / API examples:** copy-paste `curl`, CLI, or client snippets that exercise the new or changed entry points. This is usually the only place these concrete examples live.
- **Impact on existing behavior:** backward-compatibility and migration effects only — what stays the same for existing users/data/config, plus any new optional config/env and its default-off behavior.

Rules:

- This subsection is the concrete walkthrough; keep `Goals`, `Functional Requirements`, and `Requirement Shape` abstract and do not restate them verbatim here.
- Do not introduce a capability that has no matching `FR-n`; if writing this subsection surfaces one, add the `FR` first.
- The impact list covers backward-compatibility/migration, not the "won't build" scope — keep negative scope in `Non-Goals` and do not duplicate it here.

## I. Acceptance Checklist

This section is required even when Functional Requirements already include acceptance criteria.
It is the single completion artifact and also serves as the overall delivery-readiness gate (the former Definition Of Done); there is no separate Definition Of Done section.

Use grouped subsections. For architecture-heavy or refactor work, prefer:

- `Architecture Acceptance`
- `Dependency Acceptance`
- `Behavior Acceptance`
- `Frontend Acceptance` (when a frontend app changes)
- `Documentation Acceptance`
- `Validation Acceptance`
- `Delivery Readiness` (recommended approach fully implemented; no open regression or rollout blocker — the former Definition Of Done)

Each checkbox must describe a concrete, verifiable end state.
Prefer exact file paths, commands, API paths/contracts, dependency boundaries, or repository search assertions over vague quality statements.
Validation Acceptance must include the highest feasible real entry point from the Realistic Validation Plan, not only isolated lower-level tests, unless the PRD explicitly explains why no executable behavior changed. "Mocked at boundary" or "unit tests cover it" are not valid justifications for skipping real entry-point validation when executable behavior changed.
For executable behavior, it must also name the critical value provenance, actual boundaries crossed, fresh-state observation, and final-tree evidence artifact. Any relevant implementation change or contradictory real-world observation invalidates the affected prior evidence and requires re-verification before archive.
For repository-wide refactors, migrations, or path moves, include at least one repository search assertion that proves obsolete references are gone and expected target references remain.
If a default group does not fit the task, rename or replace it with a more precise group instead of dropping the section entirely.
The checklist must validate the final target state, not merely the completion of an interim first phase.
