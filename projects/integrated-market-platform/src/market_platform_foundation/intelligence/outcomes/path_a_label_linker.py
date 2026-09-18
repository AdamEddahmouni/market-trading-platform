"""Path A prospective observation ↔ post-horizon label evidence linkage (Lane A).

Append-only outward linkage from frozen prospective sources to lawful TRADE label
artifacts. Never mutates the prospective feature payload or embeds label outcomes
into hash-covered source fields.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...paper.calibration.dual_corpus.evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
)
from ..production.identity import PATH_A_HORIZON_NS
from .label_evidence import (
    BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL,
    LabelEvidenceError,
    POST_HORIZON_LABEL_EVIDENCE_KIND,
    POST_HORIZON_LABEL_SCHEMA_VERSION,
    RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
    derive_label_evidence_id,
    derive_source_observation_hash,
)

DUPLICATE_LABEL_EVIDENCE_ID = "DUPLICATE_LABEL_EVIDENCE_ID"
LABEL_OBSERVATION_ID_MISMATCH = "LABEL_OBSERVATION_ID_MISMATCH"
LABEL_OBSERVATION_HASH_MISMATCH = "LABEL_OBSERVATION_HASH_MISMATCH"
LABEL_INVALID_PROVENANCE = "LABEL_INVALID_PROVENANCE"
LABEL_UNLABELABLE_OUTCOME = "LABEL_UNLABELABLE_OUTCOME"

_FORBIDDEN_BAR_CAPABILITIES = frozenset(
    {"BAR_OHLCV_1M", "BAR_OHLCV", "OHLCV", "HISTORICAL_BAR"}
)


class PathALabelLinkageError(LabelEvidenceError):
    """Fail-closed Path A label evidence linkage violation."""


@dataclass(frozen=True, slots=True)
class PathALabelLinkageResult:
    source_observation_hash: str
    path_a_label_evidence_ids: tuple[str, ...]
    linkages: tuple[dict[str, Any], ...]
    path_a_label_value: str | None
    path_a_label_availability_ns: int | None
    source_hash_before: str
    source_hash_after: str


def prospective_source_observation_from_item9_receipt(
    receipt: Mapping[str, Any],
    *,
    p0: Mapping[str, Any],
    source_code_sha: str | None = None,
) -> dict[str, Any]:
    """Canonical prospective source body for Item 9 receipts (features stay bar-based)."""

    observation_id = str(receipt.get("experiment_id") or "").strip()
    if not observation_id:
        raise PathALabelLinkageError(LABEL_INVALID_PROVENANCE, details={"field": "experiment_id"})
    signal_ns = int(receipt.get("signal_time_ns") or 0)
    first = receipt.get("first_post_signal_bar") or {}
    bar_available = int(receipt.get("bar_available_time_ns") or first.get("available_time_ns") or 0)
    if str(p0.get("observation_kind") or "").upper() != "TRADE":
        raise PathALabelLinkageError(
            BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL,
            details={"p0_kind": p0.get("observation_kind")},
        )
    body: dict[str, Any] = {
        "source_observation_id": observation_id,
        "source_evidence_class": CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
        "instrument_id": str(receipt.get("instrument_id") or ""),
        "signal_time_ns": signal_ns,
        "feature_cutoff_ns": int(bar_available) if bar_available else signal_ns,
        "horizon_ns": PATH_A_HORIZON_NS,
        "p0": dict(p0),
        "source_code_sha": str(source_code_sha or receipt.get("runtime_git_sha") or ""),
    }
    body["source_observation_hash"] = derive_source_observation_hash(body)
    return body


def _validate_label_artifact_provenance(artifact: Mapping[str, Any]) -> None:
    if str(artifact.get("artifact_kind") or "") != POST_HORIZON_LABEL_EVIDENCE_KIND:
        raise PathALabelLinkageError(
            LABEL_INVALID_PROVENANCE,
            details={"artifact_kind": artifact.get("artifact_kind")},
        )
    if str(artifact.get("schema_version") or "") != POST_HORIZON_LABEL_SCHEMA_VERSION:
        raise PathALabelLinkageError(
            LABEL_INVALID_PROVENANCE,
            details={"schema_version": artifact.get("schema_version")},
        )
    authority = str(artifact.get("corpus_evidence_authority") or "").upper()
    if authority != CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE:
        raise PathALabelLinkageError(
            LABEL_INVALID_PROVENANCE,
            details={"corpus_evidence_authority": authority},
        )
    capability = str(artifact.get("capability_id") or "").upper()
    if capability in _FORBIDDEN_BAR_CAPABILITIES:
        raise PathALabelLinkageError(
            BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL,
            details={"capability_id": capability},
        )
    label_id = str(artifact.get("label_evidence_id") or "")
    if not label_id:
        raise PathALabelLinkageError(LABEL_INVALID_PROVENANCE, details={"field": "label_evidence_id"})
    computed_id = derive_label_evidence_id(artifact)
    if label_id != computed_id:
        raise PathALabelLinkageError(
            LABEL_INVALID_PROVENANCE,
            details={"declared_id": label_id, "computed_id": computed_id},
        )


def _assert_label_maturity(artifact: Mapping[str, Any], *, evaluation_time_ns: int | None) -> None:
    window_end = int(artifact.get("terminal_window_end_ns") or 0)
    request_ns = int(artifact.get("request_time_ns") or 0)
    if window_end and request_ns < window_end:
        raise PathALabelLinkageError(
            RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
            details={"request_time_ns": request_ns, "terminal_window_end_ns": window_end},
        )
    if evaluation_time_ns is not None and window_end and evaluation_time_ns < window_end:
        raise PathALabelLinkageError(
            RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
            details={
                "evaluation_time_ns": evaluation_time_ns,
                "terminal_window_end_ns": window_end,
            },
        )


def link_path_a_label_evidence(
    source_observation: Mapping[str, Any],
    label_evidences: Sequence[Mapping[str, Any]],
    *,
    evaluation_time_ns: int | None = None,
    allow_unlabelable: bool = True,
) -> PathALabelLinkageResult:
    """Bind post-horizon label artifacts to a prospective source without mutating it."""

    source_copy = copy.deepcopy(dict(source_observation))
    source_hash_before = derive_source_observation_hash(source_copy)
    source_hash_after = derive_source_observation_hash(source_copy)
    if source_hash_before != source_hash_after:
        raise PathALabelLinkageError(
            LABEL_OBSERVATION_HASH_MISMATCH,
            details={"before": source_hash_before, "after": source_hash_after},
        )

    if not label_evidences:
        return PathALabelLinkageResult(
            source_observation_hash=source_hash_before,
            path_a_label_evidence_ids=(),
            linkages=(),
            path_a_label_value=None,
            path_a_label_availability_ns=None,
            source_hash_before=source_hash_before,
            source_hash_after=source_hash_after,
        )

    expected_id = str(source_copy.get("source_observation_id") or "")
    expected_hash = source_hash_before
    seen_ids: set[str] = set()
    linkages: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    label_value: str | None = None
    label_availability: int | None = None

    for artifact in label_evidences:
        if str(artifact.get("source_observation_id") or "") != expected_id:
            raise PathALabelLinkageError(
                LABEL_OBSERVATION_ID_MISMATCH,
                details={
                    "expected": expected_id,
                    "artifact": artifact.get("source_observation_id"),
                },
            )
        artifact_hash = str(artifact.get("source_observation_hash") or "")
        if artifact_hash != expected_hash:
            raise PathALabelLinkageError(
                LABEL_OBSERVATION_HASH_MISMATCH,
                details={"expected": expected_hash, "artifact": artifact_hash},
            )
        _assert_label_maturity(artifact, evaluation_time_ns=evaluation_time_ns)
        _validate_label_artifact_provenance(artifact)

        artifact_id = str(artifact["label_evidence_id"])
        if artifact_id in seen_ids:
            raise PathALabelLinkageError(
                DUPLICATE_LABEL_EVIDENCE_ID,
                details={"label_evidence_id": artifact_id},
            )
        seen_ids.add(artifact_id)

        refusal = artifact.get("refusal_reason")
        direction = artifact.get("direction_label")
        if direction is None and refusal:
            if not allow_unlabelable:
                raise PathALabelLinkageError(
                    LABEL_UNLABELABLE_OUTCOME,
                    details={"refusal_reason": refusal},
                )
        elif direction is None and not refusal:
            raise PathALabelLinkageError(
                LABEL_INVALID_PROVENANCE,
                details={"direction_label": direction, "refusal_reason": refusal},
            )

        evidence_ids.append(artifact_id)
        linkages.append(
            {
                "source_observation_id": expected_id,
                "source_observation_hash": expected_hash,
                "label_evidence_id": artifact_id,
                "label_evidence_hash": derive_label_evidence_id(artifact),
            }
        )
        if direction is not None:
            if label_value is not None and label_value != str(direction):
                raise PathALabelLinkageError(
                    LABEL_INVALID_PROVENANCE,
                    details={"conflicting_directions": (label_value, direction)},
                )
            label_value = str(direction)
            label_availability = int(artifact.get("label_availability_time_ns") or 0) or None

    return PathALabelLinkageResult(
        source_observation_hash=source_hash_before,
        path_a_label_evidence_ids=tuple(evidence_ids),
        linkages=tuple(linkages),
        path_a_label_value=label_value,
        path_a_label_availability_ns=label_availability,
        source_hash_before=source_hash_before,
        source_hash_after=source_hash_after,
    )


__all__ = [
    "DUPLICATE_LABEL_EVIDENCE_ID",
    "LABEL_INVALID_PROVENANCE",
    "LABEL_OBSERVATION_HASH_MISMATCH",
    "LABEL_OBSERVATION_ID_MISMATCH",
    "LABEL_UNLABELABLE_OUTCOME",
    "PathALabelLinkageError",
    "PathALabelLinkageResult",
    "link_path_a_label_evidence",
    "prospective_source_observation_from_item9_receipt",
]
