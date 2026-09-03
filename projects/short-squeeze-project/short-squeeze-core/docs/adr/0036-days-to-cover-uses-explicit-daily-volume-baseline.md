# ADR 0036: Days to Cover Uses an Explicit Daily Volume Baseline

## Context

The inherited `core/short_interest.py::calculate_days_to_cover(shares_short,
average_daily_volume)` is a null-safe, denominator-validated formula shape
(`shares_short / average_daily_volume`, returning `(None, reason)` rather than coercing to
zero) — but the module itself never defines where `average_daily_volume` comes from: no window,
no provider, no point-in-time eligibility. Separately, `PublishedShortInterestPayload.days_to_cover`
already carries the *provider's own* published days-to-cover figure, preserved verbatim per
`docs/phase-1-known-limitations.md` ("provider-published values ... are preserved verbatim and
never recomputed"). Phase 2C needed to compute its own days-to-cover without either inheriting
the archived module's undefined denominator or silently reusing the provider's own figure.

## Decision

`DAYS_TO_COVER`'s denominator is one explicit, versioned policy:
`published_short_interest_divided_by_trailing_mean_completed_daily_share_volume.v1`. The
numerator is `payload.short_shares` from one explicitly-selected `PUBLISHED_SHORT_INTEREST`
observation (never `payload.days_to_cover`, never `payload.short_float_percent`). The
denominator is Phase 2A's own trailing-window selection (`selection.resolve_trailing_window`)
and mean-volume arithmetic (`volume_baselines.compute_mean_volume`), walked backward from
`as_of` over `BarInterval.ONE_DAY` bars only — any other interval is rejected before resolution
(`DAYS_TO_COVER_INCOMPATIBLE_VOLUME_INTERVAL`). `DaysToCoverComponents` makes every assumption
an explicit, named field: `short_interest_provider`, `volume_provider`, `volume_interval`,
`volume_window`, `volume_sample_counts`, and both age concepts (ADR 0035) — so a caller can audit
exactly what was compared without re-deriving it.

Days to cover does not call `volume_baselines.build_volume_baseline_result` wholesale, unlike
Phase 2B's own relative-volume reuse: that function requires a concrete target-bar boundary to
resolve and exclude a "current bar," a concept days-to-cover has no analogue for (there is no
specific bar being measured, only "the trailing mean volume as of `as_of`"). Instead,
`resolve_trailing_window` and `compute_mean_volume` are called directly with
`target_start=as_of`, and the resulting mean is wrapped in a real Phase 2A `MEAN_VOLUME_BASELINE`
`MetricResult` (constructed once, not recomputed) purely so `DaysToCoverComponents` can reference
a genuine, independently verifiable Phase 2A metric ID.

## Consequences

A `DAYS_TO_COVER` value of `2.5` means "2.5 average daily-volume periods under this documented
policy," never a literal calendar-day forecast — the policy name says so explicitly, and no
Phase 2C documentation states otherwise. Days to cover requires two independently explicit
providers (`short_interest_provider`, `volume_provider`) and never blends them into one implicit
source. Provider-published `short_float_percent`/`days_to_cover` remain untouched raw evidence on
the source `Observation`, confirmed absent from every Phase 2C code path by
`tests/metrics/test_pressure_cross_domain.py`.

## Rejected alternatives

Reusing `payload.days_to_cover` (the provider's own figure) as Phase 2C's `DAYS_TO_COVER` value
was rejected outright — it would misrepresent a provider-published number as a local calculation,
exactly the confusion `docs/field-semantics.md` and ADR 0029 warn against. A provider-published
"average volume" from a market snapshot (`MarketSnapshotPayload.average_volume`) was rejected as
the denominator per the handoff's explicit instruction — it has no defined window or point-in-time
policy and cannot be reconciled with the volume provider's own bar-level evidence. Phase 2B's
`RELATIVE_VOLUME`/Phase 2A's raw bar volume were rejected as denominator substitutes since neither
is a trailing multi-day average.
