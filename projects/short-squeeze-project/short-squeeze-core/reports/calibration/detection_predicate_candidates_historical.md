# Phase 3D Calibration Report

- Experiment: `detection_predicate_candidates_historical.v1`
- Type: `DETECTION_ABLATION`
- Cohort: `HISTORICAL_COMPLETED_CASES`
- Analysis unit: `CASE_BOUNDARY`
- Baseline: `baseline`

## Limitations

- **COUNTERFACTUAL_EXPLORATION_ONLY** — Calibration results are counterfactual explorations, not predictive validation.
- **NO_THRESHOLD_AUTO_PROMOTION** — No variant in this report is authorized for automatic promotion to production policy.
- **SMALL_SAMPLE_WARNING** — Small labeled cohorts limit interpretability; intervals do not repair representativeness.
- **OUTCOME_BLIND_BOUNDARY_SELECTION** — Boundary selection reuses Phase 3C outcome-blind cohort policies.

## Variant summary

### baseline

Current Phase 3B structural momentum predicate (3 rules).

- Cases: 17
- Confusion matrix: TP=2 FP=0 TN=0 FN=0 unevaluable=15

### momentum_pct_change

Add PERCENTAGE_CHANGE_MINIMUM; tests whether metric availability changes BIYA detection.

- Cases: 17
- Confusion matrix: TP=2 FP=0 TN=9 FN=0 unevaluable=6
- Classification flips from baseline: 9
  - `AVTX_ARTIFACT_DISCOVERY` (AVTX): UNEVALUABLE → TRUE_NEGATIVE
  - `BHVN_ARTIFACT_DISCOVERY` (BHVN): UNEVALUABLE → TRUE_NEGATIVE
  - `GPRE_ARTIFACT_DISCOVERY` (GPRE): UNEVALUABLE → TRUE_NEGATIVE
  - `KLRS_ARTIFACT_DISCOVERY` (KLRS): UNEVALUABLE → TRUE_NEGATIVE
  - `LMNX_ARTIFACT_DISCOVERY` (LMNX): UNEVALUABLE → TRUE_NEGATIVE
  - `MGNX_ARTIFACT_DISCOVERY` (MGNX): UNEVALUABLE → TRUE_NEGATIVE
  - `OBE_ARTIFACT_DISCOVERY` (OBE): UNEVALUABLE → TRUE_NEGATIVE
  - `SG_ARTIFACT_DISCOVERY` (SG): UNEVALUABLE → TRUE_NEGATIVE
  - `ZNTL_ARTIFACT_DISCOVERY` (ZNTL): UNEVALUABLE → TRUE_NEGATIVE

### momentum_full

Require all six momentum discovery rules.

- Cases: 17
- Confusion matrix: TP=0 FP=0 TN=9 FN=2 unevaluable=6
- Classification flips from baseline: 11
  - `AVTX_ARTIFACT_DISCOVERY` (AVTX): UNEVALUABLE → TRUE_NEGATIVE
  - `BHVN_ARTIFACT_DISCOVERY` (BHVN): UNEVALUABLE → TRUE_NEGATIVE
  - `BIYA_EARLIEST_BOUNDARY` (BIYA): TRUE_POSITIVE → FALSE_NEGATIVE
  - `BIYA_LATEST_BOUNDARY` (BIYA): TRUE_POSITIVE → FALSE_NEGATIVE
  - `GPRE_ARTIFACT_DISCOVERY` (GPRE): UNEVALUABLE → TRUE_NEGATIVE
  - `KLRS_ARTIFACT_DISCOVERY` (KLRS): UNEVALUABLE → TRUE_NEGATIVE
  - `LMNX_ARTIFACT_DISCOVERY` (LMNX): UNEVALUABLE → TRUE_NEGATIVE
  - `MGNX_ARTIFACT_DISCOVERY` (MGNX): UNEVALUABLE → TRUE_NEGATIVE
  - `OBE_ARTIFACT_DISCOVERY` (OBE): UNEVALUABLE → TRUE_NEGATIVE
  - `SG_ARTIFACT_DISCOVERY` (SG): UNEVALUABLE → TRUE_NEGATIVE
  - `ZNTL_ARTIFACT_DISCOVERY` (ZNTL): UNEVALUABLE → TRUE_NEGATIVE

### short_pressure_core

Baseline plus PUBLISHED_SHORT_INTEREST_AVAILABLE.

- Cases: 17
- Confusion matrix: TP=2 FP=0 TN=0 FN=0 unevaluable=15
- Classification flips from baseline: 0

