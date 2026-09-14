"""Point-in-time security identity binding for quantitative factor rows.

Ticker, listing MIC, and provisional symbol maps are display/join metadata.
They are not security identity. This module does not implement a CRSP,
Compustat, or FIGI master; it only refuses ticker-shaped identity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    dataclass_field_names,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from .errors import FactorContractError
from .identity import IDENTITY_VERSION, SECURITY_BINDING_ID_PREFIX, factor_hash
from .observation import FactorObservationV1
from .promotion import assert_research_only

_US_EQUITY_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
TICKER_IDENTITY_SCHEMES = frozenset(
    {
        "TICKER",
        "SYMBOL",
        "YAHOO",
        "PROVISIONAL",
        "DISPLAY",
        "FTEP.PROVISIONAL",
    }
)


def reject_ticker_as_security_id(security_id: str, *, identifier_scheme: str) -> None:
    scheme = str(identifier_scheme).strip().upper()
    if scheme in TICKER_IDENTITY_SCHEMES:
        raise FactorContractError("FACTOR_TICKER_SCHEME_IS_NOT_SECURITY_IDENTITY")
    if _US_EQUITY_TICKER.fullmatch(str(security_id)):
        raise FactorContractError("FACTOR_TICKER_IS_NOT_SECURITY_IDENTITY")


def security_binding_identity_payload(
    *,
    schema_version: str,
    security_id: str,
    issuer_id: str,
    share_class_id: str | None,
    as_of_ns: int,
    available_time_ns: int,
    identifier_scheme: str,
) -> dict[str, Any]:
    return {
        "identity_version": IDENTITY_VERSION,
        "schema_version": schema_version,
        "security_id": security_id,
        "issuer_id": issuer_id,
        "share_class_id": share_class_id,
        "as_of_ns": as_of_ns,
        "available_time_ns": available_time_ns,
        "identifier_scheme": identifier_scheme,
        "current_universe_backfill_forbidden": True,
    }


def derive_security_binding_id_from_payload(payload: dict[str, Any]) -> str:
    return factor_hash(payload, prefix=SECURITY_BINDING_ID_PREFIX)


@dataclass(frozen=True, slots=True)
class FactorSecurityBindingV1:
    """PIT mapping from a durable security to optional display/listing metadata.

    ``display_symbol`` and ``listing_mic`` are excluded from identity so a
    ticker rename does not mint a new security.
    """

    binding_id: str
    schema_version: str
    security_id: str
    issuer_id: str
    as_of_ns: int
    available_time_ns: int
    identifier_scheme: str
    share_class_id: str | None = None
    display_symbol: str | None = None
    listing_mic: str | None = None
    current_universe_backfill_forbidden: bool = True

    def __post_init__(self) -> None:
        validate_id(self.binding_id, field_name="binding_id")
        validate_schema_version(self.schema_version)
        validate_id(self.security_id, field_name="security_id")
        validate_id(self.issuer_id, field_name="issuer_id")
        validate_timestamp_ns(self.as_of_ns, field_name="as_of_ns")
        validate_timestamp_ns(self.available_time_ns, field_name="available_time_ns")
        if not self.identifier_scheme or self.identifier_scheme.strip() != self.identifier_scheme:
            raise FactorContractError("FACTOR_IDENTIFIER_SCHEME_INVALID")
        reject_ticker_as_security_id(self.security_id, identifier_scheme=self.identifier_scheme)
        if self.share_class_id is not None:
            validate_id(self.share_class_id, field_name="share_class_id")
        if self.display_symbol is not None:
            if not self.display_symbol.strip() or self.display_symbol.strip() != self.display_symbol:
                raise FactorContractError("DISPLAY_SYMBOL_INVALID")
            if self.display_symbol == self.security_id:
                raise FactorContractError("FACTOR_TICKER_IS_NOT_SECURITY_IDENTITY")
        if self.listing_mic is not None:
            if not self.listing_mic.strip() or self.listing_mic.strip() != self.listing_mic:
                raise FactorContractError("LISTING_MIC_INVALID")
            if self.listing_mic == self.security_id:
                raise FactorContractError("FACTOR_LISTING_IS_NOT_SECURITY_IDENTITY")
        if self.available_time_ns < self.as_of_ns:
            raise FactorContractError("FACTOR_SECURITY_AVAILABLE_BEFORE_AS_OF")
        if self.current_universe_backfill_forbidden is not True:
            raise FactorContractError("FACTOR_CURRENT_UNIVERSE_BACKFILL_FORBIDDEN")
        expected = derive_security_binding_id_from_payload(
            security_binding_identity_payload(
                schema_version=self.schema_version,
                security_id=self.security_id,
                issuer_id=self.issuer_id,
                share_class_id=self.share_class_id,
                as_of_ns=self.as_of_ns,
                available_time_ns=self.available_time_ns,
                identifier_scheme=self.identifier_scheme,
            )
        )
        if self.binding_id != expected:
            raise FactorContractError("FACTOR_SECURITY_BINDING_IDENTITY_MISMATCH")
        assert_research_only()


def build_security_binding(
    *,
    security_id: str,
    issuer_id: str,
    as_of_ns: int,
    available_time_ns: int,
    identifier_scheme: str,
    share_class_id: str | None = None,
    display_symbol: str | None = None,
    listing_mic: str | None = None,
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION,
) -> FactorSecurityBindingV1:
    payload = security_binding_identity_payload(
        schema_version=schema_version,
        security_id=security_id,
        issuer_id=issuer_id,
        share_class_id=share_class_id,
        as_of_ns=as_of_ns,
        available_time_ns=available_time_ns,
        identifier_scheme=identifier_scheme,
    )
    return FactorSecurityBindingV1(
        binding_id=derive_security_binding_id_from_payload(payload),
        schema_version=schema_version,
        security_id=security_id,
        issuer_id=issuer_id,
        as_of_ns=as_of_ns,
        available_time_ns=available_time_ns,
        identifier_scheme=identifier_scheme,
        share_class_id=share_class_id,
        display_symbol=display_symbol,
        listing_mic=listing_mic,
        current_universe_backfill_forbidden=True,
    )


def bind_factor_observation(
    observation: FactorObservationV1,
    binding: FactorSecurityBindingV1,
) -> FactorObservationV1:
    """Join a factor row to a PIT security binding. Does not mint a new row."""

    if observation.security_id != binding.security_id:
        raise FactorContractError("FACTOR_SECURITY_BINDING_MISMATCH")
    if observation.issuer_id != binding.issuer_id:
        raise FactorContractError("FACTOR_ISSUER_BINDING_MISMATCH")
    if observation.as_of_ns != binding.as_of_ns:
        raise FactorContractError("FACTOR_SECURITY_AS_OF_MISMATCH")
    if observation.available_time_ns < binding.available_time_ns:
        raise FactorContractError("FACTOR_SECURITY_MAPPING_NOT_YET_AVAILABLE")
    if (
        binding.display_symbol is not None
        and observation.display_symbol is not None
        and observation.display_symbol != binding.display_symbol
    ):
        raise FactorContractError("FACTOR_DISPLAY_SYMBOL_MISMATCH")
    return observation


_BINDING_ALLOWED = dataclass_field_names(FactorSecurityBindingV1)


def security_binding_to_dict(record: FactorSecurityBindingV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "binding_id": record.binding_id,
        "schema_version": record.schema_version,
        "security_id": record.security_id,
        "issuer_id": record.issuer_id,
        "as_of_ns": record.as_of_ns,
        "available_time_ns": record.available_time_ns,
        "identifier_scheme": record.identifier_scheme,
        "current_universe_backfill_forbidden": True,
    }
    if record.share_class_id is not None:
        body["share_class_id"] = record.share_class_id
    if record.display_symbol is not None:
        body["display_symbol"] = record.display_symbol
    if record.listing_mic is not None:
        body["listing_mic"] = record.listing_mic
    return body


def security_binding_from_dict(payload: dict[str, Any]) -> FactorSecurityBindingV1:
    reject_unknown_keys(payload, _BINDING_ALLOWED)
    return FactorSecurityBindingV1(
        binding_id=str(payload["binding_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        security_id=str(payload["security_id"]),
        issuer_id=str(payload["issuer_id"]),
        as_of_ns=int(payload["as_of_ns"]),
        available_time_ns=int(payload["available_time_ns"]),
        identifier_scheme=str(payload["identifier_scheme"]),
        share_class_id=payload.get("share_class_id"),
        display_symbol=payload.get("display_symbol"),
        listing_mic=payload.get("listing_mic"),
        current_universe_backfill_forbidden=bool(
            payload.get("current_universe_backfill_forbidden", True)
        ),
    )


__all__ = [
    "TICKER_IDENTITY_SCHEMES",
    "FactorSecurityBindingV1",
    "bind_factor_observation",
    "build_security_binding",
    "derive_security_binding_id_from_payload",
    "reject_ticker_as_security_id",
    "security_binding_from_dict",
    "security_binding_identity_payload",
    "security_binding_to_dict",
]
