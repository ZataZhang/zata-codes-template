# PR Evidence And Merge Acceptance

Read this reference when a PRD implementation is delivered through a pull request. It defines how the PR becomes the human review surface and how a merge can replace a second confirmation in chat without weakening evidence or archival integrity.

## Contents

- [Acceptance Event](#acceptance-event)
- [PR Body](#pr-body)
- [Evidence Publication](#evidence-publication)
- [Frontend Prototype Comparison](#frontend-prototype-comparison)
- [Evidence Identity](#evidence-identity)
- [Post-Merge Reconciliation](#post-merge-reconciliation)
- [Failure And Fallback Behavior](#failure-and-fallback-behavior)

## Acceptance Event

A merge is a valid human acceptance event only when all of these are true before merge:

1. The PR body uniquely names the pending PRD path.
2. The PR body explicitly says that merging accepts the listed human decisions and visible outcomes and authorizes post-merge archival.
3. Every `reviewer: human` presentation from PRD Section 9.1 is visible in the PR body or a stable PR evidence comment. The reviewer must not need a local checkout or an absolute local path.
4. The independent verifier and every required CI/delivery gate are green.
5. Evidence is bound to the reviewed Git tree and has not gone stale after a later push.

Squash merge, merge commit, and rebase merge are equivalent. A PR approval without merge, a closed-unmerged PR, or an ordinary merge without the explicit declaration does not satisfy `Human-Confirmed`.

This rule does not broaden authorization: create or update a PR only when the user or the established repository workflow authorized that external action.

## PR Body

Keep the body decision-oriented. Do not paste full logs into it. Use this shape or a repository-native equivalent:

```markdown
## Human Acceptance And PRD Archive

Linked PRD: `tasks/pending/<prd-file>.md`

> Merging this PR means that the merger accepts the decisions and human-visible
> outcomes below and authorizes post-merge archival of the linked PRD, provided
> the required gates remain green and the merged Git tree matches the verified tree.

### Decisions Being Accepted

1. <Section 2 decision in plain language>
2. <Section 2 decision in plain language>

### Human-Visible Outcomes

- <Section 9.1 outcome and exact expected observation>
- <Section 9.1 outcome and exact expected observation>

### Gate Summary

- Independent verifier: PASS
- Required CI: PASS
- Evidence: <stable evidence comment link>
- Verified tree: `<git-tree-oid>`
```

The decision list and visible outcomes are projections of the PRD, not a second source of truth. Regenerate the PR body when those sections change.

## Evidence Publication

Publish evidence after the final implementation push and verifier pass, before requesting merge.

### Code branch

Commit only the repository-approved text reports alongside the PRD, normally:

```text
tasks/evidence/<prd-stem>/<prd-stem>.verification-plan.md
tasks/evidence/<prd-stem>/<prd-stem>.evidence-report.md
tasks/evidence/<prd-stem>/<prd-stem>.verifier-report.md
```

Do not add raw screenshots, recordings, traces, logs, temporary data, or RV scripts to the code diff.

### Raw evidence publication

Prefer the repository's existing evidence publisher. A Keda-style implementation may push raw evidence to a dedicated orphan branch and publish one stable PR comment. Repository-specific branch names and markers are allowed; the semantic payload is required:

- linked PRD and PR;
- verified head commit and verified Git tree;
- verifier verdict and required-gate summary;
- one section per RV item;
- reproducible command;
- evidence file links and SHA-256;
- key text output quoted inline;
- still images rendered inline from stable URLs;
- recordings and large artifacts linked directly;
- explanation of why the evidence proves the oracle;
- negative control and expected failure where required;
- disclosed limitations or mock boundaries.

Run the repository's secret scanner before uploading. Evidence must not contain tokens, cookies, authorization headers, `.env` contents, private user data, or credentials embedded in URLs. Validate declared formats and reject missing, zero-byte, stale, wrong-MIME, or obviously malformed artifacts before publication.

Use a stable marker so later pushes update the same comment instead of creating an unreadable comment stream, for example:

```html
<!-- prd:validation-evidence version=1 prd=<prd-stem> tree=<git-tree-oid> -->
```

Keep evidence reachable for the repository's audit horizon. Do not delete an evidence branch immediately after merge if doing so would break the archived PRD's PR links; apply an explicit retention or snapshot policy instead.

## Frontend Prototype Comparison

Every user-visible frontend change must let the reviewer compare design intent with the delivered result without leaving the PR. For each acceptance-critical state, publish this pair in order:

1. **Target prototype — design intent:** an image rendered from the approved prototype artifact, with its prototype form and provenance link.
2. **Implemented UI — runtime evidence:** a screenshot from the real production entry at the highest feasible validation level, with the route/action used to reach it.

Use the same viewport, theme, locale, state, and representative data wherever practical. When exact matching is impossible, state the difference next to the pair; do not crop or restage images to hide a mismatch. The comparison must name the expected invariant or intended difference, not merely place two unexplained screenshots beside each other.

Recommended PR comment shape:

```markdown
### Frontend comparison: <state name>

| Target prototype — design intent | Implemented UI — real user flow |
|---|---|
| ![Prototype: state](<stable-prototype-image-url>) | ![Implementation: state](<stable-runtime-image-url>) |

- Matched context: `1440×900`, light theme, `zh-CN`, seeded account with 3 items
- Prototype source: `<prototype or Hub URL>`
- Real entry: `<route and action sequence>`
- Validation level: `real user flow`
- Compare: `<exact layout, content, or interaction outcome the reviewer should inspect>`
- Disclosed difference: `none` or `<why the implementation intentionally differs>`
```

The prototype image is not functional evidence and must never be labeled `production composition`, `real user flow`, or `live integration`. The implementation screenshot is not a prototype and must come from the real page/composition required by the repository's frontend validation rules. Both files follow the same evidence hashing, secret scanning, stable-link, and retention rules as other PR artifacts.

If the PR changes frontend code but has no user-visible visual or interaction effect, add a concise waiver to the PR evidence comment naming the affected files and observable reason, for example: `Prototype image waiver: generated TypeScript API types only; rendered UI and interaction are unchanged.` A generic “not needed” waiver is invalid.

## Evidence Identity

Record both commit and tree identity:

```text
verified_head_sha
verified_tree_sha
evidence_manifest_sha256
```

The Git tree is the authoritative content identity for merge acceptance. Squash and rebase create a new commit SHA even when the resulting files are identical; their tree remains equal. After any implementation push, repair commit, rebase, conflict resolution, generated-file update, or evidence-affecting change, recompute the tree and republish/reverify affected evidence.

Evidence is current only when the PR's reviewable head tree equals `verified_tree_sha`. Required checks must apply to that same head or a repository merge-queue result whose final tree is subsequently checked.

## Post-Merge Reconciliation

On a merged PR, repository automation should:

1. Resolve the unique linked pending PRD.
2. Confirm the PR contained the acceptance declaration and stable evidence presentation.
3. Confirm verifier and required checks passed for the accepted tree.
4. Read the final merge commit and its Git tree.
5. Compare the final tree with `verified_tree_sha`. If they differ, stop and require validation on the final tree.
6. Record:
   - PR number and URL;
   - merger identity;
   - merged timestamp;
   - merge method when available;
   - verified head SHA and tree;
   - final merge commit SHA and tree;
   - verifier and CI conclusions.
7. Check the matching `Human-Confirmed` items and the Section 9.1 surface-review item using the merge event as their evidence.
8. Update the Acceptance Status Banner to `✅ 可归档` when no checkbox remains.
9. Complete Section 13 Final Reconciliation against the merged tree.
10. Move the PRD from `tasks/pending/` to `tasks/archive/` and commit the archival record.

Prefer a restricted GitHub App or workflow identity that can write only the required archive paths. If branch protection forbids a direct archival commit, create a metadata-only archival PR and auto-merge it after deterministic checks; do not require a second human click for the same acceptance decision.

## Failure And Fallback Behavior

- **PR closed without merge:** leave `Human-Confirmed` open and the PRD pending.
- **Evidence comment missing or stale:** block merge-as-acceptance; republish evidence for the current tree.
- **Verifier or required CI not green:** block merge-as-acceptance even if GitHub technically permits merge.
- **Final tree differs after merge:** do not archive; validate the final tree and then reconcile.
- **No post-merge writer exists:** the merge is still a durable acceptance record when all preconditions were present, but keep the PRD pending until an agent pulls the merged tree, records the audit fields, updates the checklist/banner/reconciliation, and archives it.
- **No PR delivery:** use the existing chat or `just prd review` human-confirmation path; this reference adds a PR-native option rather than removing the fallback.
- **User-visible frontend evidence lacks a prototype pair:** do not present the PR as ready for human acceptance; create or update the target prototype, render it, and republish the paired comparison.
