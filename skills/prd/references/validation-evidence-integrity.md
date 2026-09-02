# Validation Evidence Integrity

Read this reference when a PRD changes executable behavior or is being prepared for archive.
The goal is to prove the delivered path, not a nearby path that happens to return the same result.

## Oracle Chain Contract

For every `R2` / `R3` executable `rv-id`, record these fields in the Section 7.6 YAML oracle.
`R0` / `R1` entries are out of scope for this contract — they need one assertion that
discriminates their own failure, not a provenance chain. Content rule F defines the split.

- `critical_value_source`: the exact origin of any URL, token, identifier, command, or payload used by the assertion.
- `must_cross`: the runtime boundaries the evidence must traverse in order, including proxies, canonical routes, transaction commits, queues, or storage reads.
- `forbidden_bypasses`: helpers, direct service calls, reconstructed values, compatibility routes, fake adapters, or pre-seeded state that would skip the behavior under test.
- `fresh_state_probe`: an independent observation made after the action, preferably from a new browser context, request, process, or database session.
- `final_tree_evidence`: how the evidence is tied to the final implementation tree and when it must be recollected.

Treat every field as a falsifiable contract. Generic text such as `normal flow`, `none`, or
`covered by tests` is insufficient when a concrete boundary or bypass exists.

## Required Patterns

### UI-generated values

When the UI displays or copies a URL, token, command, identifier, or payload:

1. Trigger creation through the real UI.
2. Extract the exact displayed/copied value from the rendered UI or browser clipboard.
3. Use that exact value for the next action.
4. Assert the actual network request uses the canonical path and contract.
5. Reject legacy, duplicated, or compatibility paths explicitly when they are a regression risk.

Do not reconstruct the value from a response fixture, hard-code an equivalent route, or call a
helper that bypasses the UI wiring.

### Write APIs and transactions

A successful write response is not proof of durable state. After the response:

1. Start a new request, browser context, process, or database session.
2. Read the created state through the consumer-facing entry point.
3. Assert the persisted record and externally visible behavior.

The `must_cross` field must name the commit/durability boundary. The `fresh_state_probe` must not
reuse the writer's unit of work or in-memory object.

### Frontend API wiring and proxies

Capture the browser's actual request URL and method. Assert the canonical path, proxy boundary,
request payload, and response contract. Add a negative assertion for known legacy variants such as
duplicated path prefixes. A backend-only request test does not prove the frontend calls that route.

### Jobs, files, caches, and messages

Observe the result from a fresh consumer rather than the producer's return value:

- jobs: wait through the real scheduler/worker boundary and query final status independently;
- files: reopen the emitted file from disk and validate its consumer-visible content;
- caches: invalidate local references and read through the real cache/client boundary;
- messages: consume from the configured broker/adapter rather than inspecting the publish mock.

## Evidence Freshness And Regression Reopening

Evidence is valid only for the final relevant code tree. Recollect affected `rv-id` evidence after
any change to its entry point, value construction, proxy/route, transaction boundary, storage,
consumer, or assertion. Record the final tree identifier or diff state in the evidence report.

If a real run or field report contradicts an archived verifier `PASS`:

1. Treat the prior evidence as invalid for the contradicted behavior.
2. Reopen the PRD or create a linked regression PRD; do not leave the archived task as accepted.
3. Add the observed failure as a negative control or regression oracle.
4. Re-run the repaired flow from the critical value source through a fresh-state probe.
5. Archive again only after independent verification passes on the repaired final tree.

## Verifier Questions

The verifier must answer all of these for each required `rv-id`:

- Did the critical value come from the real producer/UI, or was it reconstructed?
- Did the run cross every named runtime boundary?
- Could a listed bypass still make the test green while production is broken?
- Did a fresh consumer independently observe the postcondition?
- Was the evidence collected after the last relevant implementation change?

A `no` or an unknown answer to any of these is a `BLOCKER` — the behavior is not proven.

## Finding Severity

Verification rounds are expensive, so a finding only earns one when it can change the
verdict. Label every finding with the answer to a single question: **if this were fully
addressed, could the verdict flip from PASS to FAIL?**

- `BLOCKER` — yes, or it cannot be ruled out. Rejects, and drives another round.
- `NON-BLOCKING` — no. Recorded under the verdict and carried forward; never rejects.
  Missing raw logs where the result is reported and reproducible, untidy evidence naming,
  a mirror-image variant of an already-passing test that exercises the same guard, and
  coverage no acceptance item claims all live here.
- `SECURITY` — a real credential is visible in a log or screenshot. Must be fixed, but it
  casts no doubt on the behavior, so it never forces a round on its own. Prevent it
  mechanically instead: scan the evidence package before submitting, and capture status
  views rather than live one-time links.

Severity is per finding. Several `NON-BLOCKING` findings do not add up to a `BLOCKER`.

Rounds are capped at two. If `BLOCKER` items still stand after the second round, escalate
them to a human as named open items — a third round is not the answer.
