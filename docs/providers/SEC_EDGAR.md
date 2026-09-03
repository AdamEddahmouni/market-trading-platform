# SEC EDGAR regulatory provider

Status: **public read-only REGULATORY source** under `ADR-EDGAR-001`.
Live observations are **not** admitted research datasets.

Evidence classes used below: **DOCUMENTED**, **OBSERVED**, **INFERRED**, **UNTESTED**.

Phase 9 fixture-first whale disclosure on BIYA remains the admitted `regulatory_disclosure` path.
This module adds a general filing / XBRL / catalyst / dilution layer on top of that substrate.

## Architecture

```text
SEC (data.sec.gov / www.sec.gov)
        ↓
sec_edgar.transport (User-Agent + 5 rps global throttle + cache)
        ↓
submissions | companyfacts | archive documents | latest-filings Atom
        ↓
FilingEvent / XbrlFact (PIT clocks)
        ↓
FilingStore.as_of  +  CatalystEvidence / DilutionEvidence / participant hints
        ↓
optional observational allocation hint (capability, not vendor)
```

No API key. No vendor SDK. CPython 3.11 stdlib only.

## Official interfaces

| Interface | Status | Notes |
|---|---|---|
| submissions `CIK##########.json` | IMPLEMENTED | Filing metadata |
| companyfacts | IMPLEMENTED | Filtered by `filed` date; aggregate blob is not historical truth |
| companyconcept | PLANNED | Same PIT rule as companyfacts |
| frames | PLANNED | Point-in-time unsafe if used naively |
| filing archive documents | IMPLEMENTED | Policy-based; hashed |
| latest-filings Atom | IMPLEMENTED (parser) | Fast discovery path |
| bulk submissions/companyfacts archives | PLANNED | Preferred for large backfills; not downloaded in this package |

## Fair Access

- Configured max rate: **5 requests/second** process-wide (`SecTransport` global lock)
- SEC documented ceiling: 10 requests/second — we stay below it
- `SEC_USER_AGENT` required; generic `python-urllib` / `python-requests` identities are rejected
- Retries: 429 honors `Retry-After`; 5xx exponential backoff; timeouts fail closed
- Immutable archive URLs are cached
- Unreachable SEC → `SOURCE_UNAVAILABLE`, never `NO_FILINGS`

## Point-in-time clocks

| Clock | Meaning |
|---|---|
| `filing_date` | SEC filing date (date) |
| `acceptance_time` | `acceptanceDateTime` when present |
| `observed_time` | when this process first saw the metadata |
| `document_available_time` | first successful document fetch (0 until retrieved) |
| `retrieved_time` | document retrieval |
| `available_time` | metadata-only: observation; content features: document retrieval |

Do not assume `acceptance_time == document available`. Amendments never overwrite originals; `as_of` before the amendment acceptance excludes it.

## Identity

SEC identity is CIK. `EntityMap` maps CIK → `instrument_id` with temporal validity.
Unmapped CIK is `UNKNOWN_ENTITY` with empty instrument_id — never a guessed ticker.

Accession numbers are normalized to `##########-##-######`.

## How to probe (opt-in live)

```powershell
$env:SEC_USER_AGENT = "IntegratedMarketPlatform research contact@example.com"
$env:IMP_EDGAR_LIVE = "1"
python tools/sec_edgar/probe.py --cik 0000320193 --output evidence/sec_edgar/capability-report.json
```

Live tests:

```powershell
$env:SEC_LIVE_TESTS = "1"
$env:SEC_USER_AGENT = "IntegratedMarketPlatform research contact@example.com"
python -m unittest discover -s tests/live_sec -v
```

Ordinary CI does **not** run live SEC requests (`tests/sec_edgar` is fixture-only).

## Known limitations

- Live EDGAR is observational, not admitted
- 13F is delayed holdings, not a live position
- Form type is not bullish/bearish
- Dilution evidence from S-3/424B is family-level until terms are parsed
- FINRA short interest, borrow, quotes, and execution are out of scope
