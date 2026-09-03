# Phase 3D Calibration Report

- Experiment: `outcome_sensitivity_synthetic.v1`
- Type: `OUTCOME_SENSITIVITY`
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

Current Phase 3B outcome label policy (±25% over 24 hours).

- Cases: 11
- Confusion matrix: TP=1 FP=1 TN=1 FN=1 unevaluable=7

### symmetric_30

Stricter symmetric ±30% thresholds; synthetic cases at exactly 25% flip to no substantial move.

- Cases: 11
- Confusion matrix: TP=0 FP=4 TN=2 FN=0 unevaluable=5
- Classification flips from baseline: 4
  - `SYN_FALSE_NEGATIVE` (SYNFN): FALSE_NEGATIVE → TRUE_NEGATIVE
  - `SYN_MIXED_VOLATILE` (SYNMIX): UNEVALUABLE → FALSE_POSITIVE
  - `SYN_SUBSTANTIAL_DOWNWARD` (SYNDOWN): UNEVALUABLE → FALSE_POSITIVE
  - `SYN_TRUE_POSITIVE` (SYNTP): TRUE_POSITIVE → FALSE_POSITIVE

### strict_35

Stricter symmetric ±35% thresholds for boundary stress testing.

- Cases: 11
- Confusion matrix: TP=0 FP=4 TN=2 FN=0 unevaluable=5
- Classification flips from baseline: 4
  - `SYN_FALSE_NEGATIVE` (SYNFN): FALSE_NEGATIVE → TRUE_NEGATIVE
  - `SYN_MIXED_VOLATILE` (SYNMIX): UNEVALUABLE → FALSE_POSITIVE
  - `SYN_SUBSTANTIAL_DOWNWARD` (SYNDOWN): UNEVALUABLE → FALSE_POSITIVE
  - `SYN_TRUE_POSITIVE` (SYNTP): TRUE_POSITIVE → FALSE_POSITIVE

