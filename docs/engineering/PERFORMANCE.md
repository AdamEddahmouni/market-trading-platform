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
