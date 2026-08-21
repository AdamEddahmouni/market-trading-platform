"""Versioned futures contract spec registry (F1) backed by the P0 bitemporal store."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..contracts.futures import FuturesContractSpec
from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from ..runtime.pit_joins import join_as_of


def _date_to_iso(as_of: date) -> str:
    return f"{as_of.isoformat()}T00:00:00.000000000Z"


_ES_CME_V1 = FuturesContractSpec(
    multiplier=Decimal("50"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("12.50"),
    point_value=Decimal("50"),
    spec_version="es_cme_v1",
    spec_effective_date="2020-01-01",
)

_DEFAULT_STORE = BitemporalReferenceStore()
_DEFAULT_STORE.append(
    ReferenceRecord(
        kind=ReferenceKind.FUTURES_SPEC,
        entity_key="ES",
        record_id="es-spec-default",
        record_version=1,
        valid_from="2020-01-01T00:00:00.000000000Z",
        valid_to="",
        known_from="2020-01-01T00:00:00.000000000Z",
        known_to="",
        payload={
            "multiplier": str(_ES_CME_V1.multiplier),
            "tick_size": str(_ES_CME_V1.tick_size),
            "tick_value": str(_ES_CME_V1.tick_value),
            "point_value": str(_ES_CME_V1.point_value),
            "spec_version": _ES_CME_V1.spec_version,
            "spec_effective_date": _ES_CME_V1.spec_effective_date,
        },
    )
)

# Backward-compatible alias for tests and notional helpers
ES_CONTRACT_SPEC = _ES_CME_V1


def resolve_futures_spec(instrument_family: str, as_of: date) -> FuturesContractSpec | None:
    """Return the effective contract spec for a family at as_of — fail-closed when unknown.

    `as_of` is both market-valid and knowledge-valid time at 00:00:00Z.
    """
    family = instrument_family.strip().upper()
    instant = _date_to_iso(as_of)
    joined = join_as_of(_DEFAULT_STORE, ReferenceKind.FUTURES_SPEC, family, instant, instant)
    if joined["status"] != "AVAILABLE":
        return None
    payload = joined["payload"]
    return FuturesContractSpec(
        multiplier=Decimal(str(payload.get("multiplier", "0"))),
        tick_size=Decimal(str(payload.get("tick_size", "0"))),
        tick_value=Decimal(str(payload.get("tick_value", "0"))),
        point_value=Decimal(str(payload.get("point_value", "0"))),
        spec_version=str(payload.get("spec_version", "")),
        spec_effective_date=str(payload.get("spec_effective_date", "")),
    )


__all__ = [
    "ES_CONTRACT_SPEC",
    "resolve_futures_spec",
]
