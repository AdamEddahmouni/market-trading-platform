# Finviz Offline Snapshot Normalization

## Purpose and evidence basis

The adapter consumes local Finviz-shaped candidate-universe and descriptive market snapshots. It never connects to Finviz, authenticates, reads credentials, validates licensing, or claims that a field is live.

No defensible recorded export was preserved. The archived hand-built CSV test establishes representative aliases only. Valid fixtures are therefore `SANITIZED_REPRESENTATIVE_SAMPLE`; malformed and policy cases are `SYNTHETIC_EDGE_CASE`. No Phase 1C fixture is a recorded sample.

## Record contract and aliases

`FinvizSnapshotRecord` requires `source_record_id`, schema `FINVIZ_SCREENER_V1`, record type `CANDIDATE_SNAPSHOT`, an allowed fixture origin, and a symbol. Supported canonical/representative aliases are:

| Canonical field | Accepted aliases |
|---|---|
| `symbol` | `symbol`, `ticker`, `Ticker` |
| `price` | `price`, `Price` |
| `previous_close` | `previous_close`, `prev_close`, `Prev Close` |
| `change_percent` | `change_percent`, `change`, `Change` |
| `volume` | `volume`, `Volume` |
| `average_volume` | `average_volume`, `avg_volume`, `Avg Volume` |
| `relative_volume` | `relative_volume`, `Relative Volume` |
| `float_shares` | `float_shares`, `float`, `Shares Float` |
| `shares_outstanding` | `shares_outstanding`, `Shares Outstanding` |
| `short_float_percent` | `short_float_percent`, `short_float`, `Short Float` |
| `short_ratio_days` | `short_ratio_days`, `short_ratio`, `Short Ratio` |
| `market_cap` | `market_cap`, `Market Cap` |
| descriptive text | canonical lowercase name or `Sector`, `Industry`, `Country`, `Exchange`, `Earnings` |

Unknown fields are rejected. The normalizer never depends on undocumented aliases.

## Output semantics

One accepted row produces one `MARKET_SNAPSHOT` observation. The snapshot is provider-published descriptive evidence, not a trade, quote, bar, published-short-interest report, borrow record, catalyst, squeeze classification, or recommendation.

`short_float_percent` retains that exact name. It is not live short interest, borrow fee, borrow availability, short-sale volume, or current covering activity. `short_ratio_days` is separate from short-float percentage. Provider relative volume is retained as a ratio and diagnosed as using a provider-defined or unknown reference period; Phase 1C never recalculates it.

## Numeric parsing

- Price and ratios use finite `Decimal` values. Negative or formatted currency/ambiguous-separator inputs are invalid. Zero price is preserved but marks the observation invalid.
- Change and short-float percentages require `PERCENT_POINTS`, `DECIMAL_FRACTION`, or `FORMATTED_PERCENT_STRING`. Scaling is never inferred from magnitude.
- Quantities use decimal multipliers `K=1,000`, `M=1,000,000`, `B=1,000,000,000`, and `T=1,000,000,000,000`. Lowercase suffixes are accepted. Abbreviated values are marked estimated because displayed precision may be rounded.
- Quantities must resolve to nonnegative whole units. Invalid values remain null; they are never rounded or defaulted to zero.
- Earnings retains an exact date and optional BMO/AMC session qualifier. No time or timezone is invented.

## Time and freshness

Provider timestamp, capture timestamp, received timestamp, and effective timestamp remain distinct:

- A valid provider timestamp supplies source and effective time.
- Capture time is retained independently in provenance.
- When provider time is absent, capture time may satisfy the required envelope time only as `CAPTURE_TIME_UNCERTAIN_PLACEHOLDER`, with missing quality and a diagnostic. It is not provider publication time.
- When provider and capture time are absent, explicit context ingestion time is an equally uncertain placeholder.
- Context ingestion time always supplies received time.
- Known delay maps to delayed freshness. Historical is explicit. Otherwise freshness remains unknown; recent capture does not become `LIVE`.

## Partial rows, duplicates, and conflicts

Invalid fields are omitted without discarding other unambiguous descriptive fields. The observation becomes `INVALID` and partial, with stable diagnostics. Explicit zero and missing remain different.

Exact raw hashes or duplicate source IDs are emitted once. Same-symbol/same-effective-time snapshot differences are preserved and marked conflicted; no winner is selected.

## Offline command

```powershell
.\.venv\Scripts\python.exe -m squeeze_core normalize-provider --provider finviz --input tests\fixtures\providers\finviz\representative_cases.json --context tests\fixtures\providers\finviz\context.json --case finviz-complete-v1
```
