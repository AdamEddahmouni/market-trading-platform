# Options ↔ Short Squeeze Roadmap Reconciliation (Deliverable 2)

**Status:** Authoritative prerequisite for Options lane redesign implementation  
**Date:** 2026-08-18  
**Authority:** Extends (does not replace) `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`, `CROSS_LANE_BOUNDARY_MATRIX.md`, ADR-SQZ-001

## Purpose

Before any major Options lane implementation, this document reconciles the proposed Options causal redesign (P vs Q distribution intelligence) with the **already-planned and partially-implemented** Short Squeeze causal redesign. The goal is one cooperative platform roadmap, not two competing redesigns.

---

## 1. Short Squeeze Roadmap Reconstruction

### 1.1 Authoritative documents

| Document | Role |
|---|---|
| `SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md` (squeeze-core) | Causal model: FUEL × CONSTRAINT × IGNITION × REFLEXIVITY |
| `SHORT_SQUEEZE_TARGET_ARCHITECTURE.md` | Data flow, cross-lane dependencies |
| `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md` | Phases P0–P6 |
| `SHORT_SQUEEZE_DISCREPANCY_REGISTER.md` | D-01 through D-14 |
| `CROSS_LANE_BOUNDARY_MATRIX.md` | Signal ownership |
| `ADR-SQZ-001` | Causal state machine semantics |
| `ADR-TIME-001` | Timestamp mapping for squeeze bars |

### 1.2 Short Squeeze dependency graph

```text
PLATFORM P0 (PIT, provenance, quality, replay)
    │
    ├── PLATFORM P1 (price/volume features, CVD via order flow)
    │
    ├── SS P0/P1 [DONE] causal contracts, evaluator, hysteresis, UI, order-flow cross-lane
    │
    ├── SS P2 [PLANNED] lending, velocity metrics, attention, catalyst interfaces
    │
    ├── SS P3 [PLANNED] mechanism labels, logistic/hazard, calibration
    │
    ├── SS P4 [COMPLETE — fixture scope] streaming transitions, live order-flow confirmation
    │
    ├── SS P5 [COMPLETE — fixture scope] exhaustion, remaining fuel
    │
    └── SS P6 [COMPLETE — fixture scope] temporal exhaustion, borrow normalization, O5/O6 reversal
        └── SS P7 [COMPLETE — fixture scope] ShortPainDistribution, magnitude, ensemble, calibrated horizons, D-14 simulator replay
```

### 1.3 Short Squeeze state machine (owner: Short Squeeze)

```text
BASELINE → VULNERABLE → ARMED → IGNITION_WATCH → LIVE_CONFIRMATION
    → ACTIVE_SQUEEZE → EXHAUSTION → POST_SQUEEZE
(+ UNEVALUABLE)
```

Options must **not** own or override this state machine.

### 1.4 What Short Squeeze already publishes

Via `causal_intelligence` on donor API and IMP workspace projections:

- `state`, `state_since`, `transition`
- Dimensions: `vulnerability`, `constraint_pressure`, `short_stress`, `ignition_strength`, `reflexivity_strength`, `remaining_fuel`, `exhaustion_risk`
- `mechanism_labels`, `horizon_probabilities` (CALIBRATED when PIT walk-forward passes; otherwise RESEARCH_ONLY)
- `magnitude_estimate` via `HorizonModelSnapshot.magnitude` (RESEARCH_ONLY baseline)
- `explanation` graph, `supporting_evidence`, `contradicting_evidence`

### 1.5 What Short Squeeze already consumes (cross-lane)

| Source | Signals | Wiring status |
|---|---|---|
| Order Flow | `AGGRESSIVE_BUY_PRESSURE`, `CVD_*_SLOPE` | **Wired** via `cross_lane_adapter.py` |
| Options | `GAMMA_AMPLIFICATION_POTENTIAL`, `CALL_DEMAND_ANOMALY` | Contract exists; **not wired** from IMP options lane |
| Catalyst | `CATALYST_STRENGTH` | Planned |
| Attention | `ATTENTION_ACCELERATION` | Planned |

---

## 2. Options Roadmap (Proposed, Cooperative)

