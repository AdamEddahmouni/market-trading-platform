# Adam Scoring Calibration Report

- Experiment: `adam_weight_floor_live_profiles.v1`
- Methodology: `adam_evidence_gated_prime.v1`
- Baseline floor: `65%`

## Limitations

- **LIVE_METHODOLOGY_EXPLORATION_ONLY** — Adam calibration explores live methodology behavior on representative evidence profiles; it is not predictive validation.
- **NO_THRESHOLD_AUTO_PROMOTION** — No floor variant in this report is authorized for automatic promotion without human review.
- **SYNTHETIC_PROFILE_WARNING** — Profiles are synthetic admissible-evidence fixtures, not a labeled historical outcome cohort.
- **HISTORICAL_POLICY_SEPARATION** — Adam tuning does not change Phase 3B detection or outcome policies.

## Recommendation

- Action: **RETAIN_BASELINE**
- Finviz Elite core profile (SI + DTC + float + change + relvol) stays evaluable at the 65% floor.
- pressure_si_dtc_only remains UNEVALUABLE at baseline (55% pressure weight without float).
- Lowering to 50% flips 1 profile classification(s) (e.g. partial pressure without float becomes SUBPRIME).
- Lowering to 55% flips 1 profile classification(s) (e.g. partial pressure without float becomes SUBPRIME).
- Raising to 70% blocks the Finviz core profile (supported weight is exactly 65%).

## Floor variants

### 50% minimum dimension weight

- Evaluable profiles: 4
- Classification counts: {'SUBPRIME': 2, 'PRIME': 1, 'UNEVALUABLE': 1, 'NOT_QUALIFIED': 1, 'CONFLICTED': 1}
- Flips from baseline: 1
  - `pressure_si_dtc_only`: UNEVALUABLE → SUBPRIME

### 55% minimum dimension weight

- Evaluable profiles: 4
- Classification counts: {'SUBPRIME': 2, 'PRIME': 1, 'UNEVALUABLE': 1, 'NOT_QUALIFIED': 1, 'CONFLICTED': 1}
- Flips from baseline: 1
  - `pressure_si_dtc_only`: UNEVALUABLE → SUBPRIME

### 60% minimum dimension weight

- Evaluable profiles: 3
- Classification counts: {'SUBPRIME': 1, 'UNEVALUABLE': 2, 'PRIME': 1, 'NOT_QUALIFIED': 1, 'CONFLICTED': 1}
- Flips from baseline: 0

### 65% minimum dimension weight

- Evaluable profiles: 3
- Classification counts: {'SUBPRIME': 1, 'UNEVALUABLE': 2, 'PRIME': 1, 'NOT_QUALIFIED': 1, 'CONFLICTED': 1}
- Flips from baseline: 0

### 70% minimum dimension weight

- Evaluable profiles: 1
- Classification counts: {'UNEVALUABLE': 4, 'PRIME': 1, 'CONFLICTED': 1}
- Flips from baseline: 2
  - `finviz_pressure_ignition_core`: SUBPRIME → UNEVALUABLE
  - `watch_not_qualified`: NOT_QUALIFIED → UNEVALUABLE

