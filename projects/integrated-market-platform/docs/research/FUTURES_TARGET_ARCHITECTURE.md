# Futures Target Architecture (Deliverable 5)

**Status:** Target design — implementation gated by `THREE_LANE_ROADMAP_RECONCILIATION.md`  
**Date:** 2026-08-18

---

## 1. Architectural thesis

Futures evaluates **forward market state across contracts** — curve, carry, basis, positioning, fundamentals, order flow, and leverage — to surface outright, curve, and relative-value opportunities. It does **not** replace Options pricing, Short Squeeze equity mechanics, or Order Flow microstructure ownership.

```text
UNDERLYING / ECONOMIC STATE
+
FUTURES TERM STRUCTURE
+
CARRY
+
POSITIONING
+
ASSET-SPECIFIC FUNDAMENTALS
+
ORDER FLOW (consumed)
+
LEVERAGE / LIQUIDITY
        ↓
FUTURES MARKET STATE
        ↓
OUTRIGHT / CURVE / RV OPPORTUNITIES
        ↓
SHARED EXPECTED-VALUE LAYER [P4]
        ↓
SIMULATION / EXECUTION [F10]
```

---

## 2. Layer diagram

```text
                         RAW DATA
                              │
                              ▼
                    PROVIDER ADAPTERS
                              │
                              ▼
              NORMALIZED FUTURES CONTRACTS          [F1]
                              │
                              ▼
               QUALITY + PROVENANCE + PIT           [P0]
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     ROLL ENGINE         CURVE ENGINE      BASIS ENGINE       [F2/F3]
          │                   │                   │
          └─────────┬─────────┘                   │
                    ▼                             │
              CARRY ENGINE                        │
                    │                             │
          ┌─────────┴─────────┐                   │
          ▼                   ▼                   ▼
    POSITIONING/OI      ORDER FLOW (consume)  FUNDAMENTALS      [F4/F6/F7]
          │                   │                   │
          └─────────┬─────────┴───────────────────┘
                    ▼
            LEVERAGE / MARGIN STRESS                [F8]
                    │
                    ▼
         ASSET-FAMILY PLUGIN MODELS                 [F6]
                    │
                    ▼
            FUTURES MARKET STATE
                    │
                    ▼
         CROSS-LANE EVIDENCE BUS                    [P3]
                    │
                    ▼
         RELATIVE-VALUE OPPORTUNITIES               [F9]
                    │
                    ▼
         SHARED EV + SIMULATOR                      [P4/F10]
                    │
                    ▼
              EXPLAINABILITY
```

---

## 3. Contract flow

1. Provider delivers contract specs + quotes + OI + margin (as entitled).
2. Normalized to `FuturesContract` with `contract_id` ≠ `instrument_family`.
3. `FuturesContractSpec` versioned for historical simulation.
4. `event_time`, `available_time`, `ingested_time` on every record.
5. Quality flags block downstream when missing — never neutral defaults.

---

## 4. Roll flow

1. `ContractLiquidity` per listed contract.
2. `select_lead_contract()` — deterministic rule version.
3. Separate: `nearest_expiry`, `lead_contract`, `highest_volume`, `highest_OI`, `execution_contract`.
4. `RollState`: PRE_ROLL | ROLLING | POST_ROLL | EXPIRING.
5. Continuous series explicitly tagged — never masquerade as tradeable contract.
6. PnL and fills use actual contracts + roll transactions.

---

## 5. Curve / carry flow

1. `FuturesCurveSnapshot` with contracts[], prices[], OI[], volume[].
2. Derived: level, slope, curvature, calendar spreads, contango/backwardation strength.
3. `BasisObservation` with explicit `BasisDefinition`.
4. Carry per family — documented formula, inputs, assumptions, horizon.
5. Fair value ≠ directional forecast — hard distinction preserved.

---

## 6. Positioning flow

1. `FuturesPositioningSnapshot` for COT and exchange OI analytics.
2. COT: `observation_time` (Tuesday) vs `publication_time` (Friday).
3. Crowding features — hypotheses, not ground truth.
4. OI change + price joint metrics exposed as hypotheses only.

---

## 7. Asset-family plugin interface

```text
FuturesFamilyModel (conceptual)
  required_capabilities()
  fundamental_features()
  fair_value_context()
  curve_interpretation()
  positioning_interpretation()
  event_context()
  forecast_features()
  risk_features()
```

Families: EQUITY_INDEX, TREASURY, SHORT_RATE, FX, ENERGY, AGRICULTURE, METALS, CRYPTO_FUTURES (future).

---

## 8. Cross-lane evidence (Futures publishes)

| Evidence | Consumer lanes |
|---|---|
| Forward price / curve | Options (options on futures) |
| Carry / basis | Options fair-value context |
| Positioning / crowding | Options, Short Squeeze (aggregate index) |
| Macro/event state | Short Squeeze, Options |
| Leverage stress | Order Flow confirmation |
| Order flow confirming (depth) | Short Squeeze ignition context |

Futures **consumes** from Options (IV, tails), Order Flow (CVD, DOM), Short Squeeze (aggregate squeeze regime), SHARED P2 (physical P).

---

## 9. Squeeze taxonomy (Futures-owned, distinct from Short Squeeze)

| Mechanism | Causal chain |
|---|---|
| Leveraged short liquidation | price ↑ → short losses → margin pressure → buyback → amplification |
| Leveraged long liquidation | price ↓ → long losses → margin pressure → sell → decline |
| Delivery squeeze / corner | scarce deliverable + spot-month concentration + delivery obligation |

Do **not** reuse Short Squeeze state machine.

---

## 10. Opportunity taxonomy

TREND_LONG/SHORT, CARRY_LONG/SHORT, CURVE_STEEPENER/FLATTENER, CALENDAR_SPREAD, BASIS_CONVERGENCE, RELATIVE_VALUE, EVENT_DIRECTIONAL, LONG/SHORT_LIQUIDATION_RISK, DELIVERY_STRESS, NO_CLEAR_EDGE.

No universal Futures Score.

---

## 11. File map (target)

| Module | Path |
|---|---|
| Contract model | `contracts/futures.py` |
| Quality taxonomy | `contracts/futures_quality.py` |
| Roll engine | `futures/roll.py` |
| Notional / ticks | `futures/notional.py` |
| Curve engine | `futures/curve.py` (F3) |
| Basis engine | `futures/basis.py` (F3) |
| Carry engine | `futures/carry.py` (F3) |
| Positioning | `futures/positioning.py` (F4) |
| Leverage stress | `futures/leverage_stress.py` (F8) |
| Family plugins | `futures/families/` (F6) |
| Cross-lane adapter | `donor_bridge/cross_lane_adapter.py` |
