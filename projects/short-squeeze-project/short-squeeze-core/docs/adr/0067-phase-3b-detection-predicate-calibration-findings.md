# ADR 0067: Phase 3B detection-predicate calibration findings

## Context

Phase 3D counterfactual calibration (`detection_predicate_candidates_historical.v1`) was re-run after:

- BIYA published short-interest evidence became evaluable at both historical boundaries.
- TRVI and LBGJ were registered as complete historical cases, expanding the labeled cohort to **n=3 unique symbols** (four case boundaries).

The cohort remains far below `min_case_count_for_recommendation: 30` in `phase_3d_calibration_policy_v1.json`. Results are exploratory only (ADR 0065).

## Decision

1. **Retain** the production research detection predicate (`phase_3b_research_detection_policy.v1`): `PRICE_RANGE`, `MARKET_DATA_AVAILABLE`, `COMPLETED_BAR_AVAILABLE`.
2. **Reject** `momentum_full` as a detection gate. It converts BIYA true positives to false negatives because `FLOAT_MAXIMUM` stays unknown on incomplete float evidence.
3. **Reject** `short_pressure_core` as a detection gate. Even with BIYA short interest now evaluable, peer symbols lack published SI; gating detection on `PUBLISHED_SHORT_INTEREST_AVAILABLE` would block cases with honest missing evidence (ADR 0047).
4. **Do not adopt** `momentum_pct_change` unless a future cohort shows clear benefit without harm; the expanded run showed no classification flips from baseline.
5. **Defer Adam scoring calibration** (`adam_evidence_gated_prime.v1`) until detection policy and historical evidence layers stop changing. Adam tuning is a live-screener track and must not be conflated with this ADR.

## Consequences

- Phase 3B research detection policy stays provisional but unchanged.
- Calibration reports must continue to emit `SMALL_SAMPLE_WARNING` and `COUNTERFACTUAL_EXPLORATION_ONLY`.
- Repeated BIYA boundaries are not independent observations (ADR 0054).
- Outcome labels do not establish short-squeeze causation.
- No variant in the historical calibration suite is authorized for automatic promotion to production policy.

## Rejected alternatives

- Promoting `momentum_full` or `short_pressure_core` based on n=3 exploratory results.
- Substituting live Finviz or current borrow data for historical gaps (ADR 0062).
- Treating calibration confusion matrices as predictive validation.
