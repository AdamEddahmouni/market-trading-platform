# IBP admitted factual gold v1 (Lane M1 contract)

**Hypothesis:** `LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1`  
**Schema:** `imp.ibp-admitted-factual-gold/1.0.0`  
**Protocol version (caseset concept):** `IBP_FACTUAL_SMOKE_V1`  
**Status:** M1 — methodology + schema + invariants only. **No cases constructed.** **No Smoke10.**

## Scope

This contract defines how admitted-evidence factual benchmark cases and evaluator-only gold are represented, frozen, and kept out of the system under test (SUT). It does **not** authorize building cases, running Smoke10/Full30, or scoring SUT answers in this increment.

Historical stub gold under `tests/fixtures/intelligence_benchmark/evaluator_only/gold/IBP-CASE-*.json` (including `synthetic-gold-*` placeholders) and the Lane D Smoke10 baseline `ibp-smoke10-76DDD188CD080365` remain **historical** and are not overwritten.

## Artifacts

| Artifact | Path |
|---|---|
| JSON Schema (protocol) | `manifests/intelligence_benchmark/schemas/ibp_admitted_factual_gold_protocol.schema.json` |
| Empty protocol fixture | `tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_empty.json` |
| Validation module | `src/market_platform_foundation/intelligence/benchmark_protocol/admitted_factual_gold/` |
| Evaluator gold prefix | `evaluator_only/admitted_factual_gold/` (under `tests/fixtures/intelligence_benchmark/`) |

## Case fields

Each case (when built in M2+) carries:

- **SUT-visible:** `CASE_ID`, `MODE`, `QUESTION`, `EVIDENCE_SET`, `EVIDENCE_FINGERPRINT`, `TEMPORAL_CUTOFF`, `ANSWER_NORMALIZATION`, `UNKNOWN_POLICY`, `PROVENANCE_REQUIREMENTS`, `ROUTING_EXPECTATION`, `SCORING_GATE`, `EVIDENCE_ACCESS_MODE`
- **Evaluator-only:** `EXPECTED_FACTS`, `GOLD_HASH`, `ACCEPTABLE_EQUIVALENTS`, `evaluator_notes`, `evaluator_gold_ref`

`strip_factual_gold_evaluator_fields` / `project_factual_case_for_sut` enforce the SUT boundary.

## Admissible source types

`HISTORICAL_DEVELOPMENT_ARTIFACT`, `ADMITTED_FIXTURE_RECORD`, `CORPUS_SNAPSHOT_REF`, `GOVERNED_RESEARCH_MANIFEST`.

## Provenance chain

Every structured expected fact must link:

`expected_fact` → `source_artifact` → `source_record` → `source_hash` (`sha256:` prefix).

`PROVENANCE_REQUIREMENTS.gold_source_independent` must be `true` (gold derived from admitted evidence, not from SUT output).

## Evidence access modes (contamination)

`ADMITTED_EVIDENCE_FIXED` and `CURRENT_WEB_LOOKUP` are **mutually exclusive** within a case. Mixing historical fixed evidence and live web lookup requires an explicit protocol mode per case; validators reject mixed `evidence_access_mode` within `EVIDENCE_SET.sources`.

## Question and gold construction

- Questions must set `constructed_from_admitted_evidence_only: true`.
- Gold uses structured `EXPECTED_FACTS`, not placeholder strings (`synthetic-gold-*` forbidden).
- `ANSWER_NORMALIZATION.structured_facts_preferred` must be true; normalization covers case/whitespace, instrument symbols, ISO timestamps, numeric tolerance, and equivalent boolean/state labels without accepting incorrect facts.

## UNKNOWN policy (evaluator contract)

Encoded in `UNKNOWN_POLICY.correct_unknown_verdict`:

| Verdict | Meaning |
|---|---|
| `CORRECT_UNKNOWN` | SUT should abstain; abstention is correct |
| `UNNECESSARY_UNKNOWN` | Evidence supports an answer; unknown is incorrect |
| `UNSUPPORTED_ASSERTION` | SUT asserted facts not supported by admitted evidence |

`encoded_in_evaluator_contract` must be `true` (no post-hoc relabeling).

## Scoring gate

`SCORING_GATE=ANSWERABLE_FROM_ADMITTED_EVIDENCE` marks the scored factual subset. `EXCLUDED_UNANSWERABLE` cases may exist in the catalog but are excluded from scored factual metrics.

## Temporal cutoff and freshness

`TEMPORAL_CUTOFF` requires `contamination_control: true` and a supported `kind` (`AS_OF_INSTANT`, `SESSION_END`, `EVIDENCE_MAX_TIMESTAMP`). SUT and evidence loaders must not surface records after the cutoff.

## Hashing (M1 placeholders with algorithm)

- Algorithm: `sha256-canonical-json-v1` (canonical JSON via `canonical_bytes`)
- `caseset_hash`: over ordered `(case_id, evidence_fingerprint)` — stable for empty `cases: []`
- `goldset_hash`: over sorted `evaluator_gold_ref` paths
- `GOLD_HASH` (per case): over `case_id`, `EXPECTED_FACTS`, `UNKNOWN_POLICY`

M2 case builder must recompute hashes when cases are added and freeze the protocol (`freeze.status=FROZEN`).

## Freeze process

1. Build cases from admitted evidence only (M2).
2. Validate each case and protocol envelope.
3. Write evaluator gold under `evaluator_only/admitted_factual_gold/`.
4. Set `caseset_hash` / `goldset_hash` / per-case `GOLD_HASH`.
5. Set `freeze.cases_constructed=true` and `freeze.status=FROZEN` before any scored run.

## M2 handoff

M2 may use: types, validators, hashing helpers, SUT projection, schema paths, and the empty protocol fixture as a template. M2 must not mutate legacy `ibp_suite_catalog_v1` stub gold or re-run Smoke10 until explicitly authorized.
