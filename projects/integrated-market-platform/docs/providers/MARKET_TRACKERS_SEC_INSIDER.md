# Market Trackers SEC Forms 3/4/5 insider adapter (preparation)

Status: **replaceable third-party aggregate** over **primary SEC EDGAR** ownership XML.
Lane H scope is **preparation only** — no live ingest, no execution dependency, no trade
recommendations. Rows are regulatory facts, not signals.

Evidence classes: **DOCUMENTED**, **FIXTURE**, **NOT_EXECUTED** (live Market Trackers fetch).

## Replaceability doctrine

| Layer | Role |
|-------|------|
| SEC EDGAR ownership XML | Primary public record |
| LuxAlgo Market Trackers | Normalized daily dump + provenance link |
| IMP `market_trackers.sec_insider` | Receipt, PIT prep, EventV1 map prep, public-record evidence prep |
| Future `normalize_event` adapter | Admitted intelligence `EventV1` (not in this lane) |

Market Trackers may be swapped for direct EDGAR parsing or SEC bulk 345 sets without changing
IMP's primary-source clock doctrine.

## Upstream pin

| Item | Value |
|------|-------|
| Parser repo | [LuxAlgo/market-trackers](https://github.com/LuxAlgo/market-trackers) @ `9bf1045b6953e42a56f112445481d411a92261c9` |
| Data repo | [LuxAlgo/market-trackers-data](https://github.com/LuxAlgo/market-trackers-data) @ `64891b082072f7707cd070bc4e6795b74e871e88` |
| Dataset id | `insider-transactions` |
| Export dir | `insider/transactions` |
| Published `schemaVersion` | `2` |
| Parser license | MIT (parser repository) |
| Data license | CC0-1.0 (published dump files) |
| IMP adapter prep version | `market_trackers.sec_insider/0.1.0-prep` |

Code pin: `market_platform_foundation.market_trackers.sec_insider.pin.UPSTREAM_PIN`.

## Published row shape (characterized)

Source of truth upstream: `packages/core/src/schema/insider-transaction.ts` at the pinned parser commit.

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | `${accessionNumber}:{nd\|d}:${rowIndex}` |
| `accessionNumber` | yes | Dashed EDGAR accession |
| `formType` | yes | `3`, `4`, `5`, `3/A`, `4/A`, `5/A` |
| `issuerCik` | yes | Issuer CIK (zero-padded in dumps) |
| `issuerName` | yes | Verbatim issuer name |
| `insider` | yes | Name, CIK, title, role booleans |
| `filedAt` | yes | Filing date `YYYY-MM-DD` |
| `transactedAt` | nullable | Transaction date; **not** public-knowledge time |
| `code` | nullable | Raw SEC transaction code |
| `acquiredDisposed` | nullable | `A` / `D` when present |
| `ticker` | nullable | Resolved symbol when known |
| `shares`, `pricePerShare`, `sharesOwnedAfter` | nullable | Numeric when reported |
| `ownership` | yes | `direct` / `indirect` |
| `isDerivative` | yes | Non-derivative vs derivative table |
| `provenance` | yes | `source`, `sourceUrl`, `retrievedAt`, `parser`, `confidence`, `needsReview` |

## Ingestion path (target)

```text
Market Trackers JSON row (insider/transactions/…)
        ↓
ExternalSourceReceipt (IMP receipt boundary)
        ↓
XA-01 provisional instrument resolution (ticker when present; fail closed when absent)
        ↓
EventV1 normalization prep (REGULATORY_OWNERSHIP / INSIDER_OWNERSHIP_ROW)
        ↓
Deterministic public-record evidence (imp.public_record.sec_form_345_row)
        ↓
Observation Engine / OE consumers (no execution dependency)
```

Observation Ingress Router (Lane F) is **not required** for this preparation lane. When the router
lands, it should accept the same receipt + bundle shape documented in
`docs/engineering/specs/MARKET_TRACKERS_SEC_INSIDER_ADAPTER_PREP.md`.

## Point-in-time semantics

| Clock | Meaning in IMP prep |
|-------|---------------------|
| `transactedAt` | Economic attribution when present — **never** prospective public-knowledge time |
| `filedAt` | Day-bounded filing publication lower bound from aggregator |
| `provenance.retrievedAt` | When Market Trackers fetched/parsed — aggregator evidence only |
| EDGAR `acceptanceDateTime` | Authoritative sub-day public availability — reconcile via `provenance.sourceUrl` |

Flags always include `PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE` and `PRIMARY_SOURCE_EDGAR_WINS`.

## Identity (XA-01)

- Ticker present → `research.security_identity.resolve_us_equity_ticker` under `xa01.provisional` namespace.
- Ticker null → no guessed instrument; `INSTRUMENT_UNRESOLVED_TICKER_NULL`.
- Issuer CIK is entity evidence; it does not bypass instrument admission.

## Form 4 doctrine

- Transaction codes remain raw (`P`, `S`, `M`, `F`, …).
- **No** automatic bullish/bearish mapping from code or `acquiredDisposed`.
- Participant action inference used elsewhere in IMP is **not** applied at this adapter edge.

## Candidate features (metadata only)

See `market_trackers.sec_insider.features.CANDIDATE_FEATURES` for purchase vs disposition
semantics, role flags, filing lag, clustering, size, and holdings — each with defensibility
notes and pitfalls.

## Fixtures

Golden rows (synthetic, schema-faithful):

`tests/fixtures/market_trackers/sec_insider/*.json`

Tests: `tests/market_trackers/test_sec_insider_adapter_prep.py`

## Live probe

**NOT_EXECUTED** in Lane H. Future live validation must respect SEC Fair Access if fetching
primary documents from `provenance.sourceUrl`.
