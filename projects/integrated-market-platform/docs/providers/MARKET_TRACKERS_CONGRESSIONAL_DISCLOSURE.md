# Market Trackers congressional PTR adapter (preparation)

Status: **replaceable third-party aggregate** over **primary Senate eFD / House Clerk** STOCK Act
filings. Lane H scope is **preparation only** — no live ingest, no execution dependency, no trade
recommendations, no political inference. Rows are regulatory disclosure facts, not signals.

Evidence classes: **DOCUMENTED**, **FIXTURE**, **NOT_EXECUTED** (live Market Trackers fetch).

## Replaceability doctrine

| Layer | Role |
|-------|------|
| Senate eFD + House Clerk PTR | Primary public record |
| LuxAlgo Market Trackers | Normalized daily dump + provenance link |
| IMP `market_trackers.congressional_disclosure` | Receipt, PIT prep, EventV1 map prep, evidence prep |
| Future `normalize_congressional_disclosure_row` | Admitted intelligence `EventV1` (registry patch proposed; not landed) |

## Upstream pin

| Item | Value |
|------|-------|
| Parser repo | [LuxAlgo/market-trackers](https://github.com/LuxAlgo/market-trackers) @ `9bf1045b6953e42a56f112445481d411a92261c9` |
| Data repo | [LuxAlgo/market-trackers-data](https://github.com/LuxAlgo/market-trackers-data) @ `64891b082072f7707cd070bc4e6795b74e871e88` |
| Dataset id | `congress-trades` |
| Export dir | `congress/trades` |
| Schema source | `packages/core/src/schema/congress-trade.ts` at parser pin |
| Published `schemaVersion` | `1` (verify via data `manifest.json` on ingest) |
| Parser license | MIT (parser repository) |
| Data license | CC0-1.0 (published dump files) |
| IMP adapter prep version | `market_trackers.congressional_disclosure/0.1.0-prep` |

Code pin: `market_platform_foundation.market_trackers.congressional_disclosure.pin.UPSTREAM_PIN`.

## Published row shape (characterized)

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | `${chamber}:${docId}:${rowIndex}` |
| `chamber` | yes | `senate` \| `house` |
| `docId` | yes | Source-system filing id |
| `rowIndex` | yes | 0-based row within filing |
| `member` | yes | Name, optional `bioguideId`, party, state |
| `filedAt` | yes | Report filing date `YYYY-MM-DD` |
| `transactedAt` | yes | Transaction date — **not** public-knowledge time |
| `ticker` | nullable | Heuristic symbol when resolvable |
| `assetDescription` | yes | Verbatim filing text |
| `assetType` | yes | `stock`, `option`, `fund`, … |
| `side` | yes | `buy` \| `sell` \| `exchange` (disclosed label only) |
| `amountRange` | yes | `min`, nullable `max`, `text` as printed |
| `owner` | nullable | `self`, `spouse`, `joint`, `dependent` |
| `provenance` | yes | `source`, `sourceUrl`, `retrievedAt`, `parser`, `confidence`, `needsReview` |

## Data lag and uncertainty

STOCK Act rules require periodic reporting; **lag between `transactedAt` and `filedAt` is normal**
and must not be collapsed into a single timestamp. Amounts are statutory ranges; open-ended tops
set `amountRange.max` to null (`Over $50,000,000`).

## Fixtures

Synthetic schema-faithful rows:

`tests/fixtures/market_trackers/congressional_disclosure/*.json`

Primary reconcile fixture:

`tests/fixtures/congressional_disclosure/ptr_primary_senate_example.json`

Tests:

- `tests/market_trackers/test_congressional_disclosure_adapter_prep.py`
- `tests/market_trackers/test_congressional_disclosure_pit_reconcile.py`

## Live probe

**NOT_EXECUTED** in Lane H. Future live validation must respect chamber site terms and robots policy
when fetching `provenance.sourceUrl`.
