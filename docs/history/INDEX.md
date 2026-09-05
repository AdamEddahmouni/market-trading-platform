# Workspace History Audit

This audit preserves the committed history of the parent workspace and
every commit reachable from every local ref in each independent child
repository available at generation time.

## How to read this

- Start with the repository timelines for human-readable chronology.
- Use `WORK_LEDGER.jsonl` for complete commit bodies and changed paths.
- Use `REFS.json` to see which refs and exact tips were captured.
- Rationale is never invented: missing commit bodies are labeled
  `commit-subject-only` or `not-stated`.

## Repository coverage

| Repository | Commits | Refs | First commit | Latest commit |
|---|---:|---:|---|---|
| `equity-data-v1` | 601 | 116 | 2026-08-01 | 2026-09-05 |
| `governed-ticker-metadata` | 601 | 116 | 2026-08-01 | 2026-09-05 |
| `parent` | 429 | 15 | 2026-08-14 | 2026-09-05 |
| `short-squeeze` | 73 | 8 | 2026-07-26 | 2026-09-05 |

The `governed-ticker-metadata` and `equity-data-v1` entries share
one underlying Git history because the latter is a worktree; each
workspace ref set is retained separately for traceability.
## Repository timelines

- [`equity-data-v1`](repositories/equity-data-v1.md)
- [`governed-ticker-metadata`](repositories/governed-ticker-metadata.md)
- [`parent`](repositories/parent.md)
- [`short-squeeze`](repositories/short-squeeze.md)
