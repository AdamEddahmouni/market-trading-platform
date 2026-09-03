# Short intelligence sources (FINRA + Nasdaq Reg SHO)

Status: **read-only observational SHORT_INTELLIGENCE** under `ADR-SHORT-001`.
Live observations are **not** admitted research datasets.

Evidence classes: **DOCUMENTED**, **OBSERVED**, **INFERRED**, **UNTESTED**.

These sources complement SEC EDGAR (what changed) and Moomoo (how the market is reacting).
They do **not** replace borrow, cost-to-borrow, locates, or SEC fails-to-deliver quantities.

## Families (never collapse)

| Family | Canonical type | What it is | What it is not |
|---|---|---|---|
| Short interest | `ShortInterestObservation` | Twice-monthly reported outstanding short **position** | Trading flow, percent of float unless a PIT denominator exists |
| Short-sale volume | `ShortSaleVolumeObservation` | FINRA-reported short-**marked** trade **volume** | Percent of shares currently short; new bearish inventory |
| Threshold status | `ThresholdStatusObservation` | Public Reg SHO threshold **membership** | High short interest; exact FTD quantity; all-US list |

Borrow / CTB / locate / utilization remain a separate lending family. FINRA is not used to fill them.

## Architecture

```text
FINRA FIP OAuth (client credentials)
        ↓
finra.transport (Bearer, throttle, 401 refresh)
        ↓
consolidatedShortInterest | regShoDaily
        ↓
canonical observations + PIT clocks
        ↓
ShortIntelligenceStore.as_of
        ↓
features / ShortPressureState / allocation hints

Nasdaq Trader public threshold file (no FINRA credential)
        ↓
nasdaq_regsho.transport
        ↓
ThresholdStatusObservation
```

CPython 3.11 stdlib only. No `requests` / `pandas`.

## FINRA authentication

| Item | Status | Notes |
|---|---|---|
| Credential type | DOCUMENTED | Individual Public |
| Token URL | DOCUMENTED | `https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials` |
| Grant | DOCUMENTED | `client_credentials` with HTTP Basic `client_id:client_secret` |
| OAuth success | OBSERVED | Live `client_credentials` returns `Bearer` token; `expires_in` ≈ 43170s observed |
| Token cache | OBSERVED | In-memory only; never written to Git, logs, fixtures, or evidence |
| `expires_in` | OBSERVED | Seconds until expiry (string in example payload; numeric in live response) |
| Safety margin | OBSERVED | Refresh when `now >= expires_at - 120s`; second `get_token()` reuses cache (`refresh_count == 1`) |
| Concurrency | IMPLEMENTED | Single-flight lock |
| 401 recovery | IMPLEMENTED | Invalidate cache and retry once |
| Fail-closed | OBSERVED | Auth failure is not `short_interest = 0` |

Automated: token mint, cache, refresh, request Bearer attachment.

Manual (annual): Client Secret reset in FINRA Gateway / API Console. Human Gateway password is **not** runtime auth. Do not browser-automate the reset.

Credential health uses non-secret `FINRA_SECRET_ROTATED_AT` and/or `FINRA_SECRET_EXPIRES_AT`:

| Remaining | State |
|---|---|
| unknown | `UNKNOWN` |
| >30 days | `HEALTHY` |
| ≤30 days | `ROTATION_DUE` |
| ≤7 days | `ROTATION_URGENT` |
| expired | `EXPIRED` |
| 401/403 | `AUTH_FAILED` |

Live credential with `FINRA_SECRET_ROTATED_AT=2026-08-20` reports **OBSERVED** `HEALTHY` (365 days remaining on annual TTL).

## Licensing

DOCUMENTED: Individual accounts are intended for individual investors/researchers and **are not intended for commercial purposes at this time**.

Current project use: research and paper-trading development. Before commercialization, SaaS, or redistribution, require a provider/licensing review. Do not expose raw FINRA datasets through a public API.

## Consolidated Short Interest

| Item | Status | Notes |
|---|---|---|
| Dataset | OBSERVED | `group=otcMarket` `name=consolidatedShortInterest` |
| History | DOCUMENTED | About five rolling years of short interest |
| Publication | DOCUMENTED | Official settlement/due/publication calendar |
| API clock | DOCUMENTED | Available by approximately **4:40 PM ET** on the publication date |
| Schema | OBSERVED | `symbolCode`, `settlementDate`, `currentShortPositionQuantity`, `previousShortPositionQuantity`, `changePreviousNumber`, `changePercent`, `averageDailyVolumeQuantity`, `daysToCoverQuantity`, `marketClassCode`, `stockSplitFlag`, `revisionFlag`, `issueName`, `accountingYearMonthNumber`, `issuerServicesGroupExchangeCode` |
| PIT | OBSERVED | `as_of` before `available_time` cannot see the print (verified live on AAPL settlement `2026-07-15`, publication `2026-07-24`) |
| Revisions | IMPLEMENTED | Later versions do not overwrite earlier captured versions. Historical current-download is flagged `ORIGINAL_VERSION_UNAVAILABLE` |
| Request metadata | OBSERVED | `FINRA-api-request-id` returned; `record-total` header present (e.g. 207 rows for AAPL) |

