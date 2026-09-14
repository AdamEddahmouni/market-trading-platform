"""Look up DECLARED OF-03 strategy families for operator review rows.

Metadata only. Does not mint OpportunityV1 or ForecastV1, does not rank,
and does not call a scanner. Unknown or unversioned claims fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from market_platform_foundation.of03.errors import OF03Error
from market_platform_foundation.of03.strategy_families import (
    ADMISSION_KIND_METADATA_ONLY,
    LoadedStrategyFamilyRegistry,
    load_strategy_family_registry,
)

STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_ADMITTED = "ADMITTED"
STATUS_DENIED = "DENIED"


@dataclass(frozen=True, slots=True)
class ReviewFamilyResolution:
    status: str
    family_id: str | None = None
    strategy_version: str | None = None
    definition_version: int | None = None
    definition_hash: str | None = None
    reason_code: str | None = None
    admission_kind: str | None = None


def family_claim_from_metadata(metadata: Mapping[str, Any] | None) -> tuple[str | None, int | None, str | None]:
    payload = metadata if isinstance(metadata, Mapping) else {}
    raw_family = payload.get("strategy_family")
    family_id = raw_family.strip() if isinstance(raw_family, str) and raw_family.strip() else None
    raw_version = payload.get("family_definition_version")
    definition_version = raw_version if isinstance(raw_version, int) else None
    raw_strategy_version = payload.get("strategy_version")
    strategy_version = (
        raw_strategy_version.strip()
        if isinstance(raw_strategy_version, str) and raw_strategy_version.strip()
        else None
    )
    return family_id, definition_version, strategy_version


def resolve_review_family(
    metadata: Mapping[str, Any] | None,
    *,
    registry: LoadedStrategyFamilyRegistry | None = None,
) -> ReviewFamilyResolution:
    family_id, definition_version, strategy_version = family_claim_from_metadata(metadata)
    if family_id is None:
        return ReviewFamilyResolution(status=STATUS_UNAVAILABLE, reason_code="STRATEGY_FAMILY_ABSENT")
    store = registry
    if store is None:
        try:
            store = load_strategy_family_registry(fail_closed=True)
        except OF03Error as exc:
            return ReviewFamilyResolution(
                status=STATUS_DENIED,
                family_id=family_id,
                strategy_version=strategy_version,
                definition_version=definition_version,
                reason_code=str(exc.code.value),
            )
    try:
        family = store.resolve_family(family_id, definition_version)
    except OF03Error as exc:
        return ReviewFamilyResolution(
            status=STATUS_DENIED,
            family_id=family_id,
            strategy_version=strategy_version,
            definition_version=definition_version,
            reason_code=str(exc.code.value),
        )
    if family.admission_kind != ADMISSION_KIND_METADATA_ONLY or family.production_evaluator:
        return ReviewFamilyResolution(
            status=STATUS_DENIED,
            family_id=family.family_id,
            strategy_version=strategy_version,
            definition_version=family.definition_version,
            definition_hash=family.definition_hash,
            reason_code="FAMILY_NOT_METADATA_ONLY",
        )
    return ReviewFamilyResolution(
        status=STATUS_ADMITTED,
        family_id=family.family_id,
        strategy_version=strategy_version,
        definition_version=family.definition_version,
        definition_hash=family.definition_hash,
        reason_code="METADATA_ONLY_ADMITTED",
        admission_kind=ADMISSION_KIND_METADATA_ONLY,
    )


__all__ = [
    "ReviewFamilyResolution",
    "STATUS_ADMITTED",
    "STATUS_DENIED",
    "STATUS_UNAVAILABLE",
    "family_claim_from_metadata",
    "resolve_review_family",
]
