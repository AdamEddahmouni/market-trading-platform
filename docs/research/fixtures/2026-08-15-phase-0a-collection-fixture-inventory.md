# Phase 0A collection fixture inventory (read-only)

**Inventory date:** 2026-08-15  
**Scope:** Collection root `ROOT-8A4D17C2`; offline enumeration only  
**Method:** File metadata, LFS-pointer detection (files &lt; 200 bytes), SHA-256 on
selected non-pointer candidates; no LFS fetch, no donor execution, no network  
**Authority:** Supports Phase 0A planning only; does not authorize implementation,
copying, or `DF-001`/`DF-002` evaluation

## Summary

| Category | Count / finding |
|---|---|
| Git LFS pointers observed (Eric_futuresX) | 20 |
| Non-pointer ES **event** objects locally verifiable | **0** |
| Non-pointer ES-related metadata locally available | 4 (`manifest.json`, `metadata.json`, `condition.json`, `symbology.json`) |
| Non-pointer synthetic ES-shaped smoke sample | 1 (`.smoke_data/es_level2_data.csv`, 6,831 bytes) |
| Other donor market-bar bytes (non-ES) | Several (equity intraday, OHLCV demo) |
| `DF-001` aggregate feasibility | **BLOCKED** pending admitted-source decision |

## Eric_futuresX (`PROTO-FUTURESX-001`)

All primary ES market-data payloads are **Git LFS pointers** (134 bytes each).
Objects are **not** locally available. Preservation manifest digest
`E4C8EC59B4D127D7A8B8AA5E1FC538DA79AE3ABFDF8898ADA42D93DE2B43DF38` records
20 pointers.

### Notable LFS pointers (declared object size)

| Logical role | Declared bytes | Pointer state |
|---|---:|---|
| `glbx-mdp3-20100606-20250425.ohlcv-1m.csv` | 867,774,289 | LFS pointer only |
| `es_level2_data.csv` | 231,641,168 | LFS pointer only |
| `market_depth_rth_before_june9.db` | 180,203,520 | LFS pointer only |
| `ticker_data/ES/ES.csv` | 334,693,447 | LFS pointer only |
| `ticker_data/ES/ESold.csv` | 337,221,569 | LFS pointer only |
| `ticker_data/ES/ESold2.csv` | 337,246,152 | LFS pointer only |
| `ticker_data/SPY/SPY-1m-databento.csv` | 137,337,020 | LFS pointer only |
| `symbology.csv` | 3,889,319 | LFS pointer only |
| Mid-price timestamp CSVs (6 files) | 4.8M–12.5M each | LFS pointer only |
| Backtest trade CSVs (4 files) | 1.5K–2.4K each | LFS pointer only |
| `spy_data.csv`, `spxl_data.csv` | ~233K each | LFS pointer only |

### Locally available non-pointer ES-adjacent artifacts

| Artifact | Bytes | SHA-256 | Role | `DF-001` relevance |
|---|---:|---|---|---|
| `ticker_data/ES/manifest.json` | 2,342 | (job manifest) | Databento batch job `GLBX-20250427-8XCM5AR458` file list + remote URLs | Metadata only; not event records |
| `ticker_data/ES/metadata.json` | 683 | (query metadata) | Dataset `GLBX.MDP3`, schema `ohlcv-1m`, symbol `ES.FUT` | Metadata only |
| `ticker_data/ES/condition.json` | 559,416 | — | Databento condition/symbology sidecar | Metadata only |
| `ticker_data/ES/symbology.json` | 55,084 | — | Instrument symbology mapping | Metadata only |
| `.smoke_data/es_level2_data.csv` | 6,831 | `6A4AE5D34CC933C85A03A8E6FF1903981D59F0DBBD91CD16297A4913C69A3B09` | Synthetic depth smoke rows (`timestamp,bids,asks`) | Non-pointer bytes exist but provenance is synthetic smoke, not a pinned ES session; license/entitlement unresolved for platform use |

Databento job metadata in `manifest.json` pins expected hashes for pointer
targets (for example `ohlcv-1m` SHA-256
`ef7698082bb81d90e6a41871af058c40369e8b7a918e1ba8039f9f6334390fc3`) but those
bytes are not present locally.

