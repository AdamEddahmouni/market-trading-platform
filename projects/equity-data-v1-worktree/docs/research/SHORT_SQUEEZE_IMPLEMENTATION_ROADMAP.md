# Short Squeeze Implementation Roadmap (Deliverable 7)

## P0 — Correctness (complete / in progress)

- [x] Causal state contracts + baseline evaluator (`squeeze_causal_baseline.v1`)
- [x] Donor `causal_intelligence` API field
- [x] IMP bridge projection + UI schema
- [x] Cross-lane evidence contract stub
- [x] Discrepancy register + research spec
- [x] Sync `.railway-deploy` Adam coverage semantics with main tree (no deploy mirror present in repository; semantics bound to donor_bridge `_coverage_label`)

## P1 — Structural architecture

- [x] Persist prior causal state for hysteresis/cooldown in session_state
- [x] Wire IMP order-flow normalized evidence into donor cross_lane input
- [x] Rename UI "changed criteria" → failed thresholds vs state transitions
- [x] ADR for causal state machine semantics (`ADR-SQZ-001`)

## P2 — Feature / data integration

- [x] Securities lending snapshot contract (utilization, shares on loan) — `contracts/squeeze_structural.py`
- [x] Velocity/acceleration metrics with PIT publication rules — `VelocityAccelerationMetric`
- [x] Attention feature family interfaces — `AttentionFeature`
- [x] CatalystStrength / ShortThesisInvalidation interfaces — `contracts/squeeze_structural.py`

## P3 — Baseline models

- [x] Mechanism labels adjudication dataset — fixture `tests/fixtures/squeeze/mechanism_labels.json`
- [x] Logistic/hazard horizon models + walk-forward harness — `research/squeeze_models/`
- [x] Calibration reports (Brier, PR-AUC) — `research/squeeze_models/calibration.py`

## P4 — Live ignition

- [x] Streaming transition log in session_state — donor `causal_transitions` + IMP `transition_stream` replay
- [x] Cross-lane causal fusion in current mode — `_merge_cross_lane_causal` with `effective_cutoff`
- [x] Recorded order-flow adapter — `RecordedOrderFlowProvider` + `IMP_ORDER_FLOW_LIVE=1` gate (fixture replay)
- [x] Options O6 dealer evidence on cross_lane snapshot — `options_gamma_amplification` flag
- [ ] Live broker tick ingest (deferred — requires adapter authorization)

## P5 — Active squeeze + remaining fuel

- [x] Fuel subsystem (`intelligence/fuel.py`) — reflexivity, covering proxy, remaining fuel, exhaustion risk
- [x] ACTIVE_SQUEEZE → EXHAUSTION transitions via exhaustion_risk threshold (fixture scope)
- [x] RemainingSqueezeFuel estimates — structural vulnerability minus order-flow covering proxy
- [x] IMP cross-lane `REMAINING_SQUEEZE_FUEL` + `EXHAUSTION_RISK` evidence for Options consumers

## P6 — Advanced exhaustion

- [x] Temporal fuel decline — `FuelHistorySnapshot` wired from transition stream
- [x] CVD divergence history — prior slope comparison in `fuel.py`
- [x] Borrow normalization proxy — lending fixture + `borrow_normalization_score` on cross_lane
- [x] O5/O6 exhaustion signals — flow reversal + gamma decay on donor snapshot
- [x] ShortPainDistribution research interface — `ShortPainDistribution` contract + fail-closed estimator (fixture proxy only)
- [x] Simulator squeeze state replay hash — D-14 resolved via `squeeze_simulation_context` + `squeeze_replay_hash`

## P7 — Advanced models

- [x] ShortPainDistribution contract — `contracts/squeeze_structural.py` + `pain_distribution.py` (`RESEARCH_PROXY` fixture scope)
- [x] Magnitude baseline — separate from occurrence (`ss_magnitude_baseline_v1`)
- [x] Rare-event logistic ensemble — `ss_rare_event_ensemble_v1` with precision@K in walk-forward harness
- [x] Calibrated horizons in donor evaluator v4 — `HorizonModelSnapshot` + `horizon_model_bridge.py`
- [x] Simulator squeeze-state replay — `BarConservativeSimulator` v1.1.0 + `risk_simulation_root_hash` extension
- [ ] True entry-price inference pipeline — deferred (open research)
- [ ] External ML libraries (XGBoost/sklearn) — deferred
