# Short Squeeze Causal Redesign — Migration Report (Deliverable 10)

**Date:** 2026-08-18

## What changed

- Added `squeeze_core/intelligence/` — causal state machine, contracts, explanation graph (`squeeze_causal_baseline.v1`)
- Donor rows now include `causal_intelligence` via `apps/research_screener/causal_intelligence.py`
- `research_detection.ignition_state` aligned to causal state for live projections
- Frozen demo detail includes causal intelligence
- IMP `donor_bridge/projections.py` consumes causal state for UI state machine
- IMP `cross_lane/evidence.py` — normalized cross-lane evidence contract
- UI: `CausalIntelligenceBlock`, extended Zod schema
- Research docs: spec, audit, discrepancy register, architecture, matrix, gaps, roadmap, glossary

## Why it changed

Short squeeze detection must move from static SI/price screening to **evidence-gated causal states** modeling fuel, constraint, ignition, and reflexivity — without contaminating Options/Futures/Order Flow lanes.

## What was preserved

- Phase 3A canonical rules (no composite score)
- Adam Evidence-Gated Prime as **parallel comparative methodology**
- IMP read-only donor bridge architecture
- Whale lane separation (order flow, options, futures)
- Fail-closed data quality semantics
- FINRA short volume ≠ SI guardrails

## What was deprecated

- Using `research_detection.status` as squeeze lifecycle state (superseded by `causal_intelligence.state`)
- Implicit PRIME/WATCH as squeeze phase labels in UI primary state

## What remains research-only

- Calibrated horizon probabilities (explicitly `RESEARCH_ONLY`)
- ShortPainDistribution / underwater short percentages
- Utilization velocity / shares-on-loan deltas
- Exhaustion model (partial flags only)
- EV-optimized trade recommendations
- Simulator squeeze state replay

## What data is still missing

- Utilization, shares on loan, recall observability
- Verified live IBKR borrow fee at scale
- Dealer gamma positioning for most symbols
- Social attention time series
- Mechanism-labeled historical dataset at scale

## What should be built next (P2+)

1. Securities lending snapshot contract + provider matrix row updates (**P2**)
2. Walk-forward labeling pipeline for mechanism classes (**P3**)
3. Sync Railway deploy mirror with Adam coverage semantics (**P0 remaining**)

## P1 completion (2026-08-18)

| Item | Implementation |
|------|----------------|
| Hysteresis + state persistence | `hysteresis.py`, `CausalStateTransition`, `session_state._record_causal_transition` |
| Cross-lane order-flow fusion | `cross_lane_adapter.py`, `POST /api/v1/cross_lane/{symbol}`, `POST /api/v1/causal/evaluate` |
| UI threshold vs transition split | `StateTransitionBlock` — failed thresholds vs causal state transitions |
| ADR | `2026-08-18-adr-sqz-001-causal-state-machine-semantics.json` |

## Test report

Run after implementation:

```powershell
# squeeze-core intelligence tests
cd short-squeeze-project\short-squeeze-core
python -m unittest tests.intelligence.test_causal_evaluator tests.intelligence.test_hysteresis tests.app.test_causal_api

# IMP bridge tests
cd integrated-market-platform
python -m unittest tests.donor_bridge.test_causal_squeeze_projection tests.donor_bridge.test_cross_lane_adapter tests.donor_bridge.test_workspace_squeeze
```

See test output section in agent completion message.
