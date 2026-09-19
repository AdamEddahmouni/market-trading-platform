# IMP-INTEGRATE-AND-EXPERIMENT-05 — Lane H (Research Findings / Hypothesis Registry)

Lane H synthesizes **bounded historical observations** from frozen Baseline Pack v1 (fixture), OpenD Baseline Pack v2 (prediction-coupled), and Lane E Smoke10 stub references. It does **not** prove profitability, calibration, or production readiness.

## Authority

- Market / harness findings: `HISTORICAL_DEVELOPMENT` or `BOUNDED_HISTORICAL_OBSERVATION` per row
- Smoke10: intelligence-benchmark **observation**; non-stub run **not executed** in Lane H

## Machine-readable artifacts

| Artifact | Path |
|----------|------|
| Findings registry | `evidence/historical-research/imp-integrate-experiment-05-lane-h-findings/findings_registry_v1.json` |
| Hypothesis queue (ranked) + Lane E closures | `evidence/historical-research/imp-integrate-experiment-05-lane-h-findings/hypothesis_queue_v1.json` |
| Synthesis receipt | `evidence/historical-research/imp-integrate-experiment-05-lane-h-findings/lane_h_synthesis_receipt.json` |

## Source runs (read-only; frozen)

| Source | Key identifier |
|--------|----------------|
| Lane C v1 | `C2E70673…`, pack `17158E3B…`, fixture `EFCC71DF…`, `prediction_coupled_simulator=false` |
| Integrate R2 v2 (PR #268) | `E8C9ADB9…`, pack `F660218C…`, OpenD `355FDBB…`, `CODE_SHA` `0ef9a72c`, `prediction_coupled_simulator=true` |
| Lane D stub Smoke10 | `ibp-smoke10-76DDD188CD080365` (10/10 `FACTS_MISMATCH` expected) |
| Lane I1 / PR #267 | Non-stub SUT defined; **NOT_EXECUTED** / `PENDING_I1_REVIEW` |

## Findings summary (`LANE-H-FND-001` … `LANE-H-FND-009`)

- v1 pathology (9 fills / zero PnL for all strategies including no-trade) vs v2 no-trade `0/0/0` under prediction coupling — **machinery**, not edge
- v2 directional baselines: fill counts `387/387/386`, `387/387/386`, `148/148/147`; validate directional_accuracy ~0.46–0.53 — **descriptive only**
- Zero gross/net/costs despite fills → follow-up `LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3` (no v2 retune)
- v2 contamination PASS; deterministic fingerprint `32B9F7CA…` MATCH
- Governance: Item 9 untouched, LIVE OFF, #222 and #267 isolated
- IBP stub Smoke10 unchanged; non-stub Smoke10 not run

Finding contract fields: `FINDING_ID`, `SOURCE_RUN`, `OBSERVATION`, `LIMITATION`, `POSSIBLE_CAUSE`, `FOLLOW_UP_HYPOTHESIS`, `REQUIRED_DATA`, `PROPOSED_TEST`, `AUTHORITY`.

## Hypothesis queue (ranked)

| Rank | ID | Rationale |
|------|-----|-----------|
| 1 | `LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3` | Non-zero PnL/costs in a **new** v3 experiment after engineering |
| 2 | `LANE-H-HYP-IBP-NONSTUB-SMOKE10-EXEC-V1` | Smoke10 with non-stub SUT after I1 review |
| 3 | `LANE-H-HYP-BASELINE3-VOLUME-OPEND-V3` | Volume threshold ablation on OpenD (deferred) |
| 4 | `LANE-H-HYP-IBP-FULL30-AFTER-SMOKE-V1` | FULL30 after non-stub smoke exists |

Lane E hypotheses `LANE-E-HYP-OPEND-MULTI-SESSION-V2`, `LANE-E-HYP-SIMULATOR-PREDICTION-COUPLED-V1`, and `LANE-E-HYP-BASELINE0-SIM-ALIGNMENT-V1` are closed as **observed** in `lane_e_hypothesis_closure` (bounded authority).

## Non-goals (observed)

- No edits to frozen v2 evidence under `imp-integrate-experiment-05-r2-opend-baseline-pack-v2/`
- No Smoke10 execution (stub or non-stub)
- No simulator code changes in Lane H
- No Item 9 collection, no PR #222 / #267 merge, no live trading
