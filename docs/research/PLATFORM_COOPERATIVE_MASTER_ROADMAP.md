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
| Cross-lane evidence contract | **Owns** | Pub+Con | Pub+Con | Pub+Con | Pub | P0/P3 | DONE |
| Explanation framework | **Owns** | Pub | Pub | Pub | — | P0 | PARTIAL |
| Price/volume features | **Owns** | Consumes | Consumes | Consumes | Consumes | P1 | PARTIAL |
| CVD / aggressor delta | Infra | Consumes | Consumes | Major consumer | **Owns** | P1/OF2 | DONE (fixture + OF2 module) |
| L1/L2 normalization | Infra | Context | Context | Major consumer | **Owns** | P1/OF3 | PARTIAL (OF3 L1 done) |
| Microprice / queue imbalance | Infra | Context | Context | Consumer | **Owns** | OF3 | DONE (module) |
| OFI / book flow | Infra | Consumes | Context | Consumes | **Owns** | OF4 | DONE (BBO + multilevel CS v1) |
| OF6 | Liquidity dynamics | **DONE** (depth delta v1) |
| Absorption / exhaustion | Infra | Consumes | Context | Consumes | **Owns** | OF7 | DONE (aggression-price v1) |
| Short-horizon microstructure forecast | Infra | Consumes | Context | Consumes | **Owns** | OF8 | DONE (heuristic v1) |
| Execution forecasts | Shared contract | Consumes | Consumes | Consumes | **Major producer** | OF9 | DONE (fixture scope) |
| News/catalyst contracts | Infra | Consumes | O7 | F7 | — | P1 | PLANNED |
| Attention contracts | Infra | SS P2 | Context | Context | — | P1 | PLANNED |
| Corporate event registry | Infra | Context | O7 | F7 | — | P1 | PLANNED |
| Short interest / float | Donor | **Owns** | Context | — | — | SS P0 | DONE |
| Securities lending | Infra | **Owns** | Borrow for IV | — | — | SS P2 | PLANNED |
| Option contract model | Infra | — | **Owns** | Context | — | O1 | DONE (fixture) |
| Futures contract model | Infra | — | Consumes | **Owns** | — | F1 | DONE (fixture) |
| Historical option chains | Infra | — | **Owns** | — | — | O1 | PLAN (design doc) |
| IV / Greeks / surface | Infra | Context | **Owns** | Consumes | — | O2 | DONE (fixture) |
| Futures curve / carry | Infra | Context | Consumes | **Owns** | Context | F3 | DONE |
| COT / futures positioning | Infra | Context | Context | **Owns** | — | F4 | DONE (fixture scope) |
| Physical distribution P | **Shared** | Consumes | Major consumer | Consumes | Inputs | **P2** | DONE (fixture) |
| Realized volatility engine | **Shared** | Consumes | **Owns** semantics | Consumes | — | P2/O2 | PARTIAL (O2 surface) |
| Risk-neutral distribution Q | Shared contract | Context | **Owns** | Context | — | O3 | DONE (fixture) |
| P vs Q edge engine | — | — | **Owns** | — | — | O4 | DONE |
| Causal squeeze states | — | **Owns** | Consumes | No (different) | — | SS P0 | DONE |
| Squeeze probabilities | — | **Owns** | Consumes | — | — | SS P3 | DONE (baselines) |
| Options signed flow | — | Consumes | **Owns** | — | Confirms | O5 | DONE (fixture) |
| Dealer / gamma exposure | Contract | Consumes | **Produces** | Context | Confirms | O6 | COMPLETE (fixture scope) |
| Event volatility / IV crush | — | Context | **Owns** | F7 context | — | O7 | COMPLETE (fixture scope) |
| Futures leverage stress | Contract | Context | Context | **Owns** | Confirms | F8 | NOT STARTED |
| Strategy optimizer | — | — | **Owns** | Partial | — | O8 | COMPLETE (fixture scope) |
| EV / opportunity layer | **Shared** | Domain inputs | Domain inputs | Domain inputs | Inputs | **P4** | DONE (fixture scope) |
| Execution simulator | **Shared** | SS P6 | O9 | F10 | — | P4/O9/F10 | PARTIAL+ |
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

### ORDER FLOW OF4 — Versioned OFI book-flow [COMPLETE — fixture scope]

