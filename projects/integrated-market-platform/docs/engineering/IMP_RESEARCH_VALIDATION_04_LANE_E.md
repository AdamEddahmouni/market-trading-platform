# IMP-RESEARCH-VALIDATION-04 — Lane E (Research Findings / Hypothesis Queue)

Lane E synthesizes **historical observations** from completed Lane C (Historical Baseline Pack v1) and Lane D (Smoke10) runs. It does **not** prove profitability, calibration, or production readiness.

## Authority

- Market findings: `HISTORICAL_DEVELOPMENT`
- Smoke10: intelligence-benchmark **observation** under `imp-intelligence-benchmark-protocol/1.0.0`

## Machine-readable artifacts

| Artifact | Path |
|----------|------|
| Findings registry | `evidence/historical-research/imp-research-validation-04-lane-e-findings/findings_registry_v1.json` |
| Hypothesis queue (ranked) | `evidence/historical-research/imp-research-validation-04-lane-e-findings/hypothesis_queue_v1.json` |
| Synthesis receipt | `evidence/historical-research/imp-research-validation-04-lane-e-findings/lane_e_synthesis_receipt.json` |

## Source runs (read-only; other worktrees/branches)

| Lane | Branch | Key identifier |
|------|--------|----------------|
| C | `research/historical-baselines-v1` | Pack `17158E3B…`, `EXPERIMENT_HASH` `C2E706736B1EE70EDB99BDA9F7533FA59C6FAA2623995EB4422AE6FC02D66E1E`, fixture dataset `EFCC71DF…` |
| D | `benchmarks/smoke10-baseline` | `run_id` `ibp-smoke10-76DDD188CD080365`, `scores_executed` true, `full30_executed` false |
| B (dataset pin for hypotheses) | `data/real-historical-verification` | OpenD AAPL fingerprint `355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B` |

## Findings summary

Eleven findings (`LANE-E-FND-001` … `LANE-E-FND-011`) cover:

- Fixture-pathological momentum vs mean-reversion accuracy (1.0 vs 0.0)
- Simulator bar-path replay vs prediction-conditioned fills/PnL
- Baseline 0 abstention vs nonzero simulator fills
- Volume-momentum abstention on small validate sample
- Baseline pack contamination PASS (contractual scope)
- Fixture reproducibility fingerprint match
- Smoke10 execution vs FULL30 deferral
- Universal `FACTS_MISMATCH` under deterministic stub SUT
- Non-facts dimensions PASS 10/10
- Smoke10 gold isolation PASS
- IBP-CASE-001..010 catalog (not legacy CASE-019 list)

Full rows use the contract fields: `FINDING_ID`, `SOURCE_RUN`, `OBSERVATION`, `CONFIDENCE / LIMITATION`, `POSSIBLE_CAUSE`, `FOLLOW-UP_HYPOTHESIS`, `DATA NEEDED`, `PROPOSED TEST`, `AUTHORITY`.

## Hypothesis queue (ranked)

| Rank | ID | Rationale |
|------|-----|-----------|
| 1 | `LANE-E-HYP-OPEND-MULTI-SESSION-V2` | Escape fixture pathology on verified OpenD corpus (**NEW** experiment only) |
| 2 | `LANE-E-HYP-BASELINE3-VOLUME-THRESHOLD` | Volume gate behavior on real sessions |
| 3 | `LANE-E-HYP-SIMULATOR-PREDICTION-COUPLED-V1` | Explain identical sim fills across baselines |
| 4 | `LANE-E-HYP-BASELINE0-SIM-ALIGNMENT-V1` | No-trade / simulator metric alignment |
| 5 | `LANE-E-HYP-IBP-FACTS-SUT-V1` | Non-stub facts dimension on Smoke10 |
| 6 | `LANE-E-HYP-IBP-FULL30-BENCHMARK-V1` | FULL30 suite after smoke subset |

Queue entries include falsification claims, dataset pins, train/dev/test policy, metrics, failure conditions, leakage risks, and promotion evidence requirements. **None are implemented in Lane E.**

## Non-goals (observed)

- No edits to Lane C frozen experiment definitions or Smoke10 config
- No retuning, no follow-up experiment execution
- Frozen collector `.imp-actual-01-phase-d` @ `fed2d9f7` untouched

## Related docs

- [RESEARCH_EXPERIMENT_SYSTEM_V1.md](RESEARCH_EXPERIMENT_SYSTEM_V1.md) — BUILD 17 epistemic ladder
- Lane C evidence (separate branch): `evidence/historical-research/imp-research-validation-04-lane-c-baseline-pack-v1/`
