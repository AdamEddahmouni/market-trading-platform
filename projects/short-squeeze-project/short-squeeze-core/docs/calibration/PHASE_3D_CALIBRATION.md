# Phase 3D Evidence Calibration

Counterfactual policy experiments for short-squeeze research rules. This layer
explores **what would change** if detection or outcome policies differed — it does
not authorize threshold promotion or predictive claims.

## Quick start

Run the full evidence-optimal suite (outcome sensitivity first, then detection predicates):

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/run_calibration_suite.py
```

Or run a single experiment:

```powershell
python tools/run_calibration_experiment.py `
  --experiment tests/fixtures/calibration/outcome_sensitivity_synthetic.json `
  --output reports/calibration/outcome_sensitivity_synthetic.json
```

Outputs JSON + Markdown side-by-side.

## Experiment fixtures

| Fixture | Type | Cohort | Purpose |
|---------|------|--------|---------|
| `outcome_sensitivity_synthetic.json` | OUTCOME_SENSITIVITY | Synthetic | ±25/30/35% threshold sweep |
| `outcome_sensitivity_historical.json` | OUTCOME_SENSITIVITY | Historical | BIYA boundary threshold sensitivity |
| `detection_predicate_candidates_synthetic.json` | DETECTION_ABLATION | Synthetic | Predicate variants + negative control |
| `detection_predicate_candidates_historical.json` | DETECTION_ABLATION | Historical | BIYA predicate evaluability |
| `detection_ablation_baseline.json` | DETECTION_ABLATION | Synthetic | Original 3-variant ablation |

## Experiment types

| Type | Varies | Uses stored |
|------|--------|-------------|
| `DETECTION_ABLATION` | `required_rule_ids` | Phase 3A rule outcomes |
| `OUTCOME_SENSITIVITY` | outcome thresholds | move observations |

## Cohorts

- `SYNTHETIC_CASES` — 11 software-validation edge cases
- `HISTORICAL_COMPLETED_CASES` — sanitized public historical (**n=28** IBKR symbols with Stage 2 forward-outcome bars, **30** case boundaries including BIYA×2). All artifact-discovery symbols now have evaluable outcome labels from Phase 3E/3F Stage 2; `min_case_count_for_recommendation: 30` is met.

Detection-policy findings from the expanded cohort are governed in
[ADR 0067](../adr/0067-phase-3b-detection-predicate-calibration-findings.md).
Outcome-policy findings are governed in
[ADR 0068](../adr/0068-phase-3b-outcome-label-calibration-findings.md).

Adam scoring calibration (live screener track) is documented in
[ADAM_SCORING_CALIBRATION_REVIEW.md](ADAM_SCORING_CALIBRATION_REVIEW.md) and
[ADR 0069](../adr/0069-adam-evidence-gated-prime-calibration-findings.md).

Classification threshold calibration is documented in
[ADAM_CLASSIFICATION_THRESHOLD_CALIBRATION_REVIEW.md](ADAM_CLASSIFICATION_THRESHOLD_CALIBRATION_REVIEW.md) and
[ADR 0070](../adr/0070-adam-classification-threshold-calibration-findings.md).

```powershell
python tools/run_adam_calibration.py
python tools/run_adam_calibration.py --mode classification-thresholds
# or: python tools/run_adam_threshold_calibration.py
```

## Policy recommendation review

The n=30 threshold was met on 2026-08-17 after Phase 3F cohort expansion. The formal
review confirms baseline detection and outcome policies remain unchanged:

- [PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md](PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md) — full review record
- Detection: retain `phase_3b_research_detection_policy.v1` (reject all tested variants)
- Outcome: retain `phase_3b_outcome_label_policy.v1` at ±25%/24h (reject threshold raises)
- Policies remain `provisional: true` per ADR-0065 — review records confirmation, not auto-promotion

## Governance

See `src/squeeze_core/calibration/policies/phase_3d_calibration_policy_v1.json`.
Phase 3C remains descriptive-only; Phase 3D is explicitly counterfactual.

Research dataset metric rules (`PERCENTAGE_CHANGE_MINIMUM`, `RELATIVE_VOLUME_MINIMUM`,
`FLOAT_MAXIMUM`, `PUBLISHED_SHORT_INTEREST_AVAILABLE`) are populated from frozen Phase 3A
evaluations. Synthetic cases use live evaluation with explicit metric evidence; BIYA
historical cases compute momentum metrics from real bar history (ADR 0061: float and short
interest remain UNKNOWN until acquired).

## Design spec

[2026-08-16-phase-3d-calibration-design.md](../superpowers/specs/2026-08-16-phase-3d-calibration-design.md)
