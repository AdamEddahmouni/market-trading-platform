"""Structural validation for Market Trackers congress-trades rows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .schema import ASSET_TYPES, CHAMBERS, CONFIDENCE_TIERS, OWNERS, SIDES, characterize_record

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

    chamber = str(row.get("chamber") or "")
    if chamber and chamber not in CHAMBERS:
        errors.append("invalid:chamber")

    filed_at = str(row.get("filedAt") or "")
    if filed_at and not _DATE.fullmatch(filed_at):
        errors.append("invalid:filedAt")

    transacted = str(row.get("transactedAt") or "")
    if transacted and not _DATE.fullmatch(transacted):
        errors.append("invalid:transactedAt")

    side = str(row.get("side") or "")
    if side and side not in SIDES:
        errors.append("invalid:side")

    asset_type = str(row.get("assetType") or "")
    if asset_type and asset_type not in ASSET_TYPES:
        errors.append("invalid:assetType")

    owner = row.get("owner")
    if owner is not None and str(owner) not in OWNERS:
        errors.append("invalid:owner")

    member = row.get("member")
    if isinstance(member, Mapping):
        _require_str(member, "name", errors)
    elif member is not None:
        errors.append("invalid:member")

    amount = row.get("amountRange")
    if isinstance(amount, Mapping):
        if amount.get("min") is None:
            errors.append("missing:amountRange.min")
        text = str(amount.get("text") or "").strip()
        if not text:
            errors.append("missing:amountRange.text")
        max_val = amount.get("max")
        if max_val is not None and max_val != "":
            try:
                if float(max_val) < 0:
                    errors.append("invalid:amountRange.max")
            except (TypeError, ValueError):
                errors.append("invalid:amountRange.max")
    elif amount is not None:
        errors.append("invalid:amountRange")

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
        warnings.append("ticker_unresolved_use_asset_description")

    if transacted and filed_at and transacted > filed_at:
        warnings.append("transaction_date_after_filing_date_unusual")

    return ValidationOutcome(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))
