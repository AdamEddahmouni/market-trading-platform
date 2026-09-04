"""Deterministic XA-01 canonical instrument identity derivation."""

from __future__ import annotations

from typing import Mapping

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

from .enums import IDENTITY_PROFILE, InstrumentKind, XaAssetClass
from .errors import Xa01Error, Xa01ErrorCode


def _normalized_key(identity_key: Mapping[str, str]) -> dict[str, str]:
    return {str(k): str(v).strip().upper() for k, v in sorted(identity_key.items()) if str(v).strip()}


def derive_canonical_id(
    *,
    instrument_kind: InstrumentKind,
    asset_class: XaAssetClass,
    identity_key: Mapping[str, str],
) -> str:
    material = {
        "profile": IDENTITY_PROFILE,
        "instrument_kind": instrument_kind.value,
        "asset_class": asset_class.value,
        "identity_key": _normalized_key(identity_key),
    }
    if not material["identity_key"]:
        raise Xa01Error(
            Xa01ErrorCode.REGISTRY_INVALID,
            "identity_key must not be empty",
            {"instrument_kind": instrument_kind.value},
        )
    digest = sha256_bytes(canonical_bytes(material))
    return f"XA01:{digest[:16]}"


def equity_identity_key(*, symbol: str, venue_id: str = "US_EQUITY") -> dict[str, str]:
    return {"symbol": symbol.upper(), "venue_id": venue_id.upper()}


def sovereign_identity_key(
    *,
    cusip: str = "",
    issuer: str = "",
    maturity_date: str = "",
    coupon: str = "",
) -> dict[str, str]:
    if cusip:
        return {"cusip": cusip.upper()}
    if issuer and maturity_date:
        key = {"issuer": issuer.upper(), "maturity_date": maturity_date[:10]}
        if coupon:
            key["coupon"] = coupon
        return key
    raise Xa01Error(
        Xa01ErrorCode.REGISTRY_INVALID,
        "sovereign identity requires cusip or issuer+maturity",
        {},
    )


def commodity_identity_key(*, commodity_code: str) -> dict[str, str]:
    return {"commodity_code": commodity_code.upper()}


def future_family_identity_key(*, family_root: str) -> dict[str, str]:
    return {"family_root": family_root.upper()}


def future_contract_identity_key(*, contract_id: str) -> dict[str, str]:
    return {"contract_id": contract_id.upper()}


def option_contract_identity_key(*, option_id: str) -> dict[str, str]:
    return {"option_id": option_id.upper()}


def currency_identity_key(*, iso_code: str) -> dict[str, str]:
    return {"iso_code": iso_code.upper()}


def fx_pair_identity_key(*, base_currency: str, quote_currency: str) -> dict[str, str]:
    base = base_currency.upper()
    quote = quote_currency.upper()
    if base == quote:
        raise Xa01Error(
            Xa01ErrorCode.INVALID_CURRENCY_PAIR,
            "base and quote must differ",
            {"base_currency": base, "quote_currency": quote},
        )
    return {"base_currency": base, "quote_currency": quote}
