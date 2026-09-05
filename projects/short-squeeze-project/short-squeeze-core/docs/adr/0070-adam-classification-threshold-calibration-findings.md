# ADR-0070: Adam classification threshold calibration findings

**Status:** Accepted  
**Date:** 2026-08-17  
**Track:** Live screener methodology (not Phase 3B historical policy)

## Context

ADR-0069 retained the 65% minimum dimension weight for `adam_evidence_gated_prime.v1`
and deferred classification gate calibration. Live scanner ranking (`sort_rows_for_display`,
refresh priority) uses PRIME/SUBPRIME/WATCH classifications alongside pressure and
ignition scores.

Baseline classification gates:

| Gate | Value |
|------|-------|
| PRIME | Pressure ≥ 70, Ignition ≥ 70, HIGH coverage (85%+ weight) |
| SUBPRIME | (P ≥ 70 & I ≥ 50) OR (I ≥ 70 & P ≥ 50) |
| WATCH | P ≥ 50 OR I ≥ 50 |
| Coverage HIGH / MODERATE / LOW | 85% / 70% / 50% weight |

## Decision

1. **Retain** baseline classification thresholds (70/70 PRIME with 85% HIGH coverage).
2. **Reject** lowering `high_coverage_min` to 65% — Finviz-only core profile flips
   SUBPRIME → PRIME without borrow/acceleration/catalyst legs.
3. **Reject** raising PRIME gates to 75 — demotes marginal full-coverage profiles from
   PRIME to SUBPRIME without improving evidence quality.
4. **Reject** lowering PRIME gates to 65 — no material live-ranking benefit on anchor
   profiles; PRIME tier should remain strict.
5. Set `thresholds_optimal: true` in methodology metadata when default thresholds are used
   (alongside `weights_validated: true` from ADR-0069).

## Calibration summary

| Variant | Key flip from baseline |
|---------|------------------------|
| `lower_high_coverage_65` | `finviz_pressure_ignition_core`: SUBPRIME → PRIME |
| `raise_prime_75` | `prime_boundary_72`: PRIME → SUBPRIME |
| `lower_prime_65` | None on anchor profiles |
| `lower_high_coverage_70` | None on anchor profiles |
| `lower_watch_45` | None on anchor profiles |

Source: `reports/calibration/adam_classification_threshold_live_profiles.json` (2026-08-17).

## Consequences

- Finviz Elite minimum bundle (65% weight per dimension, max scores) stays **SUBPRIME**
  until additional provider legs raise weight coverage to HIGH (85%+).
- Full nine-field cloud + IBKR profiles remain **PRIME** at baseline gates.
- Live scanner sort order preserves PRIME > SUBPRIME > WATCH without inflating Finviz-only
  rows to the top tier.
- Phase 3B detection and outcome policies remain unchanged.

## Rejected alternatives

- Promoting Finviz-only rows to PRIME by lowering the HIGH coverage requirement.
- Raising PRIME gates to reduce live PRIME prevalence.
- Treating synthetic profile sweeps as predictive validation of squeeze outcomes.

## Revision history

| Date | Change |
|------|--------|
| 2026-08-17 | Initial ADR after live-screener classification-threshold calibration |
