"""Characterization of LuxAlgo insider-transactions published rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

FORM_TYPES = frozenset({"3", "4", "5", "3/A", "4/A", "5/A"})
ACQUIRED_DISPOSED = frozenset({"A", "D"})
OWNERSHIP = frozenset({"direct", "indirect"})
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


INSIDER_TRANSACTION_CHARACTERIZATION = RecordCharacterization(
    row_id_field="id",
    required_fields=(
        "id",
        "accessionNumber",
        "formType",
        "issuerCik",
        "issuerName",
        "insider",
        "filedAt",
        "securityTitle",
        "ownership",
        "isDerivative",
        "provenance",
    ),
    optional_nullable_fields=(
        "ticker",
        "transactedAt",
        "code",
        "acquiredDisposed",
        "shares",
        "pricePerShare",
        "sharesOwnedAfter",
    ),
    nested_objects=("insider",),
    provenance_fields=("source", "sourceUrl", "retrievedAt", "parser", "confidence", "needsReview"),
    notes=(
        "Transaction codes are raw SEC codes; IMP does not map P/S to bullish/bearish.",
        "transactedAt is economic attribution only, not public-knowledge time.",
        "ticker may be null when the filing omits symbol; issuerCik remains authoritative for entity linkage.",
        "Rows are replaceable Market Trackers aggregates; EDGAR acceptance time wins over filedAt when reconciling PIT.",
    ),
)


def characterize_record() -> RecordCharacterization:
    return INSIDER_TRANSACTION_CHARACTERIZATION


def insider_nested_shape() -> dict[str, str]:
    return {
        "name": "string",
        "cik": "string",
        "title": "string|null",
        "isDirector": "boolean",
        "isOfficer": "boolean",
        "isTenPctOwner": "boolean",
    }


def extract_row_id(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or "").strip()