`days_to_cover_provider` is FINRA's methodology on reported average daily volume. It is not live liquidity.

`short_interest_pct_float` is `UNKNOWN` unless a PIT-safe shares/float denominator is supplied with `known_from <= observation available_time`.

## Reg SHO Daily Short Sale Volume

| Item | Status | Notes |
|---|---|---|
| Dataset | OBSERVED | `group=otcMarket` `name=regShoDaily` |
| Retention | DOCUMENTED | Rolling **12-month** API window |
| Schema | OBSERVED | `tradeReportDate`, `securitiesInformationProcessorSymbolIdentifier`, `reportingFacilityCode`, `marketCode`, `shortParQuantity`, `shortExemptParQuantity`, `totalParQuantity` |
| Facilities | OBSERVED | Raw rows retained per facility (`NCTRF`, `NQTRF`, `NYTRF` observed for AAPL); aggregation is explicit |
| Ratio name | OBSERVED | `finra_reported_short_sale_ratio` = short-marked volume / FINRA-reported total on the same rows |

This ratio is **not** `market_short_ratio` and is **not** percent of shares outstanding.

Official downloadable daily files exist for some history; this package uses the Query API for incremental pulls and fixtures for CI. Older official archives are a documented boundary, not a scrape of third-party histories.

## Platform limits (conservative)

DOCUMENTED ceilings: 1200 sync requests/minute/IP, 20 async requests/minute/dataset/account, 5000 sync records, 100000 async records, 3 MB sync payload.

This client budgets **60 sync requests/minute**, default **1000 records**, server-side symbol/date filters, and uses sync queries for small ranges. Async exists in FINRA docs (poll ≤1/minute; do not attach Bearer to pre-signed result URLs) and is **not** the default ingest path.

Preserve `FINRA-api-request-id` when present. Do not log pre-signed URLs.

Live sync queries use POST with `compareFilters`, `limit`, and `offset`. Observed `record-total` header supports pagination characterization; default client limit is 1000 (not stress-tested).

## Nasdaq Reg SHO threshold list

| Item | Status | Notes |
|---|---|---|
| Source | DOCUMENTED | Nasdaq Trader public file `nasdaqthYYYYMMDD.txt` |
| Coverage | DOCUMENTED | Nasdaq-listed securities. Not all US threshold lists. OTC moved off NasdaqTrader (2014) |
| Criteria | DOCUMENTED | Five consecutive settlement days; aggregate fails ≥ 10,000 shares and ≥ 0.5% of TSO |
| Format | DOCUMENTED | Pipe-delimited; trailer `YYYYMMDDHHMMSS` |
| Timezone of trailer | INFERRED | Treated as `America/New_York` from Trader UI display |
| PIT | IMPLEMENTED | Availability is file creation time, never the first hidden fail day |
| FTD quantity | DOCUMENTED | Not present; future SEC FTD source is a separate lane |

Duration features use only observed list membership available at query time.

## Operations

```text
sync_short_interest()
sync_short_sale_volume()
sync_threshold_list()
reconcile()   # checkpoint metadata is not a completeness proof
```

No scheduler is hard-wired. Incremental + periodic overlap reconciliation is caller-driven.

## Testing

Ordinary CI: fixtures only. No FINRA credentials, no Nasdaq website.

```powershell
python -m unittest discover -s tests/short_intelligence -v
```

Live opt-in:

```powershell
$env:IMP_FINRA_LIVE = "1"
$env:IMP_NASDAQ_REGSHO_LIVE = "1"
python tools/short_intelligence/probe.py --output evidence/short_intelligence/capability-report.json
```

Put credentials in a local `.env` (never commit it):

```text
FINRA_CLIENT_ID=
FINRA_CLIENT_SECRET=
FINRA_SECRET_ROTATED_AT=
```

## Security

Secret scan rules cover `FINRA_CLIENT_ID`, `FINRA_CLIENT_SECRET`, `access_token`, and `Authorization: Basic|Bearer`. Evidence reports redact those keys. No trade APIs. No order placement.
