# Three-Lane Roadmap Reconciliation (Deliverable 2)

> **SUPERSEDED for cooperative sequencing.** Cross-lane dependency sequencing now lives in
> [`PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`](PLATFORM_COOPERATIVE_MASTER_ROADMAP.md). This
> reconciliation is retained for its per-lane detail and dependency rationale.

**Status:** Superseded for cooperative sequencing (retained as per-lane reference)  
**Date:** 2026-08-18  
**Authority:** Extends `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md` and `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`; does not replace them

---

## Purpose

Reconcile Short Squeeze, Options, and **Futures** cooperative redesigns into one dependency-aware platform roadmap. Futures emerges as the forward market-state, curve, carry, positioning, and leverage intelligence engine — not a third isolated architecture.

---

## 1. Lane identity (preserve boundaries)

| Lane | Core question | Primary model |
|---|---|---|
| Short Squeeze | Forced/reflexive equity buying likely? | STRUCTURE → CONSTRAINT → IGNITION → REFLEXIVITY → EXHAUSTION |
| Options | What distribution is priced (Q) vs forecast (P)? | P vs Q → MISPRICING → STRATEGY |
| Futures | What forward state across contracts? What RV opportunity? | UNDERLYING + CURVE + CARRY + POSITIONING + FLOW + LEVERAGE → OPPORTUNITY |
| Order Flow | What are buyers/sellers/liquidity doing now? | TRADES + DOM + CVD → MICROSTRUCTURE |

---

## 2. Futures roadmap (F1–F11)

```text
PLATFORM P0 — correctness foundation          [MOSTLY DONE]
PLATFORM P1 — shared market primitives        [PARTIAL]
FUTURES F1 — contract correctness             [COMPLETE — fixture scope]
FUTURES F2 — roll / continuous series           [COMPLETE — fixture]
OPTIONS O1 — contract/chain correctness         [COMPLETE — fixture]
SHORT SQUEEZE SS P2 — structural vulnerability  [PLANNED — live lending]
FUTURES F3 — curve / basis / carry              [COMPLETE — fixture]
OPTIONS O2 — IV + surface                       [COMPLETE — fixture]
SHARED P2 — physical distribution P             [COMPLETE — fixture]
FUTURES F4 — OI / COT positioning               [COMPLETE — fixture]
FUTURES F5 — trend + carry baselines              [COMPLETE — fixture]
SHORT SQUEEZE SS P3 — baseline models           [COMPLETE — fixture]
OPTIONS O3–O4 — Q and P vs Q                    [COMPLETE — fixture]
SHARED P3 — cross-lane fusion                   [COMPLETE — fixture]
FUTURES F6 — asset-family models                [COMPLETE — fixture]
FUTURES F7 — macro / fundamental events           [COMPLETE — fixture]
OPTIONS O5–O7 — flow, dealer, event vol         [COMPLETE — fixture]
FUTURES F8 — leverage / liquidation stress        [COMPLETE — fixture]
SHORT SQUEEZE SS P4–P5 — confirmation, fuel     [COMPLETE — fixture]
FUTURES F9 — relative value spreads               [COMPLETE — fixture]
OPTIONS O8 — strategy optimizer                 [COMPLETE — fixture]
SHARED P4 — EV layer                            [COMPLETE — fixture]
FUTURES F10 — simulator extensions                [COMPLETE — fixture]
OPTIONS O9 — options simulator                  [COMPLETE — fixture]
SHORT SQUEEZE SS P6 — exhaustion                [COMPLETE — fixture]
FUTURES F11 — advanced models                     [IMPLEMENTED fixture]
OPTIONS O10–O11                                 [O10 IN PROGRESS (fixture gates validated); O11 blocked Phase C]
SHARED P5 — portfolio intelligence              [DEFERRED]
```

---

## 3. Ownership matrix (Deliverable 3)

| Capability | Platform | Short Squeeze | Options | Futures | Order Flow |
|---|---|---|---|---|---|
| Point-in-time | **Owns** | Consumes | Consumes | Consumes | Consumes |
| Quality + provenance | **Owns** | Consumes | Consumes | Consumes | Consumes |
| Provider registry | **Owns** | Donor | Consumes | Consumes | Consumes |
| Deterministic replay | **Owns** | Partial | Fixture | Fixture | Fixture |
| CVD / aggressor | Infra | Consumes | Consumes | Major consumer | **Owns** |
| DOM / book imbalance | Infra | Consumes | Context | Major consumer | **Owns** |
| Physical distribution P | **Shared** | Consumes | Major consumer | Consumes | Inputs |
| Risk-neutral Q | Contract | Context | **Owns** | Context | No |
| P vs Q edge | — | No | **Owns** | No | No |
| Stock borrow / SI | Infra | **Owns** | Context | N/A | N/A |
| Option contracts / IV | Infra | — | **Owns** | Context (on futures) | No |
| Futures contracts / specs | Infra | — | Consumes | **Owns** | No |
| Futures curve / carry | Infra | Context | Consumes | **Owns** | Context |
| Basis (futures) | Infra | No | Partial | **Owns** | No |
| COT / futures positioning | Infra | Context | Context | **Owns** | No |
| OI (options) | Infra | Consumes | **Owns** | **Owns** (futures OI) | No |
| Leverage stress (futures) | Contract | Context | Context | **Owns** semantics | Confirms |
| Liquidation (equity cover) | Infra | **Owns** | Partial | Different mechanism | Context |
| Delivery squeeze | Infra | No | No | **Owns** | No |
| Causal squeeze states | — | **Owns** | Consumes | No (different) | No |
| Macro events / surprise | Infra | Consumes | O7 | F7 consumer | No |
| EV / execution | **Shared** | Domain input | Domain input | Domain input | Input |
| Simulator | **Shared** | Extends SS P6 | Extends O9 | Extends F10 | Data source |

