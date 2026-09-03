# Order Flow / Market Microstructure Target Architecture (Deliverable 5)

**Status:** Cooperative redesign target  
**Date:** 2026-08-18

---

## Lane identity

Order Flow asks:

```text
Who is demanding immediacy?
Where is liquidity resting?
Where is liquidity appearing or disappearing?
How is the book responding to aggressive flow?
How fragile or resilient is the market?
What is likely over the next short horizon?
How should another strategy execute?
```

**CVD is a benchmark (M1), not the lane definition.**

---

## Target pipeline

```text
ORDERS + CANCELLATIONS + TRADES
        ↓
AGGRESSOR CLASSIFIER (ClassifiedTrade + provenance)
        ↓
TRADE FLOW (CVD, velocity, persistence)
        +
BOOK RECONSTRUCTION → L1 / L2 / MBO
        ↓
BOOK FLOW (OFI, adds/cancels, withdrawal, replenishment)
        ↓
LIQUIDITY ENGINE (spread, depth, resiliency, fragility)
        ↓
PRICE RESPONSE / IMPACT (absorption, exhaustion)
        ↓
MICROSTRUCTURE FORECASTS + EXECUTION FORECASTS
        ↓
OrderFlowEvidence → cross-lane bus
```

---

## Module ownership (`order_flow/`)

| Module | Owns |
|---|---|
| `contracts.py` | ClassifiedTrade, L1QuoteState, CVDState, BookPressureEvidence, OrderFlowEvidence |
| `aggressor.py` | Trade classification + AggressorSource provenance |
| `cvd.py` | CVD, slope, acceleration, confidence-weighted aggregates |
| `l1.py` | spread, mid, microprice, queue imbalance |
| `quality.py` | Order-flow quality flags |
| `evidence.py` | Cross-lane evidence assembly |
| `ofi.py` (OF4) | Versioned OFI with `ofi_method`, `ofi_version` |
| `liquidity.py` (OF6) | withdrawal, replenishment, resiliency, fragility |
| `impact.py` (OF6) | price response efficiency, impact decay |
| `forecast.py` (OF8) | MicrostructureForecast object |
| `execution_forecast.py` (OF9) | fill probability, slippage, adverse selection |

---

## Capability hierarchy

| Tier | Supports |
|---|---|
| L1 | CVD, spread, QI, microprice |
| L2/MBP | depth imbalance, multi-level OFI, sweep analysis |
| MBO | queue position, order lifetime, advanced fill model |

Every output carries `capability_tier`. Unavailable depth is never fabricated.

---

## Cross-lane contracts

```text
OrderFlowEvidence
LiquidityEvidence (OF6)
MicrostructureForecast (OF8)
ExecutionForecast (OF9)
```

Fields: `instrument`, `venue`, `horizon`, `event_time`, `available_time`, `producer_version`, `data_confidence`, `model_confidence`, `quality_flags`, `supporting_evidence`, `counter_evidence`.

Domain lanes consume — they do not recompute CVD/OFI internally.

---

## Model ladder (research)

```text
M0 — Null
M1 — CVD only (baseline)
M2 — CVD + spread
M3 — QI + microprice
M4 — OFI
M5 — Multi-level OFI
M6 — Liquidity dynamics
M7 — Full engineered microstructure
M8 — Advanced LOB ML (only after M1–M7 validated)
```

---

## Integration points

| Lane | Order Flow publishes | Lane interprets |
|---|---|---|
| Short Squeeze | CVD, OFI, ask depletion, velocity, fragility | IGNITION, CONFIRMATION, EXHAUSTION |
| Options | RV evidence, hedge-like pressure, execution quality | P forecast, execution ranking |
| Futures | CVD, DOM, microprice, fragility | intraday direction, liquidation timing |

**Order Flow never sets squeeze state, P vs Q, or futures carry.**

---

## Simulator cooperation (not fork)

Extend `execution/simulator.py` with capability-tiered book-aware fills (OF9–OF10). Expose `execution_model_version`, `book_model_version`, `queue_model_version`.
