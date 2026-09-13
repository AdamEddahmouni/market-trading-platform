# Test, reliability, and performance audit

**Lane:** I | **Date:** 2026-09-12

## Test baseline (PROGRAM_STATUS)

- FULL suite historically **~4392 tests**, 48 skipped, 0 failures at G15 closure.
- FAST mandatory gate: **21 tests** (security offline denial + shared).

## Overnight validation

```
Worktree: overnight/imp-parallel-2026-09-12
Command: python tools/imp.py validate fast
Result: 21 passed, 0 failures (9.46s wall; PERF SEVERE_REGRESSION vs local median — cold path)
```

## Performance program

- P7 continuous budgets: `manifests/performance_budget.json`, gating **OBSERVE_ONLY**.
- Runtime perf artifacts: g8/g13/g14 JSON on foreground (dirty) — not modified overnight.
- Recommendation: run `validate changed` on foreground after FTEP merges, not on stale main-only worktree.

## Reliability themes

1. Fail-closed authority model consistently tested in mandatory-isolated-security suite.
2. IBKR live paths **LIVE_PROVIDER_UNVERIFIED** except bounded G11.1 L1 canary.
3. No chaos/dr DR acceptance beyond BUILD32 drill index (historical).

## Class

- Regression risk on merge: **MEDIUM** (foreground 8 commits ahead of merge-base with main).
- Overnight implement: **LOW_VALUE** — observe only.
