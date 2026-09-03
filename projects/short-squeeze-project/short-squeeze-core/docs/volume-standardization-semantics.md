# Volume Standardization Semantics

`metrics.volume_standardization` — `VOLUME_Z_SCORE`. See
[`normalized-market-activity-contract.md`](normalized-market-activity-contract.md) for common
fields and [ADR 0033](adr/0033-decimal-population-standard-deviation.md) for the standard-deviation
policy.

## Formula

```
volume_z_score = (target_volume - baseline_mean) / baseline_standard_deviation
```

where `baseline_mean`/`baseline_standard_deviation` come from a `BaselineStatistics(baseline_kind=
VOLUME)` built over an explicit trailing `BAR_COUNT` window.

## Policy: `volume_distribution_z_score.v1` (result) / `trailing_bar_count_exclude_current.v1` (baseline)

- **Distribution**: `selection.resolve_trailing_window` — the same selector
  `MEAN_VOLUME_BASELINE` uses — supplies the eligible, lifecycle-resolved, current-bar-excluded
  sample set; `volume_baselines.compute_mean_volume` computes the mean; population variance/
  standard deviation (ADR 0033) are computed on top via `metrics.statistics`.
- **Minimum samples**: caller-specified (`TrailingWindow.minimum_samples`), no implicit default;
  the handoff's recommended floor is 2. Below it: `VOLUME_DISTRIBUTION_INSUFFICIENT_SAMPLES`,
  `UNAVAILABLE`. Zero samples: `VOLUME_DISTRIBUTION_WINDOW_EMPTY`.
- **Zero-volume samples**: retained as valid `0` samples (`METRIC_ZERO_VOLUME_SAMPLE`, reused).
- **Missing-volume samples**: excluded and counted separately, never treated as `0`
  (`METRIC_MISSING_VOLUME`, reused).
- **Zero variance**: the `BaselineStatistics` itself is still `KNOWN_VALUE` with
  `standard_deviation=0` — a valid statistic. Only the *z-score* (which divides by it) becomes
  `INVALID` with `NORMALIZED_METRIC_ZERO_VARIANCE` + `VOLUME_DISTRIBUTION_ZERO_VARIANCE`.
- **Target exclusion**: the target/current bar is always excluded from its own distribution (ADR
  0034).
- **Provider/session/interval/unit compatibility**: identical to `RELATIVE_VOLUME` — see
  `docs/relative-volume-semantics.md` and `docs/phase-2b-design.md` §10.
- **Arithmetic**: exact `Decimal`, `localcontext(prec=50)` (`metrics.statistics.
  DECIMAL_STATISTICS_PRECISION`), `Decimal.sqrt()` for the standard deviation, no `float` anywhere.

## What this is not

Not "high"/"low"/"extreme" volume, not an alert threshold. A z-score of 6.9 states a fact about
distance from the mean in standard-deviation units and nothing else — see ADR 0032.
