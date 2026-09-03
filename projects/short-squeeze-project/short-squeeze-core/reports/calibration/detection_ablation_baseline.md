# Phase 3D Calibration Report

- Experiment: `detection_ablation_baseline.v1`
- Type: `DETECTION_ABLATION`
- Cohort: `SYNTHETIC_CASES`
- Analysis unit: `CASE_BOUNDARY`
- Baseline: `baseline`

## Limitations

- **COUNTERFACTUAL_EXPLORATION_ONLY** — Calibration results are counterfactual explorations, not predictive validation.
- **NO_THRESHOLD_AUTO_PROMOTION** — No variant in this report is authorized for automatic promotion to production policy.
- **SMALL_SAMPLE_WARNING** — Small labeled cohorts limit interpretability; intervals do not repair representativeness.
- **OUTCOME_BLIND_BOUNDARY_SELECTION** — Boundary selection reuses Phase 3C outcome-blind cohort policies.

## Variant summary

### baseline

Current Phase 3B momentum discovery predicate (3 rules).

- Cases: 11
- Confusion matrix: TP=1 FP=1 TN=1 FN=1 unevaluable=7

### momentum_full

Require all six momentum discovery rules to pass.

- Cases: 11
- Confusion matrix: TP=0 FP=0 TN=1 FN=1 unevaluable=9
- Classification flips from baseline: 2
  - `SYN_FALSE_POSITIVE` (SYNFP): FALSE_POSITIVE → UNEVALUABLE
  - `SYN_TRUE_POSITIVE` (SYNTP): TRUE_POSITIVE → UNEVALUABLE

### short_pressure_core

Baseline momentum rules plus published SI availability.

- Cases: 11
- Confusion matrix: TP=0 FP=0 TN=1 FN=1 unevaluable=9
- Classification flips from baseline: 2
  - `SYN_FALSE_POSITIVE` (SYNFP): FALSE_POSITIVE → UNEVALUABLE
  - `SYN_TRUE_POSITIVE` (SYNTP): TRUE_POSITIVE → UNEVALUABLE

