"""Invariant validation for IBP admitted factual gold (contract-only in M1)."""

from __future__ import annotations

import re
from typing import Any

from .constants import PROVENANCE_CHAIN_KEYS, REQUIRED_CASE_FIELDS_UPPER
from .hashing import compute_case_gold_hash
from .types import (
    AdmittedFactualEvidenceAccessMode,
    AdmittedFactualSourceType,
    FactualCaseScoringGate,
    FactualUnknownVerdict,
    FORBIDDEN_SYNTHETIC_GOLD_PREFIX,
    IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND,
    IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID,
    IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION,
    IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
)

_CASE_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,127}$")
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class AdmittedFactualGoldContractError(ValueError):
    """Raised when protocol or case invariants fail."""


def _require_mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdmittedFactualGoldContractError(code)
    return value


def _validate_temporal_cutoff(cutoff: dict[str, Any]) -> None:
    if cutoff.get("kind") not in {"AS_OF_INSTANT", "SESSION_END", "EVIDENCE_MAX_TIMESTAMP"}:
        raise AdmittedFactualGoldContractError("FACTUAL_TEMPORAL_CUTOFF_KIND_INVALID")
    instant = cutoff.get("cutoff_instant")
    if instant is not None and not _ISO_TIMESTAMP_PATTERN.match(str(instant)):
        raise AdmittedFactualGoldContractError("FACTUAL_TEMPORAL_CUTOFF_INSTANT_INVALID")
    if cutoff.get("contamination_control") is not True:
        raise AdmittedFactualGoldContractError("FACTUAL_TEMPORAL_CONTAMINATION_CONTROL_REQUIRED")


def _validate_answer_normalization(norm: dict[str, Any]) -> None:
    allowed = {
        "case_folding",
        "trim_whitespace",
        "collapse_internal_whitespace",
        "instrument_symbol_canonicalization",
        "iso_timestamp_normalization",
        "numeric_tolerance",
        "boolean_label_equivalence",
        "state_label_equivalence",
    }
    if not norm.get("structured_facts_preferred"):
        raise AdmittedFactualGoldContractError("FACTUAL_NORMALIZATION_STRUCTURED_FACTS_REQUIRED")
    extras = set(norm.keys()) - allowed - {"structured_facts_preferred"}
    if extras:
        raise AdmittedFactualGoldContractError("FACTUAL_NORMALIZATION_UNKNOWN_KEYS")
    tolerance = norm.get("numeric_tolerance")
    if tolerance is not None:
        if not isinstance(tolerance, dict) or tolerance.get("relative") is None:
            raise AdmittedFactualGoldContractError("FACTUAL_NUMERIC_TOLERANCE_INVALID")


def _validate_unknown_policy(policy: dict[str, Any]) -> None:
    verdict = policy.get("correct_unknown_verdict")
    if verdict not in {item.value for item in FactualUnknownVerdict}:
        raise AdmittedFactualGoldContractError("FACTUAL_UNKNOWN_VERDICT_INVALID")
    if policy.get("encoded_in_evaluator_contract") is not True:
        raise AdmittedFactualGoldContractError("FACTUAL_UNKNOWN_MUST_BE_EVALUATOR_ENCODED")


def _validate_provenance_requirements(req: dict[str, Any]) -> None:
    if req.get("gold_source_independent") is not True:
        raise AdmittedFactualGoldContractError("FACTUAL_GOLD_SOURCE_INDEPENDENT_REQUIRED")
    if req.get("chain") != list(PROVENANCE_CHAIN_KEYS):
        raise AdmittedFactualGoldContractError("FACTUAL_PROVENANCE_CHAIN_INVALID")


