# Phase 3D Calibration Report

- Experiment: `outcome_sensitivity_historical.v1`
- Type: `OUTCOME_SENSITIVITY`
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

Current Phase 3B outcome label policy (±25% over 24 hours).

- Cases: 31
- Confusion matrix: TP=2 FP=0 TN=0 FN=0 unevaluable=29

### upward_28

Raise upward threshold to 28%; BIYA earliest boundary (28.34% max) is near the flip point.

- Cases: 31
- Confusion matrix: TP=2 FP=0 TN=0 FN=0 unevaluable=29
- Classification flips from baseline: 0

### upward_30

Raise upward threshold to 30%; BIYA earliest boundary (28.34%) flips to no substantial move.

- Cases: 31
- Confusion matrix: TP=1 FP=1 TN=0 FN=0 unevaluable=29
- Classification flips from baseline: 1
  - `BIYA_EARLIEST_BOUNDARY` (BIYA): TRUE_POSITIVE → FALSE_POSITIVE

### strict_35

Raise upward threshold to 35%; both BIYA boundaries flip (31.68% latest still below 35%).

- Cases: 31
- Confusion matrix: TP=0 FP=2 TN=0 FN=0 unevaluable=29
- Classification flips from baseline: 2
  - `BIYA_EARLIEST_BOUNDARY` (BIYA): TRUE_POSITIVE → FALSE_POSITIVE
  - `BIYA_LATEST_BOUNDARY` (BIYA): TRUE_POSITIVE → FALSE_POSITIVE

