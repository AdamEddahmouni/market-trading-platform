# Phase 3F Cohort Expansion — Batch 04 Acquisition Plan

## Status

**Complete (2026-08-17).** BIYA yahoo-chart bars are imported, registered in private
batch-05 manifests, and frozen through Phase 3A (29/29 leakage audits).

## Discovery audit

| Source | Result |
|--------|--------|
| `batch01_discovery_rows.json` (13 scanner rows) | Exhausted — all symbols already in cohort |
| Phase 2V comparison manifest (KLRS, LBGJ, SG, SLS, TRVI) | Exhausted — all symbols already in cohort |
| Phase 3F Batch 01–03 news / prime-log / screening-universe sources | Exhausted — all US equity tickers already in cohort |
| Phase 3F Batch 01 `biya_news.jsonl` co-occurrence | **BIYA remains** (only ticker not on IBKR frozen-boundary track) |
| Archived `screener_snapshot.json` | Exhausted at 13 rows |
| KLOS identity conflict case | Excluded (`BLOCKED_CONFLICTING_IDENTITY`) |

Batch 04 adds **BIYA** to the IBKR frozen-boundary acquisition track. Phase 2V
evaluation boundaries (`BIYA_EARLIEST_BOUNDARY`, `BIYA_LATEST_BOUNDARY`) remain
unchanged and separate per ADR-0054.

## Cohort

Exactly one symbol:

| # | Symbol | Case ID | Frozen Boundary (UTC) | Discovery provenance |
|---|--------|---------|----------------------|----------------------|
| 1 | BIYA | BATCH3F04_BIYA_20260718 | 2026-07-18T13:37:55.017661Z | `biya_news.jsonl` (MT Newswires, 2026-07-20) |

Bar intake uses sanitized Phase 2V yahoo-chart intraday bars converted to
IBKR-shaped CSV via `scripts/acquisition/import_biya_yahoo_bars_to_ibkr_intake.py`
(documented provenance — not live IBKR Gateway collection).

Normalized discovery rows:
`intake/batches/phase-3f-cohort-expansion-04/normalized/batch3f04_discovery_rows.json`.

## Window adjustment

Identical to Phase 3E Stage 2:

| Parameter | Value |
|-----------|-------|
| Adjusted forward start | 2026-07-21T13:37:55Z |
| Adjusted forward end | 2026-07-22T13:37:55Z |
| Calendar shift | +72 hours (Saturday → Monday) |

## Non-goals

- No change to Phase 2V BIYA boundary evaluations
- No threshold tuning or Adam scoring calibration
- No replacement of Phase 2V yahoo-chart provenance with synthetic bars

## Acknowledged limitations

- Yahoo-chart bars are not IBKR TRADES bars; intake is IBKR-shaped for pipeline compatibility only.
- Borrow fee/availability remains UNKNOWN for BIYA at the frozen boundary.
- Detection remains UNEVALUABLE under Batch 07 price-level blocking at this boundary.
