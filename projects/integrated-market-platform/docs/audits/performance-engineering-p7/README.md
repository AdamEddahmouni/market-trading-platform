# P7 — Continuous Performance Budgets & Stable Telemetry

**Status:** COMPLETE (local evidence)
**Branch:** `perf/p7-continuous-performance-budgets`
**Parent SHA:** `efc9219ea4d1a79511278a4a8c0ea0d0d5e8e2fd` (P6)
**Budget version:** `p7-bl-0910-1`

## Objective

Establish deterministic, evidence-backed performance-budget and telemetry for IMP
validation without gating CI, changing product behavior, or destabilizing the P2
scheduler.

## Architecture

| Component | Path | Role |
|-----------|------|------|
| Budget manifest | `manifests/performance_budget.json` | Canonical workloads, thresholds, compatibility |
| Classification | `tools/performance_budget.py` | Deterministic budget comparison |
| Receipt telemetry | `tools/performance_telemetry.py` | Environment fingerprint + receipt enrichment |
| Benchmark collector | `tools/perf_baseline_measure.py` | Repeated-run evidence |
| Developer surface | `tools/imp.py env` | Read-only budget status (no validation launch) |
| CI summary | `.github/workflows/imp-python.yml` | `ci-performance-summary.json` artifact |

## Classification model

`NO_BASELINE` → `INSUFFICIENT_DATA` → `INCOMPATIBLE_BASELINE` →
`NORMAL` / `WARNING` / `REGRESSION` / `SEVERE_REGRESSION`

Gating policy: **OBSERVE_ONLY** (P7 does not fail validation on timing).

## Inherited P2 baseline

P2 scheduler (`p2-bl-0901-1`) integrated from uncommitted P2 worktree evidence.
P2 parallel baselines remain in `docs/audits/performance-engineering-p2/` as
historical reference. P7 re-measured local baselines supersede P2 numbers in
`manifests/performance_budget.json` where marked `MEASURED`.

## Evidence files

| File | Purpose |
|------|---------|
| `P7_BENCHMARK_SERIES.json` | Repeated FAST + domain macro measurements |
| `P7_CLOSURE.json` | Closure summary |
| `ENVIRONMENT_COMPATIBILITY.md` | Comparison policy |
| `TELEMETRY_ARCHITECTURE.md` | Receipt + CI telemetry design |
| `INSTRUMENTATION_OVERHEAD.json` | P7 overhead estimate |

## Known limitations

- Remote CI baselines: `REMOTE_UNMEASURED`
- Changed-validation baseline: inherited P2 representative path (`LOW` confidence)
- FULL parallel: single P7 closure sample; repeat series deferred to P2 follow-up
- Domain macro P7 measurement (~6.9s) differs from P2 (~3.3s); investigate in P2 follow-up

## Recommended next phase

Mature CI-specific baselines after sufficient remote samples; consider optional
hard gates only for metrics with proven stability (P7 follow-up).
