# Normalized Market-Activity Contract (Phase 2B)

Fields and conventions common to every Phase 2B metric. See
[`foundational-market-metric-contract.md`](foundational-market-metric-contract.md) for the Phase 2A
contract this one extends by composition, not by modifying `MetricResult`. `NormalizedMetricResult`
and `BaselineStatistics`, documented below, are unchanged by Phase 2C in every field and byte —
Phase 2C's own result models (`PressureMetricResult`/`DaysToCoverComponents`) are a third,
independent standalone model family; see
[`short-interest-derived-metric-contract.md`](short-interest-derived-metric-contract.md).

## Result models

Two new, standalone, frozen Pydantic models in `metrics/normalized_models.py`:

- **`NormalizedMetricResult`** — the result of `RELATIVE_VOLUME`, `VOLUME_PERCENT_DEVIATION`,
  `VOLUME_Z_SCORE`, `MEAN_PERCENTAGE_RETURN_BASELINE`,
  `PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE`, and `PERCENTAGE_RETURN_Z_SCORE`. Same shape as
  Phase 2A's `MetricResult` (`metric_name`, `metric_version`, `calculation_policy_version`,
  `symbol`, `asset_class`, `as_of`, `source_interval`, `session_scope`, `provider_scope`,
  `provider`, `price_field`, `window`, `value`, `unit`, `input_observation_ids`,
  `input_bar_boundaries`, `sample_counts`, `quality`, `diagnostics`, `deterministic_id`) plus four
  Phase 2B-specific fields: `standard_deviation_policy`, `target_boundary`, `baseline_metric_id`,
  `input_metric_ids`.
- **`BaselineStatistics`** — the internal distribution a `VOLUME_Z_SCORE` or return-baseline metric
  standardizes against: `baseline_kind` (`VOLUME` or `PERCENTAGE_RETURN`), `mean`, `variance`,
  `standard_deviation`, `sample_counts`, plus the same scope/provenance fields.

Neither model touches `MetricResult` or any Phase 2A field — see ADR 0032 and
`docs/phase-2b-design.md` §2 for why (`canonicalize()` serializes every field regardless of
default, so any addition to `MetricResult` would change every Phase 2A anchor's bytes).

## Identity and versioning

Every Phase 2B metric carries `metric_version="1.0.0"` (first release), a
`calculation_policy_version` naming its selection policy (e.g. `trailing_mean_ratio.v1`,
`volume_distribution_z_score.v1`, `adjacent_close_to_close_return_count.v1`,
`return_distribution_z_score.v1`), and — new to Phase 2B — `standard_deviation_policy` (`None` for
the three metrics that never divide by a standard deviation). `deterministic_id` is a UUIDv5 under
the same `METRIC_NAMESPACE` Phase 2A defines, hashing every field that affects the result except
`value`/`diagnostics`/the ID itself (`normalized_metric_identity()` / `baseline_identity()` in
`metrics/normalized_identifiers.py`).

## Units

Two new `MetricUnit` members: `RATIO` (`RELATIVE_VOLUME`) and `STANDARD_DEVIATIONS`
(`VOLUME_Z_SCORE`, `PERCENTAGE_RETURN_Z_SCORE`). `VOLUME_PERCENT_DEVIATION` reuses `PERCENT`;
`MEAN_PERCENTAGE_RETURN_BASELINE`/`PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE` reuse `PERCENT`.

## Selection: composition, not reimplementation

No Phase 2B module reimplements point-in-time eligibility, lifecycle resolution, or
provider-ambiguity handling. Every builder composes Phase 2A's own functions:
`selection.resolve_bar_at_boundary`, `selection.resolve_trailing_window`,
`volume_baselines.build_volume_baseline_result`, `volume_baselines.compute_mean_volume`,
`returns.build_return_result`, `returns.compute_percentage_return`. See
`docs/phase-2b-design.md` §6 for the full mapping.

## Target exclusion (ADR 0034)

Every baseline/distribution excludes its own target by construction — see ADR 0034. There is no
Phase 2B request shape that can re-include a target in its own baseline.

## Standard-deviation policy (ADR 0033)

`population_standard_deviation_decimal.v1` — exact `Decimal`, local `localcontext(prec=50)`,
`Decimal.sqrt()`. No `float`, no `numpy`/`scipy`/`statistics`-module call anywhere in `metrics/`.

## Zero, missing, and insufficient-history semantics

See `docs/phase-2b-design.md` §9 for the full table. Summary: missing is never zero; a zero target
volume or zero mean return is a valid `KNOWN_VALUE`; a zero baseline mean or zero baseline standard
deviation makes the *dependent* division `INVALID`, not the baseline itself; insufficient history
is `UNAVAILABLE`, never a silently-neutral value.

## What Phase 2B is not

Not a score, not a rank, not a recommendation, not a threshold classification, not a technical
indicator. See ADR 0032 and the exclusion list in `docs/phase-2b-design.md` §20.
