"""G14 — canonical multi-asset instrument selector projections."""

from __future__ import annotations

from typing import Any

from ..xa01.compatibility import (
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from ..xa01.contracts import InstrumentRecord
from ..xa01.enums import ExternalIdentifierType, InstrumentKind, Tradability
from ..xa01.errors import Xa01Error
from ..xa01.registry import InstrumentRegistry, get_registry
from ..xa01.tradability import is_executable, selector_action_for_kind
from ..paper.eligibility import ensure_operator_fixture_registered
from .instrument_route_codec import decode_instrument_route_param


DEFAULT_SEARCH_LIMIT = 25
MAX_SEARCH_LIMIT = 50


def ensure_g14_selector_catalog(*, registry: InstrumentRegistry | None = None) -> None:
    """Idempotently register the G14 selector fixture catalog."""
    store = registry or get_registry()
    ensure_operator_fixture_registered(registry=store)
    for symbol in ("NVDA", "ES"):
        register_equity(symbol=symbol, registry=store)
    register_future_family(family_root="ES", registry=store)
    register_future_contract(
        contract_id="ES202512",
        family_root="ES",
        expiration="2025-12-19",
        contract_multiplier="50",
        registry=store,
    )
    register_continuous_futures_series(family_root="ES", registry=store)
    register_option_contract(
        option_id="NVDA20260815C00130000",
        underlying_symbol="NVDA",
        expiration="2026-08-15",
        strike="130",
        call_put="call",
        registry=store,
    )
    register_crypto_pair(base_asset="BTC", quote_asset="USD", venue_id="COINBASE", registry=store)
    register_crypto_pair(base_asset="BTC", quote_asset="USDT", venue_id="BINANCE", registry=store)


def _metadata_for_record(record: InstrumentRecord) -> dict[str, Any]:
    descriptor = record.descriptor
    identity = descriptor.identity
    metadata: dict[str, Any] = {
        "venue_id": descriptor.venue_id or None,
    }
    if identity.instrument_kind == InstrumentKind.OPTION_CONTRACT:
        metadata.update(
            {
                "underlying": descriptor.expiration and _underlying_from_relationships(record) or None,
                "expiry": descriptor.expiration or None,
                "strike": descriptor.strike or None,
                "right": descriptor.call_put or None,
                "multiplier": descriptor.denomination.contract_multiplier or None,
            }
        )
    elif identity.instrument_kind in {
        InstrumentKind.FUTURE_CONTRACT,
        InstrumentKind.FUTURE_FAMILY,
        InstrumentKind.CONTINUOUS_SERIES,
    }:
        metadata.update(
            {
                "root": descriptor.display_name.split()[0] if descriptor.display_name else None,
                "expiry": descriptor.expiration or None,
                "multiplier": descriptor.denomination.contract_multiplier or None,
            }
        )
    elif identity.instrument_kind == InstrumentKind.CRYPTO_PAIR:
        metadata.update(
            {
                "base": descriptor.base_asset,
                "quote": descriptor.quote_asset,
                "venue": descriptor.venue_id or None,
                "network": descriptor.network or None,
            }
        )
    elif identity.instrument_kind in {InstrumentKind.BOND, InstrumentKind.SOVEREIGN_SECURITY}:
        metadata.update(
            {
                "issuer": descriptor.issuer or None,
                "maturity": descriptor.maturity_date or None,
                "coupon": descriptor.coupon or None,
            }
        )
    return {key: value for key, value in metadata.items() if value not in (None, "")}


def _underlying_from_relationships(record: InstrumentRecord) -> str | None:
    from ..xa01.enums import RelationshipType

    for rel in record.relationships:
        if rel.relationship_type == RelationshipType.UNDERLYING:
            return rel.to_canonical_id
    return None


def selector_result_from_record(record: InstrumentRecord) -> dict[str, Any]:
    descriptor = record.descriptor
    identity = descriptor.identity
    executable = is_executable(
        instrument_kind=identity.instrument_kind,
        tradability=descriptor.tradability,
    )
    action = selector_action_for_kind(identity.instrument_kind, executable=executable)
    return {
        "instrument_id": identity.canonical_id,
        "asset_class": identity.asset_class.value,
        "instrument_kind": identity.instrument_kind.value,
        "display_label": descriptor.display_name or identity.canonical_id,
        "tradability": descriptor.tradability.value,
        "execution_eligible": executable,
        "selection_action": action,
        "provider_availability": "FIXTURE_CATALOG",
        "metadata": _metadata_for_record(record),
    }


def _match_score(query: str, record: InstrumentRecord) -> int:
    needle = query.upper()
    descriptor = record.descriptor
    identity = descriptor.identity
    canonical = identity.canonical_id.upper()
    display = (descriptor.display_name or "").upper()
    if canonical == needle or display == needle:
        return 100
    if canonical.startswith(needle) or display.startswith(needle):
        return 80
    if needle in canonical or needle in display:
        return 60
    for alias in record.aliases:
        alias_value = alias.alias_value.upper()
        if alias_value == needle:
            return 90
        if alias_value.startswith(needle) or needle in alias_value:
            return 50
    metadata = _metadata_for_record(record)
    underlying = str(metadata.get("underlying") or "").upper()
    if underlying and (underlying == needle or underlying.startswith(needle)):
        return 40
    return 0


def resolve_instrument_route_ref(
    route_param: str,
    *,
    registry: InstrumentRegistry | None = None,
) -> str:
    """Resolve a UI route instrument reference to a canonical XA-01 id."""
    store = registry or get_registry()
    ensure_g14_selector_catalog(registry=store)
    decoded = decode_instrument_route_param(route_param)
    if not decoded:
        raise ValueError("UI_INSTRUMENT_NOT_FOUND")
    try:
        store.get(decoded)
        return decoded
    except Xa01Error:
        pass
    needle = decoded.upper()
    for canonical_id in store.list_ids():
        record = store.get(canonical_id)
        descriptor = record.descriptor
        if canonical_id.upper() == needle:
            return canonical_id
        display = (descriptor.display_name or "").upper()
        if display == needle:
            return canonical_id
        for alias in record.aliases:
            if alias.alias_value.upper() == needle:
                return canonical_id
    ticker = store.resolve_alias_scope(
        provider_id="US_EQUITY",
        identifier_type=ExternalIdentifierType.TICKER,
        alias_value=needle,
    )
    if ticker:
        return ticker
    raise ValueError("UI_INSTRUMENT_NOT_FOUND")


def search_canonical_instruments(
    query: str,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    registry: InstrumentRegistry | None = None,
) -> list[dict[str, Any]]:
    store = registry or get_registry()
    ensure_g14_selector_catalog(registry=store)
    needle = str(query or "").strip()
    if not needle:
        return []
    bounded = max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), MAX_SEARCH_LIMIT))
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for canonical_id in store.list_ids():
        record = store.get(canonical_id)
        score = _match_score(needle, record)
        if score <= 0:
            continue
        scored.append((score, canonical_id, selector_result_from_record(record)))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[:bounded]]


def build_selector_search_payload(query: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> dict[str, Any]:
    results = search_canonical_instruments(query, limit=limit)
    return {
        "query": query,
        "results": results,
        "schema_version": "g14.selector.v1",
    }


__all__ = [
    "build_selector_search_payload",
    "ensure_g14_selector_catalog",
    "resolve_instrument_route_ref",
    "search_canonical_instruments",
    "selector_result_from_record",
]
