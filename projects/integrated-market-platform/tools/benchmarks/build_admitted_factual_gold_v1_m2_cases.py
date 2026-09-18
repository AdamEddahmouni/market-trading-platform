"""Lane M2: construct IBP admitted factual gold candidate cases (evaluator-only)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold import (
    compute_case_gold_hash,
    compute_caseset_hash,
    compute_goldset_hash,
    factual_gold_hash_algorithm,
    validate_factual_gold_protocol,
)

GOLD_PREFIX = "evaluator_only/admitted_factual_gold/"
FIXTURE_ROOT = REPO / "tests" / "fixtures" / "intelligence_benchmark" / "admitted_factual_gold"
GOLD_DIR = REPO / "tests" / "fixtures" / "intelligence_benchmark" / "evaluator_only" / "admitted_factual_gold"


def _artifact_sha256(rel_path: str) -> str:
    digest = hashlib.sha256((REPO / rel_path).read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _evidence_fingerprint(evidence_set: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(evidence_set)).hexdigest()
    return f"sha256:{digest}"


def _norm_block() -> dict[str, Any]:
    return {
        "structured_facts_preferred": True,
        "case_folding": True,
        "trim_whitespace": True,
        "collapse_internal_whitespace": True,
        "instrument_symbol_canonicalization": True,
        "iso_timestamp_normalization": True,
        "numeric_tolerance": {"relative": 1e-9},
        "boolean_label_equivalence": True,
        "state_label_equivalence": True,
    }


def _provenance_block() -> dict[str, Any]:
    return {
        "gold_source_independent": True,
        "chain": ["expected_fact", "source_artifact", "source_record", "source_hash"],
    }


def _base_case(
    *,
    case_id: str,
    mode: str,
    question_text: str,
    question_class: str,
    artifact_ref: str,
    source_type: str,
    temporal_kind: str,
    cutoff_instant: str,
    expected_facts: list[dict[str, Any]],
    unknown_verdict: str,
    routing: dict[str, Any],
    scoring_gate: str,
    evaluator_notes: str,
) -> dict[str, Any]:
    evidence_set = {
        "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
        "sources": [
            {
                "source_type": source_type,
                "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
                "artifact_ref": artifact_ref,
            }
        ],
    }
    unknown_policy = {
        "correct_unknown_verdict": unknown_verdict,
        "encoded_in_evaluator_contract": True,
    }
    gold_hash = compute_case_gold_hash(
        case_id=case_id,
        expected_facts=expected_facts,
        unknown_policy=unknown_policy,
    )
    return {
        "CASE_ID": case_id,
        "MODE": mode,
        "QUESTION": {
            "text": question_text,
            "constructed_from_admitted_evidence_only": True,
            "question_class": question_class,
        },
        "EVIDENCE_ACCESS_MODE": "ADMITTED_EVIDENCE_FIXED",
        "EVIDENCE_SET": evidence_set,
        "EVIDENCE_FINGERPRINT": _evidence_fingerprint(evidence_set),
        "TEMPORAL_CUTOFF": {
            "kind": temporal_kind,
            "cutoff_instant": cutoff_instant,
            "contamination_control": True,
        },
        "EXPECTED_FACTS": expected_facts,
        "ANSWER_NORMALIZATION": _norm_block(),
        "ACCEPTABLE_EQUIVALENTS": [],
        "UNKNOWN_POLICY": unknown_policy,
        "PROVENANCE_REQUIREMENTS": _provenance_block(),
        "ROUTING_EXPECTATION": routing,
        "GOLD_HASH": gold_hash,
        "SCORING_GATE": scoring_gate,
        "evaluator_gold_ref": f"{GOLD_PREFIX}{case_id}.json",
        "evaluator_notes": evaluator_notes,
    }


def _fact(
    expected: dict[str, Any],
    artifact: str,
    record: str,
) -> dict[str, Any]:
    return {
        "expected_fact": expected,
        "source_artifact": artifact,
        "source_record": record,
        "source_hash": _artifact_sha256(artifact),
    }


def build_cases() -> list[dict[str, Any]]:
    sample = "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
    multi = "tests/fixtures/historical_development/aapl_2026-09-11_2026-09-15_rth_multi_session.json"
    frozen = (
        "evidence/historical-research/imp-research-validation-04-lane-c-baseline-pack-v1/"
        "frozen_experiment_definition.json"
    )
    wave1 = "tests/fixtures/research/wave1_non_empirical_export.json"
    matlab = "tests/fixtures/research/matlab_golden_result_v1.json"
    lane_b = "evidence/market_data/lane_b/real-historical-provider-verification.json"

    multi_data = json.loads((REPO / multi).read_text(encoding="utf-8"))
    session_keys = sorted(multi_data.keys())

    cases: list[dict[str, Any]] = []

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-001",
            mode="FACTUAL",
            question_class="MARKET_INSTRUMENT",
            question_text=(
                "From the admitted AAPL historical development sample for 2026-09-15, "
                "what instrument code appears on the first bar row?"
            ),
            artifact_ref=sample,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            temporal_kind="SESSION_END",
            cutoff_instant="2026-09-15T20:00:00Z",
            expected_facts=[
                _fact(
                    {"field": "instrument_code", "value": "US.AAPL"},
                    sample,
                    "session:2026-09-15;row:0;field:code",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "HISTORICAL_FACTUAL", "lane": "market_data"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — instrument from first admitted bar row.",
        )
    )

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-002",
            mode="FACTUAL",
            question_class="SESSION_IDENTITY",
            question_text=(
                "How many top-level session date keys are present in the admitted "
                "multi-session AAPL historical development fixture?"
            ),
            artifact_ref=multi,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            temporal_kind="EVIDENCE_MAX_TIMESTAMP",
            cutoff_instant="2026-09-15T20:00:00Z",
            expected_facts=[
                _fact(
                    {"field": "session_key_count", "value": len(session_keys)},
                    multi,
                    "root:session_keys",
                ),
                _fact(
                    {"field": "session_dates", "value": session_keys},
                    multi,
                    "root:session_keys",
                ),
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "HISTORICAL_FACTUAL", "lane": "market_data"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — session coverage from fixture keys only.",
        )
    )

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-003",
            mode="FACTUAL",
            question_class="ROW_COUNT",
            question_text=(
                "In the admitted 2026-09-15 AAPL sample fixture, how many raw bar rows "
                "are recorded under the 2026-09-15 session key?"
            ),
            artifact_ref=sample,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            temporal_kind="SESSION_END",
            cutoff_instant="2026-09-15T20:00:00Z",
            expected_facts=[
                _fact(
                    {"field": "raw_row_count", "value": 5},
                    sample,
                    "session:2026-09-15",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "HISTORICAL_FACTUAL", "lane": "market_data"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — includes contamination rows by design.",
        )
    )

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-004",
            mode="STATE",
            question_class="CONTAMINATION_SIGNAL",
            question_text=(
                "In the admitted 2026-09-15 AAPL sample fixture, how many rows use the "
                "literal time_key value 'not-a-timestamp'?"
            ),
            artifact_ref=sample,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            temporal_kind="SESSION_END",
            cutoff_instant="2026-09-15T20:00:00Z",
            expected_facts=[
                _fact(
                    {"field": "malformed_time_key_rows", "value": 1},
                    sample,
                    "session:2026-09-15;filter:time_key=not-a-timestamp",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "QUALITY_INTERPRETATION", "lane": "market_data"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — malformed timestamp row in admitted fixture.",
        )
    )

    frozen_doc = json.loads((REPO / frozen).read_text(encoding="utf-8"))
    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-005",
            mode="RESEARCH",
            question_class="GOVERNED_MANIFEST",
            question_text=(
                "What dataset_id is declared in the admitted frozen historical baseline "
                "pack experiment definition?"
            ),
            artifact_ref=frozen,
            source_type="GOVERNED_RESEARCH_MANIFEST",
            temporal_kind="AS_OF_INSTANT",
            cutoff_instant="2026-09-15T23:59:59Z",
            expected_facts=[
                _fact(
                    {"field": "dataset_id", "value": frozen_doc["dataset"]["dataset_id"]},
                    frozen,
                    "dataset:dataset_id",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "RESEARCH_MANIFEST", "lane": "historical_research"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — frozen Lane C experiment definition pin.",
        )
    )

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-006",
            mode="RESEARCH",
            question_class="BASELINE_PACK",
            question_text=(
                "How many baseline_strategies entries are listed in the admitted frozen "
                "historical baseline pack experiment definition?"
            ),
            artifact_ref=frozen,
            source_type="GOVERNED_RESEARCH_MANIFEST",
            temporal_kind="AS_OF_INSTANT",
            cutoff_instant="2026-09-15T23:59:59Z",
            expected_facts=[
                _fact(
                    {
                        "field": "baseline_strategy_count",
                        "value": len(frozen_doc["baseline_strategies"]),
                    },
                    frozen,
                    "baseline_strategies",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "RESEARCH_MANIFEST", "lane": "historical_research"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — strategy enumeration from frozen definition.",
        )
    )

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-007",
            mode="ROUTING",
            question_class="AUTHORITY_CLASS",
            question_text=(
                "What corpus_evidence_authority value is declared at the top level of the "
                "admitted frozen historical baseline pack experiment definition?"
            ),
            artifact_ref=frozen,
            source_type="GOVERNED_RESEARCH_MANIFEST",
            temporal_kind="AS_OF_INSTANT",
            cutoff_instant="2026-09-15T23:59:59Z",
            expected_facts=[
                _fact(
                    {
                        "field": "corpus_evidence_authority",
                        "value": frozen_doc["corpus_evidence_authority"],
                    },
                    frozen,
                    "corpus_evidence_authority",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "AUTHORITY_ROUTING", "lane": "governance"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — authority routing from admitted manifest.",
        )
    )

    wave_doc = json.loads((REPO / wave1).read_text(encoding="utf-8"))
    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-008",
            mode="RESEARCH",
            question_class="VALIDATION_MANIFEST",
            question_text=(
                "What validation_dataset_id is declared in the admitted Wave-1 non-empirical "
                "research export fixture?"
            ),
            artifact_ref=wave1,
            source_type="GOVERNED_RESEARCH_MANIFEST",
            temporal_kind="AS_OF_INSTANT",
            cutoff_instant="2026-09-15T23:59:59Z",
            expected_facts=[
                _fact(
                    {
                        "field": "validation_dataset_id",
                        "value": wave_doc["validation_dataset_manifest"]["validation_dataset_id"],
                    },
                    wave1,
                    "validation_dataset_manifest:validation_dataset_id",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "RESEARCH_MANIFEST", "lane": "wave1"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — Wave-1 validation manifest id.",
        )
    )

    matlab_doc = json.loads((REPO / matlab).read_text(encoding="utf-8"))
    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-009",
            mode="RESEARCH",
            question_class="PARITY_RECEIPT",
            question_text=(
                "In the admitted MATLAB golden research result fixture, what feature_row_count "
                "is recorded under diagnostics?"
            ),
            artifact_ref=matlab,
            source_type="ADMITTED_FIXTURE_RECORD",
            temporal_kind="AS_OF_INSTANT",
            cutoff_instant="2026-09-15T23:59:59Z",
            expected_facts=[
                _fact(
                    {
                        "field": "feature_row_count",
                        "value": matlab_doc["diagnostics"]["feature_row_count"],
                    },
                    matlab,
                    "diagnostics:feature_row_count",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "RESEARCH_RECEIPT", "lane": "matlab_parity"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — structured diagnostics from golden result fixture.",
        )
    )

    lane_doc = json.loads((REPO / lane_b).read_text(encoding="utf-8"))
    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-010",
            mode="PROVENANCE",
            question_class="PROVIDER_VERIFICATION",
            question_text=(
                "In the admitted Lane B real historical provider verification receipt, what "
                "ROWS count is recorded for the moomoo block?"
            ),
            artifact_ref=lane_b,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            temporal_kind="AS_OF_INSTANT",
            cutoff_instant="2026-09-16T23:59:59Z",
            expected_facts=[
                _fact(
                    {"field": "moomoo_rows", "value": lane_doc["moomoo"]["ROWS"]},
                    lane_b,
                    "moomoo:ROWS",
                )
            ],
            unknown_verdict="UNNECESSARY_UNKNOWN",
            routing={"template": "PROVENANCE_RECEIPT", "lane": "market_data"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — bounded provider verification receipt (not Item 9).",
        )
    )

    cases.append(
        _base_case(
            case_id="IBP-FACTUAL-011",
            mode="UNKNOWN",
            question_class="ABSTENTION",
            question_text=(
                "From the admitted 2026-09-15 AAPL sample fixture only, what is the closing "
                "price for MSFT on 2026-09-15?"
            ),
            artifact_ref=sample,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            temporal_kind="SESSION_END",
            cutoff_instant="2026-09-15T20:00:00Z",
            expected_facts=[
                _fact(
                    {"field": "answerability", "value": "NOT_IN_ADMITTED_EVIDENCE"},
                    sample,
                    "session:2026-09-15;instrument_scope",
                )
            ],
            unknown_verdict="CORRECT_UNKNOWN",
            routing={"template": "UNKNOWN_ABSTAIN", "lane": "market_data"},
            scoring_gate="ANSWERABLE_FROM_ADMITTED_EVIDENCE",
            evaluator_notes="M2 candidate — correct abstention; MSFT not present in evidence.",
        )
    )

    # EXCLUDED: metric not present in any admitted static artifact.
    excluded_unknown = {
        "correct_unknown_verdict": "CORRECT_UNKNOWN",
        "encoded_in_evaluator_contract": True,
    }
    excluded_evidence = {
        "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
        "sources": [
            {
                "source_type": "GOVERNED_RESEARCH_MANIFEST",
                "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
                "artifact_ref": frozen,
            }
        ],
    }
    cases.append(
        {
            "CASE_ID": "IBP-FACTUAL-EXCL-001",
            "MODE": "RESEARCH",
            "QUESTION": {
                "text": (
                    "What directional_accuracy did baseline_1_momentum_5m_sign_v1 achieve on "
                    "HISTORICAL_DEVELOPMENT_VALIDATE for the frozen baseline pack?"
                ),
                "constructed_from_admitted_evidence_only": True,
                "question_class": "UNANSWERABLE_METRIC",
            },
            "EVIDENCE_ACCESS_MODE": "ADMITTED_EVIDENCE_FIXED",
            "EVIDENCE_SET": excluded_evidence,
            "EVIDENCE_FINGERPRINT": _evidence_fingerprint(excluded_evidence),
            "TEMPORAL_CUTOFF": {
                "kind": "AS_OF_INSTANT",
                "cutoff_instant": "2026-09-15T23:59:59Z",
                "contamination_control": True,
            },
            "EXPECTED_FACTS": [
                {
                    "expected_fact": {"field": "exclusion_reason", "value": "METRIC_NOT_IN_ADMITTED_ARTIFACT"},
                    "source_artifact": frozen,
                    "source_record": "baseline_strategies:baseline_1_momentum_5m_sign_v1",
                    "source_hash": _artifact_sha256(frozen),
                }
            ],
            "ANSWER_NORMALIZATION": _norm_block(),
            "ACCEPTABLE_EQUIVALENTS": [],
            "UNKNOWN_POLICY": excluded_unknown,
            "PROVENANCE_REQUIREMENTS": _provenance_block(),
            "ROUTING_EXPECTATION": {"template": "EXCLUDED", "lane": "historical_research"},
            "GOLD_HASH": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "SCORING_GATE": "EXCLUDED_UNANSWERABLE",
            "evaluator_gold_ref": f"{GOLD_PREFIX}IBP-FACTUAL-EXCL-001.json",
            "evaluator_notes": (
                "M2 exclusion — run metrics are not serialized in the frozen definition artifact."
            ),
        }
    )

    return cases


def main() -> None:
    cases = build_cases()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for case in cases:
        ref = case["evaluator_gold_ref"]
        name = ref.split("/")[-1]
        path = GOLD_DIR / name
        path.write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    gold_refs = [c["evaluator_gold_ref"] for c in cases]
    protocol = {
        "artifact_kind": "ibp_admitted_factual_gold_protocol_v1",
        "schema_version": "imp.ibp-admitted-factual-gold/1.0.0",
        "hypothesis_id": "LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1",
        "protocol_version": "IBP_FACTUAL_SMOKE_V1",
        "hash_algorithm": factual_gold_hash_algorithm(),
        "gold_source_independent": True,
        "caseset_hash": compute_caseset_hash(cases),
        "goldset_hash": compute_goldset_hash(gold_refs),
        "cases": cases,
        "freeze": {
            "status": "UNFROZEN",
            "cases_constructed": True,
            "smoke10_executed": False,
        },
    }
    out = FIXTURE_ROOT / "protocol_ibp_factual_smoke_v1_candidate.json"
    out.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validate_factual_gold_protocol(protocol)
    print(f"wrote {len(cases)} cases")
    print(f"caseset_hash={protocol['caseset_hash']}")
    print(f"goldset_hash={protocol['goldset_hash']}")
    print(f"protocol={out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
