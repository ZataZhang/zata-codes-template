---
name: planning-with-files
version: "2.4.0"
description: Implements Manus-style file-based planning for complex tasks. Stores the active planning files under .claude/planning/current/ to avoid repo-root conflicts, with legacy fallback for existing root files. Must pass tests before completion. Use when starting complex multi-step tasks, research projects, or any task requiring >5 tool calls.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - WebSearch
hooks:
  SessionStart:
    - hooks:
        - type: command
          command: "echo '[planning-with-files] Ready. Auto-activates for complex tasks, or invoke manually with /planning-with-files'"
        - type: command
          command: "if [ -f .claude/planning/current/task_plan.md ]; then echo '[planning-with-files] Active planning session: .claude/planning/current/'; elif [ -f task_plan.md ] || [ -f findings.md ] || [ -f progress.md ]; then echo '[planning-with-files] Legacy root planning files detected. Migrate them with: ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh'; else echo '[planning-with-files] No planning session found. Initialize with: ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh'; fi"
        - type: command
          command: "python ${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py --status-report 2>/dev/null || true"
  PreToolUse:
    - matcher: "Write|Edit|Bash"
      hooks:
        - type: command
          command: "cat .claude/planning/current/task_plan.md 2>/dev/null | head -30 || cat task_plan.md 2>/dev/null | head -30 || true"
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "echo '[planning-with-files] File updated. Checking phase status...'"
        - type: command
          command: "python ${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py --auto-advance 2>/dev/null || true"
        - type: command
          command: "python ${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py --status-report 2>/dev/null || true"
  Stop:
    - hooks:
        - type: command
          command: "${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh"
        - type: command
          command: "python ${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py --status-report 2>/dev/null || true"
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## Why This Skill Exists

Large tasks exceed context windows. This skill keeps state on disk so progress is stable across long sessions.

Core model:

- Context window = RAM (volatile, limited)
- Filesystem = disk (persistent, durable)
- Rule: important state must be written to disk

## File Locations

Use two locations correctly:

| Location | Contents |
| --- | --- |
| Skill directory (`${CLAUDE_PLUGIN_ROOT}/`) | Templates, scripts, reference docs |
| Project directory (ignored workspace state) | `.claude/planning/current/task_plan.md`, `.claude/planning/current/findings.md`, `.claude/planning/current/progress.md` |
| Project directory (archived session history) | `.claude/planning/sessions/` |

Planning files must not live in tracked repo-root files. Keep active planning state under `.claude/planning/current/` so branch merges and routine commits do not keep conflicting on `task_plan.md`, `findings.md`, and `progress.md`.

## Quick Start

Before any complex task:

1. Initialize the active planning workspace: `${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh`
2. If you need a fresh planning workspace, archive the current one and recreate it: `${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh --force`
3. Confirm the three active files exist:
   - `.claude/planning/current/task_plan.md`
   - `.claude/planning/current/findings.md`
   - `.claude/planning/current/progress.md`
4. If legacy repo-root planning files already exist, the first init run migrates them into `.claude/planning/current/` and leaves the originals untouched.
5. Start work only after `.claude/planning/current/task_plan.md` has clear phases.

Reference templates:

- [templates/task_plan.md](templates/task_plan.md)
- [templates/findings.md](templates/findings.md)
- [templates/progress.md](templates/progress.md)

## Working Loop

Repeat this loop through the task:

1. Read `.claude/planning/current/task_plan.md` before major decisions.
2. Execute a small batch of actions.
3. Write new findings into `.claude/planning/current/findings.md`.
4. Log progress and test outcomes in `.claude/planning/current/progress.md`.
5. Update phase status in `.claude/planning/current/task_plan.md`.

## File Responsibilities

| File | Role | Update Trigger |
| --- | --- | --- |
| `.claude/planning/current/task_plan.md` | Phases, decisions, status tracking | At phase start/end and after major pivots |
| `.claude/planning/current/task_plan.md` / Completion Summary | Final recap, deliverables, test evidence | After all implementation and tests complete |
| `.claude/planning/current/findings.md` | Research notes, evidence, discovered constraints | After each meaningful discovery |
| `.claude/planning/current/progress.md` | Chronological execution log and test runs | Throughout execution |

## Operating Rules

### 1) Plan First

Do not start a complex task without `.claude/planning/current/task_plan.md`.

### 2) 2-Action Capture Rule

After every two `view`/browser/search actions, persist key findings to disk immediately.

### 3) Read Before Decision

Before architectural or high-impact choices, reread `.claude/planning/current/task_plan.md` to maintain alignment.

### 4) Update After Action

After each phase:

- transition status (`in_progress` -> `complete`)
- record errors and resolutions
- list files added/changed

### 5) Log Every Error

Track each failure explicitly to avoid repeated dead ends.

