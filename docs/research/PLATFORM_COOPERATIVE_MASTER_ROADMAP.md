# Platform Cooperative Master Roadmap (Deliverable 6)

**Status:** Integrated dependency-aware roadmap for Short Squeeze + Options + Futures + Order Flow + shared platform  
**Date:** 2026-08-18 (updated for Order Flow OF-series cooperative redesign)  
**Authority:** Supersedes independent lane sequencing for shared milestones only; lane-specific details remain in lane roadmaps

---

## Roadmap structure

```text
PLATFORM ROADMAP
    │
    ├── Short Squeeze Lane (SS P0–P6)
    ├── Options Lane (O1–O11)
    ├── Futures Lane (F1–F11)
    ├── Order Flow Lane (OF1–OF12)
    └── Future Domain Roadmaps (Crypto, Prediction Markets — planning only)
```

**Numbering convention:**
- **P0–P5** = Platform shared phases
- **SS P0–P6** = Short Squeeze (existing `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`)
- **O1–O11** = Options
- **F1–F11** = Futures
- **OF1–OF12** = Order Flow / Market Microstructure (replaces narrow "CVD-only" framing)

---

## Dependency matrix

| Capability | Platform | Squeeze | Options | Futures | Order Flow | Dependency | Status |
|---|---|---|---|---|---|---|---|
| Point-in-time semantics | **Owns** | Consumes | Consumes | Consumes | Consumes | P0 | DONE |
| Quality + provenance | **Owns** | Consumes | Consumes | Consumes | Consumes | P0 | DONE |
| Provider capability registry | **Owns** | Donor | Consumes | Consumes | Consumes | P0 | PARTIAL |
| Deterministic replay | **Owns** | Partial | Fixture | Fixture | Fixture | P0 | DONE |
| Feature/model versioning | **Owns** | P3 | O10 | F11 | — | P0 | PARTIAL |
| Cross-lane evidence contract | **Owns** | Pub+Con | Pub+Con | Pub+Con | Pub | P0/P3 | PARTIAL |
| Explanation framework | **Owns** | Pub | Pub | Pub | — | P0 | PARTIAL |
| Price/volume features | **Owns** | Consumes | Consumes | Consumes | Consumes | P1 | PARTIAL |
| CVD / aggressor delta | Infra | Consumes | Consumes | Major consumer | **Owns** | P1/OF2 | DONE (fixture + OF2 module) |
| L1/L2 normalization | Infra | Context | Context | Major consumer | **Owns** | P1/OF3 | PARTIAL (OF3 L1 done) |
| Microprice / queue imbalance | Infra | Context | Context | Consumer | **Owns** | OF3 | DONE (module) |
| OFI / book flow | Infra | Consumes | Context | Consumes | **Owns** | OF4 | PARTIAL (BBO OFI) |
| Liquidity dynamics | Infra | Consumes | Context | Consumes | **Owns** | OF6 | NOT STARTED |
| Execution forecasts | Shared contract | Consumes | Consumes | Consumes | **Major producer** | OF9 | NOT STARTED |
| News/catalyst contracts | Infra | Consumes | O7 | F7 | — | P1 | PLANNED |
| Attention contracts | Infra | SS P2 | Context | Context | — | P1 | PLANNED |
| Corporate event registry | Infra | Context | O7 | F7 | — | P1 | PLANNED |
| Short interest / float | Donor | **Owns** | Context | — | — | SS P0 | DONE |
| Securities lending | Infra | **Owns** | Borrow for IV | — | — | SS P2 | PLANNED |
| Option contract model | Infra | — | **Owns** | Context | — | O1 | IN PROGRESS |
| Futures contract model | Infra | — | Consumes | **Owns** | — | F1 | IN PROGRESS |
| Historical option chains | Infra | — | **Owns** | — | — | O1 | NOT STARTED |
| IV / Greeks / surface | Infra | Context | **Owns** | Consumes | — | O2 | NOT STARTED |
| Futures curve / carry | Infra | Context | Consumes | **Owns** | Context | F3 | DONE |
| COT / futures positioning | Infra | Context | Context | **Owns** | — | F4 | NOT STARTED |
| Physical distribution P | **Shared** | Consumes | Major consumer | Consumes | Inputs | **P2** | NOT STARTED |
| Realized volatility engine | **Shared** | Consumes | **Owns** semantics | Consumes | — | P2/O2 | NOT STARTED |
| Risk-neutral distribution Q | Shared contract | Context | **Owns** | Context | — | O3 | NOT STARTED |
| P vs Q edge engine | — | — | **Owns** | — | — | O4 | DONE |
| Causal squeeze states | — | **Owns** | Consumes | No (different) | — | SS P0 | DONE |
| Squeeze probabilities | — | **Owns** | Consumes | — | — | SS P3 | RESEARCH |
| Options signed flow | — | Consumes | **Owns** | — | Confirms | O5 | NOT STARTED |
| Dealer / gamma exposure | Contract | Consumes | **Produces** | Context | Confirms | O6 | NOT STARTED |
| Event volatility / IV crush | — | Context | **Owns** | F7 context | — | O7 | NOT STARTED |
| Futures leverage stress | Contract | Context | Context | **Owns** | Confirms | F8 | NOT STARTED |
| Strategy optimizer | — | — | **Owns** | Partial | — | O8 | NOT STARTED |
| EV / opportunity layer | **Shared** | Domain inputs | Domain inputs | Domain inputs | Inputs | **P4** | RESEARCH |
| Execution simulator | **Shared** | SS P6 | O9 | F10 | — | P4/O9/F10 | PARTIAL |
| 0DTE specialization | — | — | **Owns** | — | Context | O11 | NOT STARTED |
| Cross-lane portfolio | **Shared** | — | — | — | — | P5 | DEFERRED |

