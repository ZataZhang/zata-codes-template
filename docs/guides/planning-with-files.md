# Planning With Files

## Problem

The original `planning-with-files` workflow wrote `task_plan.md`, `findings.md`, and
`progress.md` directly into the repository root. That creates avoidable git noise and
frequent merge conflicts because those files change on nearly every complex task.

## Conflict-Safe Layout

The active planning workspace now lives under:

- `.claude/planning/current/task_plan.md`
- `.claude/planning/current/findings.md`
- `.claude/planning/current/progress.md`

Fresh resets are archived under `.claude/planning/sessions/`.

Initialization now fills in a contextual task title and phase titles, so the fresh
workspace is immediately readable instead of showing raw `[Brief Description]` and
`[Title]` placeholders.

The entire `.claude/planning/` subtree is ignored by git, so planning updates stay local
to the working session instead of polluting normal source-control history.

## Commands

Initialize the active workspace:

```bash
bash skills/planning-with-files/scripts/init-session.sh
```

Archive the current planning workspace and start a fresh one:

```bash
bash skills/planning-with-files/scripts/init-session.sh --force
```

Automatic session archiving now skips two kinds of noise:

- untouched workspaces that still match the freshly initialized template
- duplicate snapshots whose contents already match the latest archived session

When a session is archived, the directory name now uses the current
`task_plan.md` title slug instead of only the repository name. That makes
`sessions/` easier to scan when one repository hosts several distinct tasks.

Show the current phase status:

```bash
python3 skills/planning-with-files/scripts/update_phase_status.py --status-report
```

## Completion-Time PRD Sync

Before closing a complex task, reconcile the work against a PRD:

- Search `tasks/` first for an active PRD that matches the task.
- Use `tasks/archive/` only as fallback reference, not as the main target, unless the archived PRD is clearly the right one.
- If a matching PRD exists, update it with actual deliverables, tests run, deviations from plan, and follow-up items.
- If no PRD exists, create a new file at `tasks/[YYYYMMDD-HHMMSS]-prd-[feature-name].md`.
- Record the PRD path in `.claude/planning/current/task_plan.md` Completion Summary and `.claude/planning/current/progress.md`.

This keeps the planning workspace, delivery summary, and durable product documentation aligned.

## Legacy Compatibility

If a repository still contains legacy root files such as `task_plan.md`, the first
`init-session.sh` run migrates them into `.claude/planning/current/` and leaves the
original root files untouched. The helper scripts also fall back to the legacy root
location so older workspaces keep working during the transition.

## Recommendation

Do not commit planning files. Treat them as local working memory, similar to editor state
or scratch notes. If you need durable historical records, keep them in archived session
directories or convert the final outcome into normal project documentation such as a PRD
under `tasks/`.
