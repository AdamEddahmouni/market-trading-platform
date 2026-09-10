# Performance Engineering P3 — Validation Selector Precision

First implementation increment after the P0 forensic audit. Implements BL-0801
subsystem-aware validation partitioning, narrow evidence-only classification,
cheap `--plan` dry-run selection, and explicit CHANGED-vs-FULL selector-safety
trials.

## Commands

```powershell
# Cheap selector plan (no test execution)
python tools/validate.py changed --plan
python tools/imp.py validate changed --plan --json artifacts/p3-plan.json

# Explicit selector-safety trial (CHANGED vs FULL)
python tools/selector_safety_trial.py --paths-file <paths.txt> --json artifacts/p3-selector-safety-receipt.json
```

## Architecture

```
CHANGED PATHS
  → path classification (docs / governance / evidence-only / partition / suite / shared / fail-safe)
  → direct owner suites
  → directional dependents (BL-0801 partitions) OR legacy neighbors
  → mandatory invariant floor
  → core checkpoint when required
  → execution (or --plan stops before execution)
```

## Evidence-only (narrow)

Only governed patterns in `validation_manifest.json` → `evidence_only_patterns`
are treated as `EVIDENCE_ONLY`. Example:

- `artifacts/g*-runtime-performance.json`
- `artifacts/p*-performance-baseline.json`

`artifacts/repository-closure/**` remains **source-relevant** (validation control plane).

## BL-0801 partitions

Declared in `subsystem_partitions`:

| Partition | Owner | Dependents |
|-----------|-------|------------|
| `news_foundation` | `news` | `intelligence` |
| `intelligence_inference` | `intelligence` | (none) |
| `news_strategy_evaluation` | `intelligence` | (none) |
| `validation_control_plane` | `validation` | (none) |
| `frontend_ui` | `ui1` | (none) |

Unknown paths remain fail-safe. FULL remains the regression oracle.

## Artifacts

| File | Purpose |
|------|---------|
| `P3_BEFORE_BASELINE.json` | Pre-P3 selector measurements |
| `P3_AFTER_BASELINE.json` | Post-P3 localized scenario measurements |
| `SELECTOR_SAFETY_RECEIPT.json` | Closure CHANGED-vs-FULL trial |

## P3 initial closure (historical)

- CHANGED control-plane run: 554 tests, 1 skipped, 0 failures, 0 errors
- News-only selector-safety shadow: 1255 changed vs 4471 FULL, **ZERO OBSERVED SELECTOR MISSES**
- FULL: 4471 tests, 0 failures, **4 errors** (`GIT_REPOSITORY_NOT_FOUND` in linked Git worktree)

Root cause: canonical `git_ref.py` treated `.git` as directory-only and did not
resolve linked-worktree pointer files or shared `commondir` metadata.

## P3.1 worktree-compatibility closure

- Extended `git_ref.py` to recognize `.git` directories **and** `gitdir:` pointer
  files, resolve worktree roots separately from shared metadata, and read refs
  from both worktree-specific and common git directories.
- Added `tests/platform/test_git_ref.py` (standard repo, linked worktree, pointer
  parsing, malformed/missing targets, real perf-worktree regression).
- Re-ran changed / selector-safety / FULL in the performance worktree with
  zero failures and zero errors.

Receipts:

| Artifact | Purpose |
|----------|---------|
| `artifacts/p3.1-changed-closure.json` | Post-fix changed validation |
| `artifacts/p3.1-full-closure.json` | Post-fix clean FULL |
| `SELECTOR_SAFETY_RECEIPT_P3.1.json` | Post-fix news-only selector-safety trial |

## Next phase

Measured evidence points to **P4 — fixture/setup optimization** as the next
performance increment after P3 clean closure.
