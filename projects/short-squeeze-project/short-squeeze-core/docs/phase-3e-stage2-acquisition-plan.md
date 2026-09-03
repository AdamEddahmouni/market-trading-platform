# Phase 3E Stage 2 — Forward Outcome Acquisition Plan

## Status

**Executed (2026-08-16).** Forward-outcome bars collected for 15 symbols via IBKR
Gateway; artifacts stored under `intake/local-bars/ibkr-batch-05/raw/*-forward-outcome.*`
with summary at `build/acquisition/stage2/collection-summary.json`. Fixture regeneration
now prefers these Stage 2 bars over legacy frozen-forward artifacts.

**Preregistered.** This document was committed before any forward outcome bar data was
fetched, inspected, or computed for the 13 pilot symbols. Stage 1 evidence construction
and Phase 3A evaluation freeze scripts are available on branch
`phase/3e-historical-acquisition`. This plan authorizes outcome data access for Stage 2
only.

## Scope

This plan covers Stage 2 of Phase 3E as defined in
[`docs/phase-3e-design.md`](phase-3e-design.md). Stage 1 (outcome-blind evidence
construction) is complete on the Phase 3E feature branch atop current `main`.

## Cohort

Exactly the 13 Phase 3D pilot symbols in frozen source order:

| # | Symbol | Case ID | Frozen Boundary (UTC) |
|---|--------|---------|----------------------|
| 1 | XNCR | BATCH01_XNCR_20260718 | 2026-07-18T13:37:55.017661Z |
| 2 | PESI | BATCH01_PESI_20260718 | 2026-07-18T13:37:55.017661Z |
| 3 | SLS | BATCH01_SLS_20260718 | 2026-07-18T13:37:55.017661Z |
| 4 | ZNTL | BATCH01_ZNTL_20260718 | 2026-07-18T13:37:55.017661Z |
| 5 | GPRE | BATCH01_GPRE_20260718 | 2026-07-18T13:37:55.017661Z |
| 6 | SSPC | BATCH01_SSPC_20260718 | 2026-07-18T13:37:55.017661Z |
| 7 | LBGJ | BATCH01_LBGJ_20260718 | 2026-07-18T13:37:55.017661Z |
| 8 | TRVI | BATCH01_TRVI_20260718 | 2026-07-18T13:37:55.017661Z |
| 9 | LMNX | BATCH01_LMNX_20260718 | 2026-07-18T13:37:55.017661Z |
| 10 | MGNX | BATCH01_MGNX_20260718 | 2026-07-18T13:37:55.017661Z |
| 11 | BHVN | BATCH01_BHVN_20260718 | 2026-07-18T13:37:55.017661Z |
| 12 | OBE | BATCH01_OBE_20260718 | 2026-07-18T13:37:55.017661Z |
| 13 | AVTX | BATCH01_AVTX_20260718 | 2026-07-18T13:37:55.017661Z |

No additional symbols are added. The cohort is identical to Stage 1.

## Window adjustment

The frozen detection boundary (`2026-07-18T13:37:55.017661Z`) falls on a Saturday.
US equity markets are closed on weekends. Per the preregistered window adjustment rule
in the Phase 3E design:

> If the 24-hour forward window falls on a non-trading day (weekend or holiday), the
> window is shifted to the next available trading day.

The next available US equity trading day after Saturday 2026-07-18 is **Monday 2026-07-21**.

### Adjusted forward window

| Parameter | Value |
|-----------|-------|
| Adjusted forward start | 2026-07-21T13:37:55Z (Monday) |
| Adjusted forward end | 2026-07-22T13:37:55Z (Tuesday) |
| Calendar shift | +72 hours (Saturday → Monday) |
| Actual trading session captured | ~6.5 hours regular + extended hours |

### Acknowledged limitation

The calendar shift from Saturday to Monday expands the forward window from 24 hours to
72+ hours of calendar time while capturing only ~6.5 hours of regular trading session
plus extended hours. This materially changes the window definition and introduces a
bias. The limitation is documented and preserved per the Phase 3E design; it is not
remedied by further window manipulation.

The shift is applied identically to all 13 symbols before outcome computation. No
per-symbol window adjustment is performed.

## IBKR request parameters

| Parameter | Value |
|-----------|-------|
| Source | IBKR TWS API via IB Gateway (localhost:4001) |
| `whatToShow` | `TRADES` |
| `barSizeSetting` | `1 min` |
| `useRTH` | `0` (extended hours eligible) |
| `formatDate` | `2` (UTC epoch seconds) |
| `keepUpToDate` | `False` |
| `chartOptions` | `[]` |
| `endDateTime` | `20260722 13:37:55 UTC` |
| `durationStr` | `86400 S` |

