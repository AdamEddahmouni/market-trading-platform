# Phase 3D Policy Recommendation Review

**Status:** COMPLETE  
**Date:** 2026-08-17  
**Cohort:** `HISTORICAL_COMPLETED_CASES` — 30 case boundaries, 28 unique symbols, 27 independent symbols (BIYA×2 dependent per ADR-0054)

This document records the human-reviewed policy recommendation after the historical
calibration cohort reached `min_case_count_for_recommendation: 30` in
`phase_3d_calibration_policy_v1.json`. It confirms or rejects counterfactual variants
from Phase 3D calibration — it does **not** auto-promote thresholds or claim
predictive validation (ADR-0065).

## Cohort summary

| Metric | Count |
|--------|------:|
| Unique historical symbols | 28 |
| Case boundaries | 30 (BIYA×2 + 28 artifact-discovery) |
| Evaluable outcome labels | 30 (all boundaries have Stage 2 forward-outcome bars) |
| Independent symbols | 27 |

Cohort built through Phase 3E Stage 2 (15 IBKR symbols) and Phase 3F cohort expansion
Batches 01–03 (13 additional symbols). See
[COHORT_EXPANSION_PROGRESS.md](COHORT_EXPANSION_PROGRESS.md) for acquisition details.

## Evidence artifacts

Calibration suite run: `python tools/run_calibration_suite.py`

| Report | Path |
|--------|------|
| Detection ablation (historical) | [`reports/calibration/detection_predicate_candidates_historical.md`](../../reports/calibration/detection_predicate_candidates_historical.md) |
| Detection ablation (historical JSON) | [`reports/calibration/detection_predicate_candidates_historical.json`](../../reports/calibration/detection_predicate_candidates_historical.json) |
| Outcome sensitivity (historical) | [`reports/calibration/outcome_sensitivity_historical.md`](../../reports/calibration/outcome_sensitivity_historical.md) |
| Outcome sensitivity (historical JSON) | [`reports/calibration/outcome_sensitivity_historical.json`](../../reports/calibration/outcome_sensitivity_historical.json) |
| Detection ablation (synthetic) | [`reports/calibration/detection_predicate_candidates_synthetic.md`](../../reports/calibration/detection_predicate_candidates_synthetic.md) |
| Outcome sensitivity (synthetic) | [`reports/calibration/outcome_sensitivity_synthetic.md`](../../reports/calibration/outcome_sensitivity_synthetic.md) |

## Detection policy recommendations

**Retain** `phase_3b_research_detection_policy.v1` unchanged:

- Required rules: `PRICE_RANGE`, `MARKET_DATA_AVAILABLE`, `COMPLETED_BAR_AVAILABLE`
- Governed by [ADR-0067](../adr/0067-phase-3b-detection-predicate-calibration-findings.md)

| Variant | Cases | Confusion matrix (baseline) | Flips from baseline | Recommendation |
|---------|------:|----------------------------|--------------------:|----------------|
| `baseline` | 30 | TP=2, unevaluable=28 | — | **Retain** |
| `momentum_pct_change` | 30 | TP=2, TN=16, unevaluable=12 | 16 (UNEVALUABLE→TN) | **Reject as gate** |
| `momentum_full` | 30 | FN=2, TN=16, unevaluable=12 | 18 (includes BIYA TP→FN) | **Reject** |
| `short_pressure_core` | 30 | TP=2, unevaluable=28 | 0 | **Reject** |

### Rationale

- **baseline:** Only BIYA boundaries (2 case boundaries) are detection-evaluable under the
  structural predicate. The remaining 28 artifact-discovery cases are UNEVALUABLE because
  Batch 07 price-level blocking prevents `PRICE_RANGE` evaluation. This is expected and
  honest — missing evidence is not fabricated (ADR-0061).
