# AACP forward-outcome exclusion record

**Date:** 2026-08-18  
**Case:** `BATCH3F05_AACP_20260817`  
**Disposition:** `OUTCOME_UNEVALUABLE` (permanent, evidence-backed)

## Summary

AACP is the only Batch 05 external symbol without an evaluable Stage 2 forward-outcome
label. IBKR historical `TRADES` requests returned `SUCCESS_EMPTY` on initial collection
and on a governed retry using the Phase 3E adjusted Monday forward window. No synthetic
bars were fabricated.

## Evidence

| Attempt | Request | Status | Bars |
|---------|---------|--------|-----:|
| Initial (2026-08-17) | `FROZEN_FORWARD_24H` | `SUCCESS_EMPTY` | 0 |
| Retry (2026-08-18) | `ADJUSTED_FORWARD_OUTCOME_24H` | `SUCCESS_EMPTY` | 0 |

Machine-readable record:
[`aacp_forward_outcome_retry.json`](../../intake/batches/phase-3f-cohort-expansion-05-external/normalized/aacp_forward_outcome_retry.json)

## Context

- Cohort boundary: `2026-08-17T22:09:23.412932Z` (Sunday; Stage 2 Monday adjustment applies).
- Adjusted forward window (retry): `2026-08-20T22:09:23Z` → `2026-08-21T22:09:23Z`.
- IBKR contract: `conId=886847440`, NASDAQ.
- Detection-context bars exist (310 bars) but last trade activity ends **2026-08-14**;
  the symbol appears illiquid or inactive at the export boundary.

## Cohort accounting

| Metric | Count |
|--------|------:|
| Batch 05 case boundaries | 5 |
| Evaluable forward-outcome labels | 4 |
| Permanent outcome exclusions | 1 (AACP) |

Cohort expansion policy threshold (`min_case_count_for_recommendation: 30`) remains met
at the full-registry level (35 boundaries, 34 evaluable outcomes).

## Governance

- Does not change detection policy (ADR-0067) or outcome policy (ADR-0068).
- Does not lower Batch 07 semantics gates.
- Stage 2 pipeline correctly skips outcome artifact generation when forward CSV is empty.
