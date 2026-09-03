# Model research and historical dataset guidance

Revision 3 is authoritative if this guidance conflicts with it. This file
defines future contracts and tests only. It authorizes no dataset acquisition,
model implementation, phase transition, provider connection, or trade.

## Dataset identity and immutable replay

A research dataset identity must bind at least:

- logical dataset ID, source/provider capability, source version, retrieval or
  receipt record, content hash, manifest hash, schema version, and row/partition
  bounds;
- projection and transformation versions, corrections/revisions, quality state,
  license/rights state, and creation procedure;
- explicit cache identity, maximum object and aggregate bytes, deterministic
  eviction/invalidation, and whether a cache miss is allowed to contact a source.

Raw evidence is immutable. Derived datasets point to raw members and transform
versions. A cache is disposable acceleration, never dataset identity. Offline
replay must not contact a network, mutate a source, fill unknown schema silently,
or select an inferred “latest” object.

## Point-in-time semantics

Each observation preserves the times applicable to its source, including:
`event_time`, publication/filing time, source observability, receipt time,
ingestion time, correction/revision time, and `available_at`. A training or
prediction cutoff admits only rows and metadata knowable by that cutoff.

Delayed filings stay delayed; corrections appear only when available; unknown
aggressor and unavailable fields remain explicit. Labels may occur after the
cutoff, but features and fitted preprocessing state may not cross it.

## Research abstractions

Future canonical interfaces should separate:

- `ResearchDatasetSpec` and immutable `ResearchDatasetManifest`;
- versioned `TargetSpec` with horizon, label construction, censoring, and
  availability rules;
- `FeatureViewSpec` with PIT joins and feature provenance;
- `PreprocessingSpec` with fit state scoped to each training fold;
- `ForecastModelSpec`, `FittedModelArtifact`, and `PredictionRecord`;
- `EvaluationRunManifest` with splits, cutoffs, seeds, runtime/dependency identity,
  baselines, metrics, exceptions, and artifact hashes.

Names require accepted ADRs; donor dataframes, API DTOs, database tables, and
model objects never become canonical semantics by accident.

## Preprocessing and future covariates

- Scaling, category maps, imputation, feature selection, variance filtering,
  and rank reduction fit on training rows only inside each fold.
- The serialized fit state is versioned and hash-bound to its training cutoff.
- A future covariate is allowed only if its value was known at forecast origin or
  comes from a separately identified forecast with its own provenance and cutoff.
- Realized holdout activity cannot be used as a future regressor. Missing or
  unavailable future covariates trigger an explicit fallback, abstention, or
  failure—not substitution with realized values.

## Model provenance and evaluation

Every fitted artifact binds code, dependencies, data/feature/target versions,
split schedule, random seed policy, hyperparameters, preprocessing state,
training cutoff, runtime, serialization format, and content hash. Reloaded
predictions must match the declared tolerance.

Start with naive and simple statistical baselines. Complexity must demonstrate
incremental value under the same PIT splits and costs. Report predictive metrics
such as error, discrimination, calibration, coverage, and stability separately
from strategy metrics such as turnover, exposure, drawdown, simulated costs, and
risk-adjusted return. A forecast is not a strategy; a strategy result is not an
execution result; neither is accounting.

## Required verification

### Dataset and cache

- exact schema/projection and optional-column capability tests;
- content/manifest hash, duplicate, corrupt, correction, and revision tests;
- immutable repeated reads and byte-identical offline replay;
- object/aggregate byte bounds, deterministic eviction, and invalidation;
- precision/downcast policy and no-network-on-replay tests.

### Model and PIT

- preprocessing cutoff and leakage-sentinel fixtures;
- feature/label availability and revised-data tests;
- missing covariate, explicit fallback, and abstention tests;
- deterministic seed and dependency-lock reproduction;
- walk-forward splits, naive baselines, calibration, and regime stability;
- serialization/reload equality and complete prediction provenance.

### Boundary

- model output cannot mutate strategy, risk, execution, portfolio, or accounting;
- AI explanations cite immutable evidence and cannot fabricate missing inputs;
- unsupported performance, participant identity, intent, or profitability claims
  fail review.
