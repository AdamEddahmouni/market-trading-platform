"""Hash-bound experiment-card registry (DECISION-RESEARCH-001 §5).

Cards persist under ``<root>/<card_hash>.json`` as canonical JSON, mirroring the
repository's hash-bound acceptance-dir convention (``evidence/phase6/<hash>/``).
Registration is idempotent; a card that hashes to an existing file with
different bytes is rejected (immutability). ``verify_experiment_card_registration``
fails closed — it raises when a card hash is absent from the registry or not
bound into a run record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import load_json_strict, write_canonical_json
from .cards import ExperimentCard

CATALOG_NAME = "catalog.json"


class ExperimentCardRegistry:
    """Committed, immutable, hash-bound store of preregistered experiment cards."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, card_hash: str) -> Path:
        return self._root / f"{card_hash}.json"

    def has(self, card_hash: str) -> bool:
        return self.path_for(card_hash).is_file()

    def register(self, card: ExperimentCard) -> None:
        """Idempotent persist. Refuses body/hash mismatch and mutation."""
        destination = self.path_for(card.card_hash)
        if not destination.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_canonical_json(destination, card.to_dict())
            return
        existing = load_json_strict(destination)
        recomputed = ExperimentCard.from_dict(existing)
        if recomputed.card_hash != card.card_hash or recomputed.card_id != card.card_id:
            raise ValueError("EXPERIMENT_CARD_REGISTRY_MUTATION")

    def load(self, card_hash: str) -> ExperimentCard:
        path = self.path_for(card_hash)
        if not path.is_file():
            raise ValueError(f"EXPERIMENT_CARD_NOT_REGISTERED: {card_hash}")
        return ExperimentCard.from_dict(load_json_strict(path))

    def get(self, experiment_id: str) -> ExperimentCard | None:
        for card in self.list_cards():
            if card.experiment_id == experiment_id:
                return card
        return None

    def list_cards(self) -> list[ExperimentCard]:
        if not self._root.is_dir():
            return []
        cards: list[ExperimentCard] = []
        for path in sorted(self._root.glob("*.json")):
            if path.name == CATALOG_NAME:
                continue
            try:
                cards.append(ExperimentCard.from_dict(load_json_strict(path)))
            except (ValueError, KeyError):
                continue
        return cards


def verify_experiment_card_registration(
    card: ExperimentCard,
    run: dict[str, Any],
    *,
    registry: ExperimentCardRegistry | None = None,
) -> bool:
    """Fail closed: raise unless the card hash is in the registry and bound into a run record.

    A ``run`` record must expose ``bound_card_hashes`` (list of card hashes it is
    bound to) for verification to pass. Absent/unbound raises a ``ValueError``.
    """
    bound = run.get("bound_card_hashes")
    if not isinstance(bound, list):
        raise ValueError("EXPERIMENT_CARD_HASH_UNBOUND: run has no bound_card_hashes")
    if card.card_hash not in bound:
        raise ValueError("EXPERIMENT_CARD_HASH_UNBOUND: card hash not bound to run")
    if registry is not None and not registry.has(card.card_hash):
        raise ValueError(f"EXPERIMENT_CARD_NOT_REGISTERED: {card.card_hash}")
    return True


__all__ = [
    "CATALOG_NAME",
    "ExperimentCardRegistry",
    "verify_experiment_card_registration",
]
