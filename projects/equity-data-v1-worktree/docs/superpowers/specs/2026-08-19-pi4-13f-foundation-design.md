# PI4 — 13F Foundation (strict filing `available_time` + QoQ position changes)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Fixture-first 13F holdings parse, per-line snapshots, quarter-over-quarter diff, PIT-safe position change actions  
**Prerequisites:** PI2 IMPLEMENTED, Whale Phase 9 EDGAR ingest

## 1. Purpose

Build the 13F-specific foundation layer: treat 13F as a quarterly holdings snapshot (not a live position), enforce strict filing-time `available_time`, and emit quarter-over-quarter `POSITION_*` actions only when the later filing is visible at `prediction_cutoff`.

## 2. Temporal rules (mandatory)

| Field | 13F semantics |
|---|---|
| `action_time` | `quarter_end` — behavior research only; never copyable |
| `available_time` | Filing `accepted_at` — sole replay visibility boundary |
| QoQ change visibility | Only when later filing's `available_time <= prediction_cutoff` |
| First appearance | `POSITION_INITIATED` at filing `available_time` |
| Missing prior quarter | Snapshot only; `OWNERSHIP_DELTA_UNAVAILABLE` retained |

Quality flags on every 13F action: `QUARTER_END_NOT_COPYABLE`, `POSITION_STALE`, `ENTRY_BASIS_UNKNOWN`, `DISCLOSURE_DELAYED`.

13F limitations (shorts omitted, hedges omitted, ~45-day lag) are documented via payload metadata `limitations: ["shorts_omitted", "hedges_omitted"]` and existing stale flags — no new enum churn.

## 3. Fixture schema

13F filings in EDGAR fixtures may include:

```json
{
  "form_type": "13F-HR",
  "filer": "Alpha Fund LP",
  "quarter_end": "2026-03-31",
  "accepted_at": "2026-05-15T12:00:00Z",
  "holdings": [
    {
      "cusip": "090683109",
      "issuer_name": "BIYA International Inc",
      "symbol": "BIYA",
      "shares": 100000,
      "value_usd": 1250000
    }
  ]
}
```

Instrument resolution: `holding.symbol` when present; else fixture top-level `symbol`.

Multi-holding filings fan out to one ledger envelope per holding line (distinct `instrument_id` per symbol).

## 4. QoQ diff semantics

Shares-based, deterministic, grouped by stable `participant_id` (filer-based for 13F):

| Prior | Current | Action |
|---|---|---|
| absent | shares > 0 | `POSITION_INITIATED` |
| shares > 0 | shares > prior | `POSITION_INCREASED` |
| shares > 0 | 0 < shares < prior | `POSITION_REDUCED` |
| shares > 0 | absent or 0 | `POSITION_EXITED` |
| equal | equal | no change action (snapshot only) |

Derived change actions use `action_time = quarter_end`, `available_time = current filing acceptance`, `quantity = abs(share delta)`.

Amendments: higher `source_revision_id` for same accession+quarter supersedes prior revision before diffing.

## 5. Out of scope

- Live SEC 13F XML parser
- CUSIP master / live symbol resolution
- Portfolio-weight / AUM / relative size (W4, PI5)
- Shorts/hedges inference from 13F data

## 6. Completion definition

PI4 is complete when fixture 13F holdings ingest per-line snapshots with correct PIT fields, QoQ diff emits `POSITION_*` actions with adversarial PIT tests passing, `INSTITUTIONAL_HOLDING_CHANGE` cross-lane signal publishes for unambiguous changes, and existing PI2/PI3 tests remain green.
