# IMP-INTEGRATE-AND-EXPERIMENT-05 — Lane I1 (non-stub IBP SUT)

Hypothesis: `LANE-E-HYP-IBP-FACTS-SUT-V1`

## SUT definition

| Field | Value |
|---|---|
| **SUT_NAME** | IMP SmartRouter + Grounded Facts Responder |
| **SUT_VERSION** | `imp.ibp-facts-sut/1.0.0` |
| **SUT_PROFILE_ID** | `imp_historical_routing_grounded_facts_v1` |
| **SUT_MODEL_ID** | `grounded.evidence:deterministic.v1` |

## Git SHA vs freeze `code_sha` (operator clarity)

| Label | SHA | Meaning |
|---|---|---|
| **SUT logic commit** | `109fd650df4998d953450eda267e8edfdad6de81` | Commit that introduced grounded resolvers + historical evidence context (what frozen `code_sha` pins). |
| **Freeze pin commit** | `925025e96cd98eb36e262b7485258f5071ecd713` (verify on branch) | Commit that regenerated/pinned `tests/fixtures/intelligence_benchmark/freeze/ibp_smoke10_nonstub_sut_freeze_v1.json` without changing SUT logic. |

Frozen Smoke10 configuration intentionally records **`code_sha` = SUT logic commit**, not necessarily the latest doc/hygiene commit on the branch.

## MODEL / BOT ROUTING

- BUILD 09 `SmartRouter` + `RoutingPolicyV1` with blind-mode → `SemanticEventType` map (Modes A–E).
- Assistant path: `GroundedEvidenceInference` only (`grounded.evidence:deterministic.v1`).
- Historical fixture path: Lane B build → replay snapshot → `build_evidence_context` (`resolve_explain` / `resolve_inspect`).
- No Anthropic/network LLM in this bounded SUT (`network_llm_access: DENY` in frozen tool policy).

## TOOLS AVAILABLE

- `historical_development_fixture_reader`
- `smart_router_route`
- `grounded_evidence_infer`

## CONTEXT RULES

- `one_fresh_context_per_case_v1`
- Stateless runner (no cross-case memory)
- Evaluator gold prefix blocked (`evaluator_only/`)
- Scoring only after SUT response completes
- `ReplayStore.load_decoded_snapshot` stays **`FIXTURE_REPLAY`** (no live observational promotion on refresh)

## Limitation classification

- **Class:** `BOUNDED_OFFLINE_NO_LLM_GROUNDED_HISTORICAL`
- Grounded citations can be emitted when `historical_harness_fixture` is present and resolvers build successfully.
- **Smoke10 catalog coverage:** only **1/10** Smoke10 cases (`IBP-CASE-001`) carry `historical_harness_fixture`; **9/10** remain `UNKNOWN` + `EVIDENCE_RESOLVER_MISSING` by construction (not a resolver wiring bug alone).
- **Facts dimension vs evaluator gold:** all ten Smoke10 `gold_answer` values are **synthetic placeholders** (`synthetic-gold-001` … `010`), not factual strings aligned to grounded citations. Passing facts without gaming requires an **independently specified** factual gold/prompt corpus over admitted evidence — **not present** in `evaluator_only/gold/` today.
- **Unknown-handling risk:** stub SUT returns `UNKNOWN` for all cases (10/10 unknown_handling pass). Non-stub CASE-001 can emit cite-backed non-`UNKNOWN` text while gold remains `synthetic-gold-001` → likely **facts FAIL** and possible **unknown_handling REGRESSION** vs stub unless gold/corpus is redesigned.

## Smoke10 expectation (honest)

- **GOLD_ISOLATION:** PASS (SUT path does not read evaluator gold).
- **SMOKE10_JUSTIFIED for facts-meaningful scoring:** **NO** until real fact gold + evidence alignment exists and fixture coverage is specified by governance — not by copying one AAPL fixture onto all cases.
- Resolver hygiene (cite-backed path when evidence exists) is **necessary but not sufficient** for a meaningful Smoke10 facts run.

## Freeze artifact

- Path: `tests/fixtures/intelligence_benchmark/freeze/ibp_smoke10_nonstub_sut_freeze_v1.json`
- **`code_sha` (pinned SUT logic):** `109fd650df4998d953450eda267e8edfdad6de81`
- **Fingerprint prefix:** `4720493F` (full: `4720493F6448021E5AD4DE878E31B7EB63909BE75558992B275C9F6CCE9CF2D2`)
- Distinct from stub baseline `ibp-smoke10-76DDD188CD080365`

## Evaluator gold audit (Smoke10, read-only)

| Case | `gold_answer` | Nature |
|---|---|---|
| IBP-CASE-001 … IBP-CASE-010 | `synthetic-gold-001` … `synthetic-gold-010` | **Synthetic placeholder** (no factual corpus keys) |

No alternate IBP fact-prompt / factual gold catalog exists under `tests/fixtures/intelligence_benchmark/` beyond these placeholders.

## Out of scope (Lane I1 / hygiene)

- Smoke10 live run not executed
- Full30 not executed
- Stub baseline evidence under `evidence/intelligence-benchmark/imp-research-validation-04-lane-d-smoke10/` not modified
- Inventing or rewriting evaluator gold to match grounded SUT output
