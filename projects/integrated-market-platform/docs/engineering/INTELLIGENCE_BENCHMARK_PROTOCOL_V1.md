# Intelligence Benchmark Protocol v1 (RTH15-10)

**Protocol ID:** `imp-intelligence-benchmark-protocol-v1`  
**Schema:** `imp.intelligence-benchmark-protocol/1.0.0`  
**Suite:** `ibp-v1-30` (30 frozen cases; Smoke10 = first 10)  
**Evidence class:** `SOFTWARE_CONTROLLED`

This document is the authoritative software contract for Benchmark Protocol v1
controls required by RTH15-10. It does **not** claim market edge, FTEP empirical
status, Item 9 calibration, or Paper simulator calibration.

## Required properties (RTH15-10)

| Property | Enforcement |
|---|---|
| Blind SUT inputs | `build_blind_case_input` — no evaluator gold keys |
| Evaluator-only gold | `tests/fixtures/intelligence_benchmark/evaluator_only/` |
| Context reset | `one_fresh_context_per_case_v1` + unique `context_reset_token` |
| No lookahead | `lookahead_policy=FORBIDDEN` + forbidden blind keys |
| Modes A–E | Catalog rotation + `BLIND_MODE_DEFINITIONS` |
| Per-case booleans | Dimension `PASS` / `FAIL` / `INVALID` |
| Failure reasons | Explicit reason codes per failed dimension |
| Catastrophic criteria | Machine-readable `CATASTROPHIC_CRITERIA` |
| Frozen case definition | `ibp_suite_catalog_v1.json` + gold refs |
| Reproducible runner | `freeze_smoke10_run_configuration` + `execute_smoke10_baseline` |
| Smoke10 composition | First ten case ids (`IBP-CASE-001`…`010`) |
| No vanity aggregate | `vanity_aggregate_score_policy=FORBIDDEN` |
| Contaminated cases | `INVALIDATE_NO_PARTIAL_CREDIT` |

Freeze certificate builder: `build_protocol_v1_freeze_certificate`.

## Modes A–E

Modes select capability surfaces for routing checks (not profitability):

| Mode | Semantic event | Capability surface |
|---|---|---|
| A | `ORDER_FLOW_REVERSAL` | QUOTES, TRADES |
| B | `UNUSUAL_OPTIONS_ACTIVITY` | OPTIONS_CHAIN |
| C | `BORROW_CHANGE` | SHORT_INTEREST |
| D | `NEWS_EVENT` | NEWS |
| E | `REGIME_SHIFT` | MACRO, QUOTES |

## Catastrophic criteria

- `GOLD_EXPOSED_TO_SUT`
- `LOOKAHEAD_IN_SUT_INPUT`
- `CROSS_CASE_CONTEXT_LEAK`
- `LIVE_OR_ITEM9_AUTHORITY_CLAIM`
- `EXPLICIT_SUT_CATASTROPHIC_FLAG`

Triggered criteria fail the `catastrophic` dimension and contribute failure reasons.
Gold / context contamination also **invalidates** the case (`case_validity=INVALID`)
and clears scored dimensions — no partial credit.

## Smoke10 (RTH15-11)

Smoke10 may run only when `RTH15_10_COMPLETE=YES` and contamination controls pass.
Historical Lane D receipt `ibp-smoke10-76DDD188CD080365` remains immutable historical
software evidence and is not overwritten by new runs.

## Non-goals

- No Full30 requirement in RTH15-10/11
- No trading-performance score
- No Item 9 / FTEP / Live authority upgrade
