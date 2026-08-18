# Order Flow / Market Microstructure Current State Audit (Deliverable 1)

**Status:** Authoritative baseline before OF1+ cooperative redesign  
**Date:** 2026-08-18  
**Authority:** Subordinate to `FOUR_LANE_ROADMAP_RECONCILIATION.md` for sequencing

---

## 1. Executive summary

Order Flow today is a **fixture-first CVD bar lane** (Phase 10 `PASS`) plus **L2 snapshot lane** (Phase 13 `PASS`) and **ES futures depth** (Phase 14 `PASS`). It is **not** a full microstructure engine: no runtime trade ingest, no `ClassifiedTrade` pipeline at ingest, no liquidity dynamics, no execution forecasts.

Estimated implementation vs redesign target: **~12–15%** (post-OF1 module addition).

CVD remains an important derived feature but must not define the lane identity.

---

## 2. Concept → evidence map

| Concept | Documented | Implementation | Raw source | Transformation | Consumers | Simulator | UI | Tests |
|---|---|---|---|---|---|---|---|---|
| CVD | ADR-WHALE-003 | `cvd_formulas.py`, `order_flow/cvd.py` | NVDA fixture bars | Pre-baked `delta` + `cumulative_delta` | Cross-lane, squeeze | None | OrderFlow panel | `test_order_flow.py`, `test_order_flow_engine.py` |
| Aggressor | ADR-WHALE-003 | `order_flow/aggressor.py` | Fixture `quality` | `known/inferred/unknown` mapping | Whale envelope | None | Provenance column | `test_order_flow_engine.py` |
| Lee-Ready | Donor docs | `cvd_formulas.classify_aggressor` | — | Quote/tick rules | **Not wired at ingest** | None | — | `test_donor_patterns.py` |
| BVC | Donor docs | `cvd_formulas.bvc_buy_sell_volume` | — | Bar volume split | **Not wired** | None | — | `test_donor_patterns.py` |
| L1 spread/mid | OF3 target | `order_flow/l1.py` | Order book BBO | `compute_l1_state` | Workspace `latest_l1` | None | Partial | `test_order_flow_engine.py` |
| Queue imbalance | OF3 target | `order_flow/l1.py` | BBO sizes | QI formula | Cross-lane BOOK_IMBALANCE | None | — | `test_order_flow_engine.py` |
| Microprice | Foundation design §19 | `order_flow/l1.py` | BBO | Size-weighted mid | Workspace `latest_l1` | None | — | `test_order_flow_engine.py` |
| OFI | Cont-Kukanov-Stoikov | `cvd_formulas.ofi_events` | L2 snapshots | BBO-only `snapshot_ofi` | Order book panel | None | OFI column | `test_donor_patterns.py` |
| Depth imbalance | ADR-WHALE-006 | `order_book_lane.depth_imbalance` | L2 fixture | Bid/ask depth ratio | Order book, futures | None | Ratio display | `test_order_book.py` |
| Book direction label | Phase 13 UI | `direction_from_imbalance` | Ratio | Momentum policy | NVDA order book | None | Direction label | `test_donor_patterns.py` |
| Futures depth signal | FuturesX donor | `futures_lane.depth_imbalance_signal` | ES fixture | **Contrarian** policy | Futures workspace | None | Imbalance signal | `test_futures_lane` |
| Cross-lane evidence | `cross_lane/evidence.py` | `cross_lane_adapter.py` | Workspace payloads | CVD slope, aggression | Squeeze bridge | None | — | `test_cross_lane_adapter.py` |
| Execution | Phase 7 | `execution/simulator.py` | OHLCV bars | Bar conservative fill | Risk sim | Bar-only | Sim lab | `test_risk_simulation.py` |
| MBO / queue | Roadmap OF10 | — | — | — | — | — | — | — |
| Liquidity dynamics | Roadmap OF6 | — | — | — | — | — | — | — |

---

## 3. Data flow (current)

```text
nvda_order_flow_slice.json (ADMITTED-CVD-NVDA-ORDERFLOW-001)
        ↓
FixtureOrderFlowProvider (reads pre-baked delta — does NOT call classify_aggressor)
        ↓
Whale envelope (order_flow family)
        ↓
order_flow/cvd.py → cvd_summary in workspace payload
        ↓
cross_lane_adapter → AGGRESSIVE_BUY/SELL, CVD_SLOPE evidence
```

```text
nvda_depth_slice.json (ADMITTED-L2-NVDA-001)
        ↓
FixtureOrderBookProvider
        ↓
order_book_lane.py (imbalance, BBO OFI)
        ↓
order_flow/l1.py → latest_l1 in workspace payload
        ↓
cross_lane_adapter → BOOK_IMBALANCE_BID/ASK evidence
```

---

## 4. Implementation inventory

| Component | Path | Status |
|---|---|---|
| Lee-Ready / BVC formulas | `donor_patterns/cvd_formulas.py` | IMPLEMENTED (library) |
| ClassifiedTrade contract | `order_flow/contracts.py` | **OF1 NEW** |
| Aggressor classification | `order_flow/aggressor.py` | **OF1 NEW** |
| CVD with confidence | `order_flow/cvd.py` | **OF2 NEW** |
| L1 / microprice | `order_flow/l1.py` | **OF3 NEW** |
| OrderFlowEvidence contract | `order_flow/evidence.py` | **OF3 NEW** |
| Quality taxonomy | `order_flow/quality.py` | **OF1 NEW** |
| Fixture order-flow ingest | `providers/adapters/fixture_order_flow.py` | IMPLEMENTED (pre-baked delta) |
| Fixture order-book ingest | `providers/adapters/fixture_order_book.py` | IMPLEMENTED |
| Cross-lane publisher | `donor_bridge/cross_lane_adapter.py` | **ENHANCED** |
| Book reconstruction (MBO) | — | NOT STARTED |
| Liquidity engine | — | NOT STARTED (OF6) |
| Execution forecasts | — | NOT STARTED (OF9) |
| Short-horizon forecasts | — | NOT STARTED (OF8) |

---

## 5. Semantic audit

| Issue | Severity | Evidence |
|---|---|---|
| Ingest does not classify trades at runtime | HIGH | `fixture_order_flow.py` reads `delta` from JSON |
| NVDA momentum vs ES contrarian imbalance labels | MEDIUM | `order_book_lane` vs `futures_lane` |
| `futures_positioning` whale family for depth | MEDIUM | Phase 14 naming |
| `AGGRESSIVE_BUY_PRESSURE` naming | LOW | Now clarified as net signed volume |
| OFI uses BBO only despite multi-level fixture | MEDIUM | `snapshot_ofi` |
| No microstructure-aware simulator | HIGH | `BarConservativeSimulator` only |

**Correct language in codebase:** No literal "more buyers than sellers" found.

---

## 6. Related documents

- `ORDER_FLOW_TARGET_ARCHITECTURE.md`
- `ORDER_FLOW_DISCREPANCY_REGISTER.md`
- `FOUR_LANE_ROADMAP_RECONCILIATION.md`
- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`
