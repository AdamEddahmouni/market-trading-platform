"""Protect untouched forward evaluation from selection/training consumption."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITIES,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
    resolve_effective_corpus_evidence_authority,
)

CONSUMPTION_REFUSED_PROTECTED_CORPUS = "CONSUMPTION_REFUSED_PROTECTED_CORPUS"
TRAINING_OR_SELECTION_USE_REFUSED = "REFUSED"

_EXPLICIT_PROTECTED = frozenset({CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION})

_SAMPLE_COLLECTION_KEYS = ("examples", "calibration_examples", "samples", "rows")


class ProtectedCorpusConsumptionError(ValueError):
    """Raised when a protected corpus class is used for selection or training."""


def _normalize_authority(value: object) -> str:
    return str(value or "").strip().upper()


def protected_corpus_authorities_for_selection_training() -> frozenset[str]:
    """Canonical holdout authorities that must never feed selection or training."""

    derived = {
        authority
        for authority in CORPUS_EVIDENCE_AUTHORITIES
        if authority.endswith("_FORWARD_EVALUATION")
        or authority.endswith("_UNTOUCHED_EVALUATION")
    }
    return frozenset(_EXPLICIT_PROTECTED | derived)


def is_protected_corpus_authority(authority: str | None) -> bool:
    normalized = _normalize_authority(authority)
    if not normalized:
        return False
    return normalized in protected_corpus_authorities_for_selection_training()


def authority_refuses_selection_or_training(*, effective_authority: str) -> bool:
    return is_protected_corpus_authority(effective_authority)


def assert_corpus_consumable_for_selection_or_training(
    *,
    corpus_evidence_authority: str | None = None,
    payload: dict[str, object] | Mapping[str, object] | None = None,
    purpose: str = "selection_or_training",
) -> None:
    resolved = resolve_effective_corpus_evidence_authority(
        manifest_authority=corpus_evidence_authority,
        payload=payload,
    )
    effective = str(resolved.get("effective_authority") or corpus_evidence_authority or "").upper()
    if authority_refuses_selection_or_training(effective_authority=effective):
        raise ProtectedCorpusConsumptionError(
            f"{CONSUMPTION_REFUSED_PROTECTED_CORPUS}:{effective}:{purpose}:{TRAINING_OR_SELECTION_USE_REFUSED}"
        )


def assert_payload_samples_consumable_for_selection_or_training(
    *,
    payload: Mapping[str, Any],
    corpus_evidence_authority: str | None = None,
    purpose: str = "selection_or_training",
) -> None:
    """Fail closed on manifest-level authority and per-sample authority markers."""

    assert_corpus_consumable_for_selection_or_training(
        corpus_evidence_authority=corpus_evidence_authority
        or str(payload.get("corpus_evidence_authority") or ""),
        payload=dict(payload),
        purpose=purpose,
    )
    for key in _SAMPLE_COLLECTION_KEYS:
        rows = payload.get(key)
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            continue
        for row in rows:
            if isinstance(row, Mapping):
                assert_corpus_consumable_for_selection_or_training(
                    payload=dict(row),
                    purpose=f"{purpose}:sample",
                )


def assert_metadata_consumable_for_selection_or_training(
    metadata: Mapping[str, Any] | None,
    *,
    purpose: str,
) -> None:
    if not metadata:
        return
    assert_payload_samples_consumable_for_selection_or_training(
        payload=dict(metadata),
        purpose=purpose,
    )


__all__ = [
    "CONSUMPTION_REFUSED_PROTECTED_CORPUS",
    "ProtectedCorpusConsumptionError",
    "TRAINING_OR_SELECTION_USE_REFUSED",
    "assert_corpus_consumable_for_selection_or_training",
    "assert_metadata_consumable_for_selection_or_training",
    "assert_payload_samples_consumable_for_selection_or_training",
    "authority_refuses_selection_or_training",
    "is_protected_corpus_authority",
    "protected_corpus_authorities_for_selection_training",
]
