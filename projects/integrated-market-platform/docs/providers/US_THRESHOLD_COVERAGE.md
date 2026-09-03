# U.S. Reg SHO threshold coverage

Status: **read-only observational SHORT_INTELLIGENCE** under `ADR-SHORT-001`.
Threshold observations are **not** admitted research datasets and are **not** squeeze signals.

## Families (never collapse)

| Family | Canonical type | What it is | What it is not |
|---|---|---|---|
| Threshold status | `ThresholdStatusObservation` | Official threshold-list **membership/status** | Short interest, FTD quantity, borrow, squeeze probability |
| Short interest | `ShortInterestObservation` | Twice-monthly reported outstanding short **position** | Threshold status |
| Short-sale volume | `ShortSaleVolumeObservation` | FINRA short-marked trade **volume** | Threshold status |
| Fails-to-deliver | `FailsToDeliverObservation` | SEC-published aggregate FTD **balance** | Threshold status or flow |

## Authorities implemented

| Authority | Source | Listing scope | Format | PIT availability |
|---|---|---|---|---|
| Nasdaq | Nasdaq Trader `nasdaqthYYYYMMDD.txt` | Nasdaq-listed | Pipe file + trailer timestamp | `file_creation_time` |
| NYSE Group | `nyse.com/api/regulatory/threshold-securities/download` | NYSE, NYSE American, NYSE Arca (runtime-discovered) | Pipe file + trailer timestamp | `file_creation_time` |
| FINRA OTC | FINRA Query API `otcMarket/thresholdList` | OTC | JSON API | `first_observed_time` (publication time often unknown) |
| Cboe BZX | CDN `bzx_equities_reg_sho_threshold_YYYYMMDD.txt` | **BZX-listed only** (empirically observed) | Pipe file + trailer timestamp | `file_creation_time` (Chicago timezone inferred) |

## FINRA OTC rule families

Preserve separately:

- `regShoThresholdFlag` — Regulation SHO Rule 203(b)(3) reporting issuers
- `rule4320Flag` — FINRA Rule 4320 non-reporting issuers
- `thresholdListFlag` — `R` / `NR` list classification

These must not be collapsed into one boolean without provenance.

## Coverage routing

```text
PIT listing identity (SymbolMap.listing_authority)
        ↓
relevant authority
        ↓
official source sync
        ↓
ThresholdStatusObservation
        ↓
threshold_state_as_of / ShortPressureState
```

Routing examples:

- `NASDAQ` → Nasdaq file
- `NYSE`, `NYSE_AMERICAN`, `NYSE_ARCA` → NYSE Group download with market selector
- `OTC` → FINRA `thresholdList`
- `CBOE_BZX` → Cboe CDN file

A missing Nasdaq row for an NYSE-listed symbol is **NOT_APPLICABLE** for Nasdaq, not a global `NOT_THRESHOLD`.

## Negative-state semantics

| State | When permitted |
|---|---|
| `NOT_THRESHOLD` / `INACTIVE` | Relevant authority queried successfully and symbol absent or flag `N` with confirmed coverage |
| `UNKNOWN` | Relevant source not yet observed for trade date |
| `SOURCE_UNAVAILABLE` | Transport/auth failure for relevant authority |
| `NOT_APPLICABLE` | Non-settlement day or wrong authority for listing |
| `IDENTITY_UNRESOLVED` | Listing authority unknown at `as_of` |

## Amendments

FINRA OTC lists may be amended. The bitemporal store keeps prior versions:

- `as_of` between V1 and V2 availability → V1
- `as_of` after V2 availability → V2

File-based sources preserve `content_hash` and `record_version` on change.

## Known gaps

- NYSE National / NYSE Texas: no separate public threshold publisher discovered (Aug 2026)
- IEX / MEMX: no independent threshold list; route via primary listing authority
- Borrow, CTB, locates, utilization: separate unimplemented family
- Threshold status does not reveal hidden FTD qualification path

## Testing

```powershell
python -m unittest discover -s tests/short_intelligence -v
```

Live opt-in:

```powershell
$env:IMP_NYSE_REGSHO_LIVE = "1"
$env:IMP_FINRA_OTC_THRESHOLD_LIVE = "1"
$env:IMP_CBOE_REGSHO_LIVE = "1"
python tools/short_intelligence/threshold_coverage_report.py
```

## Security

No new credentials for NYSE or Cboe. FINRA reuses existing OAuth token manager. No tokens in evidence.
