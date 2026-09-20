# SOP: Storage audit (read-only)

**Status:** Authoritative operator convention for repository storage observability.

**Command:** `python tools/imp.py storage audit`

**storage audit output is advisory and is not deletion authority.**

## What this measures

The audit is a **read-only** inventory of this repository's disk footprint:

| Section | Contents |
|---|---|
| Repo | Scan root, HEAD, `origin/main`, branch/detached state, physical size, file/directory counts |
| Git | `git count-objects -v` fields (loose/packed/garbage/prune-packable) plus `.git` physical size |
| Worktrees | Every Git worktree: path, HEAD, branch/detached, upstream EXISTS/GONE/NONE, dirty/untracked, ahead/behind `origin/main`, ancestor-of-main, disk usage, `.venv`/`node_modules`/cache hints, classification **hints** |
| Dependencies | Project-scoped `.venv` / `venv` / `node_modules`, distinguishing physical directories from symlink/junction/reparse links. Linked copies are not counted as physical duplicates. |
| Caches | `__pycache__`, `*.pyc`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, coverage, `build`/`dist`, frontend caches, other known generated output |
| Artifacts/evidence | `artifacts/`, receipts, historical RTH/development, prospective corpora, evidence ledgers, frozen collector checkouts — **PROTECTED_OR_REVIEW_REQUIRED** |
| Review/temp | `.review-*`, `.agent-*`, `.rth-*`, other scratch trees — reported only |
| Cursor (optional) | This repository's project-scoped Cursor directory sizes/counts when `--include-cursor` can locate it **safely** |
| Largest consumers | Top directories and files (default 25; `--top N`) |
| Warnings | Conservative health warnings, not a storage score |

A classification **hint** (ACTIVE, OPEN_PR, MERGED_OR_ANCESTOR, UPSTREAM_GONE, DIRTY, DETACHED, UNIQUE_COMMITS_POSSIBLE, REVIEW_REQUIRED) is **not** permission to delete that worktree.

## What this does NOT do

The default command never:

- deletes files
- removes worktrees
- prunes branches
- closes pull requests
- runs `git clean`
- runs destructive Git GC / `git prune` / `git reflog expire` / aggressive `git gc`
- deletes Cursor history or transcripts
- deletes evidence, receipts, or market data
- mutates collector/runtime state
- modifies configuration
- installs dependencies
- requires network (core audit)
- follows symlink/junction/reparse targets out of the scan root

There is **no** `storage clean` in this SOP. A future cleanup command is a separate design; see [STORAGE_CLEAN_FUTURE_DESIGN.md](../drafts/STORAGE_CLEAN_FUTURE_DESIGN.md).

## How to run

From the IMP project root (`projects/integrated-market-platform/` in the monorepo):

```powershell
python tools/imp.py storage audit
python tools/imp.py storage audit --json
python tools/imp.py storage audit --top 40
python tools/imp.py storage audit --include-cursor
```

`--json` prints a machine-readable document (`schema_version`, `repo`, `git`, `worktrees`, `dependencies`, `caches`, `artifacts`, `temporary`, `cursor`, `largest_paths`, `warnings`, `summary`). Progress stays on stderr so JSON stdout stays parseable.

`--include-cursor` inspects **only** this repository's Cursor project directory (derived from the scan root, or `IMP_CURSOR_PROJECT_DIR` when that path is inside `~/.cursor/projects/`). It reports sizes and path classes. It does not print transcript contents, does not inspect sibling projects, and does not delete Cursor data. If the path cannot be located safely, the report says `UNAVAILABLE` / `UNSUPPORTED` rather than guessing.

`--root` is for tests and explicit local roots. Do not point it at unrelated machines paths.

## Warnings

Warnings are conservative signals, not scores:

| Code | Default trigger |
|---|---|
| `WORKTREE_COUNT_HIGH` | ≥ 50 registered worktrees |
| `GONE_UPSTREAM_WORKTREES_PRESENT` | any worktree whose upstream ref is gone |
| `DIRTY_STALE_WORKTREES_PRESENT` | any dirty worktree |
| `PHYSICAL_VENV_DUPLICATES` | more than one physically stored virtualenv |
| `PHYSICAL_NODE_MODULES_DUPLICATES` | more than one physically stored `node_modules` |
| `REVIEW_TEMP_STORAGE_HIGH` | review/temp ≥ 1 GiB |
| `CURSOR_PROJECT_STORAGE_HIGH` | Cursor project dir ≥ 2 GiB (when included) |
| `GIT_OBJECT_STORAGE_HIGH` | `.git` / packed objects ≥ 5 GiB |
| `UNKNOWN_LARGE_PATH` | a top consumer ≥ 512 MiB with no known class |
| `PROTECTED_EVIDENCE_LARGE` | protected artifact/evidence ≥ 1 GiB |
| `UNREADABLE_PATHS_PRESENT` | permission or filesystem errors |

Gone upstream, merged/ancestor HEAD, age, and size **do not** make a worktree reclaimable.

## Conservative reclaimable estimate

`summary.estimated_reviewable_reclaimable_bytes` counts **known regenerable caches only** (`CONSERVATIVE_CACHES_ONLY`). It excludes worktrees, dirty trees, gone-upstream trees, unique-commit uncertainty, protected evidence, review/temp directories, virtualenvs, and `node_modules`.

Caches may still be in use. The number is an operator hint, not a cleanup plan.

## Operator example

```text
python tools/imp.py storage audit
```

Read worktree count, `.git` size, physical vs linked `.venv`, cache total, and warnings. If `WORKTREE_COUNT_HIGH` or `GONE_UPSTREAM_WORKTREES_PRESENT` appears, review those trees manually. Do not delete from the audit output.