- [x] `order_flow/ofi.py` — `ofi_bbo_delta_v1`, `ofi_multilevel_cs_v1`
- [x] `book_state_valid` fail-closed guard on corrupt books
- [x] Fixture ingest on `ADMITTED-L2-NVDA-001` + `ADMITTED-L2-ES-001`
- [x] Workspace OFI metadata on order-book + futures depth payloads
- [x] Golden fixture — `nvda_ofi_expected.json`
- [x] UI — order-book panel shows OFI method/version

### ORDER FLOW OF6 — Liquidity dynamics [COMPLETE — fixture scope]

- [x] `order_flow/liquidity.py` — `liquidity_depth_delta_v1`
- [x] Depth withdrawal / replenishment from L2 snapshot pairs
- [x] Trajectory resiliency + fragility composite
- [x] `LiquidityEvidence` cross-lane contract
- [x] Fixture ingest on `ADMITTED-L2-NVDA-001` + `ADMITTED-L2-ES-001`
- [x] Workspace `latest_liquidity_summary` on order-book + futures payloads
- [x] Cross-lane signals — `LIQUIDITY_WITHDRAWAL`, `BOOK_FRAGILITY_ELEVATED`
- [x] SHARED P4 v1.1 liquidity extractor enrichment
- [x] Golden fixture — `nvda_liquidity_expected.json`
- [x] UI — order-book + futures panels show fragility / withdrawal

### ORDER FLOW OF7 — Absorption / exhaustion [COMPLETE — fixture scope]

- [x] `order_flow/impact.py` — `impact_aggression_price_v1`
- [x] Bar-aligned NVDA ingest (depth + order-flow fixture join)
- [x] ES depth path degrades with `MISSING_TRADE_FLOW` (no false absorption)
- [x] Workspace `latest_impact_summary` on order-book + futures payloads
- [x] Cross-lane signals — `ABSORPTION_BUY/SELL`, `EXHAUSTION_BUY/SELL`
- [x] SHARED P4 liquidity extractor enrichment (`absorption_score`, `exhaustion_score`)
- [x] Golden fixture — `nvda_impact_expected.json`
- [x] UI — order-book + futures panels show book-flow regime (not squeeze lifecycle)

### ORDER FLOW OF8 — Short-horizon microstructure forecasts [COMPLETE — fixture scope]

- [x] `order_flow/forecast.py` — `microstructure_heuristic_v1` (distinct from SHARED P2 physical P)
- [x] Composes OF3–OF7 inputs into continuation / reversal probabilities
- [x] Workspace `latest_microstructure_forecast` on order-book + futures payloads
- [x] Cross-lane signals — `MICROSTRUCTURE_CONTINUATION_UP/DOWN`, `MICROSTRUCTURE_REVERSAL_RISK`
- [x] SHARED P4 liquidity extractor enrichment (`continuation_probability`, `reversal_probability`, `microstructure_direction_bias`)
- [x] Golden fixture — `nvda_forecast_expected.json`
- [x] UI — short-horizon micro forecast block (not multi-day physical P)

### ORDER FLOW OF9 — Execution forecasts [COMPLETE — fixture scope]

- [x] `order_flow/execution_forecast.py` — `execution_book_aware_v1`
- [x] Fill probability, expected slippage, adverse selection from L2 + OF3–OF8 composites
- [x] `ExecutionForecast` cross-lane contract + evidence assembly
- [x] Fixture ingest on `ADMITTED-L2-NVDA-001` + `ADMITTED-L2-ES-001`
- [x] Workspace `latest_execution_forecast` on order-book + futures payloads
- [x] Cross-lane signals — `EXECUTION_SLIPPAGE_ELEVATED`, `EXECUTION_FILL_RISK`, `ADVERSE_SELECTION_RISK_ELEVATED`
- [x] SHARED P4 v1.2 liquidity enrichment (`fill_probability`, slippage, adverse selection)
- [x] Book-aware simulator tier — `execution/book_aware.py` (`simulation.book_aware_l2_v1`, OF-D09)
- [x] Golden fixture — `nvda_execution_forecast_expected.json`
- [x] UI — order-book + futures panels show execution forecast block

### ORDER FLOW OF10–OF12 [PLANNED]

See `FOUR_LANE_ROADMAP_RECONCILIATION.md` for OF10 MBO queue through OF12 advanced ML.

