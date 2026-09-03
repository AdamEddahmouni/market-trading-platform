# Return Metric Semantics

`metrics.returns` — `ABSOLUTE_RETURN`, `PERCENTAGE_RETURN`. See
[`foundational-market-metric-contract.md`](foundational-market-metric-contract.md) for fields
common to every Phase 2A metric.

## Formulas

```
absolute_return = ending_price - starting_price
percentage_return = ((ending_price - starting_price) / starting_price) * 100
```

Both are computed by `metrics.returns.compute_absolute_return` /
`compute_percentage_return`, pure functions of two `Decimal | None` prices — kept separate from
bar selection so their missing/zero-input branches are directly unit-testable even though a real
`BarPayload` can never actually supply a `None` or zero price (all four OHLC fields are
`Field(gt=0)`, required).

## Policy: `close_to_close_completed.v1`

- **Price field**: defaults to `CLOSE`; `price_field` is an explicit, documented request field
  (`OPEN`/`HIGH`/`LOW`/`CLOSE`), never silently assumed.
- **Bars**: the caller supplies the exact `start_bar_start`/`start_bar_end` and
  `end_bar_start`/`end_bar_end` boundaries. There is no implicit "N bars ago" resolution here —
  that is `metrics.volume_baselines`'s job, not returns'.
- **Lifecycle**: each boundary is resolved independently via
  `selection.resolve_bar_at_boundary` — partial bars are excluded
  (`METRIC_PARTIAL_INPUT`), the latest eligible completed/corrected revision is used.
- **Same bar twice**: using one bar as both start and end is well-defined (`RETURN_IDENTICAL_INPUT_BAR`,
  a zero return with `KNOWN_VALUE` quality) — it is not an error.
- **Provider scope**: `SINGLE_PROVIDER` by default; an explicit provider is required when more
  than one provider publishes at either boundary.

## Diagnostics

`RETURN_START_BAR_NOT_FOUND`, `RETURN_END_BAR_NOT_FOUND` (no eligible bar at that boundary),
`RETURN_PRICE_FIELD_UNAVAILABLE`, `RETURN_IDENTICAL_INPUT_BAR`, plus the general
`METRIC_MISSING_START_PRICE`/`METRIC_MISSING_END_PRICE`/`METRIC_ZERO_DENOMINATOR` (percentage
only) from the pure formula layer, and `METRIC_PARTIAL_INPUT`/`METRIC_CANCELLED_INPUT`/
`METRIC_CONFLICTED_INPUT`/`METRIC_AMBIGUOUS_PROVIDER` from selection.

## What this is not

Not momentum, not a trend signal, not annualized, not a rate of change over a rolling window.
Two numbers in, one number out, with full provenance back to the two source bars.
