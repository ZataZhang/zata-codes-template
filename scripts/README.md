# Script Layout

`scripts/` uses a split between stable entrypoints and internal implementations.

- Root-level scripts should be reserved for stable entrypoints that are safe to reference from docs, `just`, tests, and agent instructions.
- `hooks/` and `claude_code_hooks/` keep the agent session hook contract paths stable.
- `worktree/`, `template/`, `secrets/`, `release/`, `just/`, and `diagnostics/` hold implementation files grouped by responsibility.

When adding a new script:

1. Put implementation code in the closest responsibility subdirectory.
2. Only add a root-level wrapper when the path is a real documented or external contract worth preserving.
3. Keep `just`-private helpers out of the root unless they are intended as public CLI entrypoints.
