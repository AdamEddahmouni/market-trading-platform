"""Canonical before/after diff over the Phase 3B registry entry contract.

Every field of ``CandidateCaseRegistryEntry`` is reported -- including the ones that do not
move -- so reviewers can see the pinned fields as explicitly as the changed ones. Values
are rendered with the project's existing canonical JSON encoder, so the diff is
byte-deterministic and free of wall-clock or path-dependent text.
"""

from __future__ import annotations

from collections import Counter

from squeeze_core.research.models import CandidateCaseRegistryEntry
from squeeze_core.serialization import canonical_json_bytes

from .contract import ALLOWED_MUTABLE_FIELDS, IMMUTABLE_FIELDS
from .models import FieldChange, FieldChangeFrequency, FieldChangeKind, RegistryFieldDiff

_EMPTY_RENDERINGS = frozenset({"null", "[]", '""'})


def _render(value: object) -> str:
    """Canonical text for one field value (UTF-8, sorted keys, exact Decimal strings)."""
    return canonical_json_bytes(value).decode("utf-8")


def _change_kind(field_name: str, current: str, preview: str) -> FieldChangeKind:
    if current == preview:
        if field_name in IMMUTABLE_FIELDS:
            return FieldChangeKind.FORBIDDEN_TO_CHANGE
        return FieldChangeKind.UNCHANGED
    if current in _EMPTY_RENDERINGS:
        return FieldChangeKind.ADDED
    return FieldChangeKind.CHANGED


def _rationale(field_name: str, kind: FieldChangeKind) -> str:
    if kind is FieldChangeKind.FORBIDDEN_TO_CHANGE:
        return "PINNED_BY_BATCH09_PLAN_IMMUTABLE_FIELD"
    if kind is FieldChangeKind.UNCHANGED:
        return "NO_REVISION_REQUIRED"
    return ALLOWED_MUTABLE_FIELDS.get(field_name, "UNAUTHORIZED_FIELD_CHANGE")


class RegistryDiffError(ValueError):
    """Raised when a diff contains a change the preregistered plan does not allow."""


def build_registry_field_diff(
    current: CandidateCaseRegistryEntry,
    preview: CandidateCaseRegistryEntry,
) -> RegistryFieldDiff:
    """Diff one candidate, refusing any change outside the preregistered allow-list."""
    if current.case_id != preview.case_id or current.symbol != preview.symbol:
        raise RegistryDiffError("BATCH09_DIFF_IDENTITY_MISMATCH")

    changes = []
    for field_name in sorted(CandidateCaseRegistryEntry.model_fields):
        current_text = _render(getattr(current, field_name))
        preview_text = _render(getattr(preview, field_name))
        kind = _change_kind(field_name, current_text, preview_text)
        if kind in {FieldChangeKind.ADDED, FieldChangeKind.CHANGED}:
            if field_name not in ALLOWED_MUTABLE_FIELDS:
                raise RegistryDiffError(f"BATCH09_FORBIDDEN_FIELD_CHANGED:{field_name}")
        changes.append(FieldChange(
            field_name=field_name,
            change_kind=kind,
            current_value=current_text,
            preview_value=preview_text,
            rationale_code=_rationale(field_name, kind),
        ))
    return RegistryFieldDiff(
        case_id=current.case_id, symbol=current.symbol, changes=tuple(changes),
    )


def build_field_change_frequency(
    diffs: tuple[RegistryFieldDiff, ...],
) -> tuple[FieldChangeFrequency, ...]:
    """Aggregate how many cases move each field, per change kind."""
    counter: Counter[tuple[str, str]] = Counter()
    for diff in diffs:
        for change in diff.changes:
            counter[(change.field_name, change.change_kind.value)] += 1
    return tuple(
        FieldChangeFrequency(
            field_name=field_name,
            change_kind=FieldChangeKind(kind),
            case_count=count,
        )
        for (field_name, kind), count in sorted(counter.items())
    )


__all__ = [
    "RegistryDiffError",
    "build_field_change_frequency",
    "build_registry_field_diff",
]
