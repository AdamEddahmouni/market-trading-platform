# Bar Range Metric Semantics

`metrics.ranges` — `ABSOLUTE_BAR_RANGE`, `PERCENTAGE_BAR_RANGE`. See
[`foundational-market-metric-contract.md`](foundational-market-metric-contract.md) for fields
common to every Phase 2A metric.

## Formulas

```
absolute_range = high - low
percentage_range = ((high - low) / low) * 100
```

## Policy: `low_denominator_range.v1`

The denominator for the percentage form is the same completed bar's `low`. This is documented
and versioned, not a casual choice: `BarPayload.low` is required and `Field(gt=0)`, so it is
always available and never zero for any valid bar — no synthesized mid-price or open-price
denominator is needed. A different denominator (e.g. `open`) would be a new, separately versioned
policy (`calculation_policy_version`), not a silent change to this one.

- **Completed bars only**: `selection.resolve_bar_at_boundary` already excludes `PARTIAL` and
  `CANCELLED` latest-revisions before the range formula ever runs; a partial bar surfaces as
  `RANGE_PARTIAL_BAR_UNSUPPORTED`.
- **Corrected bars**: follow the same point-in-time lifecycle resolution as every other metric —
  a correction is only visible once its own eligibility is met; a `MetricResult` computed before
  that point is never retroactively changed.
- **Missing high/low, invalid high-below-low**: structurally unreachable via a real bar
  (`BarPayload`'s own validator rejects `high < max(...)` / `low > min(...)` at normalization
  time). The pure formula (`compute_percentage_range`) still guards a zero denominator
  defensively and is unit-tested directly for that branch.

## What this is not

Not a candlestick body/wick metric, not True Range (which compares against a *prior* close), not
ATR, not a volatility score. A single bar's own high-low spread.
