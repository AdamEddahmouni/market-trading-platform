"""Contractual leakage checks composed by the research contamination auditor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .admission import ITEM9_ADMISSION_REFUSED, evaluate_item9_prospective_corpus_admission
from .consumption import (
    CONSUMPTION_REFUSED_PROTECTED_CORPUS,
    ProtectedCorpusConsumptionError,
    assert_corpus_consumable_for_selection_or_training,
    is_protected_corpus_authority,
)
from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    resolve_effective_corpus_evidence_authority,
)
from .historical_manifest import validate_historical_development_dataset_manifest

VIOLATION_TRAIN_TEST_OVERLAP = "TRAIN_TEST_INTERVAL_OVERLAP"
VIOLATION_FEATURE_AFTER_CUTOFF = "FEATURE_TIMESTAMP_AFTER_DECISION_CUTOFF"
VIOLATION_HOLDOUT_IN_TRAINING = "HOLDOUT_ENTERED_TRAINING"
VIOLATION_PROSPECTIVE_IN_HISTORICAL_RESEARCH = "PROSPECTIVE_RECEIPTS_IN_HISTORICAL_RESEARCH"
VIOLATION_HISTORICAL_IN_ITEM9 = "HISTORICAL_DATA_ENTERED_ITEM9_PROSPECTIVE"
VIOLATION_AUTHORITY_MIXING = "AUTHORITY_CLASS_MIXING"
VIOLATION_DATASET_FINGERPRINT_MISMATCH = "DATASET_FINGERPRINT_MISMATCH"
VIOLATION_TARGET_LEAKAGE = "TARGET_LEAKAGE_INDICATOR"
VIOLATION_MISSING_LINEAGE = "MISSING_LINEAGE"
VIOLATION_PROTECTED_CORPUS_CONSUMPTION = "PROTECTED_CORPUS_CONSUMPTION"


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def check_train_test_interval_overlap(
    *,
    train: Mapping[str, Any],
    test: Mapping[str, Any],
) -> dict[str, Any] | None:
    train_start = int(train["start_ns"])
    train_end = int(train["end_ns"])
    test_start = int(test["start_ns"])
    test_end = int(test["end_ns"])
    if _ranges_overlap(train_start, train_end, test_start, test_end):
        return {
            "reason_code": VIOLATION_TRAIN_TEST_OVERLAP,
            "detail": {
                "train_start_ns": train_start,
                "train_end_ns": train_end,
                "test_start_ns": test_start,
                "test_end_ns": test_end,
            },
        }
    return None


def check_feature_temporal_violations(
    feature_lineage: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if not feature_lineage:
        return violations
    for idx, row in enumerate(feature_lineage):
        cutoff = row.get("decision_cutoff_ns")
        feature_ts = row.get("feature_as_of_ns")
        if cutoff is None or feature_ts is None:
            continue
        if int(feature_ts) > int(cutoff):
            violations.append(
                {
                    "reason_code": VIOLATION_FEATURE_AFTER_CUTOFF,
                    "detail": {
                        "index": idx,
                        "decision_cutoff_ns": int(cutoff),
                        "feature_as_of_ns": int(feature_ts),
                        "ref": row.get("ref"),
                    },
                }
            )
    return violations


def check_holdout_training_overlap(
    *,
    holdout_start_ns: int,
    holdout_end_ns: int,
    training_examples: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    if not training_examples:
        return None
    overlapping: list[str] = []
    for row in training_examples:
        decision_ns = row.get("decision_time_ns")
        if decision_ns is None:
            continue
        t = int(decision_ns)
        if holdout_start_ns <= t < holdout_end_ns:
            overlapping.append(str(row.get("snapshot_id") or row.get("ref") or t))
    if not overlapping:
        return None
    return {
        "reason_code": VIOLATION_HOLDOUT_IN_TRAINING,
        "detail": {
            "holdout_start_ns": holdout_start_ns,
            "holdout_end_ns": holdout_end_ns,
            "overlapping_refs": tuple(sorted(overlapping)),
        },
    }


def check_protected_corpus_inputs(
    corpus_inputs: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if not corpus_inputs:
        return violations
    for idx, row in enumerate(corpus_inputs):
        purpose = str(row.get("purpose") or "").strip().lower()
        if purpose not in {"selection_or_training", "training", "selection"}:
            continue
        authority = str(row.get("corpus_evidence_authority") or "")
        payload = row.get("payload")
        try:
            assert_corpus_consumable_for_selection_or_training(
                corpus_evidence_authority=authority or None,
                payload=dict(payload) if isinstance(payload, Mapping) else None,
                purpose=purpose,
            )
        except ProtectedCorpusConsumptionError as exc:
            violations.append(
                {
                    "reason_code": VIOLATION_PROTECTED_CORPUS_CONSUMPTION,
                    "detail": {"index": idx, "message": str(exc)},
                }
            )
        except ValueError:
            violations.append(
                {
                    "reason_code": VIOLATION_PROTECTED_CORPUS_CONSUMPTION,
                    "detail": {"index": idx, "authority": authority},
                }
            )
    return violations


def check_authority_mixing_in_historical_research(
    corpus_inputs: Sequence[Mapping[str, Any]] | None,
    *,
    research_authority: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if research_authority != CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return violations
    if not corpus_inputs:
        return violations
    for idx, row in enumerate(corpus_inputs):
        purpose = str(row.get("purpose") or "").strip().lower()
        if purpose not in {"historical_research", "development", "feature_build"}:
            continue
        resolved = resolve_effective_corpus_evidence_authority(
            manifest_authority=str(row.get("corpus_evidence_authority") or ""),
            payload=dict(row.get("payload") or {}) if isinstance(row.get("payload"), Mapping) else None,
        )
        effective = str(resolved.get("effective_authority") or "")
        if effective == CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE:
            violations.append(
                {
                    "reason_code": VIOLATION_PROSPECTIVE_IN_HISTORICAL_RESEARCH,
                    "detail": {"index": idx, "effective_authority": effective},
                }
            )
        elif effective and effective != CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
            if is_protected_corpus_authority(effective):
                violations.append(
                    {
                        "reason_code": VIOLATION_AUTHORITY_MIXING,
                        "detail": {"index": idx, "effective_authority": effective},
                    }
                )
    return violations


def check_item9_prospective_admission(
    item9_inputs: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if not item9_inputs:
        return violations
    for idx, receipt in enumerate(item9_inputs):
        outcome = evaluate_item9_prospective_corpus_admission(payload=dict(receipt))
        if outcome.get("disposition") == ITEM9_ADMISSION_REFUSED:
            violations.append(
                {
                    "reason_code": VIOLATION_HISTORICAL_IN_ITEM9,
                    "detail": {
                        "index": idx,
                        "admission_reason": outcome.get("reason_code"),
                        "effective_authority": outcome.get("effective_authority"),
                    },
                }
            )
    return violations


def check_dataset_fingerprint_bindings(
    corpus_inputs: Sequence[Mapping[str, Any]] | None,
    *,
    historical_dataset_manifest: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if historical_dataset_manifest is not None:
        gate = validate_historical_development_dataset_manifest(historical_dataset_manifest)
        if not gate.get("ok"):
            violations.append(
                {
                    "reason_code": VIOLATION_DATASET_FINGERPRINT_MISMATCH,
                    "detail": {"scope": "historical_dataset_manifest", "gate": gate},
                }
            )
    if not corpus_inputs:
        return violations
    for idx, row in enumerate(corpus_inputs):
        expected = row.get("expected_dataset_fingerprint")
        actual = row.get("dataset_fingerprint")
        if expected is None and actual is None:
            continue
        if expected is None or actual is None or str(expected) != str(actual):
            violations.append(
                {
                    "reason_code": VIOLATION_DATASET_FINGERPRINT_MISMATCH,
                    "detail": {
                        "index": idx,
                        "expected_dataset_fingerprint": expected,
                        "dataset_fingerprint": actual,
                    },
                }
            )
    return violations


def check_target_leakage_indicators(
    target_leakage_rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    if not target_leakage_rows:
        return violations
    for idx, row in enumerate(target_leakage_rows):
        cutoff = row.get("decision_cutoff_ns")
        label_ns = row.get("label_available_ns")
        if cutoff is None or label_ns is None:
            continue
        if int(label_ns) <= int(cutoff):
            violations.append(
                {
                    "reason_code": VIOLATION_TARGET_LEAKAGE,
                    "detail": {
                        "index": idx,
                        "decision_cutoff_ns": int(cutoff),
                        "label_available_ns": int(label_ns),
                    },
                }
            )
    return violations


__all__ = [
    "CONSUMPTION_REFUSED_PROTECTED_CORPUS",
    "VIOLATION_AUTHORITY_MIXING",
    "VIOLATION_DATASET_FINGERPRINT_MISMATCH",
    "VIOLATION_FEATURE_AFTER_CUTOFF",
    "VIOLATION_HISTORICAL_IN_ITEM9",
    "VIOLATION_HOLDOUT_IN_TRAINING",
    "VIOLATION_MISSING_LINEAGE",
    "VIOLATION_PROTECTED_CORPUS_CONSUMPTION",
    "VIOLATION_PROSPECTIVE_IN_HISTORICAL_RESEARCH",
    "VIOLATION_TARGET_LEAKAGE",
    "VIOLATION_TRAIN_TEST_OVERLAP",
    "check_authority_mixing_in_historical_research",
    "check_dataset_fingerprint_bindings",
    "check_feature_temporal_violations",
    "check_holdout_training_overlap",
    "check_item9_prospective_admission",
    "check_protected_corpus_inputs",
    "check_target_leakage_indicators",
    "check_train_test_interval_overlap",
]
