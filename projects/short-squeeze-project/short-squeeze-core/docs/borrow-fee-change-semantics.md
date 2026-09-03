# Borrow-Fee Change Metric Semantics

`metrics.borrow_fee_changes` — `BORROW_FEE_ABSOLUTE_CHANGE`,
`BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE`. See
[ADR 0037](adr/0037-borrow-fee-points-versus-relative-percent-change.md) for the percentage-point
vs. relative-percentage distinction this file exists to enforce.

## Formula

```
BORROW_FEE_ABSOLUTE_CHANGE           = ending.annualized_fee_percent - starting.annualized_fee_percent   (PERCENTAGE_POINTS)
BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE = (ending - starting) / starting * 100                              (PERCENT)
```

`BorrowFeePayload.annualized_fee_percent` is already normalized to one consistent percentage-point
scale by the Phase 1B IBKR adapter regardless of the provider's input unit (`PERCENT_POINTS` or
`DECIMAL_FRACTION`) — Phase 2C never performs a second unit conversion.

## Selection: `explicit_observation_pair.v1`

- Caller supplies one explicit `provider` and two explicit `effective_timestamp` boundaries
  (`starting_effective_timestamp`, `ending_effective_timestamp`) — IBKR borrow observations have
  no revision/lifecycle concept (no `supersedes` field exists on `IbkrBorrowRecord`), so there is
  no "latest revision" to resolve, only "the observation at this exact boundary."
- `pressure_selection.resolve_borrow_observation_at` groups eligible `BORROW_FEE` observations
  for `(symbol, provider)` by `effective_timestamp` — the same key IBKR's own normalizer groups
  conflicts by. A conflicted group yields no winner (`PRESSURE_METRIC_CONFLICTED_INPUT`).
- `starting_effective_timestamp >= ending_effective_timestamp` is rejected
  (`PRESSURE_METRIC_IDENTICAL_INPUT` / `PRESSURE_METRIC_START_AFTER_END`) before resolution.
- A resolved observation with `payload.annualized_fee_percent is None` yields
  `BORROW_FEE_MISSING_VALUE` — missing is never `0`. An explicit `0` fee is a known value.

## Zero-denominator asymmetry

`starting.annualized_fee_percent == 0` is a valid input for the absolute (percentage-point)
change but a `BORROW_FEE_ZERO_START_DENOMINATOR` (`INVALID`) for the relative percentage change
— identical asymmetry to the short-interest and borrow-availability change metrics.

## What this is not

Not a hard-to-borrow classification — `payload.hard_to_borrow` (a raw provider status flag) is
read by no code path in this file, verified by both a dedicated unit test and the isolation
test's forbidden-substring scan. Not a cost-to-borrow score. No threshold, no "tightening
lending" label, no rank, no recommendation.