---

### FUTURES F1 — Contract correctness [COMPLETE — fixture scope]

**Parallel with O1 and SS P2 — no mutual dependency.**

- [x] Canonical `FuturesContract` schema
- [x] Futures quality taxonomy
- [x] Notional / tick economics module
- [x] COT point-in-time helper
- [x] Wire schema to fixture ingestion — `futures_contract_from_dict`, chain PIT + envelopes
- [x] Versioned spec registry per product — `futures/spec_registry.py`
- [x] `FuturesChainProvider` interface — PIT + ADR-PROV-001 metadata on fixture chain
- [x] Composition wiring via `bootstrap_default_providers()`

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

### FUTURES F4 — OI / COT positioning [COMPLETE — fixture scope]

- [x] COT ingestion with publication delay — `cot.fixture.futures_positioning` on `ADMITTED-COT-ES-001`
- [x] Crowding / hedging pressure features — `futures/positioning.py` (`futures_positioning_v1`)
- [x] OI velocity hypotheses — non-directional labels from chain `open_interest_history`
- [x] Workspace wiring — `positioning_snapshot`, `futures_positioning_available`, `oi_velocity_hypothesis`
- [x] Cross-lane signals — `FUTURES_POSITIONING_CROWDED_LONG`, `FUTURES_POSITIONING_CROWDED_SHORT`
- [x] Golden regression — `tests/fixtures/futures/es_positioning_expected.json`
- [x] UI — futures panel shows COT net, crowding regime, OI velocity disclaimer

### FUTURES F5 — Trend + carry baselines [COMPLETE — fixture scope]

Empirical baselines before advanced ML. See `FUTURES_RESEARCH_PLAN.md`.

- [x] Vol-scaled trend features (1m/3m/6m/12m) — `futures/baselines.py` (`futures_baselines_v1`)
- [x] Carry percentile/change extending F3 — fixture `carry_history`
- [x] Curve momentum from term structure — `curve_slope_history`
- [x] Settlement bar ingest — `bars.fixture.futures_settlement` on `ADMITTED-BARS-ES-001`
- [x] Workspace wiring — `trend_baseline_snapshot`, `carry_baseline`, `curve_momentum`, `futures_baselines_available`
- [x] Cross-lane signals — `FUTURES_TREND_UP`, `FUTURES_TREND_DOWN`
- [x] Golden regression — `tests/fixtures/futures/es_baselines_expected.json`
- [x] UI — futures panel shows vol-scaled trends, carry percentile, curve momentum disclaimer

---

### FUTURES F6–F11 [PLANNED / FUTURE]

See `THREE_LANE_ROADMAP_RECONCILIATION.md` for F6 family models through F11 advanced modeling.

---

### OPTIONS O1 — Contract / chain correctness [COMPLETE — fixture scope]

**Parallel with SS P2 — no mutual dependency.**

- [x] Canonical `OptionContract` schema
- [x] Options quality taxonomy
- [x] Extend Phase 11 envelope toward canonical model
- [x] Historical chain archive plan — `OPTIONS_HISTORICAL_CHAIN_ARCHIVE_PLAN.md` (design only)
- [x] Corporate action adjustment semantics — fixture `biya_adjusted_option_slice.json`
- [x] `OptionChainProvider` interface hardening — PIT + ADR-PROV-001 chain envelopes
- [x] `OptionChainSnapshot` workspace wiring — `build_workspace_options_payload`
- [x] Versioned product spec registry — `options/spec_registry.py`

**Deliverables:** `contracts/options.py`, `contracts/options_quality.py`

---

### SHORT SQUEEZE SS P2 — Structural vulnerability [PARTIAL — contract scope]

- [x] Securities lending snapshot contract — `contracts/squeeze_structural.py`
- [x] Velocity/acceleration PIT metrics — `VelocityAccelerationMetric`
- [x] Attention + catalyst interfaces — `AttentionFeature`, `CatalystStrength`
- [x] Lending cross-lane adapter (fixture scope) — `donor_bridge/lending_adapter.py`
- [ ] Live securities lending ingest — deferred (requires vendor pipeline)

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

### SHORT SQUEEZE SS P3 — Baseline models [COMPLETE — fixture scope]

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

### SHORT SQUEEZE SS P4 — Live confirmation [COMPLETE — fixture scope]

