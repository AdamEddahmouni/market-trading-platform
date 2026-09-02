"""XA-01 builders and compatibility adapters for existing asset models."""

from __future__ import annotations

from market_platform_foundation.contracts.futures import FuturesContract
from market_platform_foundation.contracts.options import OptionContract
from market_platform_foundation.providers.contracts import SymbolMapping

from .contracts import (
    CanonicalInstrumentIdentity,
    DenominationMetadata,
    DomainParticipation,
    ExternalIdentifier,
    InstrumentDescriptor,
    InstrumentRelationship,
)
from .enums import (
    IDENTITY_PROFILE,
    AnalyticalDomain,
    ExternalIdentifierType,
    InstrumentKind,
    PriceUnitKind,
    RelationshipType,
    XaAssetClass,
)
from .identity import (
    commodity_identity_key,
    currency_identity_key,
    derive_canonical_id,
    equity_identity_key,
    future_contract_identity_key,
    future_family_identity_key,
    fx_pair_identity_key,
    option_contract_identity_key,
    sovereign_identity_key,
)
from .registry import InstrumentRegistry, get_registry


def _descriptor(
    *,
    instrument_kind: InstrumentKind,
    asset_class: XaAssetClass,
    identity_key: dict[str, str],
    display_name: str = "",
    venue_id: str = "",
    denomination: DenominationMetadata | None = None,
    **fields: str,
) -> InstrumentDescriptor:
    canonical_id = derive_canonical_id(
        instrument_kind=instrument_kind,
        asset_class=asset_class,
        identity_key=identity_key,
    )
    identity = CanonicalInstrumentIdentity(
        canonical_id=canonical_id,
        instrument_kind=instrument_kind,
        asset_class=asset_class,
        identity_profile=IDENTITY_PROFILE,
        identity_key=identity_key,
    )
    return InstrumentDescriptor(
        identity=identity,
        display_name=display_name or canonical_id,
        venue_id=venue_id,
        denomination=denomination or DenominationMetadata(),
        **fields,
    )


def register_equity(
    *,
    symbol: str,
    venue_id: str = "US_EQUITY",
    display_name: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.TRADABLE_SECURITY,
        asset_class=XaAssetClass.EQUITY,
        identity_key=equity_identity_key(symbol=symbol, venue_id=venue_id),
        display_name=display_name or symbol.upper(),
        venue_id=venue_id,
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.CURRENCY_PER_SHARE,
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(canonical_id, (AnalyticalDomain.EQUITY,))
    store.add_alias(
        canonical_id,
        ExternalIdentifier(
            identifier_type=ExternalIdentifierType.TICKER,
            alias_value=symbol.upper(),
            venue_id=venue_id,
        ),
    )
    return canonical_id


def register_sovereign_security(
    *,
    cusip: str,
    issuer: str,
    currency: str = "USD",
    security_type: str = "TREASURY_NOTE",
    issue_date: str = "",
    maturity_date: str = "",
    coupon: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    identity_key = sovereign_identity_key(
        cusip=cusip,
        issuer=issuer,
        maturity_date=maturity_date,
        coupon=coupon,
    )
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.SOVEREIGN_SECURITY,
        asset_class=XaAssetClass.SOVEREIGN_DEBT,
        identity_key=identity_key,
        display_name=f"{issuer}:{maturity_date}",
        denomination=DenominationMetadata(
            currency=currency,
            price_unit_kind=PriceUnitKind.YIELD_RATE,
        ),
        sovereign_issuer=issuer,
        security_type=security_type,
        issue_date=issue_date,
        maturity_date=maturity_date,
        coupon=coupon,
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.RATES,
            AnalyticalDomain.SOVEREIGN,
            AnalyticalDomain.MACRO,
        ),
    )
    store.add_alias(
        canonical_id,
        ExternalIdentifier(identifier_type=ExternalIdentifierType.CUSIP, alias_value=cusip.upper()),
    )
    return canonical_id


def register_commodity_economic(
    *,
    commodity_code: str,
    display_name: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.COMMODITY_ECONOMIC,
        asset_class=XaAssetClass.COMMODITY,
        identity_key=commodity_identity_key(commodity_code=commodity_code),
        display_name=display_name or commodity_code.upper(),
        commodity_code=commodity_code.upper(),
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.COMMODITY_UNIT,
            quantity_unit="troy_oz",
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.COMMODITY,
            AnalyticalDomain.MONETARY_RESERVE,
            AnalyticalDomain.MACRO,
            AnalyticalDomain.SAFE_HAVEN,
        ),
    )
    return canonical_id


def register_future_family(
    *,
    family_root: str,
    display_name: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.FUTURE_FAMILY,
        asset_class=XaAssetClass.FUTURE,
        identity_key=future_family_identity_key(family_root=family_root),
        display_name=display_name or family_root.upper(),
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.CURRENCY_PER_CONTRACT,
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(canonical_id, (AnalyticalDomain.DERIVATIVES,))
    return canonical_id


def register_future_contract(
    *,
    contract_id: str,
    family_root: str,
    underlying_commodity_code: str = "",
    contract_month: str = "",
    expiration: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.FUTURE_CONTRACT,
        asset_class=XaAssetClass.FUTURE,
        identity_key=future_contract_identity_key(contract_id=contract_id),
        display_name=contract_id.upper(),
        contract_month=contract_month,
        expiration=expiration,
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.CURRENCY_PER_CONTRACT,
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.DERIVATIVES,
            AnalyticalDomain.COMMODITY,
            AnalyticalDomain.MONETARY_RESERVE,
            AnalyticalDomain.MACRO,
        ),
    )
    family_id = register_future_family(family_root=family_root, registry=store)
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.CONTRACT_ROOT,
            from_canonical_id=canonical_id,
            to_canonical_id=family_id,
        )
    )
    if underlying_commodity_code:
        commodity_id = register_commodity_economic(
            commodity_code=underlying_commodity_code,
            registry=store,
        )
        store.add_relationship(
            InstrumentRelationship(
                relationship_type=RelationshipType.UNDERLYING,
                from_canonical_id=canonical_id,
                to_canonical_id=commodity_id,
            )
        )
    return canonical_id


