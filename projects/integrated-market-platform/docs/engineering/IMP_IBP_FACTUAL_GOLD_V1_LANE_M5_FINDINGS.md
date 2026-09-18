# IMP-IBP-FACTUAL-GOLD-V1 — Lane M5 findings (post-baseline)

Lane M5 findings synthesize **historical observations** from the merged
`IBP_FACTUAL_SMOKE_V1` baseline run (`RUN_ID` `ibp-factual-smoke-28EA7748057E312D`,
[#280](https://github.com/AdamEddahmouni/market-trading-platform/pull/280)). This lane
registers **capability-gap hypotheses only** — no SUT implementation, no gold
retrofit, no smoke rerun.

## Authority

- Benchmark observation: `HISTORICAL_DEVELOPMENT`
- Evaluator gold: **`EVALUATOR_ONLY`** (`BENCHMARK_GOLD_AUTHORITY`)
- OpenD v3 machinery: **`HISTORICAL_DEVELOPMENT`** (`V3_AUTHORITY`) — unchanged

## Machine-readable artifacts

| Artifact | Path |
|----------|------|
| Findings registry | `evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5-findings/findings_registry_v1.json` |
| Hypothesis queue (ranked) | `evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5-findings/hypothesis_queue_v1.json` |
| Synthesis receipt | `evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5-findings/lane_m5_synthesis_receipt.json` |

## Source run (read-only on `main`)

| Field | Value |
|-------|-------|
| Protocol | `IBP_FACTUAL_SMOKE_V1` |
| `RUN_ID` | `ibp-factual-smoke-28EA7748057E312D` |
| Cases scored | 11 (`IBP-FACTUAL-EXCL-001` excluded) |
| SUT profile | `imp_historical_routing_grounded_facts_v1` |
| Software landing SHA | `3aa87e51` ([#280](https://github.com/AdamEddahmouni/market-trading-platform/pull/280)) — **not** the docs findings commit |
| Pre-run gates | **PASS** |
| Contamination audit | **PASS** |

## Score summary (preserved failures)

| Dimension / verdict | Result |
|---------------------|--------|
| **facts** | **FAIL 11/11** |
| **unknown_handling** | **FAIL 7 / PASS 4** |
| **FACT_MISMATCH** | **5** |
| **UNNECESSARY_UNKNOWN** | **7** |
| catastrophic, final_state, freshness, operator_close, provenance, **routing** | **PASS 11/11** each |

**Routing PASS does not imply SUT factual quality.** Facts failures indicate an
**intelligence capability gap**, not invalidity of the admitted factual gold
methodology.

## Legacy Smoke10 comparison

Legacy `ibp-smoke10-76DDD188CD080365` used **synthetic** evaluator gold and a
deterministic UNKNOWN stub SUT. Comparison to `IBP_FACTUAL_SMOKE_V1` is
**structural only** — not an apples-to-apples intelligence delta.

| Protocol | `SMOKE10_JUSTIFIED` (facts-meaningful) |
|----------|----------------------------------------|
| Legacy IBP-CASE stub catalog | **NO** (synthetic-gold-NNN) |
| **`IBP_FACTUAL_SMOKE_V1`** | **YES** (executed once; facts failed; methodology valid) |

## Findings (`LANE-M5-FND-001` … `008`)

Eight findings cover: baseline gate satisfaction, universal facts FAIL,
`FACT_MISMATCH` / `UNNECESSARY_UNKNOWN` counts, non-facts dimensional PASS,
routing orthogonality, legacy structural comparison, and protocol-specific
`SMOKE10_JUSTIFIED`.

## Hypothesis queue (capability gaps — not implemented)

| Rank | ID | Gap |
|------|-----|-----|
| 1 | `LANE-M5-HYP-GROUNDED-FACT-EXTRACTION-V1` | Structured facts from admitted evidence |
| 2 | `LANE-M5-HYP-ANSWERABLE-EVIDENCE-UNKNOWN-V1` | UNNECESSARY_UNKNOWN / unknown_handling |
| 3 | `LANE-M5-HYP-STRUCTURED-FACT-NORMALIZATION-V1` | FACT_MISMATCH normalization policy |

**Closure:** `LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1` → methodology observed
(baseline recorded); intelligence gaps remain open.

## Invariants (unchanged)

| Token | Value |
|-------|-------|
| `ITEM9_CALIBRATED` | **NO** |
| Item 7 forecast | **not ready** |
| PR #222 | **isolated** |
| `FTEP_EMPIRICAL_ACTIVE` | **NO** |
| Live | **OFF** |
| Frozen collector | `.imp-actual-01-phase-d` @ **`fed2d9f7`** |

## Non-goals (this lane)

- No SUT patch from gold
- No factual smoke rerun
- No PR #222 merge
- No Item 9 mutation
- No Full30 execution

## Related docs

- [IBP_ADMITTED_FACTUAL_GOLD_V1.md](IBP_ADMITTED_FACTUAL_GOLD_V1.md)
- Baseline receipt: `evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5/factual_smoke_baseline_evidence_receipt.json`
