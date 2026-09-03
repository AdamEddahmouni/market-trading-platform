# Published Short-Interest Semantics

Published short interest is a periodically reported position snapshot associated with a settlement or reporting period. It is not a live count merely because it was recently downloaded.

## Distinct dates and times

| Concept | Meaning | Point-in-time role |
|---|---|---|
| Settlement date | Market period described by the position value | Reporting-period age only; never grants availability |
| Observation/reporting date | Provider name for the described period | Treated as settlement date for the supported shape |
| Publication date/time | When the source made the record available | Strict eligibility boundary |
| Provider timestamp | Separate provider row/file timestamp when supplied | Provenance; publication only when explicitly declared |
| Capture timestamp | When a local file/page was captured | Provenance; cannot prove publication |
| Received timestamp | When this system obtained the record | Strict eligibility boundary |
| Effective timestamp | Earliest time both published and locally available | `max(publication availability, receipt)` |

A bundle includes published short interest only when publication/source, receipt, and effective timestamps are all at or before `as_of`. Settlement date cannot satisfy any availability gate.

## Age and freshness

`availability_age_ms` measures time from effective availability to bundle time. `reporting_period_age_days` measures calendar age from settlement date. A newly received record can therefore be operationally recent and describe an old market period. A separate reporting-period policy can retain it as `STALE` or exclude it without turning it into missing or current evidence.

## Revisions and hindsight resistance

Originals and corrections remain separate canonical observations with separate raw hashes, publication times, and receipt times. A later eligible revision creates a relationship to the preserved prior observation. It does not overwrite it. Rebuilding an earlier bundle with the full observation history still selects only what was published and received by that earlier time.

## Related but non-interchangeable evidence

- Daily short-sale volume describes daily transaction volume, not current open short positions.
- Finviz `short_float_percent` is a descriptive snapshot with provider methodology, float, reporting-date, rounding, and timing limitations.
- Published `short_shares` is a settlement-period position count.
- IBKR borrow fee is securities-lending cost.
- IBKR available shares is provider inventory.

Published short-float percentages are not automatically compared with Finviz short float because scope, period, and float methodology are not established as compatible. Borrow fields are never compared with published position fields.

Phase 1D does not estimate real-time market-wide short interest, calculate squeeze probability, or produce a score, rank, recommendation, or trade instruction.