- **momentum_pct_change:** Resolves 16 artifact-discovery cases as TRUE_NEGATIVE by adding
  `PERCENTAGE_CHANGE_MINIMUM`, but provides no detection benefit (BIYA unchanged) and should
  not become a detection gate.
- **momentum_full:** Converts both BIYA true positives to false negatives because
  `FLOAT_MAXIMUM` stays unknown on incomplete float evidence. Also flips 16 UNEVALUABLE→TN.
  Harmful to the only evaluable positive cases.
- **short_pressure_core:** Zero classification flips, but gating on
  `PUBLISHED_SHORT_INTEREST_AVAILABLE` would block cases with honest missing SI evidence
  (ADR-0047). Peer symbols lack published short interest at historical boundaries.

## Outcome policy recommendations

**Retain** `phase_3b_outcome_label_policy.v1` unchanged:

- Reference price: `first_eligible_trade_bar_close_at_or_after_boundary.v1`
- Horizon: 24 hours
- Thresholds: ±25%
- Governed by [ADR-0068](../adr/0068-phase-3b-outcome-label-calibration-findings.md)

| Variant | Threshold | Flips from baseline | Recommendation |
|---------|-----------|--------------------:|----------------|
| `baseline` | ±25% | — | **Retain** |
| `upward_28` | +28% | 0 | No change (BIYA earliest at 28.34% is below flip point) |
| `upward_30` | +30% | 1 (BIYA earliest TP→FP) | **Reject** |
| `strict_35` | +35% | 2 (both BIYA boundaries TP→FP) | **Reject** |

### Rationale

- **baseline ±25%:** Both BIYA boundaries classify as TRUE_POSITIVE. Stable across the
  full n=30 cohort (28 cases remain outcome-unevaluable for detection classification).
- **upward_28:** BIYA earliest boundary max move is 28.34% — just below the 28% variant
  flip point. No classification changes.
- **upward_30 / strict_35:** Raising the upward threshold flips BIYA boundaries from
  substantial upward move to false positive, undermining the only evaluable positive
  outcome labels in the cohort.

## Explicit non-recommendations

- **Adam scoring calibration** (`adam_evidence_gated_prime.v1`) is complete on the live-screener
  track — retain 65% minimum dimension weight ([ADR 0069](../adr/0069-adam-evidence-gated-prime-calibration-findings.md))
  and baseline classification gates ([ADR 0070](../adr/0070-adam-classification-threshold-calibration-findings.md)).
  It is separate from this historical policy review.
- **No threshold auto-promotion.** Policies remain `provisional: true` per ADR-0065.
  This review records human-reviewed confirmation, not automatic promotion.
- **No predictive validation claims.** Calibration results are counterfactual explorations.

## Known limitations

1. **28/30 cases detection-unevaluable** under baseline due to Batch 07 price-level
   blocking and absent scanner field values on artifact-discovery symbols.
2. **BIYA boundaries are dependent** observations (ADR-0054) — only 27 independent
   symbols contribute to policy recommendation.
3. **Short-pressure evidence** (published SI, borrow) remains UNKNOWN for most
   historical IBKR symbols at their detection boundaries.
4. **Artifact-discovery provenance** is weaker than Batch 01 scanner rows for Phase 3F
   symbols discovered via archived platform logs.
5. **SMALL_SAMPLE_WARNING** continues to be emitted on all calibration reports by design,
   even at n=30, because representativeness limits persist for artifact-discovery cases.

## Governance references

- [ADR-0065: Phase 3D does not optimize prior policies](../adr/0065-phase-3d-does-not-optimize-prior-policies.md)
- [ADR-0067: Phase 3B detection-predicate calibration findings](../adr/0067-phase-3b-detection-predicate-calibration-findings.md)
- [ADR-0068: Phase 3B outcome-label calibration findings](../adr/0068-phase-3b-outcome-label-calibration-findings.md)
- [phase_3d_calibration_policy_v1.json](../../src/squeeze_core/calibration/policies/phase_3d_calibration_policy_v1.json)
