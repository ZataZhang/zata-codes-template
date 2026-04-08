# Requirement Checklist

Use this checklist selectively. Load only the sections relevant to the request.

## 1. Goal And Outcome

- Is the user outcome explicit?
- Is success observable?
- Is the requirement describing behavior, not only intent?
- Is there a clear trigger and a clear end state?

## 2. Scope And Boundaries

- What is in scope?
- What is explicitly out of scope?
- Is the requirement secretly asking for multiple features at once?
- Is rollout expected for all users, some users, or behind a flag?

## 3. Business Rules

- Are permissions and roles defined?
- Are state transitions defined?
- Are billing, quota, approval, or ownership rules implied but unstated?
- Would two reasonable engineers implement different behavior from the same text?

## 4. Data And Schema

- Does the requested behavior require new fields, tables, enums, or persistent state?
- Are null, empty, deleted, archived, or duplicated states defined?
- Are migrations or backfill rules implied but missing?
- Does current schema structure make the requirement expensive or impossible as written?

## 5. API And Contract Shape

- Are inputs, outputs, and error states defined?
- Are idempotency, retries, pagination, and partial failure behavior relevant?
- Does the request conflict with current API conventions or route structure?
- Are versioning implications ignored?

## 6. UI And User Flow

- What should users see before, during, and after the action?
- Are loading, empty, error, and success states defined?
- Are cancel, retry, refresh, or duplicate-submit behaviors defined?
- Does the request imply cross-page navigation or stale-client-state issues?

## 7. Security And Trust Boundaries

- Does the requirement assume untrusted input is safe?
- Does it weaken authz/authn boundaries?
- Does it expose sensitive data in logs, UI, exports, or APIs?
- Does it assume client-side checks are sufficient?

## 8. Consistency With The Existing Repository

- Does current code or docs already define the opposite behavior?
- Does the request break naming, typing, or architecture conventions?
- Would implementation require bypassing existing abstractions or invariants?
- Are docs, tests, and operational scripts likely to need changes too?

## 9. Testing And Verification

- Can the requirement be tested deterministically?
- Are acceptance criteria measurable?
- Are edge cases and regression targets named?
- Is there a clear distinction between unit, integration, and UI verification needs?

## 10. Operations And Rollout

- Does the change require migration, seeding, backfill, or feature flags?
- Is observability needed: logs, metrics, alerts, audit trail?
- Are rollback conditions defined?
- Does the requirement assume zero downtime when that is unrealistic?

## 11. External Best-Practice Drift

- Does the repository still rely on a manual step that current tooling usually automates?
- Is there no CI where current team scale or risk profile clearly warrants CI?
- Is deployment manual, person-dependent, or undocumented where CI/CD would materially reduce risk?
- Is the requirement locking the team into an outdated framework pattern, hosting model, or release process?
- Do official docs or active upstream repos recommend a different default today?
- Would keeping the old way create security, compliance, operability, or rollback problems?

## Typical Smells

- "Make it smarter" with no measurable output
- "Support all cases" without enumerating cases
- "Any user can ..." in a system with role-based permissions
- "Just add a field" when historical data must be backfilled
- "Show real-time updates" with no existing push model
- "No docs needed" when public behavior changes
- "We deploy by hand" in a multi-contributor or production system
- "No CI needed" despite shared branches, releases, or automated tests existing

## Rewrite Heuristics

When the requirement is weak, rewrite it into:

1. actor
2. trigger
3. behavior
4. state change
5. failure behavior
6. constraints
7. measurable acceptance criteria