- [x] Streaming transition log in session_state (donor `causal_transitions` + IMP `transition_stream` replay)
- [x] Cross-lane causal fusion in current mode (`_effective_prediction_cutoff`)
- [x] Recorded order-flow adapter (`IMP_ORDER_FLOW_LIVE=1` → fixture replay, no broker HTTP)
- [x] Options evidence supplementary wiring — `options_gamma_amplification` + O6 dealer proxy on cross_lane snapshot
- [ ] Live broker tick ingest (deferred — blocked on adapter authorization)

---

### OPTIONS O5 — Signed flow [COMPLETE — fixture scope]

- [x] Buy/sell initiation where available — `options/flow.py`
- [x] Opening/closing where available — fail-closed `OPEN_CLOSE_UNKNOWN`
- [x] Delta/gamma/vega flow aggregates
- [x] Abnormal flow baselines — fixture-bounded
- [ ] Complex order handling — deferred

**Improves:** Options forecasting + SS ignition/confirmation

---

### OPTIONS O6 — Dealer positioning [COMPLETE — fixture scope]

**Depends on O5 + chain correctness (R-07).**

- [x] OI×gamma proxy with explicit uncertainty — `options/dealer.py` (`OI_GAMMA_PROXY_V1`, confidence LOW)
- [x] `estimated_dealer_delta/gamma/vega`, `gamma_regime`, `hedging_pressure_estimate`, `gamma_flip_estimate`
- [x] Workspace `dealer_snapshot` + `dealer_position_available` in `build_workspace_options_payload`
- [x] Cross-lane `GAMMA_AMPLIFICATION_POTENTIAL` + `ESTIMATED_HEDGING_PRESSURE` evidence
- [ ] True participant-side dealer positioning — deferred (requires vendor data)

---

### SHORT SQUEEZE SS P5 — Active squeeze + remaining fuel [COMPLETE — fixture scope]

- [x] Fuel subsystem — `squeeze_core/intelligence/fuel.py` (`STRUCTURAL_CVD_GAMMA_PROXY_V1`)
- [x] Reflexivity, covering pressure, remaining fuel, exhaustion risk proxies in donor evaluator (`squeeze_causal_baseline.v2`)
- [x] `ACTIVE_SQUEEZE` reachable with order flow + O6 gamma amplification fixtures
- [x] Cross-lane `REMAINING_SQUEEZE_FUEL` + `EXHAUSTION_RISK` evidence published to Options lane
- [x] Chain-only NVDA options path wired into cross_lane snapshot
- [ ] True SI-delta covering estimates — deferred (requires lending pipeline)

---

### OPTIONS O7 — Event volatility [COMPLETE — fixture scope]

- [x] Earnings event state machine — `classify_event_state` (`NO_EVENT` → `POST_EVENT_NORMALIZATION`)
- [x] Implied event move — ATM straddle from `nvda_earnings_event_slice.json`
- [x] IV crush empirical baseline — `estimate_iv_crush` with fixture crush history
- [x] SS exhaustion conditioning (JQ-6) — crush boost when `exhaustion_risk >= 70`
- [x] Cross-lane evidence — `EVENT_VOL_PREMIUM`, `IV_CRUSH_RISK`, `POST_EVENT_IV_NORMALIZATION`
- [x] Workspace wiring — `event_vol_snapshot` on options payload; VRP uses O7 `event_state`
- [ ] Live earnings calendar ingest — deferred (O-23 centralized PIT joins)

---

### OPTIONS O8 — Strategy optimizer [COMPLETE — fixture scope]

- [x] Payoff engine — `options/payoff.py` (`OptionLeg`, `payoff_at_spot`, `expected_pnl_under_physical_p`)
- [x] P vs Q template candidates — `long_call_atm`, spreads, `long_straddle`, `long_otm_call`
- [x] Liquidity gating — `liquidity_gate` per leg; multi-leg fail-closed
- [x] Ranking by `net_expected_pnl` — no universal score; `NO_CLEAR_EDGE` when no positive candidate
- [x] Workspace wiring — `strategy_snapshot` on options payload
- [x] Cross-lane evidence — `STRATEGY_OPPORTUNITY_RANKED`, `NO_CLEAR_EDGE`
- [ ] Calibrated walk-forward strategy EV — deferred (research milestone R-O10)

