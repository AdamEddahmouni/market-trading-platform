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
    Tradability,
    XaAssetClass,
)
from .errors import Xa01Error, Xa01ErrorCode
from .identity import (
    bond_identity_key,
    commodity_identity_key,
    commodity_spot_identity_key,
    continuous_series_identity_key,
    crypto_pair_identity_key,
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
from .tradability import default_tradability, validate_tradability


def _descriptor(
    *,
    instrument_kind: InstrumentKind,
    asset_class: XaAssetClass,
    identity_key: dict[str, str],
    display_name: str = "",
    venue_id: str = "",
    denomination: DenominationMetadata | None = None,
    tradability: Tradability | None = None,
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
    effective_tradability = tradability if tradability is not None else default_tradability(instrument_kind)
    validate_tradability(instrument_kind=instrument_kind, tradability=effective_tradability)
    return InstrumentDescriptor(
        identity=identity,
        display_name=display_name or canonical_id,
        venue_id=venue_id,
        denomination=denomination or DenominationMetadata(),
        tradability=effective_tradability,
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


def _get_or_register_commodity(
    *,
    store: InstrumentRegistry,
    commodity_code: str,
    commodity_sector: str = "",
) -> str:
    """Reuse an already-registered economic commodity, or register it.

    Descriptive metadata (sector) must never conflict with an existing
    registration, so relationship builders reuse the existing identity when
    the commodity is already present.
    """
    from .errors import Xa01Error

    commodity_id = derive_canonical_id(
        instrument_kind=InstrumentKind.COMMODITY_ECONOMIC,
        asset_class=XaAssetClass.COMMODITY,
        identity_key=commodity_identity_key(commodity_code=commodity_code),
    )
    try:
        existing = store.get(commodity_id)
        return existing.descriptor.identity.canonical_id
    except Xa01Error:
        return register_commodity_economic(
            commodity_code=commodity_code,
            commodity_sector=commodity_sector,
            registry=store,
        )


def register_commodity_economic(
    *,
    commodity_code: str,
    display_name: str = "",
    commodity_sector: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.COMMODITY_ECONOMIC,
        asset_class=XaAssetClass.COMMODITY,
        identity_key=commodity_identity_key(commodity_code=commodity_code),
        display_name=display_name or commodity_code.upper(),
        commodity_code=commodity_code.upper(),
        commodity_sector=commodity_sector,
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.COMMODITY_UNIT,
            quantity_unit="troy_oz" if commodity_code.upper() in {"GOLD", "SILVER"} else "",
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


def register_commodity_spot(
    *,
    commodity_code: str,
    quote_currency: str = "USD",
    venue_id: str = "",
    display_name: str = "",
    commodity_sector: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    """Register a spot/index/reference identity for a commodity (e.g. XAU/USD).

    The spot/reference identity is distinct from the economic commodity and
    from any specific futures contract; it is REFERENCE_ONLY and linked to the
    economic commodity via BENCHMARK_OF.
    """
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.COMMODITY_SPOT,
        asset_class=XaAssetClass.COMMODITY,
        identity_key=commodity_spot_identity_key(
            commodity_code=commodity_code,
            quote_currency=quote_currency,
            venue_id=venue_id,
        ),
        display_name=display_name or f"{commodity_code.upper()}/{quote_currency.upper()}",
        venue_id=venue_id,
        commodity_code=commodity_code.upper(),
        quote_currency=quote_currency.upper(),
        denomination=DenominationMetadata(
            currency=quote_currency.upper(),
            price_unit_kind=PriceUnitKind.COMMODITY_UNIT,
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.COMMODITY,
            AnalyticalDomain.MACRO,
        ),
    )
    commodity_id = _get_or_register_commodity(
        store=store,
        commodity_code=commodity_code,
        commodity_sector=commodity_sector,
    )
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.BENCHMARK_OF,
            from_canonical_id=canonical_id,
            to_canonical_id=commodity_id,
        )
    )
    return canonical_id


def register_commodity_proxy(
    *,
    symbol: str,
    commodity_code: str,
    venue_id: str = "US_EQUITY",
    display_name: str = "",
    commodity_sector: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    """Register an ETF/security proxy (e.g. GLD) over an economic commodity.

    The proxy is a tradable security whose UNDERLYING relationship points to
    the economic commodity — it is never the same identity as the commodity or
    its futures contracts.
    """
    store = registry or get_registry()
    proxy_id = register_equity(
        symbol=symbol,
        venue_id=venue_id,
        display_name=display_name,
        registry=store,
    )
    commodity_id = _get_or_register_commodity(
        store=store,
        commodity_code=commodity_code,
        commodity_sector=commodity_sector,
    )
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.UNDERLYING,
            from_canonical_id=proxy_id,
            to_canonical_id=commodity_id,
        )
    )
    return proxy_id


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
        tradability=Tradability.REFERENCE_ONLY,
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
    contract_multiplier: str | None = None,
    currency: str = "USD",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    # G4: a futures contract has no safe default multiplier. Missing
    # economics fail closed at registration so a derivative can never silently
    # acquire equity-style multiplier=1 semantics. Callers must supply the
    # contract multiplier / point value from authoritative contract specs.
    if contract_multiplier is None or not str(contract_multiplier).strip():
        raise Xa01Error(
            Xa01ErrorCode.INVALID_INSTRUMENT_KIND,
            "future contract requires explicit contract_multiplier (no safe default)",
            {"contract_id": str(contract_id)},
        )
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.FUTURE_CONTRACT,
        asset_class=XaAssetClass.FUTURE,
        identity_key=future_contract_identity_key(contract_id=contract_id),
        display_name=contract_id.upper(),
        contract_month=contract_month,
        expiration=expiration,
        denomination=DenominationMetadata(
            currency=currency.upper(),
            price_unit_kind=PriceUnitKind.CURRENCY_PER_CONTRACT,
            contract_multiplier=str(contract_multiplier),
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
        commodity_id = _get_or_register_commodity(
            store=store,
            commodity_code=underlying_commodity_code,
        )
        store.add_relationship(
            InstrumentRelationship(
                relationship_type=RelationshipType.UNDERLYING,
                from_canonical_id=canonical_id,
                to_canonical_id=commodity_id,
            )
        )
    return canonical_id


def register_continuous_futures_series(
    *,
    family_root: str,
    methodology: str = "unadjusted_continuous",
    display_name: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    """Register a continuous/synthetic futures series identity.

    The continuous series is a research/analytics/reference identity with
    CONTINUOUS_SERIES tradability. It is linked to its futures family via
    CONTRACT_ROOT and can never become an executable contract.
    """
    store = registry or get_registry()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.CONTINUOUS_SERIES,
        asset_class=XaAssetClass.FUTURE,
        identity_key=continuous_series_identity_key(
            family_root=family_root,
            methodology=methodology,
        ),
        display_name=display_name or f"{family_root.upper()} continuous ({methodology})",
        denomination=DenominationMetadata(
            currency="USD",
            price_unit_kind=PriceUnitKind.CURRENCY_PER_CONTRACT,
        ),
        tradability=Tradability.CONTINUOUS_SERIES,
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.DERIVATIVES,
            AnalyticalDomain.COMMODITY,
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
    return canonical_id


def register_option_contract(
    *,
    option_id: str,
    underlying_symbol: str,
    expiration: str = "",
    strike: str = "",
    call_put: str = "",
    contract_multiplier: str | None = None,
    currency: str = "USD",
    registry: InstrumentRegistry | None = None,
) -> str:
    store = registry or get_registry()
    # G4: multiplier is explicit canonical economics, never inferred. Standard
    # US equity options default to 100 (the long-standing convention) but the
    # value is a parameter so non-standard contracts (mini/single-stock, index
    # options) are representable without symbol heuristics. It is never
    # silently defaulted to 1.
    effective_multiplier = contract_multiplier if contract_multiplier is not None else "100"
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.OPTION_CONTRACT,
        asset_class=XaAssetClass.OPTION,
        identity_key=option_contract_identity_key(option_id=option_id),
        display_name=option_id.upper(),
        expiration=expiration,
        strike=strike,
        call_put=call_put,
        denomination=DenominationMetadata(
            currency=currency.upper(),
            price_unit_kind=PriceUnitKind.CURRENCY_PER_CONTRACT,
            contract_multiplier=effective_multiplier,
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


def register_bond(
    *,
    issuer: str,
    maturity_date: str,
    coupon: str = "",
    security_type: str = "BOND",
    credit_tier: str = "CORPORATE",
    par_value: str = "1000",
    currency: str = "USD",
    cusip: str = "",
    isin: str = "",
    issue_date: str = "",
    provider_id: str = "",
    provider_symbol: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    """Register a typed bond / fixed-income identity.

    Identity is driven by the standard external identifier (CUSIP/ISIN) when
    available, otherwise by typed terms (issuer + maturity + coupon). A bond is
    REFERENCE_ONLY in IMP today: no bond execution surface exists, so it fails
    closed at any execution boundary.
    """
    store = registry or get_registry()
    security_id = cusip or isin
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.BOND,
        asset_class=XaAssetClass.BOND,
        identity_key=bond_identity_key(
            issuer=issuer,
            maturity_date=maturity_date,
            coupon=coupon,
            security_id=security_id,
        ),
        display_name=f"{issuer}:{maturity_date}",
        issuer=issuer,
        security_type=security_type,
        credit_tier=credit_tier,
        par_value=par_value,
        issue_date=issue_date,
        maturity_date=maturity_date,
        coupon=coupon,
        denomination=DenominationMetadata(
            currency=currency,
            price_unit_kind=PriceUnitKind.YIELD_RATE,
        ),
        tradability=Tradability.REFERENCE_ONLY,
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.RATES,
            AnalyticalDomain.MACRO,
        ),
    )
    if cusip:
        store.add_alias(
            canonical_id,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.CUSIP,
                alias_value=cusip.upper(),
            ),
        )
    if isin:
        store.add_alias(
            canonical_id,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.ISIN,
                alias_value=isin.upper(),
            ),
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


def register_crypto_pair(
    *,
    base_asset: str,
    quote_asset: str,
    venue_id: str = "",
    network: str = "",
    product_type: str = "SPOT",
    display_name: str = "",
    provider_id: str = "",
    provider_symbol: str = "",
    registry: InstrumentRegistry | None = None,
) -> str:
    """Register a first-class crypto pair identity (e.g. BTC/USD).

    Base and quote assets are explicit; venue/network participate in identity
    where identity-relevant. A bare ``BTC`` is never silently treated as a
    pair, and BTC/USD != BTC/USDT. Pairs are tradable spot identities; the
    identity model intentionally does not cover wallets/on-chain execution.
    """
    store = registry or get_registry()
    base = base_asset.upper()
    quote = quote_asset.upper()
    descriptor = _descriptor(
        instrument_kind=InstrumentKind.CRYPTO_PAIR,
        asset_class=XaAssetClass.CRYPTO,
        identity_key=crypto_pair_identity_key(
            base_asset=base,
            quote_asset=quote,
            venue_id=venue_id,
            network=network,
        ),
        display_name=display_name or f"{base}/{quote}",
        venue_id=venue_id,
        base_asset=base,
        quote_asset=quote,
        base_currency=base,
        quote_currency=quote,
        network=network,
        security_type=product_type.upper() or "SPOT",
        denomination=DenominationMetadata(
            currency=quote,
            price_unit_kind=PriceUnitKind.FX_PAIR_QUOTE,
        ),
    )
    canonical_id = store.register_descriptor(descriptor)
    store.add_domains(
        canonical_id,
        (
            AnalyticalDomain.FX,
            AnalyticalDomain.MACRO,
        ),
    )
    quote_id = register_currency(iso_code=quote, registry=store)
    store.add_relationship(
        InstrumentRelationship(
            relationship_type=RelationshipType.DENOMINATED_IN,
            from_canonical_id=canonical_id,
            to_canonical_id=quote_id,
        )
    )
    if provider_id and provider_symbol:
        store.add_alias(
            canonical_id,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value=provider_symbol,
                provider_id=provider_id,
                venue_id=venue_id,
            ),
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
    # G4: multiplier comes from the authoritative contract spec when present;
    # a contract without a spec multiplier fails closed in
    # register_future_contract (never silently 1).
    spec_multiplier = None
    if contract.spec is not None:
        spec_multiplier = str(contract.spec.multiplier)
    return register_future_contract(
        contract_id=contract.contract_id,
        family_root=contract.instrument_family,
        underlying_commodity_code=underlying_commodity_code,
        contract_month=contract.expiration[:7].replace("-", "") if contract.expiration else "",
        expiration=contract.expiration,
        contract_multiplier=spec_multiplier,
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
        # G4: the contract's own multiplier is canonical economics — carried
        # through explicitly instead of assuming the 100 default.
        contract_multiplier=str(contract.multiplier),
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
    if identity.instrument_kind == InstrumentKind.CRYPTO_PAIR:
        base = str(identity.identity_key.get("base_asset", ""))
        quote = str(identity.identity_key.get("quote_asset", ""))
        return {"instrument_id": f"{base}/{quote}", "venue_id": record.descriptor.venue_id or "CRYPTO"}
    if identity.instrument_kind == InstrumentKind.CONTINUOUS_SERIES:
        family = str(identity.identity_key.get("family_root", ""))
        return {"instrument_id": f"{family} continuous", "venue_id": "FUTURES"}
    if identity.instrument_kind == InstrumentKind.FUTURE_FAMILY:
        return {"instrument_id": str(identity.identity_key.get("family_root", "")), "venue_id": "FUTURES"}
    if identity.instrument_kind == InstrumentKind.BOND:
        issuer = str(identity.identity_key.get("issuer", ""))
        maturity = str(identity.identity_key.get("maturity_date", ""))
        return {"instrument_id": f"{issuer}:{maturity}" or canonical_id, "venue_id": "FIXED_INCOME"}
    if identity.instrument_kind == InstrumentKind.COMMODITY_SPOT:
        commodity = str(identity.identity_key.get("commodity_code", ""))
        quote = str(identity.identity_key.get("quote_currency", "USD"))
        return {"instrument_id": f"{commodity}/{quote}", "venue_id": record.descriptor.venue_id or "GLOBAL"}
    return {"instrument_id": canonical_id, "venue_id": record.descriptor.venue_id or "GLOBAL"}