---

## Phase detail

### PLATFORM P0 — Correctness foundation [MOSTLY DONE]

**Supports all lanes simultaneously.**

- [x] `event_time` / `available_time` semantics
- [x] Provenance gates
- [x] Quality observations
- [x] Provider composition registry
- [x] Deterministic replay lifecycle
- [x] Cross-lane evidence interface stub
- [x] Explanation contracts (partial)
- [ ] Full bitemporal reference store
- [ ] Centralized PIT joins for OI/earnings/dividends (O-23)

**SS benefit:** Prevents stale SI/lending leakage  
**Options benefit:** Prevents OI/surface/earnings leakage

---

### PLATFORM P1 — Shared market primitives [PARTIAL]

- [x] Bar OHLCV features
- [x] Order flow fixture + CVD (Phase 10 PASS)
- [x] Order Flow OF1–OF3 foundation module (`order_flow/`)
- [ ] Liquidity features (spread, depth dynamics) — unified OF6
- [ ] Catalyst/attention interfaces
- [ ] Corporate event registry

**Parallel with:** SS P2, O1

---

### SHORT SQUEEZE SS P0/P1 [DONE]

See `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`.

- Causal evaluator, hysteresis, UI, order-flow cross-lane, ADR-SQZ-001

---

**Options benefit:** Prevents OI/surface/earnings leakage  
**Futures benefit:** Prevents COT/settlement/margin leakage

---

### ORDER FLOW OF1 — Trade / aggressor correctness [DONE — module]

- [x] `ClassifiedTrade` canonical contract
- [x] `AggressorSource` provenance taxonomy
- [x] `classify_trade` / `classify_bar_delta`
- [ ] Runtime tick ingest wiring (blocked on live adapter authorization)

**Deliverables:** `order_flow/contracts.py`, `order_flow/aggressor.py`, `order_flow/quality.py`

---

### ORDER FLOW OF2 — CVD baseline [DONE — module + workspace]

