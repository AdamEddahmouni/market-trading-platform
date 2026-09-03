# Baseline Prediction System V1 (BUILD 08)

> BUILD 08 converts immutable snapshot-bound `SignalV1` inputs into simple reproducible control forecasts represented as `ForecastV1`.

## Purpose

Future AI systems must demonstrate value above simple controls — not merely beat zero. BUILD 08 establishes permanent scientific floors (always-up, momentum, logistic regression, etc.) that later specialists must outperform on clean forward evidence.

## What BUILD 08 Is Not

| Concern | Owner |
|---|---|
| Calibration / fusion | BUILD 14 |
| Expert reasoning / LLM agents | BUILD 11+ |
| Model promotion / champion-challenger | BUILD 20 |
| Online learning | Deferred |
| Outcome adjudication | BUILD 15 |
| Evaluation dashboards | BUILD 16 |
| Training factory | BUILD 18 |
| Rigorous validation / holdouts | BUILD 19 |
| Model registry persistence | BUILD 23 |

## Architecture

```text
SnapshotV1 + SignalV1[]
        ↓
FeatureVectorBuilder (explicit schema, no EventV1 recalculation)
        ↓
BaselineModel.predict (read-only, no refit)
        ↓
ForecastV1 builder (identity excludes computed probability)
        ↓
IntelligenceRepository.put_forecast (optional orchestration)
```

Cross-links:

- [INTELLIGENCE_CONTRACTS_V1.md](./INTELLIGENCE_CONTRACTS_V1.md)
- [FEATURE_FAST_SIGNAL_LAYER_V1.md](./FEATURE_FAST_SIGNAL_LAYER_V1.md)
- [IMMUTABLE_SNAPSHOT_ENGINE_V1.md](./IMMUTABLE_SNAPSHOT_ENGINE_V1.md)
- [REPLAY_RUNTIME_V1.md](./REPLAY_RUNTIME_V1.md)
- [EVENT_DETECTOR_SMART_ROUTER_V1.md](./EVENT_DETECTOR_SMART_ROUTER_V1.md)

## Baseline Catalog

| Baseline | Training? | Features | Output | Version |
|---|---:|---|---|---|
| Always Up | No | none | UP, p_up=1.0 | `always-up/1` |
| Always Down | No | none | DOWN, p_up=0.0 | `always-down/1` |
| Fixed Prior | No | none | configured p_up | `fixed-prior/1` |
| Deterministic Random | No | none | hash-derived p_up | `deterministic-random/1` |
| Momentum | No | `momentum_simple@300s` | direction from sign; zero→abstain | `momentum/1` |
| Empirical Prior | Yes | none | training base rate | `empirical-prior/1` |
| Logistic Regression | Yes | default statistical schema | sklearn `predict_proba` (uncalibrated) | `logistic-regression/1` |
| Gradient Boosting | Yes | default statistical schema | sklearn GBM `predict_proba` | `gradient-boosting/1` |
| Regime Prior | Yes | external `regime_key` | conditional base rate | `regime-prior/1` |

All probabilistic outputs are **UNCALIBRATED** (`metadata.calibration_status = UNCALIBRATED`, `estimate.calibrated_probability = None`).

## Feature Schema

Default statistical schema (`DEFAULT_STATISTICAL_FEATURE_SCHEMA`):

| Selector | signal_type | window | calculator |
|---|---|---|---|
| spread_bps | spread_bps | point | spread-calculator v1 |
| net_signed_share | net_signed_share | 300s | cvd-calculator v1 |
| depth_imbalance | depth_imbalance | point | depth-imbalance-calculator v1 |
| momentum_simple | momentum_simple | 300s | momentum-calculator v1 |
| realized_vol | realized_vol | 300s | realized-volatility-calculator v1 |
| relative_volume | relative_volume | 300s | relative-volume-calculator v1 |

Rules:

- No auto feature discovery.
- Missing required feature → abstain (no zero imputation).
- Duplicate ambiguous matches → abstain.
- Signals must match `source_snapshot_ref → snapshot.snapshot_id`.

## Training Data

`BaselineTrainingExample` fields:

- `snapshot_id`, `decision_time_ns`
- `feature_vector` (from shared `FeatureVectorBuilder`)
- `label` (`UP` / `DOWN`)
- `label_available_time_ns`
- optional `regime_key`

**Anti-lookahead:** `label_available_time_ns <= training_cutoff_ns` (inclusive boundary). Future labels cause hard `BaselineTrainingError`.

Dataset fingerprint: `training-dataset-sha256-v1` over canonical sorted examples (order-independent).

## Model Identity

`model_id = BLMOD-{sha256}` from:

- model kind + implementation version
- feature schema fingerprint
- target spec
- training dataset fingerprint + cutoff (fitted models)
- hyperparameters + seed

Separate `parameter_fingerprint` (`BLPF-…`) captures learned coefficients/state where available.

## Forecast Identity

`forecast_id = BLFC-{sha256}` from:

- snapshot_id
- ordered source signal IDs
- model_id
- target + horizon
- `baseline-prediction-policy-v1`

**Computed probability is excluded** so same spec + different output triggers `RepositoryConflictError`.

## Abstention

Abstention returns `BaselinePredictionResult(status=ABSTAINED, forecast=None)` for:

- missing / duplicate / invalid features
- degraded features when disallowed
- model not fitted
- unsupported target
- unknown regime (when configured)
- momentum == 0
- invalid model output (no silent clamping)

## Live / Replay Parity

Identical `SnapshotV1`, `SignalV1[]`, model, and target produce identical `ForecastV1` in live-like and observed replay paths. Counterfactual replay reproduces deterministically for the same fault scenario.

## Regime Prior Limitation

Regime keys are caller-supplied. No regime engine exists in BUILD 08; live regime producer integration is deferred.

## Model Artifact Persistence

Fitting is reproducible from dataset fingerprint + config + version. Durable model registry is intentionally deferred (BUILD 23).

## BUILD Handoffs

- **BUILD 09:** May consume signals, quality, and baseline disagreement for routing; does not alter baseline semantics.
- **BUILD 14:** Consumes raw uncalibrated `ForecastV1` for calibration/fusion.
- **BUILD 15/16:** Uses forecast IDs/lineage for outcome settlement and baseline-vs-expert evaluation.

## Public API

```python
from market_platform_foundation.intelligence.baselines import (
    BaselinePredictionEngine,
    AlwaysUpBaseline,
    direction_up_down_target,
    persist_forecast,
)
```
