"""Research contamination auditor — contractual leakage properties for research runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .leak_audit import (
    VIOLATION_FEATURE_AFTER_CUTOFF,
    VIOLATION_HISTORICAL_IN_ITEM9,
    VIOLATION_HOLDOUT_IN_TRAINING,
    VIOLATION_MISSING_LINEAGE,
    VIOLATION_PROSPECTIVE_IN_HISTORICAL_RESEARCH,
    VIOLATION_TRAIN_TEST_OVERLAP,
    check_authority_mixing_in_historical_research,
    check_dataset_fingerprint_bindings,
    check_feature_temporal_violations,
    check_holdout_training_overlap,
    check_item9_prospective_admission,
    check_protected_corpus_inputs,
    check_target_leakage_indicators,
    check_train_test_interval_overlap,
)
from .run_manifest import validate_research_contamination_run_manifest

CONTAMINATION_STATUS_PASS = "PASS"
CONTAMINATION_STATUS_FAIL = "FAIL"

QUESTION_TRAIN_SAW_TEST = "DID_TRAIN_SEE_TEST"
QUESTION_FEATURES_SAW_FUTURE = "DID_FEATURES_SEE_FUTURE_DATA"
QUESTION_HOLDOUT_IN_TRAINING = "DID_HOLDOUT_ENTER_TRAINING"
QUESTION_PROSPECTIVE_IN_HISTORICAL = "DID_PROSPECTIVE_RECEIPTS_ENTER_HISTORICAL_RESEARCH"
QUESTION_HISTORICAL_IN_ITEM9 = "DID_HISTORICAL_DATA_ENTER_PROSPECTIVE_ITEM9"

_AUDIT_QUESTIONS: tuple[str, ...] = (
    QUESTION_TRAIN_SAW_TEST,
    QUESTION_FEATURES_SAW_FUTURE,
    QUESTION_HOLDOUT_IN_TRAINING,
    QUESTION_PROSPECTIVE_IN_HISTORICAL,
    QUESTION_HISTORICAL_IN_ITEM9,
)

ITEM9_EFFECT_NONE = "NONE"
ITEM9_EFFECT_PROSPECTIVE_INPUT = "PROSPECTIVE_CALIBRATION_INPUT"


def _question_verdict(*, question: str, violations: Sequence[Mapping[str, Any]]) -> str:
    codes = {str(v.get("reason_code") or "") for v in violations}
    mapping: dict[str, set[str]] = {
        QUESTION_TRAIN_SAW_TEST: {VIOLATION_TRAIN_TEST_OVERLAP},
        QUESTION_FEATURES_SAW_FUTURE: {VIOLATION_FEATURE_AFTER_CUTOFF},
        QUESTION_HOLDOUT_IN_TRAINING: {VIOLATION_HOLDOUT_IN_TRAINING},
        QUESTION_PROSPECTIVE_IN_HISTORICAL: {VIOLATION_PROSPECTIVE_IN_HISTORICAL_RESEARCH},
        QUESTION_HISTORICAL_IN_ITEM9: {VIOLATION_HISTORICAL_IN_ITEM9},
    }
    triggers = mapping.get(question, set())
    if codes & triggers:
        return CONTAMINATION_STATUS_FAIL
    return CONTAMINATION_STATUS_PASS


def build_evidence_language_summary(authority_context: Mapping[str, Any]) -> dict[str, str]:
    primary = str(authority_context.get("primary_authority") or "UNKNOWN").upper()
    item9_effect = str(authority_context.get("item9_effect") or ITEM9_EFFECT_NONE).upper()
    return {
        "AUTHORITY": primary,
        "ITEM9_EFFECT": item9_effect,
    }


def audit_research_contamination_run(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Inspect a research run manifest and return a fail-closed contamination verdict."""

    gate = validate_research_contamination_run_manifest(manifest)
    violations: list[dict[str, Any]] = []
    if not gate.get("ok"):
        violations.append(
            {
                "reason_code": VIOLATION_MISSING_LINEAGE,
                "detail": gate,
            }
        )
        authority_context = manifest.get("authority_context") if isinstance(manifest.get("authority_context"), Mapping) else {}
        questions = {q: CONTAMINATION_STATUS_FAIL for q in _AUDIT_QUESTIONS}
        return {
            "run_id": str(manifest.get("run_id") or ""),
            "CONTAMINATION_STATUS": CONTAMINATION_STATUS_FAIL,
            "questions": questions,
            "violations": violations,
            "evidence_language": build_evidence_language_summary(authority_context),
            "contract_scope": "contractual_leakage_properties_only",
        }

    splits = manifest["splits"]
    train = splits["train"]
    test = splits["test"]
    overlap = check_train_test_interval_overlap(train=train, test=test)
    if overlap is not None:
        violations.append(overlap)

    violations.extend(check_feature_temporal_violations(manifest.get("feature_lineage")))

    holdout = manifest.get("holdout")
    if isinstance(holdout, Mapping):
        hs = holdout.get("holdout_start_ns")
        he = holdout.get("holdout_end_ns")
        if isinstance(hs, int) and isinstance(he, int) and hs < he:
            holdout_v = check_holdout_training_overlap(
                holdout_start_ns=hs,
                holdout_end_ns=he,
                training_examples=manifest.get("training_examples"),
            )
            if holdout_v is not None:
                violations.append(holdout_v)

    violations.extend(check_protected_corpus_inputs(manifest.get("corpus_inputs")))

    authority_context = manifest["authority_context"]
    research_authority = str(authority_context.get("primary_authority") or "").upper()
    violations.extend(
        check_authority_mixing_in_historical_research(
            manifest.get("corpus_inputs"),
            research_authority=research_authority,
        )
    )
    violations.extend(check_item9_prospective_admission(manifest.get("item9_prospective_inputs")))
    violations.extend(
        check_dataset_fingerprint_bindings(
            manifest.get("corpus_inputs"),
            historical_dataset_manifest=manifest.get("historical_dataset_manifest"),
        )
    )
    violations.extend(check_target_leakage_indicators(manifest.get("target_leakage")))

    questions = {q: _question_verdict(question=q, violations=violations) for q in _AUDIT_QUESTIONS}
    status = CONTAMINATION_STATUS_PASS if all(v == CONTAMINATION_STATUS_PASS for v in questions.values()) else CONTAMINATION_STATUS_FAIL
    if violations and status == CONTAMINATION_STATUS_PASS:
        status = CONTAMINATION_STATUS_FAIL

    return {
        "run_id": str(manifest["run_id"]),
        "CONTAMINATION_STATUS": status,
        "questions": questions,
        "violations": violations,
        "evidence_language": build_evidence_language_summary(authority_context),
        "contract_scope": "contractual_leakage_properties_only",
    }


__all__ = [
    "CONTAMINATION_STATUS_FAIL",
    "CONTAMINATION_STATUS_PASS",
    "ITEM9_EFFECT_NONE",
    "ITEM9_EFFECT_PROSPECTIVE_INPUT",
    "QUESTION_FEATURES_SAW_FUTURE",
    "QUESTION_HISTORICAL_IN_ITEM9",
    "QUESTION_HOLDOUT_IN_TRAINING",
    "QUESTION_PROSPECTIVE_IN_HISTORICAL",
    "QUESTION_TRAIN_SAW_TEST",
    "audit_research_contamination_run",
    "build_evidence_language_summary",
]
