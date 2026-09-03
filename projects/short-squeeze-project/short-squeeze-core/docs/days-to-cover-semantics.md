# Days-to-Cover Metric Semantics

`metrics.days_to_cover` — `DAYS_TO_COVER_COMPONENTS`, `DAYS_TO_COVER`. See
[ADR 0036](adr/0036-days-to-cover-uses-explicit-daily-volume-baseline.md) for why the denominator
is a locally-computed trailing daily volume baseline, never the provider's own published figure.

## Formula

```
days_to_cover = published_short_interest_shares / trailing_mean_completed_daily_share_volume
```

Policy: `published_short_interest_divided_by_trailing_mean_completed_daily_share_volume.v1`
(shared by both `DAYS_TO_COVER_COMPONENTS` and `DAYS_TO_COVER` — one policy governs the whole
calculation).

**Interpretation.** A value of `2.5` means *2.5 average daily-volume periods under this
documented policy*, never a literal calendar-day forecast. It is a ratio of two exact,
independently-selected quantities, not a prediction.

## `DaysToCoverComponents` — the auditable breakdown

No scalar `value` field — every numerator/denominator assumption is a named field
(`metrics.pressure_models.DaysToCoverComponents`): `short_interest_provider`,
`short_interest_observation_id`, `short_interest_reporting_period`, `short_interest_value`,
`short_interest_source_age`, `volume_provider`, `volume_baseline_metric_id`,
`volume_baseline_value`, `volume_interval`, `volume_session_scope`, `volume_window`,
`volume_sample_counts`. `DAYS_TO_COVER` (a `PressureMetricResult`) references this breakdown via
`days_to_cover_components_id`.

## Numerator: published short interest

Resolved exactly like [`PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE`](short-interest-derived-metric-contract.md)
resolves either side of a comparison — one explicit `(symbol, short_interest_provider,
short_interest_reporting_period)`, point-in-time eligible, lifecycle-resolved
(`pressure_selection.resolve_short_interest_at_period`). `short_interest_value` is
`payload.short_shares` verbatim, in `SHARES`.

## Denominator: trailing daily volume baseline

- **Interval**: `BarInterval.ONE_DAY` only. Any other interval is rejected before resolution
  (`DAYS_TO_COVER_INCOMPATIBLE_VOLUME_INTERVAL`, `INVALID`) — intraday volume is never silently
  used.
- **Selection**: Phase 2A's `selection.resolve_trailing_window`, called with
  `target_start=as_of` directly (not via `volume_baselines.build_volume_baseline_result`, which
  requires a concrete target-bar boundary that days-to-cover has no analogue for — see ADR 0036).
  This still inherits every Phase 2A eligibility/lifecycle/provider guarantee: current/future-bar
  exclusion, missing-vs-zero-volume handling, corrected/cancelled-bar resolution, mixed-unit
  rejection.
- **Arithmetic**: Phase 2A's `volume_baselines.compute_mean_volume`, called directly (exact
  `Decimal`, `localcontext(prec=28)`) — the identical function, not a reimplementation.
- **Provider**: one explicit `volume_provider`, independent of `short_interest_provider`. The two
  provider roles are recorded as two separately-named fields and never coalesced.
- **`volume_sample_counts`**: `requested`/`eligible`/`used`/`missing`, identical shape to Phase
  2A's own `SampleCounts`. `used < minimum_samples` (including `used == 0`) is
  `DAYS_TO_COVER_VOLUME_BASELINE_UNAVAILABLE`, `UNAVAILABLE` — insufficient history is never `0`.
- **Zero baseline**: a computed mean of exactly `0` is `DAYS_TO_COVER_ZERO_VOLUME_BASELINE`,
  `INVALID` — division never proceeds.

An internal `MEAN_VOLUME_BASELINE` `MetricResult` (Phase 2A's own model) is constructed once from
this same resolution and referenced via `volume_baseline_metric_id`, so the denominator is always
a real, independently verifiable Phase 2A metric ID, not an opaque number.

## Age

`short_interest_source_age` (`SourceAgeMetadata`, ADR 0035) is always populated: a stale
numerator (large `reporting_period_age_days`) is still computable and still reported — age is
metadata, never a gate, never a fabricated freshness threshold.

## What this is not

Not short-float percentage. Not a provider-published "average volume" from a market snapshot —
`MarketSnapshotPayload.average_volume` is never read here. Not Phase 2A `MEAN_VOLUME_BASELINE`
reused as-is for a *different* target — the internal baseline construction is specific to `as_of`
and the requested window, computed once per `DAYS_TO_COVER` call. Not Phase 2B `RELATIVE_VOLUME`.
No squeeze-likelihood claim, no threshold, no score, no rank.
