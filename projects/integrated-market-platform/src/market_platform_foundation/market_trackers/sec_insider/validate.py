"""Structural validation for Market Trackers insider-transactions rows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .schema import ACQUIRED_DISPOSED, CONFIDENCE_TIERS, FORM_TYPES, OWNERSHIP, characterize_record

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"errors": list(self.errors), "ok": self.ok, "warnings": list(self.warnings)}


def _require_str(row: Mapping[str, Any], field: str, errors: list[str]) -> str:
    value = row.get(field)
    text = str(value).strip() if value is not None else ""
    if not text:
        errors.append(f"missing:{field}")
    return text


def validate_market_trackers_row(row: Mapping[str, Any]) -> ValidationOutcome:
    errors: list[str] = []
    warnings: list[str] = []
    spec = characterize_record()

    for field in spec.required_fields:
        if field in spec.nested_objects:
            if not isinstance(row.get(field), Mapping):
                errors.append(f"nested_missing:{field}")
            continue
        if row.get(field) is None and field not in spec.optional_nullable_fields:
            errors.append(f"missing:{field}")

    form_type = str(row.get("formType") or "")
    if form_type and form_type not in FORM_TYPES:
        errors.append("invalid:formType")

    filed_at = str(row.get("filedAt") or "")
    if filed_at and not _DATE.fullmatch(filed_at):
        errors.append("invalid:filedAt")

    transacted = row.get("transactedAt")
    if transacted is not None:
        text = str(transacted)
        if text and not _DATE.fullmatch(text):
            errors.append("invalid:transactedAt")

    ad = row.get("acquiredDisposed")
    if ad is not None and str(ad) not in ACQUIRED_DISPOSED:
        errors.append("invalid:acquiredDisposed")

    ownership = str(row.get("ownership") or "")
    if ownership and ownership not in OWNERSHIP:
        errors.append("invalid:ownership")

    insider = row.get("insider")
    if isinstance(insider, Mapping):
        _require_str(insider, "name", errors)
        _require_str(insider, "cik", errors)
    elif insider is not None:
        errors.append("invalid:insider")

    provenance = row.get("provenance")
    if isinstance(provenance, Mapping):
        for pf in spec.provenance_fields:
            if provenance.get(pf) is None:
                errors.append(f"missing:provenance.{pf}")
        conf = provenance.get("confidence")
        if conf is not None and conf not in CONFIDENCE_TIERS:
            errors.append("invalid:provenance.confidence")
        source_url = str(provenance.get("sourceUrl") or "")
        if source_url and not (source_url.startswith("https://") or source_url.startswith("http://")):
            errors.append("invalid:provenance.sourceUrl")
    elif provenance is not None:
        errors.append("invalid:provenance")

    if row.get("ticker") is None:
        warnings.append("ticker_unresolved_use_cik")

    if transacted and not filed_at:
        warnings.append("transacted_without_filed_at")

    return ValidationOutcome(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))
