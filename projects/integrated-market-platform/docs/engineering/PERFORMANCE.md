# Performance

**Status:** Current performance governance.

## Bundle budget

| Metric | Limit | Enforcement |
|--------|-------|-------------|
| Initial JS (gzip) | **200 KiB** | `ui/scripts/check-bundle-budget.mjs` on `npm run build` |
| Lazy chunk (raw) | **500 KB** | same script |

Last recorded: **199.17 KiB gzip** (2026-09-01).

## Rules

1. Lazy-load lane routes, assistant, settings, provider health, canary page
2. Avoid eager Paper-only imports on Demo/Live entry paths
3. Prefer Lightweight Charts over adding new chart libraries
4. Review `recharts` usage — keep off initial path

## Regression process

1. `npm run build` — must pass budget script
2. If intentional increase needed — ADR + budget script update with justification

## Backend

Foundation optimized for correctness over micro-latency. No formal latency SLO for local workstation.

Intelligence BUILD workloads may use numpy/sklearn — separate from UI API hot path.

The largest single per-request cost on `/screener` is the fail-closed
secret-leak audit, not data access or response serialization. It is a security
control, not a performance knob.

## Screener / AI pipeline

The Live Screener and its AI analysis path have their own measurement contract:
[Screener / AI pipeline performance](SCREENER_AI_PERFORMANCE.md). It records the
stage profile, the comparability policy (`COMPARABLE` / `INCOMPATIBLE_WORKLOAD` /
`INCOMPATIBLE_ENVIRONMENT` / `INSUFFICIENT_EVIDENCE`) and provenance rules
for a synthetic 4,622-row admitted US equity fixture served as 200-row pages.
Earlier before/after claims remain provisional until the corrected final source
has independent review, controlled paired measurements and runtime acceptance.

Measure with `python tools/screener_ai_perf_profile.py`, then
`python tools/screener_ai_perf_compare.py BEFORE.json AFTER.json`. Never quote
a speedup from a different machine, fixture or interpreter.
