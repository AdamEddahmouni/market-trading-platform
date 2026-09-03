# Short Squeeze Discrepancy Register (Deliverable 2)

| ID | Existing behavior | Why incorrect/incomplete | Evidence | Risk | Recommended change | Affected files | Priority |
|---|---|---|---|---|---|---|---|
| D-01 | `ignition_state` mapped from research_detection.status | Conflates research detection with causal lifecycle | IMP `projections._ignition_state` | UI misstates squeeze phase | Use `causal_intelligence.state` only; UNKNOWN + quality flags when absent | projections.py, donor API | P0 — **RESOLVED** (fixture scope) |
| D-02 | Adam PRIME ≈ "squeeze imminent" | Static weighted dimensions, not causal states | adam_v1.py | False precision | Parallel causal evaluator; keep Adam as legacy view | intelligence/evaluator.py | P0 |
| D-03 | state_machine is single frozen snapshot | No transitions, hysteresis, or reversal | projections._build_state_machine | Misleading "STATE" UX | Causal transition metadata + live stream (future) | projections.py | P1 |
| D-04 | No utilization / shares-on-loan | Missing lender squeeze mechanics | No code references | Blind to lender squeezes | **PARTIAL (IBKR borrow path)**: `SecuritiesLendingSnapshot` + `lending_adapter.py` + session_state snapshot; utilization/shares-on-loan remain UNAVAILABLE when provider omits | intelligence contracts, lending_adapter.py | P2 |
| D-05 | No exhaustion logic | Exit thesis unsupported | None | Hold-through-collapse risk | Exhaustion evaluator — **PARTIAL (fixture scope)**: P5 single-snapshot proxy + P6 temporal fuel decline, CVD divergence history, borrow normalization, O5/O6 reversal; full exit thesis still research | intelligence/fuel.py, evaluator.py | P2 |
| D-06 | No horizon probabilities | Single implicit "squeeze likelihood" UX gap | Forbidden squeeze_probability | Over/under confidence | **PARTIAL (fixture scope)**: CALIBRATED horizons when `HorizonModelSnapshot` + PIT walk-forward pass; otherwise RESEARCH_ONLY | evaluator.py | P3 |
| D-07 | Options card on frozen donor UNAVAILABLE | Honest but blocks cross-lane fusion | institutional_ignition.py | Missed gamma context | Normalized cross-lane evidence contract | cross_lane/evidence.py | P1 — **PARTIAL (fixture scope)**: NVDA chain-only dealer/O6 evidence wired via cross_lane adapter; frozen BIYA path still UNAVAILABLE without replay context |
| D-08 | FINRA short volume collected | Could be misused as SI proxy | collectors/finra_published_si.py | Data integrity | Keep as flow feature only; document | METHODOLOGIES + spec | P0 |
| D-09 | FTD forbidden entirely | Correct exclusion but no supplemental feature | test_isolation.py | None if stays forbidden | Optional future FTD structure feature with disclaimers | metrics (future) | P4 |
| D-10 | `.railway-deploy` Adam LOW coverage drift | Deploy copy treats LOW as UNEVALUABLE | ADR 0069 vs deploy copy | Production misclassification | Sync deploy mirror | .railway-deploy/ | P0 — **RESOLVED** (adam_v1.py synced) |
| D-11 | IMP maps FAIL rules to "changed criteria" | Semantically "failed thresholds" not "state change" | StateTransitionBlock | UX confusion | Rename to failed_criteria in UI (future) | UI | P3 |
| D-12 | No ShortPainDistribution | Cannot estimate underwater shorts | No entry price data | Model gap | **PARTIAL (fixture scope)**: `ShortPainDistribution` contract + fail-closed estimator; `RESEARCH_PROXY` fixture only | squeeze_structural.py, pain_distribution.py | RESEARCH |
| D-13 | Catalyst = generic news age step | Not thesis invalidation | adam catalyst_age_hours | Weak ignition signal | **RESOLVED (fixture scope)**: MC8 `CatalystEvidence` + `ShortThesisInvalidationEvidence` via `market_context_adapter.py` on BOXL fixtures | market_context/catalyst.py, market_context_adapter.py | P3 |
| D-14 | Simulator ignores squeeze state | Non-reproducible lane replay | execution/simulator.py | Research gap | **RESOLVED (fixture scope)**: `squeeze_context` in simulator + `squeeze_replay_hash` in `risk_simulation_root_hash` | simulator, evaluation.py | P4 |

## Migration classification

| Component | Action |
|---|---|
| Phase 3A rules | KEEP |
| Adam methodology | KEEP (legacy comparative view) |
| IMP donor bridge | EXTEND |
| projections state_machine | REFACTOR |
| squeeze_score paths | DEPRECATED (already removed) |
| Calibrated probabilities | RESEARCH FIRST |
| Utilization velocity | RESEARCH FIRST |