def _validate_evidence_set(evidence_set: dict[str, Any], access_mode: str) -> None:
    declared_mode = evidence_set.get("evidence_access_mode")
    if declared_mode != access_mode:
        raise AdmittedFactualGoldContractError("FACTUAL_EVIDENCE_MODE_MISMATCH")
    sources = evidence_set.get("sources")
    if not isinstance(sources, list) or not sources:
        raise AdmittedFactualGoldContractError("FACTUAL_EVIDENCE_SOURCES_REQUIRED")
    modes_seen: set[str] = set()
    for source in sources:
        row = _require_mapping(source, "FACTUAL_EVIDENCE_SOURCE_INVALID")
        source_type = row.get("source_type")
        if source_type not in {item.value for item in AdmittedFactualSourceType}:
            raise AdmittedFactualGoldContractError("FACTUAL_SOURCE_TYPE_INADMISSIBLE")
        mode = row.get("evidence_access_mode")
        if mode not in {item.value for item in AdmittedFactualEvidenceAccessMode}:
            raise AdmittedFactualGoldContractError("FACTUAL_SOURCE_ACCESS_MODE_INVALID")
        modes_seen.add(str(mode))
    if len(modes_seen) != 1:
        raise AdmittedFactualGoldContractError("FACTUAL_MIXED_EVIDENCE_ACCESS_MODE_FORBIDDEN")
    if modes_seen.pop() != access_mode:
        raise AdmittedFactualGoldContractError("FACTUAL_EVIDENCE_SET_MODE_INVALID")


def _validate_expected_facts(expected_facts: list[Any]) -> None:
    if not isinstance(expected_facts, list) or not expected_facts:
        raise AdmittedFactualGoldContractError("FACTUAL_EXPECTED_FACTS_REQUIRED")
    for fact in expected_facts:
        row = _require_mapping(fact, "FACTUAL_EXPECTED_FACT_INVALID")
        for key in PROVENANCE_CHAIN_KEYS:
            if key not in row:
                raise AdmittedFactualGoldContractError(f"FACTUAL_PROVENANCE_MISSING:{key}")
        if not str(row["source_hash"]).startswith("sha256:"):
            raise AdmittedFactualGoldContractError("FACTUAL_SOURCE_HASH_FORMAT_INVALID")
        for token in (row.get("expected_fact"), row.get("source_record")):
            if token is not None and str(token).startswith(FORBIDDEN_SYNTHETIC_GOLD_PREFIX):
                raise AdmittedFactualGoldContractError("FACTUAL_SYNTHETIC_GOLD_STRING_FORBIDDEN")


def validate_factual_gold_case(case: dict[str, Any]) -> None:
    """Validate a single admitted factual gold case (evaluator storage)."""
    missing = REQUIRED_CASE_FIELDS_UPPER - set(case.keys())
    if missing:
        raise AdmittedFactualGoldContractError(f"FACTUAL_CASE_FIELDS_MISSING:{sorted(missing)}")
    case_id = case.get("CASE_ID")
    if not case_id or not _CASE_ID_PATTERN.match(str(case_id)):
        raise AdmittedFactualGoldContractError("FACTUAL_CASE_ID_INVALID")
    access_mode = case.get("EVIDENCE_ACCESS_MODE")
    if access_mode not in {item.value for item in AdmittedFactualEvidenceAccessMode}:
        raise AdmittedFactualGoldContractError("FACTUAL_CASE_ACCESS_MODE_INVALID")
    scoring_gate = case.get("SCORING_GATE")
    if scoring_gate not in {item.value for item in FactualCaseScoringGate}:
        raise AdmittedFactualGoldContractError("FACTUAL_SCORING_GATE_INVALID")
    if scoring_gate == FactualCaseScoringGate.EXCLUDED_UNANSWERABLE.value:
        return
    question = case.get("QUESTION")
    if not isinstance(question, dict) or not question.get("text"):
        raise AdmittedFactualGoldContractError("FACTUAL_QUESTION_INVALID")
    if question.get("constructed_from_admitted_evidence_only") is not True:
        raise AdmittedFactualGoldContractError("FACTUAL_QUESTION_MUST_USE_ADMITTED_EVIDENCE")
    _validate_evidence_set(_require_mapping(case.get("EVIDENCE_SET"), "FACTUAL_EVIDENCE_SET_INVALID"), str(access_mode))
    fingerprint = case.get("EVIDENCE_FINGERPRINT")
    if not fingerprint or not str(fingerprint).startswith("sha256:"):
        raise AdmittedFactualGoldContractError("FACTUAL_EVIDENCE_FINGERPRINT_INVALID")
    _validate_temporal_cutoff(_require_mapping(case.get("TEMPORAL_CUTOFF"), "FACTUAL_TEMPORAL_CUTOFF_INVALID"))
    _validate_expected_facts(case.get("EXPECTED_FACTS"))
    _validate_answer_normalization(
        _require_mapping(case.get("ANSWER_NORMALIZATION"), "FACTUAL_ANSWER_NORMALIZATION_INVALID")
    )
    _validate_unknown_policy(_require_mapping(case.get("UNKNOWN_POLICY"), "FACTUAL_UNKNOWN_POLICY_INVALID"))
    _validate_provenance_requirements(
        _require_mapping(case.get("PROVENANCE_REQUIREMENTS"), "FACTUAL_PROVENANCE_REQUIREMENTS_INVALID")
    )
    routing = case.get("ROUTING_EXPECTATION")
    if not isinstance(routing, dict):
        raise AdmittedFactualGoldContractError("FACTUAL_ROUTING_EXPECTATION_INVALID")
    declared_hash = case.get("GOLD_HASH")
    expected_hash = compute_case_gold_hash(
        case_id=str(case_id),
        expected_facts=case.get("EXPECTED_FACTS"),
        unknown_policy=case.get("UNKNOWN_POLICY"),
    )
    if declared_hash != expected_hash:
        raise AdmittedFactualGoldContractError("FACTUAL_GOLD_HASH_MISMATCH")


