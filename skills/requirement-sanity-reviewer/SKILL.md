---
name: requirement-sanity-reviewer
description: "[Updated 2026-04-08] Review user requests, tickets, PRDs, and implementation plans for requirement flaws before coding. Detect ambiguity, contradictions, hidden assumptions, missing acceptance criteria, infeasible scope, unsafe trust boundaries, and conflicts with the existing codebase. Use when the requirement itself may be wrong, incomplete, or internally inconsistent."
---

# Requirement Sanity Reviewer

## Overview

Use this skill when the risky part is not only the code, but the request itself.

This skill reviews a requirement, issue, ticket, PRD, or user prompt for:

- hidden assumptions
- contradictions
- missing business rules
- undefined edge cases
- mismatch with the current codebase
- unsafe security or trust-boundary assumptions
- acceptance criteria gaps
- rollout and operability gaps
- outdated delivery or engineering practices compared with current norms

It is the upstream counterpart to `code-reviewer`.
`code-reviewer` asks "is the implementation safe and correct?"
This skill asks "is the requirement coherent enough to implement safely?"

Use it before implementation, during planning, or when code review suggests the spec may be wrong.

This skill has two modes:

- **Local sanity mode**: check the requirement against this repository's actual code, docs, tests, and workflows
- **External reality mode**: when the requirement depends on current best practices, platform norms, tooling evolution, or ecosystem standards, verify those with browsing before concluding

## When To Activate

Activate when any of these are true:

- The user says the requirement may be wrong, vague, incomplete, or self-contradictory.
- A ticket or PRD exists, but acceptance criteria are weak or missing.
- The requested behavior may conflict with current product logic, architecture, or security boundaries.
- The implementation would require guessing business rules.
- A reviewer needs to decide whether a bug is in the code or in the requirement.
- A change sounds simple in prose but likely has hidden state, permission, data, or migration consequences.
- The request may preserve legacy workflow choices that are now an operational liability.
- The team may be using an outdated process and needs a reminder that current practice has moved on.

## Inputs To Review

Start from the strongest artifact available:

1. Explicit requirement text from the user
2. Issue, PRD, task file, or design note
3. Existing docs under `docs/` and `mkdocs.yml`
4. Current code paths, tests, API contracts, and schemas
5. Recent diffs or commits if the requirement is already partly implemented
6. External sources when the quality of the decision depends on what is current now

Do not ask questions that can be answered by reading the repository.

## Workflow

### Step 1: Pin Down The Actual Claim

Rewrite the requirement in one or two plain statements:

- Who wants what behavior?
- Under which conditions?
- What should change in system state, UI, or API output?

If you cannot rewrite it concretely, that is already a finding.

### Step 2: Inspect Repository Reality

Read only the files needed to verify the request:

- route handlers, services, models, settings, tests
- docs and existing product behavior descriptions
- auth, billing, state machine, or migration code if relevant

Prefer repository facts over assumptions.

### Step 3: Decide Whether External Validation Is Required

You MUST use browsing when the conclusion depends on information that may have changed recently or varies across the ecosystem, for example:

- CI/CD and deployment norms
- framework or platform best practices
- security guidance
- cloud, Docker, Kubernetes, GitHub Actions, or vendor capabilities
- API deprecations or current recommended patterns
- whether a manual process has become an obvious operational smell compared with current practice

Prioritize:

1. official documentation
2. primary vendor sources
3. well-maintained upstream repositories
4. strong practitioner references only if primary sources are insufficient

Use GitHub to inspect how actively maintained projects currently structure the same concern.
Do not equate popularity with correctness. Compare:

- current repository practice
- current external norm
- migration cost
- actual risk of staying behind

### Step 4: Run The Sanity Checks

Apply the checklist in [Requirement Checklist](references/requirement-checklist.md).

Treat every finding as one of:

- **Fact**: directly supported by code, docs, or the provided requirement text
- **Inference**: a likely risk derived from those facts
- **Open question**: cannot be resolved from local evidence

Do not present inferences as facts.

### Step 5: Decide Severity

