# Return Baseline and Return Standardization Semantics

`metrics.return_baselines` — `MEAN_PERCENTAGE_RETURN_BASELINE`,
`PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE`. `metrics.return_standardization` —
`PERCENTAGE_RETURN_Z_SCORE`. See
[`normalized-market-activity-contract.md`](normalized-market-activity-contract.md) for common
fields and [ADR 0033](adr/0033-decimal-population-standard-deviation.md) for the standard-deviation
policy.

## Formulas

```
mean_percentage_return = arithmetic mean of eligible historical percentage returns

return_variance = Σ(returnᵢ - mean_return)² / N
return_standard_deviation = sqrt(return_variance)

return_z_score = (target_percentage_return - historical_mean) / historical_standard_deviation
```

## Pairing policy: `adjacent_close_to_close_return_count.v1`

Each historical return is the Phase 2A `compute_percentage_return` result of one adjacent pair of
trailing bars (`price_field=CLOSE` by default), built by calling Phase 2A's own
`returns.build_return_result(..., MetricName.PERCENTAGE_RETURN)` for each pair — not a
reimplementation of the return formula. `ReturnCountWindow.requested_count = N` translates to `N +
1` trailing bars fetched via a price-only trailing-bar walk (`return_baselines.
_resolve_price_trailing_bars`, built on `selection.py`'s private boundary/lifecycle helpers rather
than `selection.resolve_trailing_window`, which is volume-specific and would incorrectly exclude a
bar missing `volume` even though only `close` is needed — see `docs/phase-2b-design.md` §6).

- **Target exclusion**: the target return's own two boundary bars are excluded from the historical
  distribution by construction — the walk only considers bars strictly before the target return's
  *start* boundary (ADR 0034).
- **Zero starting close**: a pair whose start price would make the denominator zero is excluded
  from the distribution (Phase 2A's own `METRIC_ZERO_DENOMINATOR`, reused verbatim via
  `build_return_result`'s diagnostics), not treated as a zero return.
- **Zero return**: a genuine `0%` return is retained as a valid sample.
- **Insufficient bars**: fewer than 2 eligible bars → `RETURN_DISTRIBUTION_INSUFFICIENT_BARS`.
  Enough bars but fewer usable returns than `minimum_samples` → `RETURN_DISTRIBUTION_
  INSUFFICIENT_RETURNS`. Zero eligible bars → `RETURN_DISTRIBUTION_WINDOW_EMPTY`.
- **`MEAN_PERCENTAGE_RETURN_BASELINE`** and **`PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE`**
  both read from one shared internal `BaselineStatistics(baseline_kind=PERCENTAGE_RETURN)` (built
  once by `return_baselines.build_return_distribution_statistics`) — never two independent
  computations of the same distribution.
- **`PERCENTAGE_RETURN_Z_SCORE`** additionally resolves the target return via Phase 2A's
  `returns.build_return_result` and combines it with the same distribution.
- **Zero variance**: as with volume, the baseline itself remains `KNOWN_VALUE`
  (`standard_deviation=0` is a valid statistic); only the *z-score* becomes `INVALID`
  (`NORMALIZED_METRIC_ZERO_VARIANCE` + `RETURN_DISTRIBUTION_ZERO_VARIANCE`).
- **Arithmetic**: exact `Decimal`, `localcontext(prec=50)`, `Decimal.sqrt()`.

## What this is not

Not trend, not momentum, not volatility (no annualization, no ATR, no realized/annualized
volatility score). A return z-score states how many baseline-standard-deviations a return sits
from the baseline mean and nothing else — see ADR 0032.