## Trading CVD Bubble (`PROTO-CVD-001`)

| Artifact | Bytes | SHA-256 | Notes |
|---|---:|---|---|
| `demo_data/candles_1min.jsonl.gz` | 1,289,151 | `64492DEF7D77C004D357925CDF974B2239590188A739E82F688FF08CD54B8AC9` | NVDA 1m OHLCV + estimated buy/sell volume (`quality: bvc`, `source: ibkr_hist`); equity not ES futures |

## Short Squeeze (`PROTO-SHORTSQ-001`)

| Artifact | Bytes | SHA-256 | Notes |
|---|---:|---|---|
| `tests/fixtures/validation/outcome_amendment/biya_market_bars_intraday.jsonl` | 8,046,257 | `6895533AA441AE309BD944AE9AD2ACAB81B348CE972DB7E4287BCFF264389E3A` | Equity intraday bars test fixture; nested Git repo; rights via prototype license |

Large runtime snapshots and acquisition exports exist but are research/private
state; not proposed as platform fixtures without separate rights review.

## DS-340W (`PROTO-DS340W-001`)

| Artifact | Bytes | Notes |
|---|---:|---|
| `cleaned_fantasy_football_data.xlsx` | 820,049 | Football annual table; rights unresolved; not financial market data |

## GridIQ (`PROTO-GRIDIQ-001`)

| Artifact | Bytes | Notes |
|---|---:|---|
| `gridiq-backend/gridiq.db` | 196,608 | Private SQLite; schema/count only in donor notes; excluded from fixture candidacy |

## Governed repository (`ROOT-2E7C91F4`)

No admitted-source event objects under `integrated-market-platform/`. Phase 0
evidence bundles are governance artifacts only.

## `DF-001` feasibility assessment

**Current state: BLOCKED.**

Passing predicates require a **selected source object** that:

1. exists as non-pointer bytes locally (or in an explicitly authorized governed
   fixture path after procurement);
2. matches a pinned SHA-256;
3. yields ≥1 parser-readable **event** record under an approved offline parser
   report;
4. has license/entitlement classification recorded.

No object in the collection currently satisfies all four for an ES futures
event session. The nearest candidates fail for distinct reasons:

| Candidate path | Blocker |
|---|---|
| Eric_futuresX LFS targets | Pointer only; retrieval prohibited in Phase 0A characterization |
| Eric_futuresX metadata JSON | Not event records |
| Eric_futuresX smoke CSV | Synthetic smoke; not pinned ES session; entitlement unclear |
| CVD demo gzip | Equity OHLCV demo; not ES; donor copy prohibited |
| Short Squeeze intraday JSONL | Equity bars; nested-repo rights; not ES |

## Admitted-source paths (planning options)

These are **planning options**, not selections. Principal must authorize one
before `DF-001` evidence generation.

1. **Procure lawful non-pointer bytes** for a pinned Databento `GLBX.MDP3` object
   (for example the already-metadata-pinned `ohlcv-1m` export) into a governed,
   rights-documented fixture path **without** copying from Eric_futuresX LFS
   pointers or using Git LFS retrieval during characterization.
2. **Admit a non-ES admitted source** under Revision 3 alternative-source rules
   (for example equity intraday bars) if Phase 1 ADR scope is explicitly narrowed;
   capability manifest must not claim ES futures semantics absent from the source.
3. **Admit a governed synthetic fixture** produced inside `ROOT-2E7C91F4` under
   implementation authorization, with explicit synthetic classification and zero
   implied production entitlement; must still satisfy non-pointer, pinned-hash,
   and parser-read predicates.
4. **Remain BLOCKED** until an external lawful source is procured; Phase 1
   fixture-dependent ADRs stay blocked.

## Negative capability anchor

Eric_futuresX metadata explicitly documents `ohlcv-1m` for `ES.FUT`. If only
that schema is eventually admitted, the canonical **`ohlcv-1m`-only failure case**
(`SC-002` negative fixture) applies: sweep/CVD capabilities must be explicitly
false in the capability manifest (`DF-002`).
