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

- [ ] Mechanism labels adjudication dataset
- [ ] Logistic/hazard horizon models + walk-forward harness
- [ ] Calibration reports (Brier, PR-AUC)

## P4 — Live ignition

- [ ] Streaming transition log in session_state
- [ ] Live confirmation from order flow adapter (non-fixture)

## P5 — Exhaustion

- [ ] Exhaustion subsystem + ACTIVE_SQUEEZE → EXHAUSTION transitions
- [ ] RemainingSqueezeFuel estimates

## P6 — Advanced modeling

- [ ] ShortPainDistribution research
- [ ] Magnitude model separate from occurrence
- [ ] Simulator squeeze state replay hash