The `endDateTime` is derived from the adjusted forward end
(`2026-07-22T13:37:55.017661Z`) with fractional seconds truncated. This matches the
existing truncation convention established in Batch 05 (`REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND`).

## Bar semantics

Forward outcome bars use the identical semantic declarations as the detection-context
bars (ADR 0066):

| Field | Value | Source |
|-------|-------|--------|
| `price_adjustment_semantics` | `SPLIT_ADJUSTED` | Official IBKR documentation |
| `corporate_action_handling` | `ADJUSTMENTS_APPLIED` | Official IBKR documentation |
| `timestamp_representation` | Epoch seconds → UTC | Official IBKR documentation |
| `session_policy` | `EXTENDED` (useRTH=0) | Request parameter |
| `volume_adjustment_semantics` | `UNKNOWN` | ADR 0066 |
| `timestamp_semantics` | `UNKNOWN` | ADR 0066 |
| `volume_unit` | `HISTORICAL_VOLUME_UNIT_UNRESOLVED` | ADR 0066 |

Semantics are never resolved differently for outcome bars than for detection-context
bars.

## Outcome computation protocol

After forward bars are collected:

1. Compute reference price: first eligible trade-bar close at or after the detection
   boundary.
2. For each forward bar, compute percentage return from reference price.
3. Apply `phase_3b_outcome_label_policy.v1`:
   - Horizon: 24 hours
   - Upward threshold: +25%
   - Downward threshold: -25%
   - Labels: `SUBSTANTIAL_UPWARD_MOVE`, `NO_SUBSTANTIAL_UPWARD_MOVE`,
     `MIXED_OR_VOLATILE`, `SUBSTANTIAL_DOWNWARD_MOVE`, `OUTCOME_INSUFFICIENT_DATA`,
     `OUTCOME_UNKNOWN`
4. Record outcome in a separate manifest (never merged with Phase 3A evidence).

## Leakage audit requirements

Before any outcome is published, the Phase 3D leakage audit must verify:

1. This acquisition plan was committed before outcome capture.
2. The boundary freeze was committed before outcome capture.
3. The Phase 3A request was frozen before outcome capture.
4. The Phase 3A result was frozen before outcome capture.
5. The outcome manifest is a separate contract from the evaluation freeze.

Any audit failure blocks empirical publication while retaining the attempted case.

## Artifact output

| Artifact | Location |
|----------|----------|
| Forward outcome CSVs | `intake/local-bars/ibkr-batch-05/raw/{SYMBOL}-forward-outcome.csv` |
| Forward outcome JSONLs | `intake/local-bars/ibkr-batch-05/raw/{SYMBOL}-forward-outcome.jsonl` |
| Collection summary | `build/acquisition/stage2/collection-summary.json` |
| Phase 3A freeze | `build/acquisition/stage2/phase3a-freeze/{SYMBOL}/` |
| Outcome manifests | `build/acquisition/stage2/outcomes/{SYMBOL}/` |
| Leakage audit | `build/acquisition/stage2/leakage-audit/` |
| Phase 3B outputs | `build/acquisition/stage2/phase3b/` |
| Phase 3C reports | `build/acquisition/stage2/phase3c/` |

## Policies

All policies are frozen at the versions established in prior phases. No policy is
changed, optimized, or threshold-adjusted during Stage 2.

| Policy | Version |
|--------|---------|
| Outcome-label policy | `phase_3b_outcome_label_policy.v1` |
| Research detection policy | `phase_3b_research_detection_policy.v1` |
| Transparent candidate policy | `phase_3a_transparent_candidate_policy.v1` |
| Descriptive statistics policy | `phase_3c_descriptive_statistics_policy.v1` |
| Interval policy | `phase_3c_interval_policy.v1` |
| Sample-size policy | `phase_3c_sample_size_policy.v1` |
| Acquisition plan policy | `phase_3d_acquisition_plan_policy.v1` |
| Outcome leakage policy | `phase_3d_outcome_leakage_policy.v1` |

## Non-goals

Stage 2 does not:
- Change any policy version or threshold
- Create composite scores, rankings, or recommendations
- Perform backtesting, P&L, or trading simulation
- Expand the symbol universe
- Fabricate missing evidence
- Begin Phase 3F