- [x] CVD with `native/inferred/unknown` fractions
- [x] `cvd_confidence` in workspace `cvd_summary`
- [x] `AGGRESSIVE_SELL_PRESSURE` cross-lane signal
- [ ] Session reset policies per instrument

---

### ORDER FLOW OF3 — L1 / microprice [DONE — module + workspace]

- [x] spread, mid, queue imbalance, microprice
- [x] `latest_l1` in order-book workspace payload
- [x] `OrderFlowEvidence` cross-lane contract
- [x] `BOOK_IMBALANCE_BID/ASK` evidence (resting liquidity — not aggression)

---

### ORDER FLOW OF4–OF12 [PLANNED]

See `FOUR_LANE_ROADMAP_RECONCILIATION.md` for OF4 OFI through OF12 advanced ML.

---

### FUTURES F1 — Contract correctness [IN PROGRESS]

**Parallel with O1 and SS P2 — no mutual dependency.**

- [x] Canonical `FuturesContract` schema
- [x] Futures quality taxonomy
- [x] Notional / tick economics module
- [x] COT point-in-time helper
- [x] Wire schema to fixture ingestion — `futures_contract_from_dict`, chain PIT + envelopes
- [ ] Versioned spec registry per product
- [x] `FuturesChainProvider` interface — PIT + ADR-PROV-001 metadata on fixture chain

**Deliverables:** `contracts/futures.py`, `contracts/futures_quality.py`, `futures/notional.py`

---

### FUTURES F2 — Roll / continuous-series correctness [COMPLETE]

- [x] Lead contract selection rule v1
- [x] RollState enum
- [x] Continuous series builders (explicit methodology)
- [x] Roll execution in simulator
- [x] Lead-contract switch tests

**Blocks:** Trustworthy historical PnL research

---

### FUTURES F3 — Curve / basis / carry [COMPLETE]

- [x] `FuturesCurveSnapshot` engine — `futures/curve.py`
- [x] Basis engine with explicit definitions — `futures/basis.py`
- [x] Carry per family (documented formulas) — `futures/carry.py` (EQUITY_INDEX v1)
- [x] Publish `FuturesCurveEvidence` cross-lane — contango/backwardation + carry signals

**Parallel with:** O2

---

### FUTURES F4 — OI / COT positioning [NOT STARTED]

- [ ] COT ingestion with publication delay
- [ ] Crowding / hedging pressure features
- [ ] OI velocity — hypotheses only, not direction

---

### FUTURES F5 — Trend + carry baselines [NOT STARTED]

Empirical baselines before advanced ML. See `FUTURES_RESEARCH_PLAN.md`.

---

### FUTURES F6–F11 [PLANNED / FUTURE]

See `THREE_LANE_ROADMAP_RECONCILIATION.md` for F6 family models through F11 advanced modeling.

---

### OPTIONS O1 — Contract / chain correctness [IN PROGRESS]

**Parallel with SS P2 — no mutual dependency.**

- [x] Canonical `OptionContract` schema
- [x] Options quality taxonomy
- [x] Extend Phase 11 envelope toward canonical model
- [ ] Historical chain archive plan
- [ ] Corporate action adjustment semantics
- [x] `OptionChainProvider` interface hardening — PIT + ADR-PROV-001 chain envelopes

**Deliverables:** `contracts/options.py`, `contracts/options_quality.py`

---

### SHORT SQUEEZE SS P2 — Structural vulnerability [PLANNED]

- Securities lending contract
- Velocity/acceleration PIT metrics
- Attention + catalyst interfaces

**Options:** Does not block. May consume lending for borrow/carry in IV (O2).

---

### OPTIONS O2 — IV + Greeks + surface [COMPLETE]

- [x] Normalized internal IV + provider IV tracking
- [x] Reproducible Greeks
- [x] Surface σ(K,T) with QA
- [x] Begin publishing volatility context via cross-lane

**Does not alter SS P2 infrastructure.**

---

### SHARED P2 — Physical distribution / volatility foundation [COMPLETE]

