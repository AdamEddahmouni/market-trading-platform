# Volume Baseline Metric Semantics

`metrics.volume_baselines` — `MEAN_VOLUME_BASELINE`. See
[`foundational-market-metric-contract.md`](foundational-market-metric-contract.md) for fields
common to every Phase 2A metric, and [ADR 0031](adr/0031-volume-baseline-without-relative-volume.md)
for why relative volume is explicitly out of scope.

## Formula

```
mean_volume_baseline = arithmetic mean of eligible completed/corrected bar volumes
                        over an explicit trailing BAR_COUNT window
```

## Policy: `trailing_mean_exclude_current.v1`

- **Window**: `TrailingWindow(window_type=BAR_COUNT, requested_count, exclude_current_bar=True,
  minimum_samples)`. Only `BAR_COUNT` is implemented in Phase 2A; `TIME_RANGE`/`SESSION_COUNT` are
  named in `metrics.models.WindowType` for forward compatibility and raise `NotImplementedError`
  if requested.
- **Current-bar exclusion**: the target/current bar is excluded from its own baseline by default
  (`exclude_current_bar=True`) — walking strictly backward from (not including) the target bar's
  `bar_start`. Requesting `exclude_current_bar=False` is supported but not the default.
- **Ordering**: candidates are walked from the most recent eligible boundary backward until
  `requested_count` usable samples are collected or candidates run out. No forward-fill,
  backfill, interpolation, or bar synthesis occurs anywhere in this path.
- **Zero-volume bars**: retained as valid `0` samples (`METRIC_ZERO_VOLUME_SAMPLE`, informational).
- **Missing-volume bars** (`payload.volume is None`): excluded and counted separately in
  `missing`, never treated as `0` (`METRIC_MISSING_VOLUME`).
- **Wrong volume unit** (a candidate's `volume_unit` differs from the target bar's): excluded and
  counted in `missing` (`VOLUME_BASELINE_MIXED_UNITS`) — units are never mixed into one mean.
- **Mixed interval/session candidates**: excluded upstream by `evidence.bars.build_bar_series`'s
  own interval/session filter before the window walk ever sees them — there is no separate
  "mixed interval" diagnostic because the metric structurally cannot receive one.
- **Partial/cancelled/conflicted candidates**: excluded via the same
  `selection._resolve_group` lifecycle resolution every other metric uses.
- **Sample counts**: every result reports `requested` (what was asked for), `eligible` (usable
  boundaries encountered during the scan), `used` (contributed to the mean, `<= requested`), and
  `missing` (`eligible - used`, from null volume, wrong unit, or unresolved conflict).
- **Minimum samples**: `used < minimum_samples` yields `VOLUME_BASELINE_INSUFFICIENT_SAMPLES`,
  quality `UNAVAILABLE`. `used == 0` yields `VOLUME_BASELINE_WINDOW_EMPTY`. `used >= minimum_samples`
  but `< requested_count` yields `KNOWN_VALUE` with `completeness=PARTIAL`.
- **Arithmetic**: exact `Decimal` division under an explicit `localcontext(prec=28)`; a
  non-terminating mean (e.g. three samples summing to a non-multiple-of-3) retains full precision
  rather than being rounded for storage.

## What this is not

Not relative volume — the output is the baseline itself, never `current_volume / baseline`. Not a
volume trend, not a liquidity score, not turnover, not dollar volume.