def register_option_contract(
    *,
    option_id: str,
    underlying_symbol: str,
    expiration: str = "",
    strike: str = "",
    call_put: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.OPTION_CONTRACT,
        asset_class=XaAssetClass.OPTION,
        identity_key=option_contract_identity_key(option_id=option_id),
        display_name=option_id.upper(),
        expiration=expiration,
        strike=strike,
        call_put=call_put,
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.CURRENCY_PER_CONTRACT,
            contract_multiplier="100",
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(canonical_id, (AnalyticalDomain.DERIVATIVES, AnalyticalDomain.EQUITY))
    underlying_id = register_equity(symbol=underlying_symbol, registry=store)
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.UNDERLYING,
            from_canonical_id=canonical_id,
            to_canonical_id=underlying_id,
        )
    )
    return canonical_id


def register_currency(
    *,
    iso_code: str,
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.CURRENCY_UNIT,
        asset_class=XaAssetClass.CURRENCY,
        identity_key=currency_identity_key(iso_code=iso_code),
        display_name=iso_code.upper(),
        denomination=DenominationMetadata(currency=iso_code.upper()),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(canonical_id, (AnalyticalDomain.FX, AnalyticalDomain.MACRO))
    return canonical_id


def register_fx_pair(
    *,
    base_currency: str,
    quote_currency: str,
    provider_id: str = "",
    provider_symbol: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.FX_PAIR,
        asset_class=XaAssetClass.FX_PAIR,
        identity_key=fx_pair_identity_key(
            base_currency=base_currency,
            quote_currency=quote_currency,
        ),
        display_name=f"{base_currency.upper()}/{quote_currency.upper()}",
        base_currency=base_currency.upper(),
        quote_currency=quote_currency.upper(),
        denomination=DenominationMetadata(
            currency=quote_currency.upper(),
            price_unit_kind=PriceUnitKind.FX_PAIR_QUOTE,
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(canonical_id, (AnalyticalDomain.FX, AnalyticalDomain.MACRO))
    base_id = register_currency(iso_code=base_currency, registry=store)
    quote_id = register_currency(iso_code=quote_currency, registry=store)
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.DENOMINATED_IN,
            from_canonical_id=canonical_id,
            to_canonical_id=quote_id,
        )
    )
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.UNDERLYING,
            from_canonical_id=canonical_id,
            to_canonical_id=base_id,
        )
    )
    if provider_id and provider_symbol:
        store.add_alias(
            canonical_id,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value=provider_symbol,
                provider_id=provider_id,
            ),
        )
    return canonical_id


def from_symbol_mapping(
    mapping: SymbolMapping,
    *,
    provider_id: str,
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    canonical_id = register_equity(
        symbol=mapping.instrument_id,
        venue_id=mapping.venue_id,
        registry=store,
    )
    store.add_alias(
        canonical_id,
        ExternalIdentifier(
            identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
            alias_value=mapping.provider_symbol,
            provider_id=provider_id,
            venue_id=mapping.venue_id,
        ),
    )
    return canonical_id


def from_futures_contract(
    contract: FuturesContract,
    *,
    underlying_commodity_code: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    return register_future_contract(
        contract_id=contract.contract_id,
        family_root=contract.instrument_family,
        underlying_commodity_code=underlying_commodity_code,
        contract_month=contract.expiration[:7].replace("-", "") if contract.expiration else "",
        expiration=contract.expiration,
        registry=store,
    )


def from_option_contract(
    contract: OptionContract,
    *,
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    return register_option_contract(
        option_id=contract.option_id,
        underlying_symbol=contract.underlying_id,
        expiration=contract.expiration,
        strike=str(contract.strike),
        call_put=contract.call_put,
        registry=store,
    )


def legacy_instrument_ref(canonical_id: str, *, registry: InstrumentRegistry | None = None) -> dict[str, str]:
    store = registry or get_registry()
    record = store.get(canonical_id)
    identity = record.descriptor.identity
    if identity.instrument_kind == InstrumentKind.TRADABLE_SECURITY:
        symbol = str(identity.identity_key.get("symbol", ""))
        venue = str(identity.identity_key.get("venue_id", "US_EQUITY"))
        return {"instrument_id": symbol, "venue_id": venue}
    if identity.instrument_kind == InstrumentKind.FUTURE_CONTRACT:
        return {"instrument_id": str(identity.identity_key.get("contract_id", "")), "venue_id": "FUTURES"}
    if identity.instrument_kind == InstrumentKind.OPTION_CONTRACT:
        return {"instrument_id": str(identity.identity_key.get("option_id", "")), "venue_id": "US_OPTIONS"}
    return {"instrument_id": canonical_id, "venue_id": record.descriptor.venue_id or "GLOBAL"}