- **CRITICAL**: dangerous or impossible to implement safely as written
- **HIGH**: likely wrong, self-contradictory, or guaranteed to create regressions or guesswork
- **MEDIUM**: under-specified, but fixable with explicit decisions
- **LOW**: clarity or polish gaps that do not block implementation

Escalate outdated practice findings to **HIGH** when the requirement preserves a pattern that materially harms security, reliability, delivery speed, rollback safety, or team scalability.

Examples:

- manual production deploys with no repeatable pipeline
- no CI checks on a collaborative codebase
- mutable production servers with hand-applied fixes
- undocumented release steps known only by one operator

### Step 6: Produce A Corrective Output

Do not stop at criticism.
Always convert findings into a tighter requirement shape:

- corrected requirement wording
- missing acceptance criteria
- missing assumptions to confirm
- explicit non-goals
- recommended implementation direction if obvious from the codebase
- recommended modernization direction when the current process is behind current practice

## Review Rules

- Prioritize correctness over completeness.
- Report only findings with solid evidence or strong reasoning.
- Consolidate related gaps into one finding.
- Skip purely stylistic product opinions unless they create implementation ambiguity.
- Flag whenever the implementation would require inventing business rules.
- If the requirement conflicts with repository reality, prefer the repository as evidence and call out the mismatch explicitly.
- If the task needs current external facts, say that browsing or external validation is required before implementation.
- If the repository uses a legacy workflow and the wider ecosystem has clearly moved to a safer or more maintainable pattern, call that out explicitly.
- Do not treat "this is how we do it today" as a defense if the process is brittle, manual, or unscalable.
- Recommend modernization only when it changes outcomes that matter: reliability, security, operability, delivery speed, auditability, or maintenance burden.

## Project-Specific Checks

These are especially important in this repository:

- Documentation is part of the product. If behavior changes, `docs/` and `mkdocs.yml` may also need changes.
- Windows-safe file I/O requires explicit `encoding="utf-8"`.
- Public Python APIs should have Google Style docstrings and type annotations.
- AI-native naming and SSA-style flow matter; vague requirements often produce vague variable and type design.
- `uv`, `just`, and MkDocs workflows are first-class constraints, not optional details.

## Output Format

Present findings first, ordered by severity.

Use this structure:

```text
[HIGH] Requirement contradicts current permission model
Evidence: `src/auth/...` only allows owners/admins to perform this action, but the request says "any signed-in user".
Impact: Implementation would either weaken authorization or silently ignore the request.
Needed decision: Choose whether the action is owner-only, admin-only, or broadly authenticated.
Recommended rewrite: "Only workspace owners and admins can ..."
```

For external-practice findings, use this structure:

```text
[HIGH] Requirement preserves an outdated deployment process
Repository evidence: Releases are performed manually via undocumented shell steps and there is no repeatable CI/CD pipeline.
External evidence: Current official/vendor guidance and maintained repositories center automated CI validation and scripted deployments for repeatability and rollback safety.
Impact: The requirement keeps operational risk high and makes deployments person-dependent.
Recommended rewrite: "All production deployments must run through a documented CI/CD workflow with automated validation, versioned artifacts, and rollback steps."
```

Then end with:

```markdown
## External Validation
- Checked: ...
- Sources: ...
- Inferences: ...

## Open Questions
- ...

## Suggested Requirement Rewrite
- ...

## Proposed Acceptance Criteria
- [ ] ...
- [ ] ...

## Non-Goals
- ...

## Sanity Verdict
- PASS: Ready to implement
- WARNING: Implement only after clarifying medium-risk gaps
- BLOCK: Do not implement until critical/high requirement flaws are resolved
```

## Relationship To Other Skills

- Use `prd` when the user wants a full implementation-facing PRD.
- Use `code-reviewer` after code changes exist and the question becomes implementation quality.
- Use deep research style workflows when requirement validity depends on current external facts, regulation, competitors, or vendor behavior.
- Use GitHub and official docs when checking whether the team's current engineering process is behind current norms.

## Examples

- "Review this feature request and tell me if the requirement itself is broken."
- "Check whether this ticket is implementable without guessing business rules."
- "The code may be fine; I think the product requirement is wrong. Audit the requirement."
- "Before coding, sanity-check this PRD against the current repo."