**Major cooperative milestone — blocks O4 and SS P3 magnitude.**

- [x] Realized volatility estimators (close-to-close; Parkinson in `realized_vol.py`)
- [x] Volatility forecasting baselines (EWMA, GARCH, HAR-RV)
- [x] Multi-horizon return distribution forecasts (P) — `research/distribution/forecast.py`
- [x] Event/jump primitives — `research/distribution/events.py`
- [x] Fixture provider wiring — `providers/adapters/fixture_distribution.py`

**Location:** `research/distribution/` (platform), not `options/`

**SS uses:** expected magnitude, downside, EV inputs  
**Options uses:** P in P vs Q

---

### SHORT SQUEEZE SS P3 — Baseline models [IN PROGRESS]

**Depends on SHARED P2 for magnitude.**

- [x] Mechanism labels adjudication dataset — `tests/fixtures/squeeze/mechanism_labels.json`
- [x] Logistic/hazard models — `research/squeeze_models/`
- [x] Calibrated horizon probabilities

---

### OPTIONS O3 — Risk-neutral distribution [COMPLETE]

**Depends on O2.**

- [x] Surface → Q inference — `options/risk_neutral.py`
- [x] Risk-neutral moments and tails
- [ ] Event-implied distribution

---

### OPTIONS O4 — P vs Q edge engine [COMPLETE]

**Depends on O3 + SHARED P2.**

- [x] Decomposed edge components (no universal score) — `options/edge.py`
- [x] Theoretical vs executable edge — `apply_executable_edge`
- [x] Volatility risk premium research — `options/vrp.py`

---

### SHARED P3 — Cross-lane evidence fusion [COMPLETE]

**Depends on O2 partial + SS P1.**

- [x] Order flow → squeeze (done)
- [x] Order book → BOOK_IMBALANCE evidence (OF3)
- [x] Options publisher adapter (minimal unusual-activity)
- [x] Futures depth fused into squeeze bridge
- [x] Evidence provenance classes + DAG validation
- [x] Cross-lane evidence UI block (`CrossLaneEvidenceBlock`)
- [x] Squeeze evidence → Options P features — `squeeze_context` + publisher
- [x] Circular dependency tests (integration-level)

**Milestone:** Options amplification visible in squeeze workspace with traceable refs.

---

### SHORT SQUEEZE SS P4 — Live confirmation [PLANNED]

- Streaming transition log
- Live order-flow adapter
- Options evidence supplementary (degraded if unavailable)

---

### OPTIONS O5 — Signed flow [COMPLETE — fixture scope]

- [x] Buy/sell initiation where available — `options/flow.py`
- [x] Opening/closing where available — fail-closed `OPEN_CLOSE_UNKNOWN`
- [x] Delta/gamma/vega flow aggregates
- [x] Abnormal flow baselines — fixture-bounded
- [ ] Complex order handling — deferred

**Improves:** Options forecasting + SS ignition/confirmation

---

### OPTIONS O6 — Dealer positioning [NOT STARTED]

**Only after O5 + chain correctness (R-07).**

- Confidence-aware dealer estimates
- `estimated_gamma_exposure` (not claimed dealer gamma)
- Publish hedging pressure for Order Flow confirmation

---

### SHORT SQUEEZE SS P5 — Active squeeze + remaining fuel [PLANNED]

- Feedback detection, covering estimates, remaining fuel
- Options reflexivity via O6 evidence

---

### OPTIONS O7 — Event volatility [NOT STARTED]

- Earnings-first event models
- IV crush, post-event IV expectation
- Options event state machine

**Largely independent of SS P5.**

---

### OPTIONS O8 — Strategy optimizer [NOT STARTED]

**Only after O4 + liquidity (O1).**

- Forecast-driven strategy generation
- Expected P&L distributions
- NO_CLEAR_EDGE support

---

### SHORT SQUEEZE SS P6 — Exhaustion [PLANNED]

