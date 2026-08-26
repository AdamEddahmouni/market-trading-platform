# Evaluation, Calibration Diagnostics & Error Analysis (BUILD 16)

BUILD 16 measures immutable `ForecastV1`, `PredictionLedgerEntryV1`, and `OutcomeV1`
artifacts. It does not settle outcomes, fit calibrators, train models, or promote champions.

## Evaluation-as-of semantics

Every repository-backed evaluation requires explicit `evaluation_as_of_ns`. A settled label
is eligible for predictive metrics only when:

```text
label_available_time_ns <= evaluation_as_of_ns
```

Equality at the cutoff is eligible. `adjudicated_at_ns` is operational settlement timing,
not scientific label availability.

## Immutable inputs

- `ForecastV1` — prediction probabilities and metadata are never mutated.
- `PredictionLedgerEntryV1` — frozen settlement specification.
- `OutcomeV1` — settled result authority from BUILD 15.

## Cohort eligibility

Cohort rows bind forecast, ledger entry, and outcome via exact `forecast_id` and derived
`outcome_id`. No nearest-timestamp joins. Mode and scenario are part of evaluation identity.

Decision range uses half-open semantics:

```text
decision_start_ns <= forecast_decision_time_ns < decision_end_ns
```

## Settlement coverage

```text
settlement_coverage = outcome_available_count / registered_count
labelable_fraction = labelable_count / outcome_available_count
```

Unlabelable outcomes (`ZERO_RETURN`, `UNLABELABLE_NO_REFERENCE_PRICE`, etc.) count in
settlement diagnostics but not in Brier, log-loss, or directional-hit denominators.

## True prediction coverage

No durable immutable opportunity/abstention denominator exists in BUILD 01–15 artifacts.
Reports emit `TRUE_PREDICTION_COVERAGE_UNAVAILABLE`. Settlement coverage is not prediction
coverage.

## Metrics

- **Brier**: `mean((p - y)^2)` with per-row contributions preserved.
- **Log loss**: `-(y ln p + (1-y) ln(1-p))` with metric-local epsilon clipping.
- **Directional hit rate**: uses persisted predicted direction when available; `p >= 0.5` ⇒ UP.
- **Confidence**: `max(p, 1 - p)` — descriptive only.

Epsilon clipping applies only inside metric computation; `ForecastV1` remains unchanged.

## Calibration diagnostics

Reliability bins (default 10 equal-width), ECE, MCE, and optional Brier decomposition are
computed diagnostically. No calibrator fitting (`IsotonicRegression`, Platt, temperature scaling).

## Probability views

- **RAW** — `estimate.probability`
- **CALIBRATED** — `estimate.calibrated_probability` when present (no silent substitution)
- **OPERATIONAL** — calibrated for final fused forecasts when present, otherwise raw

## Error taxonomy

Primary states: `CORRECT`, `FALSE_UP`, `FALSE_DOWN`, `UNLABELABLE`, `NOT_SETTLED`,
`FUTURE_LABEL`. Orthogonal flags include `HIGH_CONFIDENCE`, `LOW_CONFIDENCE`,
`DEGRADED_QUALITY`, `BOUNDARY_PROBABILITY`, `OOD`.

## Control comparison

Matched candidate/control pairs use deterministic keys:

```text
snapshot_id, instrument_id, target_kind, horizon_ns, mode, scenario_id
```

Unmatched aggregates are not head-to-head evidence. No significance claims.

## Identity and reproducibility

- `EvaluationSpec` → `evaluation_spec_id` (SHA-256)
- Frozen cohort → `cohort_fingerprint`
- Report ID = spec ID + cohort fingerprint + implementation version

Same spec and immutable inputs at the same evaluation-as-of reproduce identical reports.
Fixed-as-of evaluations are invariant to later inserts.

## Persistence

Immutable `EvaluationReportV1` records may be stored in `evaluation_reports` (no TTL).

## Handoffs

- **BUILD 17** — consumes error cohorts, rankings, slices, and paired comparisons without
  re-adjudicating outcomes.
- **BUILD 19** — formal temporal validation, purge/embargo, holdouts (not provided here).
- **BUILD 20** — champion/challenger promotion using independently validated metrics.

## No strategy PnL

Realized return from `OutcomeV1` is descriptive market movement, not strategy PnL.
