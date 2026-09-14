# IMP state path operator convention

**Status:** Operator reference (Phase 1 Lane A).  
**Scope:** Where durable SQLite state lives vs feature Git worktrees.

## Three paths to keep separate

| Role | Location | Notes |
|------|----------|--------|
| **Canonical software checkout** | Current `origin/main` in an isolated worktree (e.g. `.worktrees/phase1-state-path-contract`) or, after fast-forward, primary monorepo checkout | Edit IMP only under `projects/integrated-market-platform/`. Do not implement on a stale primary `main` when lanes require current main. |
| **Canonical durable empirical state** | Primary IMP tree: `projects/integrated-market-platform/.local/` (`imp-state.sqlite3`) | FTEP governed sessions, campaign bindings, forward-test rows. Protected — no destructive reset, no manual SQL edits. |
| **Feature-worktree `.local`** | `<worktree>/projects/integrated-market-platform/.local/` | Test/dev only. Empty DB is normal. **Never** infer “no sessions” from this path alone. |

`IMP_STATE_DIR` overrides the effective directory for the current process. Setting it is required for read-only FTEP diagnostics from a linked worktree.

Optional override when the primary checkout path is non-standard:

| Variable | Purpose |
|----------|---------|
| `IMP_CANONICAL_STATE_DIR` | Absolute path to the canonical `.local` directory used by `python tools/imp.py state-path` for mismatch comparison |
| `IMP_STATE_DIR` | Effective persistence directory for this process (read or write) |
| `IMP_PERSIST_STATE=1` | Enable persistence at default `REPO_ROOT/.local` when `IMP_STATE_DIR` is unset |

See also [CONFIGURATION.md](CONFIGURATION.md) and `src/market_platform_foundation/local_state/paths.py` (PLATFORM-STATE-001).

## Operator commands (PowerShell)

From IMP root (`projects/integrated-market-platform` in your worktree):

```powershell
# 1) Detect worktree vs canonical state (non-zero exit if mismatch warnings)
python tools/imp.py state-path

# 2) Read-only FTEP campaign status against canonical durable state
$report = python tools/state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
python tools/imp.py ftep campaign-status FTEP-V1-002 --json

# 3) Integrity against canonical state
python tools/imp.py ftep integrity-check FTEP-V1-002
```

Override discovery with `IMP_CANONICAL_STATE_DIR` when the primary checkout is not the non-`.worktrees` `main` worktree.

## Common failure modes

1. **`governed_session_count=0` with persist off** — `campaign_status` returns `empirical_counts_source=persistence_disabled`. Sessions may still exist in canonical SQLite.
2. **Empty worktree `.local`** — Default `state_dir()` points here. Use `IMP_STATE_DIR` for operator reads.
3. **Stale primary `main`** — Software on old SHA; durable state on primary `.local` may reflect newer operator actions. Prefer an `origin/main` worktree for code changes.

## Campaign binding `manifest_path` provenance

Durable rows may store the absolute path present at activation time (e.g. under `.worktrees/ftep-session-release/...`). Runtime authority uses **`manifest_fingerprint`** and slug-based manifest loading under `artifacts/forward-test-campaigns/`, not re-reading the stored path on every gate. Optional release guards may compare path substrings when operators supply them.

Do **not** normalize historical SQLite rows for cosmetics; that would rewrite empirical provenance. Future activations from the primary checkout record repo-relative paths under `artifacts/forward-test-campaigns/`.

## Related

- [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md) — linked worktrees and `python tools/imp.py env`
- [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md) — forward-test persistence