---

## 4. Shared work (do not duplicate in Futures)

| Primitive | Location | Futures action |
|---|---|---|
| CVD / aggressor | Order Flow / `cvd_formulas.py` | Consume `OrderFlowEvidence` |
| Physical P forecast | SHARED P2 (planned) | Consume; add curve/RV outputs separately |
| EV mathematics | SHARED P4 | Supply return dist, margin, carry, roll costs |
| Bar simulator core | `execution/simulator.py` | Extend F10 — no parallel simulator |
| Cross-lane contract | `cross_lane/evidence.py` | Publish + consume via contracts |
| Event/catalyst | Catalyst lane | Consume for macro surprise F7 |

---

## 5. Futures-owned (do not rebuild elsewhere)

Contract specs, multipliers, ticks, expiration, settlement, delivery metadata, roll state, lead contract, continuous series semantics, basis definitions, curve snapshots, carry (per family), futures OI interpretation, COT positioning, margin/leverage stress, delivery squeeze taxonomy, calendar spreads, family-specific fundamentals, futures opportunity taxonomy.

---

## 6. Cross-lane contracts

### Futures publishes → consumers

| Signal | Consumer | Phase |
|---|---|---|
| `FUTURES_CURVE_CONTANGO` / `BACKWARDATION` | Options, UI | F3 / P3 |
| `FUTURES_CARRY_POSITIVE` / `NEGATIVE` | Options | F3 |
| `FUTURES_POSITIONING_CROWDED_*` | Options, SS (aggregate) | F4 |
| `FUTURES_LONG/SHORT_LIQUIDATION_RISK` | Order Flow, UI | F8 |
| `FUTURES_MACRO_EVENT_RISK` | SS, Options | F7 |
| `FUTURES_ORDER_FLOW_CONFIRMING` | SS (index context) | P3 (depth stub) |
| Forward/curve evidence objects | Options on futures | F3 |

### Futures consumes → producers

| Source | Signals | Owner |
|---|---|---|
| Order Flow | CVD, DOM, trade velocity | Order Flow |
| Options | IV, tails, skew, event move, dealer pressure | Options |
| Short Squeeze | Aggregate squeeze regime, concentration | Short Squeeze |
| SHARED P2 | Physical return distribution | Platform |
| Catalyst | Macro surprise, event state | Platform/Catalyst |

### Prevent circularity (F75)

```text
INVALID: Futures(t) → Options forecast(t) → Futures(t)
VALID:   Options flow(t) → Futures forecast(t+1)
VALID:   Futures risk regime(t) → Squeeze state(t+1)
```

---

## 7. Conflict analysis

### Parallel safe now

| Track | Work | Blocked by |
|---|---|---|
| Futures F1 | Contract schema + quality + notional | Nothing |
| Futures F2 | Roll engine v1 | F1 |
| Options O1 | Option contract schema | Nothing |
| SS P2 | Lending interfaces | Nothing |
| Platform P1 | Liquidity features | Nothing |
| Futures cross-lane depth publisher | `build_cross_lane_snapshot_from_futures` | Nothing |

### Coordination required

| Milestone | Risk | Resolution |
|---|---|---|
| Physical P | Futures might build own forecaster | SHARED P2 only |
| CVD in Futures lane | Duplicate Order Flow | Futures consumes evidence |
| `futures_positioning` whale name | Confuses COT | Document + split evidence types F-D-01 |
| Simulator | Three lane extensions | Single `simulator.py` with plugins |
| Equity squeeze vs futures liquidation | Mechanism conflation | Separate taxonomies |

### Futures does NOT block SS P2 or O1

### SHARED P2 blocks SS P3, O4, and Futures magnitude features that need physical P

### F1/F2 block trustworthy Futures backtests

---

## 8. Parallelizable work (next 90 days)

| Track | Work |
|---|---|
| Futures | F1 wire schema to fixtures; F2 roll tests; F3 curve schema + stub engine |
| Options | O1 chain plan; O2 IV research |
| SS | SS P2 lending |
| Platform | P1 liquidity; SHARED P3 wire options + futures publishers |
| Cross-lane | Circular dependency tests; evidence DAG for all three lanes |

---

## Related documents

- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`
- `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md`
- `FUTURES_TARGET_ARCHITECTURE.md`
- `FUTURES_DISCREPANCY_REGISTER.md`
- `CROSS_LANE_BOUNDARY_MATRIX.md`
