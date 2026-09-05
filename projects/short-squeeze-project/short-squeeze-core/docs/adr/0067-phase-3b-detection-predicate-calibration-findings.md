# ADR 0067: Phase 3B detection-predicate calibration findings

## Context

Phase 3D counterfactual calibration (`detection_predicate_candidates_historical.v1`) was
re-run after the historical cohort reached **n=30 case boundaries** (28 unique symbols,
27 independent symbols per ADR-0054):

- Phase 3E Stage 2 collected forward-outcome bars for 15 IBKR symbols.
- Phase 3F cohort expansion Batches 01–03 added 13 symbols from archived platform logs
  and screening-universe history.
- BIYA published short-interest evidence is evaluable at both historical boundaries.

The cohort now meets `min_case_count_for_recommendation: 30` in
`phase_3d_calibration_policy_v1.json`. This ADR supersedes the exploratory n=3 run
(TRVI, LBGJ, BIYA) documented in the original 2026-08-16 revision.

See [PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md](../calibration/PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md)
for the full review record.

## Decision

1. **Retain** the production research detection predicate
   (`phase_3b_research_detection_policy.v1`): `PRICE_RANGE`, `MARKET_DATA_AVAILABLE`,
   `COMPLETED_BAR_AVAILABLE`.
2. **Reject** `momentum_full` as a detection gate. At n=30 it converts both BIYA true
   positives to false negatives because `FLOAT_MAXIMUM` stays unknown on incomplete float
   evidence. It also flips 16 artifact-discovery cases from UNEVALUABLE to TRUE_NEGATIVE.
3. **Reject** `short_pressure_core` as a detection gate. Zero classification flips at n=30,
   but gating on `PUBLISHED_SHORT_INTEREST_AVAILABLE` would block cases with honest
   missing evidence (ADR-0047). Peer symbols lack published SI at historical boundaries.
4. **Reject** `momentum_pct_change` as a detection gate. At n=30 it resolves 16
   artifact-discovery cases as TRUE_NEGATIVE (UNEVALUABLE→TN) by adding
   `PERCENTAGE_CHANGE_MINIMUM`, but provides no detection benefit — BIYA classification
   is unchanged. Reclassification of unevaluable cases is not sufficient grounds for
   adoption.
5. **Defer Adam scoring calibration** (`adam_evidence_gated_prime.v1`) until detection
   policy and historical evidence layers stop changing. Adam tuning is a live-screener
   track and must not be conflated with this ADR.

## n=30 calibration summary

| Variant | TP | TN | FN | Unevaluable | Flips |
|---------|---:|---:|---:|------------:|------:|
| `baseline` | 2 | 0 | 0 | 28 | — |
| `momentum_pct_change` | 2 | 16 | 0 | 12 | 16 |
| `momentum_full` | 0 | 16 | 2 | 12 | 18 |
| `short_pressure_core` | 2 | 0 | 0 | 28 | 0 |

Source: `reports/calibration/detection_predicate_candidates_historical.json` (2026-08-17).

## Consequences

- Phase 3B research detection policy stays provisional but unchanged.
- Calibration reports must continue to emit `SMALL_SAMPLE_WARNING` and
  `COUNTERFACTUAL_EXPLORATION_ONLY`.
- Repeated BIYA boundaries are not independent observations (ADR-0054).
- Outcome labels do not establish short-squeeze causation.
- No variant in the historical calibration suite is authorized for automatic promotion
  to production policy.
- 28 of 30 case boundaries remain detection-unevaluable under baseline due to Batch 07
  price-level blocking on artifact-discovery symbols.

## Rejected alternatives

- Promoting `momentum_full` or `short_pressure_core` based on counterfactual results.
- Adopting `momentum_pct_change` because it resolves unevaluable cases as true negatives
  without improving detection on evaluable positives.
- Substituting live Finviz or current borrow data for historical gaps (ADR-0062).
- Treating calibration confusion matrices as predictive validation.

## Revision history

| Date | Change |
|------|--------|
| 2026-08-16 | Initial ADR at n=3 (TRVI, LBGJ, BIYA boundaries) |
| 2026-08-17 | Revised at n=30 after Phase 3F cohort expansion; supersedes exploratory n=3 findings |
