# Futures Current State Audit (Deliverable 1)

**Status:** Authoritative baseline before F1+ cooperative redesign  
**Date:** 2026-08-18  
**Authority:** Subordinate to `THREE_LANE_ROADMAP_RECONCILIATION.md` for sequencing

---

## 1. Executive summary

The Futures lane today is a **fixture-first ES depth integration** (Phase 14 `PASS`) with optional read-only donor bridge to Eric_futuresX. It is **not** a forward market-state, curve, carry, positioning, or leverage intelligence engine. Estimated implementation vs redesign target: **~5–8%**.

The lane correctly fails closed on missing data but incorrectly labels depth-derived imbalance as `futures_positioning` in the whale family taxonomy.

---

## 2. Data flow (current)

```text
es_depth_slice.json (ADMITTED-L2-ES-001)
        OR
FuturesX bridge :8788 (not replay-admitted)
        ↓
FixtureFuturesProvider
        ↓
Whale envelope (futures_positioning family)
        ↓
futures_lane.py patterns (depth imbalance, OFI, RTH gate)
        ↓
futures_projections.py → UI workspace /explore
```

No canonical `FuturesContract`, no curve snapshot, no COT, no margin engine, no roll state beyond implicit `contract_month` string in fixture.

---

## 3. Implementation inventory

| Component | Path | Status |
|---|---|---|
| Depth imbalance signal | `donor_patterns/futures_lane.py` | IMPLEMENTED |
| Quarterly contract month helper | `donor_patterns/futures_lane.py` | IMPLEMENTED (family-level only) |
| Fixture provider | `providers/adapters/fixture_futures.py` | IMPLEMENTED |
| Donor bridge client | `donor_bridge/futures_client.py` | IMPLEMENTED |
| UI workspace | `ui/src/components/futures/` | IMPLEMENTED |
| Lane acceptance | `tools/integration/futures_lane_acceptance.py` | IMPLEMENTED |
| Canonical futures contract | `contracts/futures.py` | **F1 NEW** |
| Roll engine | `futures/roll.py` | **F1 NEW** |
| Notional / tick economics | `futures/notional.py` | **F1 NEW** |
| Curve engine | — | NOT STARTED |
| Basis engine | — | NOT STARTED |
| Carry engine | — | NOT STARTED |
| COT / positioning | — | NOT STARTED |
| Margin / leverage stress | — | NOT STARTED |
| Asset-family models | — | NOT STARTED |
| Cross-lane futures publisher | `cross_lane_adapter.py` | **PARTIAL** (depth only) |
| Futures EV inputs | — | NOT STARTED |
| Simulator rolls/margin | `execution/simulator.py` | NOT STARTED (bar-only) |

---

## 4. Features (current)

| Feature | Source | Correct? | Owner |
|---|---|---|---|
| Depth imbalance ratio | L2 fixture | Partial — contrarian signal, not positioning | Order Flow semantics |
| OFI snapshot delta | L2 fixture | Valid microstructure | Order Flow |
| RTH gate | `is_rth()` | Valid session label | Futures (session context) |
| `contract_month` YYYYMM | Fixture field | Partial — not full contract_id | Futures F1 |
| `imbalance_signal` | Depth logic | Valid as order-book hypothesis | Order Flow interpretation |
| `futures_positioning` whale label | Phase 14 naming | **Incorrect semantics** | Misleading — not COT |

---

## 5. Strategies / simulator

- No futures-specific strategies in IMP canonical path.
- FuturesX donor has ORB/backtest experiments — **not admitted** to IMP replay.
- `BarConservativeSimulator` supports equity bars only; no rolls, variation margin, or calendar spreads.

---

## 6. UI (current)

`/workspace/ES/futures` shows depth-derived snapshot table, imbalance signal, contract month, RTH state. Does not show curve, carry, positioning, leverage stress, or opportunity taxonomy.

---

## 7. Tests

| Test area | Coverage |
|---|---|
| Fixture provider envelopes | `tests/providers/test_providers.py` |
| Donor bridge | `tests/donor_bridge/test_futures_bridge.py` |
| Lane acceptance tool | `tests/integration/test_futures_lane_acceptance.py` |
| Contract schema F1 | `tests/contracts/test_futures_contract.py` |
| Roll / notional / COT PIT | `tests/contracts/test_futures_contract.py` |
| Curve / carry / COT integration | NOT STARTED |
| Cross-lane futures publisher | NOT STARTED |

---

## 8. Documentation (current)

| Document | Status |
|---|---|
| `docs/integration/FUTURES_LANE.md` | Operational integration guide |
| `FUTURESX_NOTES.md` | Donor operational notes |
| Futures redesign docs | **This audit + companion deliverables** |
| Cooperative master roadmap | Updated with F-series |

---

## 9. Dependency graph (current)

```text
PLATFORM P0 (PIT, replay, quality) [DONE]
        ↓
Phase 14 whale futures_positioning [DONE — depth only]
        ↓
Futures workspace UI [DONE]
        ↓
[F1 contract correctness] ← NEW
        ↓
[F2 roll / continuous series]
        ↓
[F3 curve / basis / carry]
        ...
```

Futures does **not** block Short Squeeze SS P2 or Options O1. F1 can proceed in parallel.

---

## 10. What Futures does NOT own today (correctly deferred)

- CVD / aggressor classification → Order Flow
- IV / Greeks / Q distribution → Options
- Stock borrow / short-interest mechanics → Short Squeeze
- Physical distribution P forecast → SHARED P2