---

### SHORT SQUEEZE SS P6 — Advanced exhaustion [COMPLETE — fixture scope]

- [x] Temporal fuel context — `FuelHistorySnapshot` + PIT transition stream `extract_fuel_history`
- [x] CVD divergence history — `detect_cvd_divergence` with prior slope from transition stream
- [x] Borrow normalization proxy — `lending_normalization_slice.json` + `estimate_borrow_normalization`
- [x] O5/O6 exhaustion signals — `options_flow_reversal`, `options_gamma_decay` on cross_lane snapshot
- [x] Donor evaluator v3 (`squeeze_causal_baseline.v3`, `STRUCTURAL_CVD_GAMMA_BORROW_PROXY_V2`)
- [x] ShortPainDistribution / simulator replay — delivered in P7 (fixture scope)

---

### SHORT SQUEEZE SS P7 — Advanced models [COMPLETE — fixture scope]

- [x] ShortPainDistribution contract — fail-closed without entry-price proxy; `short_pain_proxy_slice.json`
- [x] Magnitude model — separate from occurrence (`predict_squeeze_magnitude`, `ss_magnitude_baseline_v1`)
- [x] Rare-event ensemble — stdlib weighted logistic heads (`ss_rare_event_ensemble_v1`)
- [x] Calibrated horizons — donor v4 (`squeeze_causal_baseline.v4`) via `HorizonModelSnapshot` when PIT harness passes
- [x] Simulator squeeze-state replay — D-14: `squeeze_replay_hash` in `risk_simulation_root_hash`
- [ ] True entry-price inference — deferred (open research Q)

---

### SHARED P4 — EV / opportunity layer [COMPLETE — fixture scope]

- [x] Single framework: probability × payoff × costs × liquidity — `cross_lane/fusion.py`
- [x] Input contracts — `cross_lane/opportunity.py`, `cross_lane/extractors.py`
- [x] SS supplies event probability, magnitude, fuel (via cross-lane snapshot extractors)
- [x] Options supplies strategy P&L, friction, liquidity gates (O8 payoff decomposition)
- [x] Cross-lane evidence — `CROSS_LANE_OPPORTUNITY_FUSED`, `OPPORTUNITY_NO_ACTIONABLE_EDGE`
- [x] Workspace wiring — `opportunity_snapshot` on options + squeeze payloads
- [x] NVDA golden fixture — `nvda_opportunity_fusion_expected.json`
- [x] Spec — `SHARED_P4_EV_OPPORTUNITY_SPEC.md`
- [x] UI blocks — `OpportunityFusionBlock`, strategy/execution/dealer panels on options + squeeze workspaces
- [ ] Futures outright opportunity fusion — deferred (F8–F10)
- [x] Order Flow OF9 execution forecast inputs — `latest_execution_forecast` + P4 liquidity enrichment

**Do not duplicate EV engines per lane.**

---

### OPTIONS O9 — Execution / simulation [COMPLETE — fixture scope]

- [x] Conservative NBBO fills — `options/execution.py` (long pays ask, short receives bid)
- [x] Multi-leg entry — `simulate_multi_leg_entry` with per-leg `liquidity_gate`; fail-closed
- [x] Options conservative simulator — `execution/options_conservative.py` registered as `simulation.options_conservative`
- [x] Lifecycle — expiration settlement, early exercise, assignment (`portfolio/options_ledger.py`)
- [x] Workspace wiring — `execution_snapshot` on options payload
- [x] Cross-lane evidence — `OPTIONS_EXECUTION_SIMULATED`, `ASSIGNMENT_RISK`
- [ ] Equity+options unified risk simulation loop — deferred (separate harness for fixture scope)
- [x] Book-aware partial fills — `simulation.book_aware_l2_v1` (OF9 fixture scope)

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
| Futures | F6 family models + F8 leverage stress | Nothing (fixture research) |
| Order Flow | OF10 MBO / queue semantics | OF9 (complete) |
| SS | Live lending ingest wiring | Vendor authorization |
| Platform | P1 catalyst/attention runtime interfaces | Nothing |
| Options | O10 advanced modeling research | O4 baseline (complete) |
| SHARED P4 | Futures outright/curve fusion extension | F8–F10 |
| Discrepancy | D-01 ignition_state mapping, D-10 deploy mirror | Nothing |

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
