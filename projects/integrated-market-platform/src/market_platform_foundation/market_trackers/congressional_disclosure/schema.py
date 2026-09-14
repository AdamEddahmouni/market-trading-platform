"""Characterization of LuxAlgo congress-trades published rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CHAMBERS = frozenset({"senate", "house"})
SIDES = frozenset({"buy", "sell", "exchange"})
ASSET_TYPES = frozenset({"stock", "option", "bond", "crypto", "fund", "other"})
OWNERS = frozenset({"self", "spouse", "joint", "dependent"})
CONFIDENCE_TIERS = frozenset({1, 0.9, 0.7})


@dataclass(frozen=True, slots=True)
class RecordCharacterization:
    """Stable field inventory for docs, validation, and fixture authors."""

    row_id_field: str
    required_fields: tuple[str, ...]
    optional_nullable_fields: tuple[str, ...]
    nested_objects: tuple[str, ...]
    provenance_fields: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nested_objects": list(self.nested_objects),
            "notes": list(self.notes),
            "optional_nullable_fields": list(self.optional_nullable_fields),
            "provenance_fields": list(self.provenance_fields),
            "required_fields": list(self.required_fields),
            "row_id_field": self.row_id_field,
        }


CONGRESS_TRADE_CHARACTERIZATION = RecordCharacterization(
    row_id_field="id",
    required_fields=(
        "id",
        "chamber",
        "docId",
        "rowIndex",
        "member",
        "filedAt",
        "transactedAt",
        "assetDescription",
        "assetType",
        "side",
        "amountRange",
        "provenance",
    ),
    optional_nullable_fields=("ticker", "owner"),
    nested_objects=("member", "amountRange"),
    provenance_fields=("source", "sourceUrl", "retrievedAt", "parser", "confidence", "needsReview"),
    notes=(
        "Disclosed amounts are statutory ranges; IMP never fabricates midpoints.",
        "transactedAt is economic attribution only, not public-knowledge time.",
        "side is the filing's disclosed label (buy/sell/exchange); not LONG/SHORT execution mapping.",
        "ticker may be null when asset description does not resolve; assetDescription remains authoritative text.",
        "Rows are replaceable Market Trackers aggregates; chamber PTR publication wins when primary supplied.",
        "STOCK Act reporting lag between transaction and filing is expected; do not treat transactedAt as filedAt.",
    ),
)


def characterize_record() -> RecordCharacterization:
    return CONGRESS_TRADE_CHARACTERIZATION