- Fuel decline, CVD divergence, borrow normalization
- Options may contribute gamma decay, flow reversal (O6/O5)

---

### SHARED P4 — EV / opportunity layer [RESEARCH]

- Single framework: probability × payoff × costs × liquidity
- SS supplies event probability, magnitude, fuel
- Options supplies strategy P&L, margin, assignment risk

**Do not duplicate EV engines per lane.**

---

### OPTIONS O9 — Execution / simulation [NOT STARTED]

- Extend shared `execution/simulator.py`
- Multi-leg, assignment, exercise
- No Options-only parallel simulator

**Coordinates with SS P6 simulator replay (D-14).**

---

### SHORT SQUEEZE SS P7 — Advanced models [FUTURE]

- Hazard models, boosting, rare-event ensembles
- After baseline causal models validated

---

### OPTIONS O10 — Advanced modeling [FUTURE]

- Distributional ML, surface forecasting, option-return ML
- Delta-hedged research primitive
- Only after O4 baseline works

---

### OPTIONS O11 — 0DTE specialization [FUTURE]

- Only after O9 execution correctness
- Intraday surface, pinning, expiration effects

---

### SHARED P5 — Cross-lane portfolio intelligence [DEFERRED]

- Combine Squeeze, Options, Futures, Order Flow, Crypto, Prediction Markets
- Do not entangle with current lane redesigns

---

## Parallelizable work (next 90 days)

| Track | Work | Blocked by |
|---|---|---|
| SS | SS P2 lending interfaces | Nothing |
| Options | O1 contract schema + quality taxonomy | Nothing |
| Options | Cross-lane evidence extension (SHARED P3 partial) | Nothing |
| Platform | P1 catalyst/attention interfaces | Nothing |
| Options | O2 IV engine research (offline) | O1 schema |
| SS | SS P3 models | SHARED P2 |
| Options | O4 P vs Q | O3 + SHARED P2 |

---

## Conflict detection checklist

Before any milestone implementation, verify:

- [ ] Does this modify shared contracts?
- [ ] Does another lane depend on them?
- [ ] Does semantics change?
- [ ] Provider coupling introduced?
- [ ] Ownership boundary violated?
- [ ] Duplicate primitive created?

If yes → update this roadmap + reconciliation doc + migrate consumers together.

---

## Joint research questions

| ID | Question | Lanes |
|---|---|---|
| JQ-1 | Does squeeze state improve upside IV / call skew / RV forecasts? | SS → Options |
| JQ-2 | Does signed call demand improve ignition after controlling price/volume? | Options → SS |
| JQ-3 | Does estimated negative gamma increase conditional squeeze magnitude? | Options → SS |
| JQ-4 | Does expensive upside skew indicate squeeze already priced? | Options ↔ SS |
| JQ-5 | Can options flow predict squeeze before equity confirmation? | Options → SS |
| JQ-6 | Does squeeze exhaustion predict IV collapse / skew normalization? | SS → Options |
| OF-Q1 | Does OFI outperform CVD for next ES mid move? | Order Flow |
| OF-Q3 | Does liquidity withdrawal improve squeeze ignition beyond CVD? | Order Flow → SS |

Empirical — not assumptions. See `OPTIONS_RESEARCH_PLAN.md`, `ORDER_FLOW_RESEARCH_PLAN.md`.

---

## Related documents

- `FOUR_LANE_ROADMAP_RECONCILIATION.md`
- `THREE_LANE_ROADMAP_RECONCILIATION.md`
- `ORDER_FLOW_CURRENT_STATE_AUDIT.md`
- `ORDER_FLOW_TARGET_ARCHITECTURE.md`
- `FUTURES_TARGET_ARCHITECTURE.md`
- `FUTURES_CURRENT_STATE_AUDIT.md`
- `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`
- `OPTIONS_TARGET_ARCHITECTURE.md`
- `CROSS_LANE_BOUNDARY_MATRIX.md`
