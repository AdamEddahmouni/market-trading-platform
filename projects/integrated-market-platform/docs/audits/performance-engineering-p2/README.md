# P2 — Safe Test Parallelization

Performance Engineering secondary lane increment completed 2026-09-10.

## Objective

Reduce validation wall time by executing proven-independent suite work concurrently at
process level, without weakening tests, changing product behavior, or compromising
P3/P4/P5/P6 contracts.

## Worktree

- Path: `C:/Users/adame/Desktop/market-trading-platform-perf-p2`
- Branch: `perf/p2-safe-parallelization`
- Starting SHA: `6e44948cf9cd3b28b7a21c1f07a26c91370ad84a`
- Committed: **no** (review-only)

## Architecture

```
P3 selection (what runs)
  → build_execution_schedule (how eligible suites run)
  → mandatory invariants (serial)
  → SERIAL_REQUIRED / UNKNOWN_FAIL_SAFE wave (serial)
  → PARALLEL_SAFE wave (bounded process workers)
  → RESOURCE_HEAVY wave (capped concurrency)
  → LIVE_EXCLUSIVE wave (serial, live only)
  → aggregate JSON receipt
```

- Scheduler version: `p2-bl-0901-1`
- Default workers: `2` (opt-in via `--workers` / `IMP_VALIDATION_WORKERS`)
- FAST mode: serial (`workers=1`)
- Process-level suite workers only (no pytest-xdist)

## Key artifacts

| File | Purpose |
|------|---------|
| `PARALLEL_SAFETY_MAP_CURRENT.json` | Refreshed suite concurrency classification |
| `P2_BEFORE_BASELINE.json` | Serial measurements before P2 parallelism |
| `P2_AFTER_BASELINE.json` | Parallel measurements after P2 |
| `CONCURRENCY_SCENARIOS.json` | Worker-count matrix |
| `FLAKE_STABILITY_RECEIPT.json` | Repeated parallel run evidence |
| `P2_CLOSURE.json` | Closure summary |

## P0 → P2 classification delta

| Class | P0 | P2 |
|-------|----|----|
| PARALLEL_SAFE | 45 | 56 |
| GLOBAL_STATE_MUTATION | 11 | 0 |
| RESOURCE_HEAVY | 5 | 5 |
| SERIAL_REQUIRED | 5 | 2 |
| LIVE_EXCLUSIVE | 12 | 12 |

Eleven suites reclassified from `GLOBAL_STATE_MUTATION` to `PARALLEL_SAFE` after
P2 audit confirmed process-local globals and suite-specific artifact paths only.

## Default policy

**OPT_IN** — parallelism available via `--workers N` (default 2). Serial fallback
via `--workers 1`. Evidence supports opt-in default until broader FULL stability
history is collected on CI.
