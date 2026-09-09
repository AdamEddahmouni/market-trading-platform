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


def commodity_spot_identity_key(
    *,
    commodity_code: str,
    quote_currency: str = "USD",
    venue_id: str = "",
) -> dict[str, str]:
    """Spot/index/reference identity for a commodity (e.g. XAU/USD reference).

    Distinct from both the economic commodity identity (no quote) and any
    specific futures contract trading that commodity.
    """
    key = {"commodity_code": commodity_code.upper(), "quote_currency": quote_currency.upper()}
    if venue_id.strip():
        key["venue_id"] = venue_id.upper()
    return key


def future_family_identity_key(*, family_root: str) -> dict[str, str]:
    return {"family_root": family_root.upper()}


def future_contract_identity_key(*, contract_id: str) -> dict[str, str]:
    return {"contract_id": contract_id.upper()}


def continuous_series_identity_key(
    *,
    family_root: str,
    methodology: str = "unadjusted_continuous",
) -> dict[str, str]:
    """Continuous/synthetic futures series identity (e.g. continuous ES).

    A continuous series is a research/reference aggregate — never an
    executable contract. The kind carries CONTINUOUS_SERIES tradability so the
    identity fails closed at any execution boundary.
    """
    return {"family_root": family_root.upper(), "methodology": methodology.lower()}


def option_contract_identity_key(*, option_id: str) -> dict[str, str]:
    return {"option_id": option_id.upper()}


def bond_identity_key(
    *,
    issuer: str = "",
    maturity_date: str = "",
    coupon: str = "",
    security_id: str = "",
) -> dict[str, str]:
    """Typed fixed-income identity.

    A standard external identifier (CUSIP/ISIN) is preferred when available;
    otherwise the issuer + maturity (+ coupon) typed terms define identity.
    ``issuer`` is required when no security_id is supplied.
    """
    if security_id.strip():
        return {"security_id": security_id.strip().upper()}
    if not issuer.strip() or not maturity_date.strip():
        raise Xa01Error(
            Xa01ErrorCode.REGISTRY_INVALID,
            "bond identity requires security_id or issuer+maturity_date",
            {},
        )
    key = {"issuer": issuer.upper(), "maturity_date": maturity_date[:10]}
    if coupon.strip():
        key["coupon"] = coupon
    return key


def crypto_pair_identity_key(
    *,
    base_asset: str,
    quote_asset: str,
    venue_id: str = "",
    network: str = "",
) -> dict[str, str]:
    """Crypto pair identity: base + quote (+ venue/network when identity-relevant).

    Base/quote order matters (BTC/USD != USD/BTC), BTC/USD != BTC/USDT, and a
    venue-qualified pair differs from the unqualified pair. A bare asset
    (``BTC``) is never silently treated as a pair.
    """
    base = base_asset.upper()
    quote = quote_asset.upper()
    if not base or not quote:
        raise Xa01Error(
            Xa01ErrorCode.REGISTRY_INVALID,
            "crypto pair requires base_asset and quote_asset",
            {"base_asset": base, "quote_asset": quote},
        )
    if base == quote:
        raise Xa01Error(
            Xa01ErrorCode.INVALID_CURRENCY_PAIR,
            "base and quote assets must differ",
            {"base_asset": base, "quote_asset": quote},
        )
    key: dict[str, str] = {"base_asset": base, "quote_asset": quote}
    if venue_id.strip():
        key["venue_id"] = venue_id.upper()
    if network.strip():
        key["network"] = network.upper()
    return key


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
