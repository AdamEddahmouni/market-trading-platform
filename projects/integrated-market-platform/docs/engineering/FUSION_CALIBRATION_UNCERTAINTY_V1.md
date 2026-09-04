# Fusion, Calibration & Uncertainty (BUILD 14)

**Generated:** 2026-08-25

BUILD 14 combines explicit probabilistic forecast contributors using dependency-aware static fusion, calibrates the raw fused probability only with temporally legal pre-existing calibration artifacts, measures structured uncertainty/OOD/coverage, and emits a final `ForecastV1` only when policy permits.

## Current production limitation

Current production has no eligible production probabilistic specialist contributor. BUILD 08 forecasts remain controls (`contributor_role=CONTROL`, `forecast_stage=CONTROL_RAW`). Therefore BUILD 14 currently abstains in the default production path rather than manufacturing a final forecast. This is not a bug.

## Control vs production contributors

| Role | Default source | Production fusion |
|------|----------------|-------------------|
| `CONTROL` | BUILD 08 baselines | Excluded by default |
| `PRODUCTION` | Future specialist forecasts | Eligible when explicitly tagged |
| `RESEARCH` | Diagnostic/test only | Only in explicit research policy |

## Sealed fusion manifest

`ForecastFusionManifest` freezes the exact contributor set. Late `ForecastV1` records cannot retroactively enter an existing manifest.

## Compatibility

Contributors must match on:

- target
- horizon
- snapshot
- decision time
- scope/instrument

## Dependence grouping

Forecasts are dependency-connected when they share:

- the same `forecast_family_key`, or
- explicit terminal source lineage overlap (signals, evidence, hypotheses)

Connected components form dependence groups. Different forecast IDs are not assumed independent.

## False consensus protection

Example: three correlated clones at `p=0.9` plus one independent model at `p=0.2`.

**Within-group pool:**

\[
p_g = \frac{\sum_i w_i p_i}{\sum_i w_i}
\]

**Across-group pool (default equal group weights):**

\[
p_{raw} = \frac{1}{G}\sum_g p_g
\]

For the example: group A = 0.9, group B = 0.2 → `p_raw = 0.55`, not 0.73.

## Static weights

Contributor and group weights are configured in `FusionPolicy`. They are not learned from outcomes.

## Hypothesis boundary

`HypothesisV1` may appear as manifest context/lineage. It does not numerically change fused probability under default policy.

## Calibration temporal firewall

| Rule | Constraint |
|------|------------|
| Label availability | `label_available_time_ns > forecast_decision_time_ns` |
| Horizon completion | `label_available_time_ns >= forecast_decision_time_ns + horizon_ns` |
| Calibration cutoff | `label_available_time_ns <= calibration_cutoff_ns` |
| Artifact availability | `calibration_model.available_time_ns <= forecast_decision_time_ns` |

Example: training cutoff 10:00, calibrator created 10:05, forecast decision 10:03 → calibrator illegal.

## Calibration methods

- `LOGISTIC_PROBABILITY` — sklearn logistic regression on raw fused probability
- `ISOTONIC` — isotonic regression with `out_of_bounds=raise`
- `IDENTITY_CONTROL` — no-op control, status `IDENTITY_CONTROL`

No pickle/joblib artifact loading. Parameters are deterministic serializable data.

## Raw vs calibrated probability

Final `ForecastV1` stores:

- `estimate.probability` — raw fused probability
- `estimate.calibrated_probability` — calibrated value

Raw probability is never overwritten.

## Uncertainty

- **Predictive entropy** — Bernoulli entropy; not empirical forecast error probability
- **Inter-group dispersion** — model-disagreement diagnostic; not a calibrated epistemic posterior
- **One independent group** — dispersion `None`, epistemic state `UNKNOWN`

## OOD

`CALIBRATION_RANGE_OOD` when raw fused probability falls outside the calibrator training range. Default production policy abstains when `fail_on_calibration_ood=True`.

## Abstention

Abstention emits no operational `ForecastV1`. Missing contributors/calibration never become `p=0.5`.

## Related documents

- [Baseline Prediction System](BASELINE_PREDICTION_SYSTEM_V1.md)
- [Expert Blackboard / Blind Council](EXPERT_BLACKBOARD_BLIND_COUNCIL_V1.md)
- [Composite Hypothesis Engine](COMPOSITE_HYPOTHESIS_ENGINE_V1.md)
- [Immutable Snapshot Engine](IMMUTABLE_SNAPSHOT_ENGINE_V1.md)

## BUILD 15 handoff

Final `ForecastV1` records now include stable ID, target, horizon, decision time, raw/calibrated probabilities, contributor lineage, fusion/calibration receipts, and uncertainty/OOD state for outcome settlement without mutating forecast semantics.

## BUILD 16 handoff

BUILD 16 can compute Brier, log loss, calibration curves, coverage/selectivity, and baseline-vs-final comparisons from settled forecasts without changing BUILD 14 semantics.