Options phases use prefix **O** to avoid collision with Short Squeeze **P**/**SS** numbering.

```text
PLATFORM P0 — correctness foundation          [MOSTLY DONE]
PLATFORM P1 — shared market primitives          [PARTIAL]
OPTIONS O1 — contract/chain correctness       [COMPLETE — fixture scope]
OPTIONS O2 — IV + Greeks + surface              [NOT STARTED]
SHARED P2 — physical distribution / RV          [NOT STARTED]
OPTIONS O3 — risk-neutral distribution Q        [NOT STARTED]
OPTIONS O4 — P vs Q edge engine                 [NOT STARTED]
SHARED P3 — cross-lane evidence fusion         [PARTIAL — order flow only]
OPTIONS O5 — signed flow                        [NOT STARTED]
OPTIONS O6 — dealer positioning                 [COMPLETE — fixture scope]
OPTIONS O7 — event volatility                   [COMPLETE — fixture scope]
OPTIONS O8 — strategy optimizer                 [COMPLETE — fixture scope]
SHARED P4 — EV / opportunity layer              [COMPLETE — fixture scope]
OPTIONS O9 — execution / simulation             [COMPLETE — fixture scope]
OPTIONS O10 — advanced modeling                 [IN PROGRESS — fixture gates validated (O10-S5)]
OPTIONS O11 — 0DTE specialization               [FUTURE — blocked Phase C intraday]
```

---

## 3. Shared Infrastructure Inventory

### 3.1 Platform owns (build once)

| Component | Location | SS status | Options status |
|---|---|---|---|
| Point-in-time (`event_time`, `available_time`) | `contracts/temporal.py`, `replay/lifecycle.py` | Consumes | Consumes |
| Quality engine | `data_quality/observations.py` | Consumes | Consumes |
| Provenance gates | `donor_patterns/provenance_gates.py` | Consumes | Consumes |
| Provider composition | `providers/composition.py` | Donor-side | Fixture BIYA only |
| Whale ledger | `providers/whale_ledger.py` | N/A (donor) | Phase 11 PASS |
| Cross-lane evidence contract | `cross_lane/evidence.py` | Publishes + consumes | Must publish |
| Deterministic replay | `replay/feature_lifecycle.py` | Partial | Fixture PIT |
| Bar simulator | `execution/simulator.py` | P6 planned | O9 planned |
| Walk-forward harness | `research/walk_forward.py`, `options/research/harness.py` | P3 planned | O10 fixture scope (O10-S5) |
| Model spec identity | `research/model_spec.py` | P3 planned | O10 fixture scope |
| UI API + capabilities | `ui_api/server.py` | Wired | BIYA workspace |

### 3.2 Short Squeeze owns (Options must not duplicate)

- Causal state machine and transitions
- Short crowding, SI interpretation, lending pressure
- Borrow utilization, fee stress, short-pain estimation
- Squeeze probability semantics (when calibrated)
- Remaining squeeze fuel, exhaustion

### 3.3 Options owns (Short Squeeze must not duplicate)

- Option contract normalization, chain state
- IV, Greeks, volatility surface, skew, term structure
- Risk-neutral distribution Q
- Option flow interpretation, dealer-position estimates
- Options strategy generation, payoff modeling
- Event volatility, IV crush
- P vs Q comparison and edge decomposition

### 3.4 Order Flow owns (both consume)

- CVD, aggressor classification, trade imbalance, book imbalance

---

## 4. Conflict Analysis

### 4.1 No conflicts (parallel work safe)

| Work item | SS phase | Options phase | Notes |
|---|---|---|---|
| Securities lending contract | SS P2 | — | Options does not own borrow |
| Canonical option contracts | — | O1 | SS does not own chain |
| IV/Greeks/surface | — | O2 | SS consumes via evidence only |
| Causal evaluator + hysteresis | SS P0/P1 | — | Options does not touch |
| Phase 11 fixture options lane | — | O1 baseline | Already PASS; extend, don't replace |

### 4.2 Shared milestones requiring coordination

| Milestone | Risk if duplicated | Resolution |
|---|---|---|
| Physical distribution P | SS P3 magnitude + Options O4 both need return distributions | **SHARED P2** — one platform module; Options primary consumer, SS consumes magnitude/tail features |
| Cross-lane evidence bus | SS P1 wired order flow; Options not publishing | **SHARED P3** — extend `evidence.py` signals; add Options publisher adapter; never import lane internals |
| EV / opportunity layer | Both lanes may compute EV differently | **SHARED P4** — domain engines supply inputs; one fusion framework |
| Simulator | SS P6 squeeze replay; Options O9 multi-leg | **SHARED** — extend `execution/simulator.py`; domain-specific fill models plug in |
| Confirmation score vs edge decomposition | Phase 11 `confirmation_score` could become pseudo-universal score | **Migrate** `confirmation_score` to per-event liquidity/activity context only; primary Options output becomes edge components (O4) |

### 4.3 Resolved discrepancies (from SS register affecting Options)

| SS ID | Issue | Options reconciliation |
|---|---|---|
| D-07 | Options card UNAVAILABLE blocks fusion | Options O1/O2 must publish `NormalizedLaneEvidence`; wire `build_cross_lane_snapshot_from_options` (P3 milestone) |
| D-06 | Horizon probabilities RESEARCH_ONLY | Options must not substitute IV rank for calibrated squeeze probability |
| D-14 | Simulator ignores squeeze state | Options O9 and SS P7 share simulator extension; D-14 resolved (fixture scope) via `squeeze_replay_hash` |

### 4.4 New conflicts to prevent

| Potential conflict | Prevention rule |
|---|---|
| Options builds its own CVD | Consume Order Flow evidence only |
| SS builds gamma/GEX internally | Consume Options `estimated_gamma_exposure` evidence |
| Two physical distribution engines | Single SHARED P2 module under `research/distribution/` or `features/forecast/` |
| Options `squeeze_probability → buy calls` | P vs Q must ask if squeeze risk is already priced |
| Circular model leakage at t | Evidence DAG: tag `RAW` / `DERIVED` / `MODEL_OUTPUT` / `CROSS_LANE_MODEL_OUTPUT`; no same-timestamp feedback |

---

## 5. Cross-Lane Evidence Contract (Target)

### 5.1 Options publishes → Short Squeeze consumes

| Signal | SS use case | Earliest phase |
|---|---|---|
| `CALL_DEMAND_ANOMALY` | IGNITION_WATCH | O5 (stub from O1 activity) |
| `GAMMA_AMPLIFICATION_POTENTIAL` | LIVE_CONFIRMATION, ACTIVE_SQUEEZE | O6 — wired to donor `options_gamma_amplification` (SS P5) |
| `UPSIDE_SKEW_ELEVATED` | reflexivity context | O2 |
| `IMPLIED_UPSIDE_TAIL_PROBABILITY` | priced-in check | O3 |
| `OPTION_FLOW_DIRECTION` | ignition supplement | O5 |
| `ESTIMATED_HEDGING_PRESSURE` | reflexivity | O6 — boosts `reflexivity_strength` via `options_hedging_pressure` |

### 5.2 Short Squeeze publishes → Options consumes

| Field | Options use case | Earliest phase |
|---|---|---|
| `squeeze_state` | tail forecast feature | SHARED P3 |
| `ignition_strength` | upside jump probability | SHARED P3 |
| `remaining_squeeze_fuel` | duration/magnitude | SS P5 — published as `REMAINING_SQUEEZE_FUEL` evidence |
| `exhaustion_risk` | IV crush / skew normalization | SS P5/P6 fixture proxy; O7 `estimate_iv_crush` boosts crush when exhaustion_risk ≥ 70 (JQ-6) |
| `structural_vulnerability` | event distribution conditioning | SHARED P3 |

### 5.3 Temporal semantics for cross-lane feedback

```text
VALID:   Options flow at t → Squeeze evaluate at t+1
VALID:   Squeeze state at t → Options P forecast at t+1
INVALID: Squeeze MODEL_OUTPUT at t → Options at t → Squeeze at t
```

---

## 6. Sequencing: What Blocks What

### 6.1 Options does NOT block Short Squeeze

SS P2–P5 can proceed without Options O3–O8. Options evidence is **supplementary**; squeeze evaluator degrades confidence when Options unavailable (already designed in causal spec).

### 6.2 Short Squeeze does NOT block Options O1–O2

Contract correctness and IV/surface are independent of squeeze state.

### 6.3 Shared P2 blocks Options O4 and SS P3 magnitude

Both need multi-horizon distribution forecasts. **Do not implement O4 or SS calibrated magnitude without SHARED P2.**

### 6.4 Options O2 blocks O3 (Q inference)

Risk-neutral distribution requires valid surface.

### 6.5 Options O3 + SHARED P2 block O4 (P vs Q)

Edge engine requires both distributions.

### 6.6 Options O8 blocks on O4 + liquidity (O1)

Strategy optimizer requires trustworthy P vs Q and executable quotes.

---

## 7. Parallelizable Work Matrix

| Time window | Short Squeeze | Options | Platform |
|---|---|---|---|
| Now | SS P2 lending interfaces | O1 contract model + historical chain plan | P0 audit completion |
| Next | SS P2 attention/catalyst | O2 IV/Greeks/surface QA | P1 liquidity features |
| After O2 + SS P2 | SS P3 baseline models | O3 Q inference research | **SHARED P2** distribution |
| After SHARED P2 | SS P4 live confirmation | O4 P vs Q edge | **SHARED P3** fusion wiring |
| After SHARED P3 | SS P5 exhaustion | O5 signed flow | — |
| Later | SS P7 advanced / simulator | O6–O11 | SHARED P4 EV |

---

## 8. UI Cooperation

Security-level workspace tabs (already partially implemented):

```text
OVERVIEW | SHORT SQUEEZE | OPTIONS | ORDER FLOW | NEWS | DEEP DIVE
```

Rules:

- Short Squeeze shows `Options Amplification` as cross-lane summary with link to Options workspace
- Options shows `Cross-Lane: Squeeze State` when available, with explanation of priced-in risk
- Do not duplicate evidence; reference `source_ref` and `observed_at`

---

## 9. Provider Coordination

Extend `PROVIDER_AND_DATA_RESEARCH_MATRIX.md` jointly for:

| Capability | SS need | Options need | Shared adapter |
|---|---|---|---|
| Short interest / float | Primary | Context | Finviz (donor) |
| Securities lending | Primary | Borrow for IV | TBD |
| Options chain + quotes | — | Primary | Tradier (stub exists) |
| Historical option chains | — | Primary (backtest) | TBD — paid |
| NBBO option trades | — | O5 flow | TBD |
| Participant side (open/close) | — | O5 | Often unavailable — fail closed |

---

## 10. Testing Cooperation

Joint test scenarios (add to both lane test suites):

| Scenario | SS expected | Options expected |
|---|---|---|
| Options unavailable | Functions; confidence reduced for reflexivity | N/A |
| Squeeze unavailable | N/A | Functions; tail models lose squeeze feature |
| Stale Options evidence | Rejects amplification | N/A |
| Stale squeeze evidence | N/A | Rejects squeeze cross-feature |
| Circular dependency | Architecture test detects cycle | Same |
| Same-timestamp replay | Deterministic cross-lane output | Same |

---

## 11. Decision Log

| ID | Decision | Rationale |
|---|---|---|
| R-01 | Options phases use **O** prefix | Avoid collision with SS P0–P6 |
| R-02 | Physical distribution is **SHARED P2**, not `options/` only | SS needs magnitude; Futures/Crypto may consume later |
| R-03 | Phase 11 `confirmation_score` is **not** the terminal Options output | Per ADR-WHALE-004; migrate to edge components at O4 |
| R-04 | No Options event state machine in SS evaluator | Options event lifecycle is O7-specific |
| R-05 | Extend `evidence.py` rather than lane-to-lane imports | ADR-SQZ-001 publishing rule |
| R-06 | SHARED P3 wires Options publisher before SS P4 live confirmation | D-07 resolution |
| R-07 | No implementation of O6 dealer models before O5 flow correctness | Prevents GEX pollution |

---

## 12. Approval Gate

**No major Options implementation beyond O1 contract scaffolding and cross-lane contract extension may proceed until:**

- [x] This reconciliation document exists
- [x] `OPTIONS_DISCREPANCY_REGISTER.md` exists
- [x] `OPTIONS_TARGET_ARCHITECTURE.md` exists
- [x] `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` exists
- [ ] Principal review of SHARED P2 ownership location

---

## Related documents

- `OPTIONS_CURRENT_STATE_AUDIT.md`
- `OPTIONS_TARGET_ARCHITECTURE.md`
- `OPTIONS_DISCREPANCY_REGISTER.md`
- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`
- `CROSS_LANE_BOUNDARY_MATRIX.md` (extended)
- `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md` (unchanged authority for SS phases)
