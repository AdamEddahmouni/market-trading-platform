# Parent Monorepo History Audit Design

## Goal

Give the private parent monorepo a complete, organized, and reproducible
paper trail for all reachable work in the parent repository and each
independent child repository, without changing any child repository.

## Scope

The audit includes every commit reachable from every local Git ref currently
available in:

- the parent `market-trading-platform` repository;
- `integrated-market-platform`;
- `governed-ticker-metadata-enrichment`;
- `equity-data-v1-worktree`; and
- `short-squeeze-project`.

Each record preserves the repository, commit SHA, direct refs, parents, author
and committer identities, authored and committed timestamps, subject, complete
commit body, and changed-path names. Rationale is sourced only from commit
messages and linked documentation; the audit labels missing rationale instead
of inventing it.

## Organization

The audit has three layers:

1. `docs/history/INDEX.md` explains the scope, provenance, date ranges, and
   navigation.
2. `docs/history/repositories/*.md` provides readable chronological timelines,
   grouped by repository and date, with commit subjects and rationale excerpts.
3. `docs/history/WORK_LEDGER.jsonl` is the complete loss-minimized ledger for
   programmatic filtering and review.

`docs/history/REFS.json` records every source ref and its tip at generation
time. `workspace-manifest.json` remains the authoritative source-to-snapshot
mapping.

## Reproducibility and safety

`tools/generate_history_ledger.py` reads child repositories with Git commands
and writes only parent-repository audit files. It never commits, resets,
checks out, changes remotes, changes visibility, or writes inside a child
repository. Its `--check` mode regenerates into a temporary directory and
fails if tracked audit output is stale.

CI runs the parent-only schema and snapshot checks plus audit freshness checks.
Hosted CI does not need root-level child repositories: the committed ledger
and ref manifest are validated against the parent snapshot.

## Known limits

Git commit history records committed work only. Uncommitted child working-tree
changes are not assigned false commit identities or dates; the generator
records their existence in the local report when source repositories are
available. Git-LFS payloads unavailable in this checkout remain excluded as
already documented by the parent repository.
