# SEC Fails-to-Deliver (FTD) market-activity source

Status: **read-only observational settlement-failure evidence** under `ADR-FTD-001`.
Live captures are **not** admitted research datasets.

Evidence classes: **DOCUMENTED**, **OBSERVED**, **INFERRED**, **UNTESTED**.

SEC FTD complements FINRA short interest, FINRA Reg SHO daily flow, and Nasdaq threshold status.
It does **not** replace borrow, cost-to-borrow, locates, or real-time market reaction (Moomoo).

## What it is / what it is not

| Concept | FTD is | FTD is not |
|---|---|---|
| Quantity | Aggregate **net balance outstanding** as of settlement date | Daily fail volume |
| Shorting | May arise from long or short sales (DOCUMENTED by SEC) | Proof of naked or illegal shorting |
| Timing | Published twice monthly with substantial lag | Real-time squeeze confirmation |
| Identity | CUSIP + symbol + issuer description | Canonical borrow availability |

## Official source

| Item | Status | Notes |
|---|---|---|
| Index | DOCUMENTED | `https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data` |
| Archive pattern | OBSERVED | `/files/data/fails-deliver-data/cnsfailsYYYYMM{a|b}.zip` |
| Credentials | DOCUMENTED | None required |
| User-Agent | DOCUMENTED | Reuse SEC Fair Access (`SEC_USER_AGENT`) |
| Rate limit | IMPLEMENTED | 5 req/s via shared `SecTransport` |
| Coverage start | DOCUMENTED | February 2004 |
| Modern cadence | DOCUMENTED | Half-month archives from July 2009 |

## Schema (pipe-delimited inside ZIP)

| Field | Meaning |
|---|---|
| SETTLEMENT DATE | Economic/reference date |
| CUSIP | 9-character identifier (retain internally) |
| SYMBOL | Ticker at publication time |
| QUANTITY (FAILS) | **Balance outstanding**, not daily flow |
| DESCRIPTION | Issuer name |
| PRICE | Previous-day close when > $0.01; `.` = unknown |

## PIT clocks

| Clock | Role |
|---|---|
| `settlement_date` | Economic validity |
| `source_period_start` / `source_period_end` | Archive logical window |
| `first_observed_time` | Live availability (safe default) |
| `available_time` | Knowledge cutoff for `as_of` queries |
| `retrieved_time` / `ingested_time` | Capture audit |

Historical backfills mark `PUBLICATION_TIME_UNCERTAIN`. Do not fabricate exact historical publication hours.

## Historical coverage caveats

- **Before 2008-09-16**: only balances ≥ 10,000 shares included (`HISTORICAL_COVERAGE_LIMITED`)
- **On/after 2008-09-16**: all positive balances; zero balances omitted
- **Before July 2009**: quarterly/monthly legacy archives (deferred parser; documented only)

## Architecture

```text
SEC FTD index page
        ↓
sec_ftd.discovery
        ↓
SecTransport + FtdTransport (hash cache)
        ↓
parser (ZIP + pipe-delimited)
        ↓
FailsToDeliverObservation
        ↓
ShortIntelligenceStore.ftd_as_of
        ↓
features / ShortPressureState.fails_to_deliver
```

## Short intelligence integration

`ShortPressureState` exposes `fails_to_deliver` separately from `threshold_status`.
Threshold observations still carry `FTD_QUANTITY_UNKNOWN` because Nasdaq files do not publish FTD balances.

Canonical type: `FailsToDeliverObservation` (`ObservationFamily.FAILS_TO_DELIVER`).

Forbidden default API: summing balances across settlement dates as "total fails".

## Operations

```powershell
$env:SEC_USER_AGENT = "YourName your.email@example.com"
$env:IMP_SEC_FTD_LIVE = "1"
python -m unittest discover -s tests/sec_ftd -v
python -m unittest discover -s tests/live_sec_ftd -v
python tools/sec_ftd/probe.py --period cnsfails202607b --symbol BIYA
```

## Testing

| Suite | Gate | Purpose |
|---|---|---|
| `tests/sec_ftd` | offline | Parser, PIT, balance semantics, duplicates |
| `tests/live_sec_ftd` | `IMP_SEC_FTD_LIVE=1` | Discovery, download, BIYA probe |

## Security / compliance

- No API keys or OAuth
- CUSIP: internal research use; redistribution requires separate licensing review
- Capture artifacts live under `evidence/sec_ftd/captures/` (not committed)

## Known limitations

- Publication delay limits live squeeze confirmation utility
- SEC price is approximate context only
- Absence from a complete post-2008 file ≠ proven zero balance without completeness proof
- Source file replacement detected via content hash; prior versions preserved in cache
