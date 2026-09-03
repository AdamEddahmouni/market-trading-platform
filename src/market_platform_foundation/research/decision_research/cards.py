"""Preregistered experiment cards for governed decision research.

Implements DECISION-RESEARCH-001 §5. Cards extend the Phase 6 preregistration
semantics in ``strategy/preregistration.py`` — same ``canonical_bytes`` /
``sha256_bytes`` hashing and identity-hash binding — but are a distinct
card-level contract. The card body is hashed over all fields except
``card_id`` / ``card_hash``; a change in any preregistered field is therefore a
new card, never a mutation of an existing one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

# Fixed RFC-4122 URL namespace — deterministic across runs and machines.
CARD_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

DEFAULT_EVALUATION_WINDOW: dict[str, Any] = {
    "schema": "expanding_window",
    "folds": 4,
    "oos_block_frac": 0.15,
    "min_oos_block": 50,
}

DEFAULT_OUTCOME_SPEC: dict[str, Any] = {
    "horizon_ns": 1_800_000_000_000,  # 30 minutes
    "return_basis": "MARK_TO_MARK",
    "cost_model_version": "execution_book_aware_v1",
}


@dataclass(slots=True)
class ExperimentCard:
    """A hash-bound, preregistered experiment hypothesis (DECISION-RESEARCH-001 §5)."""

    experiment_id: str
    family: str
    hypothesis_label: str
    baseline_id: str
    added_evidence: tuple[str, ...]
    feature_spec: dict[str, Any]
    outcome_spec: dict[str, Any]
    inclusion_criteria: tuple[str, ...]
    exclusion_criteria: tuple[str, ...]
    primary_metric: str
    min_sample_oos: int
    primary_metric_threshold: float = 0.05
    evaluation_window: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_EVALUATION_WINDOW))
    preregistered_at_ns: int = 0

    card_id: str = field(init=False)
    card_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.experiment_id or not self.family or not self.baseline_id:
            raise ValueError("CARD_IDENTITY_FIELD_MISSING")
        if self.hypothesis_label not in ("CONFIRMATORY", "EXPLORATORY"):
            raise ValueError("CARD_HYPOTHESIS_LABEL_INVALID")
        if self.min_sample_oos < 1:
            raise ValueError("CARD_MIN_SAMPLE_OOS_INVALID")
        if self.primary_metric_threshold < 0.0 or self.primary_metric_threshold > 1.0:
            raise ValueError("CARD_PRIMARY_METRIC_THRESHOLD_INVALID")
        body = self._body()
        # Canonical business fields first (sorted keys), so ordering never
        # matters for the hash. uuid5 needs a str; latin-1 is a lossless
        # round-trip of the canonical bytes, keeping the id deterministic over
        # the exact same bytes the hash covers.
        canonical = canonical_bytes(body)
        self.card_hash = sha256_bytes(canonical)
        self.card_id = "CARD-" + str(uuid.uuid5(CARD_NAMESPACE, canonical.decode("latin-1")))

    def _body(self) -> dict[str, Any]:
        """Hash-relevant body: every field except ``card_id`` / ``card_hash``.

        Lists are sorted so the same logical card always hashes identically
        regardless of the order they were written in.
        """
        return {
            "added_evidence": sorted(self.added_evidence),
            "baseline_id": self.baseline_id,
            "evaluation_window": self.evaluation_window,
            "exclusion_criteria": sorted(self.exclusion_criteria),
            "experiment_id": self.experiment_id,
            "family": self.family,
            "feature_spec": self.feature_spec,
            "hypothesis_label": self.hypothesis_label,
            "inclusion_criteria": sorted(self.inclusion_criteria),
            "min_sample_oos": self.min_sample_oos,
            "outcome_spec": self.outcome_spec,
            "preregistered_at_ns": self.preregistered_at_ns,
            "primary_metric": self.primary_metric,
            "primary_metric_threshold": self.primary_metric_threshold,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._body(),
            "card_hash": self.card_hash,
            "card_id": self.card_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperimentCard":
        card = cls(
            experiment_id=str(payload["experiment_id"]),
            family=str(payload["family"]),
            hypothesis_label=str(payload["hypothesis_label"]),
            baseline_id=str(payload["baseline_id"]),
            added_evidence=tuple(payload.get("added_evidence", ())),
            feature_spec=payload.get("feature_spec", {}),
            outcome_spec=payload.get("outcome_spec", {}),
            inclusion_criteria=tuple(payload.get("inclusion_criteria", ())),
            exclusion_criteria=tuple(payload.get("exclusion_criteria", ())),
            primary_metric=str(payload["primary_metric"]),
            min_sample_oos=int(payload["min_sample_oos"]),
            primary_metric_threshold=float(payload.get("primary_metric_threshold", 0.05)),
            evaluation_window=payload.get("evaluation_window", dict(DEFAULT_EVALUATION_WINDOW)),
            preregistered_at_ns=int(payload.get("preregistered_at_ns", 0)),
        )
        provided_hash = str(payload.get("card_hash") or "")
        if provided_hash and provided_hash != card.card_hash:
            raise ValueError("CARD_HASH_MISMATCH")
        provided_id = str(payload.get("card_id") or "")
        if provided_id and provided_id != card.card_id:
            raise ValueError("CARD_ID_MISMATCH")
        return card


__all__ = [
    "CARD_NAMESPACE",
    "DEFAULT_EVALUATION_WINDOW",
    "DEFAULT_OUTCOME_SPEC",
    "ExperimentCard",
]
