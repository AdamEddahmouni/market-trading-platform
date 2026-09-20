# Future design: `imp storage clean` (NOT IMPLEMENTED)

**Status:** Draft only. This PR ships `python tools/imp.py storage audit` — read-only observability.

**Do not implement destructive cleanup from this note.**

`storage audit output is advisory and is not deletion authority.`

## Why this is separate

Audit can run repeatedly without changing Git, evidence, or Cursor state. Cleanup can destroy unique commits, dirty work, prospective receipts, and frozen collector checkouts. Those are different authority classes.

## Required gates before any future `storage clean`

1. **Explicit verb and flags.** No implicit cleanup from `storage audit`. Command would be `python tools/imp.py storage clean` with required selectors.
2. **Dry-run default.** `storage clean` without `--execute` only prints a plan. `--execute` still requires an allowlist.
3. **Classification proof.** Each candidate must prove it is disposable. Hints from audit (`UPSTREAM_GONE`, `MERGED_OR_ANCESTOR`, age, size) are insufficient.
4. **Active-worker checks.** Refuse to touch a worktree that appears owned by an active agent, merge, or evidence collector.
5. **Unique commit checks.** If HEAD is not an ancestor of `origin/main`, or uniqueness cannot be proven, exclude the tree.
6. **Dirty-tree refusal.** Dirty or untracked work is never auto-removed.
7. **Evidence protection.** Never delete `artifacts/`, receipts, historical RTH/development, prospective corpora, frozen collector checkouts (`.imp-actual-01-phase-d`), or Item 9/FTEP evidence.
8. **No broad `git clean`.** No `git clean -fdx` over the monorepo.
9. **No aggressive GC by default.** `git gc --prune=now`, reflog expire, and `git prune` stay out of default cleanup.
10. **Confirmation / allowlists.** Operator must name paths or classes. No "delete all gone-upstream worktrees" default.
11. **Linked vs physical.** Remove a junction/symlink `.venv` only when the operator asked for that link; never delete the canonical physical venv because many worktrees point at it.
12. **Cursor.** Future cleanup must not delete transcripts, checkpoints, or unrelated projects.

## Suggested later phases (still not this PR)

- Phase A: dry-run report of regenerable caches (`__pycache__`, `.pytest_cache`) with path allowlist.
- Phase B: optional removal of proven-empty linked worktrees after unique-commit and dirty checks.
- Phase C: never automatic.

Until those gates exist in code and docs, operators review audit output and act manually.