```markdown
## Errors Encountered
| Error | Attempt | Resolution |
| --- | --- | --- |
| FileNotFoundError | 1 | Created default config |
| Pytest AssertionError | 2 | Fixed off-by-one logic |
```

### 6) Never Repeat the Same Failed Action

```python
if action_failed:
    next_action_must_differ = True
```

### 7) Mandatory Testing Before Completion

Never mark work complete without verification.

- check whether `tests/` exists
- run relevant test commands (unit/integration/e2e as applicable)
- if a test fails, log it in `.claude/planning/current/progress.md`, fix it, and rerun
- record exact command + pass/fail status in `.claude/planning/current/progress.md` and Completion Summary

## Completion Summary Rules

Only fill Completion Summary after:

1. all planned phases are complete
2. required tests are green

Simple task example:

```markdown
## Completion Summary
- **Status:** Complete (2026-02-10)
- **Tests:** Passed (`pytest tests/test_core.py`)
- **Deliverables:** `src/file1.ts`, `docs/readme.md`
- **Notes:** Optional key decisions and caveats
```

For complex tasks, include:

- full deliverable list with locations
- final test commands and outcomes
- key tradeoffs and lessons learned
- follow-up items

## 3-Strike Error Protocol

If blocked, escalate methodically:

1. Attempt 1: Diagnose root cause and apply targeted fix.
2. Attempt 2: Use a different approach/tool/library.
3. Attempt 3: Rethink assumptions and update plan.

After 3 failed attempts, escalate to the user with:

- what you tried
- concrete error output
- the decision point requiring guidance

## Read vs Write Decision Matrix

| Situation | Action | Why |
| --- | --- | --- |
| Just wrote a file | Usually do not reread immediately | Content is still in context |
| Viewed image/PDF | Write findings now | Multimodal details are easy to lose |
| Browser returned data | Persist summary to file | Remote content is transient |
| Starting a new phase | Read plan/findings first | Re-establish context |
| Test failure or runtime error | Read relevant files now | Need current state for diagnosis |
| Resuming after interruption | Read all planning files | Recover full task state |

## 5-Question Reboot Check

If these are answerable, context management is healthy:

| Question | Source |
| --- | --- |
| Where am I? | Current phase in `.claude/planning/current/task_plan.md` |
| Where am I going? | Remaining phases in `.claude/planning/current/task_plan.md` |
| What is the goal? | Goal statement in `.claude/planning/current/task_plan.md` |
| What have I learned? | `.claude/planning/current/findings.md` |
| Did tests pass? | `.claude/planning/current/progress.md` + terminal logs |

## When to Use

Use this pattern for:

- multi-step tasks (3+ steps)
- research-heavy work
- feature implementation across many files
- sessions with many tool calls

Skip for:

- simple one-shot questions
- trivial single-file edits
- quick lookups without execution flow

## Scripts

- `scripts/init-session.sh`: initialize planning files under `.claude/planning/current/` (no overwrite by default)
- `scripts/check-complete.sh`: verify phase completion state

## Minimum Completion Checklist

Before ending a task, confirm:

1. `.claude/planning/current/task_plan.md` phases are complete.
2. `.claude/planning/current/findings.md` contains key discoveries.
3. `.claude/planning/current/progress.md` includes test commands and results.
4. Completion Summary is filled with deliverables and verification.

## Automation

`scripts/update_phase_status.py` supports status reporting and phase transitions.

Common commands:

```bash
# Show current status report
python "${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py" --status-report

# Mark a phase complete
python "${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py" --phase "Phase 1" --status complete

# Auto-advance if current phase is complete
python "${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py" --auto-advance

# Append a progress log line
python "${CLAUDE_PLUGIN_ROOT}/scripts/update_phase_status.py" --log "Completed API integration and passed tests"
```

Safe initialization commands:

```bash
# Safe mode: create the active workspace only if one does not already exist
bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh"

# Force mode: archive current workspace and create a fresh one
bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh" --force
```

## Auto-Update Behavior (v2.4.0+)

- Session start: show status report
- After `Write`/`Edit`: attempt auto-advance and show updated status
- Session end: show final status report

## Anti-Patterns

| Don't | Do Instead |
| --- | --- |
| Use ephemeral todo memory only | Persist plan in `.claude/planning/current/task_plan.md` |
| State goals once and forget | Re-read plan before decisions |
| Retry failures silently | Log failures and resolutions |
| Overload transient context | Store large content in files |
| Execute before planning | Create plan first |
| Repeat failed actions | Change strategy each attempt |
| Finish without verification | Run tests and record results |
| Write planning files in tracked repo root | Write planning files in `.claude/planning/current/` |

## Additional References

- `reference.md`: Manus principles and deeper guidance
- `examples.md`: concrete usage examples
