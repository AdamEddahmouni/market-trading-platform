# Performance Engineering P4 — Fixture / Setup Optimization

Measurement-first reduction of repeated test infrastructure work while
preserving per-test isolation, selector semantics, and product/safety
invariants.

## Environment (linked worktree)

P4 benchmarks use the canonical project `.venv` via a directory junction from
the linked worktree checkout:

```powershell
cmd /c mklink /J projects\integrated-market-platform\.venv `
  C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.venv
```

Activate with `projects\integrated-market-platform\.venv\Scripts\python.exe`
before `tools\imp.py` / `tools\validate.py`. This avoids
`ZoneInfoNotFoundError: America/New_York` from system Python missing `tzdata`.

## Implemented optimizations

| ID | Area | Change | Isolation |
|----|------|--------|-----------|
| P4-001 | `ReplayStore.load` | `_cached_decoded_replay_snapshot` + `deepcopy` per load | `test_replay_store_loading`, `test_fixture_setup_cache_isolation` |
| P4-002 | `build_combined_fixture_ledger` | Immutable template cache + defensive clone | `test_fixture_setup_cache_isolation` |
| P4-003 | `ReplayStore` | `hydrate_replay_bars_from` + `refresh_mutable_runtime` | broker wiring + isolation tests |
| P4-004 | `test_broker_runtime_wiring` | Class-warm replay + per-test mutable refresh | 7 broker tests green |
| P4-005 | `validation_worker` | Emit `slowest_tests` in worker JSON | profiling support |

## Root-cause ledger (investigated)

| Target | Outcome | Notes |
|--------|---------|-------|
| `ReplayStore.load` warm path | OPTIMIZED | 17.4s → 0.49s warm microbenchmark |
| `build_combined_fixture_ledger` | OPTIMIZED | warm build ~3ms |
| `platform` unified workstation tests | NOT ACTUALLY A HOTSPOT (setup) | ~8s/test is projection body time |
| `donor_bridge` cross-lane harness | NOT ACTUALLY A HOTSPOT (setup) | ~4s/test is fusion body time |
| `ui1` duplicate class `setUpClass` | SAFE BUT LOW VALUE | second load already warm at ~0.5s |
| Test discovery import graph (`platform`) | DEFER TO P6 | ~8.9s discovery per worker |
| Parallel execution | DEFER TO P2 | not implemented in P4 |

## Artifacts

| File | Purpose |
|------|---------|
| `P4_BEFORE_BASELINE.json` | Pre-change timings |
| `P4_AFTER_BASELINE.json` | Post-change timings |
| `OPTIMIZATION_LEDGER.json` | Machine-readable decision log |

## Evidence commands

```powershell
python tools/imp.py validate fast
python tools/validation_worker.py --repository-root . --suite-id platform --suite-path tests/platform --profile-fixtures
python -m unittest tests.validation.test_fixture_setup_cache_isolation -q
```
