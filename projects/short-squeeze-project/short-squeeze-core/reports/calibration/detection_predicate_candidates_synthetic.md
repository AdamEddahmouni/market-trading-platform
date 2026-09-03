# Phase 3D Calibration Report

- Experiment: `detection_predicate_candidates_synthetic.v1`
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

Current Phase 3B structural momentum predicate (3 rules).

- Cases: 11
- Confusion matrix: TP=1 FP=1 TN=1 FN=1 unevaluable=7

### two_rule_minimal

Negative control: drop PRICE_RANGE gate; shows false detection on true negatives.

- Cases: 11
- Confusion matrix: TP=4 FP=2 TN=0 FN=0 unevaluable=5
- Classification flips from baseline: 4
  - `SYN_FALSE_NEGATIVE` (SYNFN): FALSE_NEGATIVE → TRUE_POSITIVE
  - `SYN_TRUE_NEGATIVE` (SYNTN): TRUE_NEGATIVE → FALSE_POSITIVE
  - `SYN_UNEVALUABLE_CONFLICTED` (SYNCFL): UNEVALUABLE → TRUE_POSITIVE
  - `SYN_UNEVALUABLE_INSUFFICIENT` (SYNINS): UNEVALUABLE → TRUE_POSITIVE

### momentum_pct_change

Add PERCENTAGE_CHANGE_MINIMUM; tests evaluability cost when metric rules are UNKNOWN.

- Cases: 11
- Confusion matrix: TP=1 FP=0 TN=2 FN=1 unevaluable=7
- Classification flips from baseline: 1
  - `SYN_FALSE_POSITIVE` (SYNFP): FALSE_POSITIVE → TRUE_NEGATIVE

### momentum_full

Require all six momentum discovery rules; collapses evaluability when metrics are UNKNOWN.

- Cases: 11
- Confusion matrix: TP=1 FP=0 TN=2 FN=1 unevaluable=7
- Classification flips from baseline: 1
  - `SYN_FALSE_POSITIVE` (SYNFP): FALSE_POSITIVE → TRUE_NEGATIVE

### short_pressure_core

Baseline plus PUBLISHED_SHORT_INTEREST_AVAILABLE; tests short-pressure dependency.

- Cases: 11
- Confusion matrix: TP=1 FP=1 TN=1 FN=1 unevaluable=7
- Classification flips from baseline: 0

