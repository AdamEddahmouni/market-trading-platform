# Order Flow Joint Lane Report (Deliverable 11 — Final Cooperative Report)

**Date:** 2026-08-18  
**Scope:** Order Flow / Market Microstructure redesign integrated with Short Squeeze, Options, Futures, shared platform

---

## What Order Flow now owns

- `ClassifiedTrade` with `AggressorSource` provenance (OF1)
- CVD with `native/inferred/unknown` fractions and `cvd_confidence` (OF2)
- L1 primitives: spread, mid, queue imbalance, microprice (OF3)
- `BookPressureEvidence` — raw resting-depth metrics without domain directional labels
- `OrderFlowEvidence` cross-lane contract
- `OrderFlowQualityFlag` taxonomy
- Cross-lane signals: `AGGRESSIVE_BUY/SELL_PRESSURE`, `CVD_*_SLOPE`, `BOOK_IMBALANCE_BID/ASK`

**Module:** `src/market_platform_foundation/order_flow/`

---

## What CVD now means

```text
signed_volume = +quantity if buyer-initiated, -quantity if seller-initiated
CVD_t = Σ signed_volume
```

Workspace payloads expose `cvd_summary` with classification-quality metadata. CVD > 0 is **not** equivalent to BULLISH.

---

## What remains shared

- Event ordering, `available_time`, deterministic replay (Platform P0)
- Provider capability registry, quality engine, provenance (Platform)
- Physical forecast foundation (SHARED P2)
- EV / execution framework (SHARED P4) — Order Flow contributes execution inputs at OF9
- `execution/simulator.py` — to be extended, not forked
- Explanation graph infrastructure

---

## What Short Squeeze gains

- Confidence-weighted CVD evidence for ignition/confirmation/exhaustion research
- `BOOK_IMBALANCE` and aggression signals via cross-lane bus (interpretation stays in squeeze evaluator)
- Future: liquidity withdrawal + fragility for ignition beyond CVD-only (OF6, OF-Q3)

---

## What Options gains

- Short-horizon directional and RV context without Order Flow computing P vs Q
- Execution-quality evidence for strategy ranking (OF9)
- Ability to compare estimated hedge pressure to observed microstructure (wording: "consistent with")

---

## What Futures gains

- ES L2 as primary microstructure validation environment (Order Flow primitives, Futures context)
- CVD, OFI, microprice, fragility as intraday inputs (Futures interprets for liquidation/direction)
- Separation of raw `BookPressureEvidence` from FuturesX contrarian `depth_imbalance_signal` policy

---

## What Execution gains

- Foundation for fill probability, slippage, adverse selection forecasts (OF9)
- Path to book-aware simulator tiers without Order Flow-only fork

---

## What duplication was removed / avoided

- No fourth isolated architecture — integrated into `FOUR_LANE_ROADMAP_RECONCILIATION.md`
- No Order Flow-owned squeeze/options/futures semantics
- Book pressure separated from duplicate directional labels
- `AGGRESSIVE_SELL_PRESSURE` now symmetric with buy pressure

---

## What cross-lane contracts were added

- `OrderFlowEvidence` (`order_flow/evidence.py`)
- `BookPressureEvidence` (raw depth — domain applies interpretation)
- Enhanced workspace: `cvd_summary`, `latest_l1`
- `build_cross_lane_snapshot_from_order_book`

---

## What data remains missing

- Live tick ingest with native aggressor
- Historical MBO
- Sequence-number book reconstruction
- Multi-venue consolidated equity flow
- ES session lawful bytes (ADR-DATA-001)

---

## What remains research-only

- Liquidity withdrawal / replenishment / resiliency (OF6)
- Absorption / exhaustion formalization (OF7)
- Short-horizon ML forecasts (OF8)
- Execution forecasts (OF9)
- MBO queue modeling (OF10)
- Metaorder / whale identity (OF11)
- Deep LOB ML (OF12)

---

## What the next shared milestone should be

**SHARED P3 — Cross-lane evidence fusion (partial → complete)**

Parallel work:
1. **OF4** — versioned OFI book-flow on admitted ES/NVDA fixtures
2. **Options O1** — contract schema (independent)
3. **SS P2** — lending interfaces (independent)
4. Wire `OrderFlowEvidence` into squeeze explanation graph with traceable refs

---

## Test report

Run: `python -m unittest discover -s tests -p "test_*.py"`

New tests: `tests/order_flow/test_order_flow_engine.py` (OF1–OF3 coverage)

---

## Design rule (permanent)

> CVD measures net aggressive executed flow. OFI measures book state changes. Liquidity determines absorption capacity. Resiliency determines repair speed. Price impact reveals effectiveness. Order Flow combines these as evidence — no single indicator is a magical signal.
