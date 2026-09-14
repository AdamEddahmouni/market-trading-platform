# PIT contract — Market Trackers congressional PTR (`congress-trades`)

## Authority layers

| Layer | Role |
|-------|------|
| Senate eFD + House Clerk PTR filings | **Primary** public record (STOCK Act) |
| LuxAlgo Market Trackers | Replaceable normalized dump + `provenance.sourceUrl` |
| IMP prep (`market_trackers.congressional_disclosure`) | Receipt, PIT prep, reconcile flags — not trading authority |

## Clock characterization

| Clock | Source field | Role |
|-------|--------------|------|
| Economic event | `transactedAt` | Transaction attribution date only |
| Filing publication (aggregator) | `filedAt` | Day-bounded lower bound when primary not supplied |
| Primary publication | PTR `published_at` (optional reconcile input) | Sub-day public availability when supplied |
| Aggregator retrieved | `provenance.retrievedAt` | Evidence of parser fetch — not public knowledge |
| Platform received | Caller-injected `platform_received_time_ns` | IMP ingress boundary |

## Lawful availability rule

`available_time_ns` = max of lawful candidates **excluding** `transactedAt` start-of-day.

Default aggregator path: end of UTC day for `filedAt`. When `PtrPrimaryFiling` is supplied,
`published_at` wins when present; otherwise end of UTC day for primary `filing_date`.

## Mandatory flags

- `PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE`
- `MARKET_TRACKERS_REPLACEABLE`
- `STOCK_ACT_REPORTING_LAG_EXPECTED`
- `DISCLOSED_AMOUNT_IS_RANGE` (prep bundle PIT flags)

Reconcile path without primary:

- `PTR_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY`
- `AGGREGATOR_FILING_PUBLICATION_ONLY`

With primary:

- `PRIMARY_SOURCE_PTR_WINS`
- `PTR_PUBLICATION_FROM_PRIMARY` when `published_at` parses

## Non-rules (fail closed intellectually)

- Do **not** set `available_time_ns` from `transactedAt`.
- Do **not** infer exact trade size from amount range.
- Do **not** map `side` (`buy`/`sell`/`exchange`) to LONG/SHORT execution sides.

## Implementation references

- Prep: `market_trackers.congressional_disclosure.pit.derive_pit_clocks`
- Reconcile: `market_trackers.congressional_disclosure.reconcile.reconcile_congressional_clocks`
- Tests: `tests/market_trackers/test_congressional_disclosure_pit_reconcile.py`
