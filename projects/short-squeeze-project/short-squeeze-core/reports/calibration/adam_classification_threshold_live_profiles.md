# Adam Classification Threshold Calibration Report

- Experiment: `adam_classification_threshold_live_profiles.v1`
- Methodology: `adam_evidence_gated_prime.v1`
- Baseline variant: `baseline`

## Limitations

- **LIVE_METHODOLOGY_EXPLORATION_ONLY** — Adam calibration explores live methodology behavior on representative evidence profiles; it is not predictive validation.
- **NO_THRESHOLD_AUTO_PROMOTION** — No floor variant in this report is authorized for automatic promotion without human review.
- **SYNTHETIC_PROFILE_WARNING** — Profiles are synthetic admissible-evidence fixtures, not a labeled historical outcome cohort.
- **HISTORICAL_POLICY_SEPARATION** — Adam tuning does not change Phase 3B detection or outcome policies.

## Recommendation

- Action: **RETAIN_BASELINE**
- Baseline keeps `full_provider_prime` at PRIME.
- Baseline keeps `finviz_pressure_ignition_core` at SUBPRIME.
- Baseline keeps `watch_not_qualified` at NOT_QUALIFIED.
- Baseline keeps `subprime_pressure_led` at SUBPRIME.
- Baseline keeps `watch_mid` at WATCH.
- Reject `lower_high_coverage_65` — promotes Finviz core to PRIME without full provider coverage.
- PRIME requires HIGH coverage (85%+ weight); Finviz-only rows stay SUBPRIME until borrow/acceleration/catalyst legs arrive.

## Threshold variants

### baseline

- Evaluable profiles: 7
- Classification counts: {'PRIME': 2, 'SUBPRIME': 3, 'WATCH': 1, 'NOT_QUALIFIED': 1}
- Flips from baseline: 0

### lower_prime_65

- Evaluable profiles: 7
- Classification counts: {'PRIME': 2, 'SUBPRIME': 3, 'WATCH': 1, 'NOT_QUALIFIED': 1}
- Flips from baseline: 0

### raise_prime_75

- Evaluable profiles: 7
- Classification counts: {'PRIME': 1, 'SUBPRIME': 4, 'WATCH': 1, 'NOT_QUALIFIED': 1}
- Flips from baseline: 1
  - `prime_boundary_72`: PRIME → SUBPRIME

### lower_high_coverage_70

- Evaluable profiles: 7
- Classification counts: {'PRIME': 3, 'SUBPRIME': 2, 'WATCH': 1, 'NOT_QUALIFIED': 1}
- Flips from baseline: 1
  - `moderate_coverage_strong`: SUBPRIME → PRIME

### lower_high_coverage_65

- Evaluable profiles: 7
- Classification counts: {'PRIME': 4, 'SUBPRIME': 1, 'WATCH': 1, 'NOT_QUALIFIED': 1}
- Flips from baseline: 2
  - `finviz_pressure_ignition_core`: SUBPRIME → PRIME
  - `moderate_coverage_strong`: SUBPRIME → PRIME

### lower_watch_45

- Evaluable profiles: 7
- Classification counts: {'PRIME': 2, 'SUBPRIME': 3, 'WATCH': 1, 'NOT_QUALIFIED': 1}
- Flips from baseline: 0

