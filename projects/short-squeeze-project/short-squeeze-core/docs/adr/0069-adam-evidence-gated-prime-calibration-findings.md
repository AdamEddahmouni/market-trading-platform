# ADR-0069: Adam Evidence-Gated Prime v1 calibration findings

**Status:** Accepted  
**Date:** 2026-08-17  
**Track:** Live screener methodology (not Phase 3B historical policy)

## Context

`adam_evidence_gated_prime.v1` uses a 65% minimum supported weight per dimension before
pressure or ignition scores are computed. Prior ADRs (0067, 0068) and the Phase 3D policy
review deferred Adam calibration until historical detection and outcome policies stabilized.
Those policies are now confirmed unchanged at n=30.

Adam tuning affects **live scanner ranking** (`sort_rows_for_display`, refresh priority)
and must not be conflated with historical research policy review.

## Decision

1. **Retain** `MIN_DIMENSION_WEIGHT = 65` for Evidence-Gated Prime v1.
2. **Reject** lowering the floor to 50% or 55% — partial pressure (SI + DTC without float)
   would flip from `UNEVALUABLE` to `SUBPRIME`.
3. **Reject** raising the floor to 70% — Finviz Elite core profiles have exactly 65%
   supported weight per dimension and become unevaluable.
4. **Complete** classification threshold calibration — see [ADR 0070](../adr/0070-adam-classification-threshold-calibration-findings.md).
5. Set `weights_validated: true` in methodology metadata when the default floor is used.

## Calibration summary

| Floor | Evaluable profiles | Key flip from 65% baseline |
|-------|-------------------|---------------------------|
| 50% | 4 | `pressure_si_dtc_only`: UNEVALUABLE → SUBPRIME |
| 55% | 4 | `pressure_si_dtc_only`: UNEVALUABLE → SUBPRIME |
| 60% | 3 | None |
| **65%** | **3** | **Baseline** |
| 70% | 1 | `finviz_pressure_ignition_core`: SUBPRIME → UNEVALUABLE |

Source: `reports/calibration/adam_weight_floor_live_profiles.json` (2026-08-17).

## Consequences

- Live cloud deployments with Finviz Elite retain evaluable methodology for the minimum
  provider bundle (SI + DTC + float + change + relvol).
- Partial Finviz pressure (without float) remains honestly withheld as `UNEVALUABLE`.
- Scanner default sort continues to prefer evaluable classifications over discovery score.
- Phase 3B detection and outcome policies remain unchanged.

## Rejected alternatives

- Lowering the floor to increase live evaluability counts without full pressure evidence.
- Raising the floor to reduce `LOW_COVERAGE` classifications on Finviz-only rows.
- Treating synthetic profile sweeps as predictive validation of squeeze outcomes.

## Revision history

| Date | Change |
|------|--------|
| 2026-08-17 | Initial ADR after live-screener weight-floor calibration |
| 2026-08-17 | Classification threshold calibration completed in ADR 0070 |
