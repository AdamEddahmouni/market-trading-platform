# ADR 0068: Phase 3B outcome-label calibration findings

## Context

Phase 3D counterfactual calibration (`outcome_sensitivity_historical.v1`) was run against
the expanded historical cohort of **30 case boundaries** (28 unique symbols, 27
independent symbols per ADR-0054). The cohort reached
`min_case_count_for_recommendation: 30` after Phase 3E Stage 2 and Phase 3F cohort
expansion Batches 01–03.

The experiment varied upward outcome thresholds (±25% baseline, +28%, +30%, +35%) over
the fixed 24-hour horizon defined in `phase_3b_outcome_label_policy.v1`. Results are
governed by ADR-0065 (counterfactual exploration only, no auto-promotion).

See [PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md](../calibration/PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md)
for the full review record.

## Decision

1. **Retain** the production outcome label policy (`phase_3b_outcome_label_policy.v1`):
   ±25% over 24 hours with reference price
   `first_eligible_trade_bar_close_at_or_after_boundary.v1`.
2. **Reject** `upward_30` (raise upward threshold to 30%). It flips
   `BIYA_EARLIEST_BOUNDARY` from TRUE_POSITIVE to FALSE_POSITIVE (max move 28.34% is
   below 30%).
3. **Reject** `strict_35` (raise upward threshold to 35%). It flips both BIYA boundaries
   from TRUE_POSITIVE to FALSE_POSITIVE (latest boundary max move 31.68% is below 35%).
4. **No action on** `upward_28` — it produced zero classification flips. BIYA earliest
   boundary at 28.34% is near but below the 28% variant flip point.
5. **Defer Adam scoring calibration** (`adam_evidence_gated_prime.v1`). Outcome policy
   review does not authorize live-screener weight tuning.

## Consequences

- Phase 3B outcome label policy stays provisional but unchanged.
- Calibration reports must continue to emit `COUNTERFACTUAL_EXPLORATION_ONLY` and
  `NO_THRESHOLD_AUTO_PROMOTION`.
- Outcome labels describe forward price movement from a frozen boundary — they do not
  establish short-squeeze causation.
- Repeated BIYA boundaries are not independent observations (ADR-0054).
- No outcome threshold variant is authorized for automatic promotion to production policy.

## Rejected alternatives

- Raising the upward threshold to 30% or 35% based on n=30 counterfactual results.
- Treating outcome sensitivity confusion matrices as predictive validation.
- Substituting current market prices for historical boundary reference prices (ADR-0062).

## Revision history

| Date | Change |
|------|--------|
| 2026-08-17 | Initial ADR at n=30 after Phase 3F cohort expansion completion |
