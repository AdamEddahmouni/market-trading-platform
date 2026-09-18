# IMP-INTEGRATE-AND-EXPERIMENT-05 — Lane I1 (non-stub IBP SUT)

Hypothesis: `LANE-E-HYP-IBP-FACTS-SUT-V1`

## SUT definition

| Field | Value |
|---|---|
| **SUT_NAME** | IMP SmartRouter + Grounded Facts Responder |
| **SUT_VERSION** | `imp.ibp-facts-sut/1.0.0` |
| **SUT_PROFILE_ID** | `imp_historical_routing_grounded_facts_v1` |
| **SUT_MODEL_ID** | `grounded.evidence:deterministic.v1` |
| **CODE_SHA** | `7d67d48edc5760e218f946ee7fd836d6b5c431a2` (branch base; run SHA recorded in freeze artifact) |

## MODEL / BOT ROUTING

- BUILD 09 `SmartRouter` + `RoutingPolicyV1` with blind-mode → `SemanticEventType` map (Modes A–E).
- Assistant path: `GroundedEvidenceInference` only (`grounded.evidence:deterministic.v1`).
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

## Limitation classification

- **Class:** `BOUNDED_OFFLINE_NO_LLM_NO_IBP_FACT_PROMPT`
- Facts answers remain `UNKNOWN` until IBP fact prompts and authorized inference are wired; Lane I2 executes Smoke10.

## Freeze artifact

- `tests/fixtures/intelligence_benchmark/freeze/ibp_smoke10_nonstub_sut_freeze_v1.json`
- Fingerprint prefix: `BD4C88CCC1244E7D` (distinct from stub baseline `ibp-smoke10-76DDD188CD080365`)

## Out of scope (Lane I1)

- Smoke10 live run not executed
- Full30 not executed
- Stub baseline evidence under `evidence/intelligence-benchmark/imp-research-validation-04-lane-d-smoke10/` not modified
