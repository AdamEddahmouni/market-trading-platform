# Short Squeeze — Current State Audit (Deliverable 1)

**Date:** 2026-08-18  
**Scope:** `short-squeeze-core` + IMP squeeze lane bridge

## Executive summary

The platform today is a **research evidence screener** with a **read-only IMP bridge**. Short squeeze logic is split: scoring/rules live in `short-squeeze-core`; IMP projects HTTP DTOs to UI. There is **no calibrated squeeze predictor** and **no true temporal state machine** until this redesign.

## Concept map

| Concept | Documented | Implemented | Source data | Consumers |
|---|---|---|---|---|
| squeeze score | Removed (ADR 0048) | Forbidden in code | N/A | N/A |
| Adam pressure/ignition | METHODOLOGIES.md | `adam_v1.py` | Finviz SI/DTC/float; IBKR return/borrow | Screener ranking |
| PRIME/WATCH tiers | METHODOLOGIES.md | Static classification | Same | Explore/scanner UI |
| research_detection | Phase 3B policy docs | `research/detection.py` | Phase 3A rules | Research classification |
| ignition_state | IMP wireframe | **Was** research_detection.status | Donor aggregate | IMP state_machine UI |
| state_machine | Wireframe 08 | Rule PASS/FAIL partition | Frozen rules | StateTransitionBlock |
| CVD | Whale ADR-003 | `cvd_formulas.py` (IMP) | Order flow fixtures | Order Flow lane |
| gamma | Not in IMP | Not implemented | N/A | N/A |
| borrow/utilization | Spec brief | Partial (borrow fee/avail rules) | IBKR+Finviz | Adam pressure |
| FTD | Explicitly excluded | Forbidden identifier | N/A | N/A |
| short volume | Documented separate | FINRA collector (flow only) | FINRA | Not scored as SI |
| probability | Not claimed | Forbidden in API | N/A | N/A |

## Data flow (today)

```text
Providers → collectors → session_state rows
    → methodologies (Adam) → HTTP API
    → IMP squeeze_client → projections.py → UI
```

Cross-lane: institutional ignition cards merge Options/Borrow/Depth at IMP replay boundary only.

## Simulator

IMP `execution/simulator.py` is bar-conservative Phase 7 — **not yet replaying squeeze states**.

## Tests

- Adam/truthfulness: `tests/app/test_batch14_methodology_engine.py`
- Bridge: `tests/donor_bridge/test_workspace_squeeze.py`
- Lane acceptance: `tools/integration/squeeze_lane_acceptance.py`

## Sound architecture preserved

- Provider-agnostic evidence gates
- Phase 3A no composite score
- Point-in-time eligibility on Adam inputs
- Fail-closed missing data
- Separate whale lanes (order flow, options, futures)