def validate_factual_gold_protocol(protocol: dict[str, Any], *, allow_empty_cases: bool = True) -> None:
    """Validate protocol envelope; M1 permits zero cases."""
    if protocol.get("artifact_kind") != IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND:
        raise AdmittedFactualGoldContractError("FACTUAL_PROTOCOL_KIND_MISMATCH")
    if protocol.get("schema_version") != IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION:
        raise AdmittedFactualGoldContractError("FACTUAL_PROTOCOL_SCHEMA_MISMATCH")
    if protocol.get("hypothesis_id") != IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID:
        raise AdmittedFactualGoldContractError("FACTUAL_HYPOTHESIS_MISMATCH")
    if protocol.get("protocol_version") != IBP_FACTUAL_SMOKE_PROTOCOL_VERSION:
        raise AdmittedFactualGoldContractError("FACTUAL_PROTOCOL_VERSION_MISMATCH")
    if protocol.get("gold_source_independent") is not True:
        raise AdmittedFactualGoldContractError("FACTUAL_PROTOCOL_GOLD_SOURCE_INDEPENDENT_REQUIRED")
    cases = protocol.get("cases")
    if not isinstance(cases, list):
        raise AdmittedFactualGoldContractError("FACTUAL_CASES_INVALID")
    if not cases and not allow_empty_cases:
        raise AdmittedFactualGoldContractError("FACTUAL_CASES_EMPTY_NOT_ALLOWED")
    seen: set[str] = set()
    gold_refs: list[str] = []
    for case in cases:
        validate_factual_gold_case(case)
        cid = case["CASE_ID"]
        if cid in seen:
            raise AdmittedFactualGoldContractError("FACTUAL_DUPLICATE_CASE_ID")
        seen.add(cid)
        ref = case.get("evaluator_gold_ref")
        if not ref or not str(ref).startswith("evaluator_only/admitted_factual_gold/"):
            raise AdmittedFactualGoldContractError("FACTUAL_EVALUATOR_GOLD_REF_INVALID")
        gold_refs.append(str(ref))
    declared_caseset = protocol.get("caseset_hash")
    declared_goldset = protocol.get("goldset_hash")
    from .hashing import compute_caseset_hash, compute_goldset_hash

    if declared_caseset != compute_caseset_hash(cases):
        raise AdmittedFactualGoldContractError("FACTUAL_CASESET_HASH_MISMATCH")
    if declared_goldset != compute_goldset_hash(gold_refs):
        raise AdmittedFactualGoldContractError("FACTUAL_GOLDSET_HASH_MISMATCH")


__all__ = [
    "AdmittedFactualGoldContractError",
    "validate_factual_gold_case",
    "validate_factual_gold_protocol",
]
