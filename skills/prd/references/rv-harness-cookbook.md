# RV Harness Cookbook — Isolated Real-Entry Fixtures

Read this reference **before writing any Realistic Validation harness** — the moment an oracle's `real_entry` requires an isolated end-to-end run of the repository's real CLI/pipeline. Typical signals in the oracle block:

- `mock_boundary` says only the external executor (agent CLI / network service) is a deterministic fixture while git, the database, and the CLI itself stay real;
- `negative_control` demands a fallback, timeout, or path-escape scenario;
- `fresh_state_probe` requires reading outcomes back through a **new** process after the run ends.

The recipe below is tool-neutral. It produces one isolated "scene" per scenario and the evidence files the oracle promises, without ever replacing the real entry point with in-process fakes.

## 0. Non-negotiables

These repeat the evidence-integrity contract; they shape every design decision below.

1. **Real entry points only.** The CLI/pipeline under test is invoked exactly as an operator would. In-process fakes, mocks, or test clients standing in for the real entry point invalidate the evidence.
2. **Every harness script lives under `<evidence-dir>/scripts/`** and never enters the code diff. Evidence artifacts live beside them, one file per oracle item.
3. **Fail loudly.** Any fixture that silently pretends success on an input it does not recognize produces green evidence that proves nothing.

## 1. The five building blocks

### 1.1 Isolated scene builder

One function builds the entire run scene under a fresh temp root and returns a handle:

- a fake state home (where the tool persists its database/state) plus a repo-local config override pointing there — so **every freshly spawned CLI process resolves the same state**, not just the one that created it;
- a real git repository (real history, real worktree);
- a `bin/` directory of shims prepended to `PATH` (see 1.2 / 1.3);
- helpers to run the real CLI (foreground with timeout, and detached when an oracle must kill a mid-flight process);
- readers that observe outcomes the way a new operator would (see 1.4);
- fingerprint helpers: SHA-256 of fixture file contents and of the implementation tree, for `final_tree_evidence`.

Destroy the whole scene between scenarios. Isolation is per scenario, not per suite.

### 1.2 Fail-loud boundary fakes

For each external system the real entry talks to (forge/CLI wrappers, network APIs):

- implement **only the argv shapes the real client actually emits** — derive the list by reading the client, not by guessing;
- persist responses in a state file (JSON) so processes started later observe the writes made earlier;
- any unrecognized argv → non-zero exit with the argv echoed to stderr. Never guess a default success.

This is what makes harness gaps visible within seconds instead of producing evidence that "passes" while exercising nothing.

### 1.3 Plan-driven deterministic executor fixture

The executor fixture stands in for the external agent/worker CLI:

- behavior is fully driven by a JSON plan consumed per `(executor, role)` key; when a queue is exhausted, repeat the last step so repeated calls stay predictable;
- **append one JSONL probe line per invocation** (argv, cwd, prompt head, timestamp). The probe is the independent proof that the real process boundary was crossed — the harness asserts against it, not against its own bookkeeping;
- deliberately fail the first executor in fallback scenarios so the negative control is deterministic, not lucky.

### 1.4 Fresh-process verification

Outcomes are read the way the next operator would read them:

- spawn a **new** CLI process (or open a **new** database connection) to verify what the run persisted; never assert from in-memory handles the run left behind;
- pair start/end markers from the real logs and check field-level identity (ids, roles, model/executor fields, retry links);
- for kill/timeout oracles: start detached, kill at a known point, then verify the surviving record is marked incomplete — never a fabricated end state.

### 1.5 Negative control first

Record `expected_fail` **before** the green run:

1. run the scenario with the failure injected (first executor fails, sentinel string emitted, out-of-bounds path requested);
2. assert the bad shape appears (e.g. two linked records instead of one merged success; sentinel absent from storage; foreign path rejected);
3. then run the clean scenario and capture the evidence file.

A checkpoint with only a green path and no demonstrated red does not discriminate — it passes even if the feature is missing.

## 2. Ordering discipline

- **Cheapest oracle first.** Produce the first evidence file with the thinnest possible scene, then grow the harness. Do not build the full harness for every item before producing any evidence file.
- Write each item's evidence file **immediately** after that item's real run passes; never batch evidence production to the end.
- One harness run may serve several oracles, but each evidence file must contain **only its own item's output** — no global stdout redirection (e.g. `exec > >(tee -a ...)`) that merges items into one file.
- Exit code 0 is not the assertion. Parse the captured output and assert discriminating substrings.

## 3. Anti-patterns

- In-process fakes or test clients substituting for the `real_entry`.
- Fixtures that return success for unknown inputs; `|| true` / `|| echo ok` green-washing.
- Asserting from the same process/memory that produced the outcome instead of a fresh consumer.
- Harness constants copied from production config instead of an isolated scene (accidentally touching real repos, real issue trackers, or shared state).
- RV scripts or raw artifacts entering the code diff; secrets in evidence files or scripts.
