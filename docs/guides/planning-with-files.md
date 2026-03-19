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

Show the current phase status:

```bash
python skills/planning-with-files/scripts/update_phase_status.py --status-report
```

## Legacy Compatibility

If a repository still contains legacy root files such as `task_plan.md`, the first
`init-session.sh` run migrates them into `.claude/planning/current/` and leaves the
original root files untouched. The helper scripts also fall back to the legacy root
location so older workspaces keep working during the transition.

## Recommendation

Do not commit planning files. Treat them as local working memory, similar to editor state
or scratch notes. If you need durable historical records, keep them in archived session
directories or convert the final outcome into normal project documentation instead.
