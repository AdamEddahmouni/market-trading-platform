"""Protect untouched forward evaluation from selection/training consumption."""

from __future__ import annotations

from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
    resolve_effective_corpus_evidence_authority,
)

CONSUMPTION_REFUSED_PROTECTED_CORPUS = "CONSUMPTION_REFUSED_PROTECTED_CORPUS"

_PROTECTED_FROM_SELECTION_TRAINING = frozenset(
    {CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION}
)


class ProtectedCorpusConsumptionError(ValueError):
    """Raised when a protected corpus class is used for selection or training."""


def assert_corpus_consumable_for_selection_or_training(
    *,
    corpus_evidence_authority: str | None = None,
    payload: dict[str, object] | None = None,
    purpose: str = "selection_or_training",
) -> None:
    resolved = resolve_effective_corpus_evidence_authority(
        manifest_authority=corpus_evidence_authority,
        payload=payload,
    )
    effective = str(resolved.get("effective_authority") or corpus_evidence_authority or "").upper()
    if effective in _PROTECTED_FROM_SELECTION_TRAINING:
        raise ProtectedCorpusConsumptionError(
            f"{CONSUMPTION_REFUSED_PROTECTED_CORPUS}:{effective}:{purpose}"
        )


__all__ = [
    "CONSUMPTION_REFUSED_PROTECTED_CORPUS",
    "ProtectedCorpusConsumptionError",
    "assert_corpus_consumable_for_selection_or_training",
]
