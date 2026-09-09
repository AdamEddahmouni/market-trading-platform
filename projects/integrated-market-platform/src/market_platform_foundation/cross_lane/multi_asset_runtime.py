"""G12 — canonical multi-asset runtime domain projection.

One shared path:

XA-01 identity → provider qualification → canonical observation/history
→ runtime domain projection → portfolio/valuation → risk admission → API projection

Asset-specific extensions exist only where semantics genuinely differ. This
module does not create parallel registries, portfolios, or provider systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from ..market_data.observational_lanes import ObservationalLaneRuntime
from ..market_data.observational_state import ObservationalStateStore
from ..portfolio.canonical import (
    BondPriceBasis,
    MarkDataStatus,
    PortfolioPosition,
    ValuationMark,
    ValuationStatus,
)
from ..portfolio.instrument_economics import EconomicsError, economics_from_descriptor
from ..portfolio.valuation import ValuationContext, value_bond_position, value_position
from ..risk.pretrade import PreTradeRiskContext, evaluate_pretrade
from ..xa01.contracts import InstrumentDescriptor
from ..xa01.enums import InstrumentKind, Tradability, XaAssetClass
from .runtime_status import RuntimeDomainStatus


@dataclass(frozen=True, slots=True)
class RuntimeProjectionRequest:
    """Inputs for one deterministic runtime domain projection."""

    descriptor: InstrumentDescriptor
    provider: str = ""
    source_time_ns: int | None = None
    received_time_ns: int | None = None
    as_of_time_ns: int | None = None
    # Domain-specific optional facts (never replace canonical identity).
    price: float | None = None
    multiplier: float | None = None
    underlying_id: str | None = None
    chain_status: str = "available"
    chain_count: int | None = None
    greeks: Mapping[str, float | None] | None = None
    iv: float | None = None
    open_interest: int | None = None
    volume: int | None = None
    delayed: bool = False
    stale: bool = False
    fx_rate: Decimal | None = None
    bond_price_basis: BondPriceBasis = BondPriceBasis.PAR_PERCENT
    bond_price: Decimal | None = None
    position: PortfolioPosition | None = None
    mark: ValuationMark | None = None
    # Pre-trade probe (no execution authority).
    pretrade_quantity: int = 0
    pretrade_side: str = "BUY"
    account_cash_minor: int = 0
    margin_facts: Any | None = None


@dataclass(frozen=True, slots=True)
class RuntimeDomainProjection:
    """Structured runtime projection — never naked domain data without status."""

    instrument_id: str
    instrument_kind: str
    asset_class: str
    provider: str
    source_time_ns: int | None
    received_time_ns: int | None
    freshness: str
    admission: str
    status: RuntimeDomainStatus
    reason: str | None
    domain_payload: dict[str, Any]
    provenance: dict[str, Any]
    execution_available: bool = False
    risk_available: bool = False
    analytics_authority: str = "NON_AUTHORITATIVE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission": self.admission,
            "analytics_authority": self.analytics_authority,
            "asset_class": self.asset_class,
            "domain_payload": dict(self.domain_payload),
            "execution_available": self.execution_available,
            "freshness": self.freshness,
            "instrument_id": self.instrument_id,
            "instrument_kind": self.instrument_kind,
            "provenance": dict(self.provenance),
            "provider": self.provider,
            "reason": self.reason,
            "received_time_ns": self.received_time_ns,
            "risk_available": self.risk_available,
            "source_time_ns": self.source_time_ns,
            "status": self.status.value,
        }


def _base_provenance(request: RuntimeProjectionRequest) -> dict[str, Any]:
    identity = request.descriptor.identity
    return {
        "asset_class": identity.asset_class.value,
        "instrument_id": identity.canonical_id,
        "instrument_kind": identity.instrument_kind.value,
        "provider": request.provider,
        "received_time_ns": request.received_time_ns,
        "source_time_ns": request.source_time_ns,
    }


def _timeliness_label(delayed: bool, stale: bool) -> str:
    if stale:
        return "STALE"
    if delayed:
        return "DELAYED"
    return "REAL_TIME"


def _status_from_lane_state(state: str) -> RuntimeDomainStatus:
    mapping = {
        "READY": RuntimeDomainStatus.AVAILABLE,
        "DEGRADED": RuntimeDomainStatus.DELAYED,
        "STALE": RuntimeDomainStatus.STALE,
        "UNAVAILABLE": RuntimeDomainStatus.UNAVAILABLE,
        "UNSUPPORTED_INSTRUMENT": RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT,
    }
    return mapping.get(state, RuntimeDomainStatus.UNAVAILABLE)


def project_runtime_domain(request: RuntimeProjectionRequest) -> RuntimeDomainProjection:
    """Project one canonical instrument into a structured runtime domain view."""
    kind = request.descriptor.identity.instrument_kind
    if kind == InstrumentKind.FUTURE_CONTRACT:
        return _project_future(request)
    if kind == InstrumentKind.FUTURE_FAMILY or kind == InstrumentKind.CONTINUOUS_SERIES:
        return _reject_unsupported_future_identity(request, kind)
    if kind == InstrumentKind.OPTION_CONTRACT:
        return _project_option(request)
    if kind == InstrumentKind.CRYPTO_PAIR:
        return _project_crypto(request)
    if kind in {InstrumentKind.BOND, InstrumentKind.SOVEREIGN_SECURITY}:
        return _project_bond(request)
    if kind in {
        InstrumentKind.COMMODITY_ECONOMIC,
        InstrumentKind.COMMODITY_SPOT,
        InstrumentKind.TRADABLE_SECURITY,
    }:
        return _project_commodity_or_proxy(request, kind)
    return RuntimeDomainProjection(
        instrument_id=request.descriptor.identity.canonical_id,
        instrument_kind=kind.value,
        asset_class=request.descriptor.identity.asset_class.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness=_timeliness_label(request.delayed, request.stale),
        admission="REFERENCE_ONLY",
        status=RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT,
        reason="UNSUPPORTED_KIND",
        domain_payload={},
        provenance=_base_provenance(request),
        execution_available=False,
        risk_available=False,
    )


def project_runtime_from_store(
    request: RuntimeProjectionRequest,
    store: ObservationalStateStore,
) -> RuntimeDomainProjection:
    """Attach observational lane facts when a canonical store is available."""
    lanes = ObservationalLaneRuntime(store)
    if request.as_of_time_ns is not None:
        lanes._as_of_time_ns = request.as_of_time_ns
    kind = request.descriptor.identity.instrument_kind
    symbol = request.descriptor.identity.canonical_id
    if kind == InstrumentKind.FUTURE_CONTRACT:
        multiplier = request.multiplier
        if multiplier is None:
            try:
                economics = economics_from_descriptor(request.descriptor)
                multiplier = float(economics.contract_multiplier)
            except EconomicsError:
                multiplier = None
        lane = lanes.build_futures_observation_payload(
            instrument_id=symbol,
            instrument_kind=kind.value,
            price=request.price,
            multiplier=multiplier,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
        )
        status = _status_from_lane_state(str(lane.get("state") or "UNAVAILABLE"))
        return RuntimeDomainProjection(
            instrument_id=symbol,
            instrument_kind=kind.value,
            asset_class=request.descriptor.identity.asset_class.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness=_timeliness_label(request.delayed, request.stale),
            admission="OBSERVATIONAL",
            status=status,
            reason=str(lane.get("reason") or ""),
            domain_payload=dict(lane),
            provenance=_base_provenance(request),
            execution_available=request.descriptor.tradability == Tradability.TRADABLE,
            risk_available=False,
        )
    if kind == InstrumentKind.OPTION_CONTRACT:
        lane = lanes.build_options_observation_payload(
            instrument_id=symbol,
            instrument_kind=kind.value,
            underlying_id=request.underlying_id,
            chain_status=request.chain_status,
            delayed=request.delayed,
            stale=request.stale,
            multiplier=request.multiplier,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
        )
        status = _status_from_lane_state(str(lane.get("state") or "UNAVAILABLE"))
        if request.chain_status == "empty":
            status = RuntimeDomainStatus.EMPTY
        return RuntimeDomainProjection(
            instrument_id=symbol,
            instrument_kind=kind.value,
            asset_class=request.descriptor.identity.asset_class.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness=_timeliness_label(request.delayed, request.stale),
            admission="OBSERVATIONAL",
            status=status,
            reason=str(lane.get("reason") or ""),
            domain_payload=_enrich_option_payload(request, lane),
            provenance=_base_provenance(request),
            execution_available=request.descriptor.tradability == Tradability.TRADABLE,
            risk_available=False,
        )
    return project_runtime_domain(request)


def build_api_projection(projection: RuntimeDomainProjection) -> dict[str, Any]:
    """Coherent multi-asset API envelope — canonical identity + structured status."""
    body = projection.to_dict()
    body["canonical_instrument_id"] = projection.instrument_id
    body["provider_provenance"] = dict(projection.provenance)
    return body


def project_portfolio_valuation(
    request: RuntimeProjectionRequest,
) -> dict[str, Any]:
    """Value a position when supplied; explicit status when mark missing/stale."""
    if request.position is None:
        return {"status": ValuationStatus.MISSING_MARK.value, "valuation": None}
    kind = request.descriptor.identity.instrument_kind
    if kind in {InstrumentKind.BOND, InstrumentKind.SOVEREIGN_SECURITY}:
        if request.bond_price is None:
            return {"status": ValuationStatus.MISSING_MARK.value, "valuation": None}
        result = value_bond_position(
            request.position,
            price=request.bond_price,
            basis=request.bond_price_basis,
            mark=request.mark,
        )
        return {"status": result.status.value, "valuation": result.to_dict()}
    marks = None
    if request.mark is not None:
        marks = {request.position.instrument_id: request.mark}
    valuation = value_position(
        request.position,
        mark=request.mark,
        context=ValuationContext(
            marks=marks,
            as_of_ns=request.as_of_time_ns,
            reference_prices=(
                {request.position.instrument_id: request.mark.price}
                if request.mark is not None
                and request.position.instrument_kind == InstrumentKind.FUTURE_CONTRACT.value
                else None
            ),
        ),
    )
    return {
        "status": valuation.valuation_status.value,
        "valuation": valuation.to_dict(),
    }


def probe_risk_admission(request: RuntimeProjectionRequest) -> dict[str, Any]:
    """Fail-closed risk probe — never grants execution authority."""
    identity = request.descriptor.identity
    economics = None
    multiplier = 1
    try:
        economics = economics_from_descriptor(request.descriptor)
        multiplier = int(economics.contract_multiplier)
    except EconomicsError:
        multiplier = int(request.multiplier or 1)
    currency = "USD"
    if economics is not None:
        currency = str(economics.settlement_currency)
    ctx = PreTradeRiskContext(
        operational_identity="probe",
        account_id="probe",
        mode="PAPER",
        instrument_id=identity.canonical_id,
        asset_class=identity.asset_class.value,
        instrument_kind=identity.instrument_kind.value,
        contract_multiplier=multiplier,
        side=request.pretrade_side,
        quantity=request.pretrade_quantity,
        portfolio_cash_minor=request.account_cash_minor,
        currency=currency,
        currency_cash_minor={currency: request.account_cash_minor},
        margin_facts=request.margin_facts,
        source_time_ns=int(request.as_of_time_ns or request.source_time_ns or 0),
    )
    result = evaluate_pretrade(ctx)
    reason = result.reason_codes[0] if result.reason_codes else None
    return {
        "allowed": result.accepted,
        "execution_authority": False,
        "reason": reason,
    }


def _reject_unsupported_future_identity(
    request: RuntimeProjectionRequest,
    kind: InstrumentKind,
) -> RuntimeDomainProjection:
    return RuntimeDomainProjection(
        instrument_id=request.descriptor.identity.canonical_id,
        instrument_kind=kind.value,
        asset_class=request.descriptor.identity.asset_class.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness="UNKNOWN",
        admission="BLOCKED",
        status=RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT,
        reason="SPECIFIC_FUTURE_CONTRACT_REQUIRED",
        domain_payload={},
        provenance=_base_provenance(request),
        execution_available=False,
        risk_available=False,
    )


def _project_future(request: RuntimeProjectionRequest) -> RuntimeDomainProjection:
    multiplier = request.multiplier
    if multiplier is None:
        try:
            economics = economics_from_descriptor(request.descriptor)
            multiplier = float(economics.contract_multiplier)
        except EconomicsError as exc:
            return RuntimeDomainProjection(
                instrument_id=request.descriptor.identity.canonical_id,
                instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
                asset_class=request.descriptor.identity.asset_class.value,
                provider=request.provider,
                source_time_ns=request.source_time_ns,
                received_time_ns=request.received_time_ns,
                freshness="UNKNOWN",
                admission="BLOCKED",
                status=RuntimeDomainStatus.UNAVAILABLE,
                reason=exc.code.value,
                domain_payload={},
                provenance=_base_provenance(request),
                execution_available=False,
                risk_available=False,
            )
    if request.price is None:
        return RuntimeDomainProjection(
            instrument_id=request.descriptor.identity.canonical_id,
            instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
            asset_class=request.descriptor.identity.asset_class.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness=_timeliness_label(request.delayed, request.stale),
            admission="OBSERVATIONAL",
            status=RuntimeDomainStatus.UNAVAILABLE,
            reason="NO_QUOTE",
            domain_payload={"multiplier": multiplier},
            provenance=_base_provenance(request),
            execution_available=request.descriptor.tradability == Tradability.TRADABLE,
            risk_available=False,
        )
    risk = probe_risk_admission(request)
    return RuntimeDomainProjection(
        instrument_id=request.descriptor.identity.canonical_id,
        instrument_kind=InstrumentKind.FUTURE_CONTRACT.value,
        asset_class=request.descriptor.identity.asset_class.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness=_timeliness_label(request.delayed, request.stale),
        admission="OBSERVATIONAL",
        status=RuntimeDomainStatus.AVAILABLE,
        reason=None,
        domain_payload={
            "multiplier": multiplier,
            "notional_per_point": multiplier,
            "price": request.price,
            "risk_probe": risk,
        },
        provenance=_base_provenance(request),
        execution_available=False,
        risk_available=bool(risk.get("allowed")),
    )


def _project_option(request: RuntimeProjectionRequest) -> RuntimeDomainProjection:
    symbol = request.descriptor.identity.canonical_id
    underlying = request.underlying_id or request.descriptor.base_asset or ""
    if underlying and symbol.upper() == underlying.upper():
        return RuntimeDomainProjection(
            instrument_id=symbol,
            instrument_kind=InstrumentKind.OPTION_CONTRACT.value,
            asset_class=request.descriptor.identity.asset_class.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness="UNKNOWN",
            admission="BLOCKED",
            status=RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT,
            reason="UNDERLYING_ONLY_AMBIGUOUS",
            domain_payload={},
            provenance=_base_provenance(request),
            execution_available=False,
            risk_available=False,
        )
    if request.chain_status == "missing":
        return RuntimeDomainProjection(
            instrument_id=symbol,
            instrument_kind=InstrumentKind.OPTION_CONTRACT.value,
            asset_class=request.descriptor.identity.asset_class.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness="UNKNOWN",
            admission="BLOCKED",
            status=RuntimeDomainStatus.UNAVAILABLE,
            reason="CHAIN_MISSING",
            domain_payload={"chain_count": None},
            provenance=_base_provenance(request),
            execution_available=False,
            risk_available=False,
        )
    if request.chain_status == "empty":
        return RuntimeDomainProjection(
            instrument_id=symbol,
            instrument_kind=InstrumentKind.OPTION_CONTRACT.value,
            asset_class=request.descriptor.identity.asset_class.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness="UNKNOWN",
            admission="OBSERVATIONAL",
            status=RuntimeDomainStatus.EMPTY,
            reason=None,
            domain_payload={"chain_count": 0},
            provenance=_base_provenance(request),
            execution_available=False,
            risk_available=False,
        )
    payload = _enrich_option_payload(request, {})
    risk = probe_risk_admission(request)
    status = RuntimeDomainStatus.DELAYED if request.delayed else RuntimeDomainStatus.AVAILABLE
    if request.stale:
        status = RuntimeDomainStatus.STALE
    return RuntimeDomainProjection(
        instrument_id=symbol,
        instrument_kind=InstrumentKind.OPTION_CONTRACT.value,
        asset_class=request.descriptor.identity.asset_class.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness=_timeliness_label(request.delayed, request.stale),
        admission="OBSERVATIONAL",
        status=status,
        reason=None,
        domain_payload={**payload, "risk_probe": risk},
        provenance=_base_provenance(request),
        execution_available=False,
        risk_available=bool(risk.get("allowed")),
    )


def _enrich_option_payload(
    request: RuntimeProjectionRequest,
    lane: Mapping[str, Any],
) -> dict[str, Any]:
    greeks = dict(request.greeks or {})
    payload: dict[str, Any] = {
        "chain_count": request.chain_count,
        "greeks": greeks,
        "iv": request.iv,
        "multiplier": request.multiplier,
        "open_interest": request.open_interest,
        "underlying_id": request.underlying_id,
        "volume": request.volume,
    }
    payload.update(lane)
    # Missing analytics remain explicit null — never fabricated zero.
    for key in ("iv", "open_interest", "volume"):
        if payload.get(key) is None:
            payload[key] = None
    for greek_key, value in greeks.items():
        if value is None:
            greeks[greek_key] = None
    return payload


def _project_crypto(request: RuntimeProjectionRequest) -> RuntimeDomainProjection:
    base = request.descriptor.base_asset or request.descriptor.base_currency
    quote = request.descriptor.quote_asset or request.descriptor.quote_currency
    if not base or not quote:
        return RuntimeDomainProjection(
            instrument_id=request.descriptor.identity.canonical_id,
            instrument_kind=InstrumentKind.CRYPTO_PAIR.value,
            asset_class=XaAssetClass.CRYPTO.value,
            provider=request.provider,
            source_time_ns=request.source_time_ns,
            received_time_ns=request.received_time_ns,
            freshness="UNKNOWN",
            admission="BLOCKED",
            status=RuntimeDomainStatus.INVALID,
            reason="INCOMPLETE_PAIR_IDENTITY",
            domain_payload={},
            provenance=_base_provenance(request),
            execution_available=False,
            risk_available=False,
        )
    # USDT/USDC are not silently USD.
    fx_note = None
    if quote in {"USDT", "USDC"} and request.fx_rate is None:
        fx_note = "QUOTE_NOT_FIAT_USD"
    payload = {
        "base_asset": base,
        "fx_rate": str(request.fx_rate) if request.fx_rate is not None else None,
        "fx_note": fx_note,
        "price": request.price,
        "quote_asset": quote,
    }
    status = RuntimeDomainStatus.AVAILABLE if request.price is not None else RuntimeDomainStatus.UNAVAILABLE
    return RuntimeDomainProjection(
        instrument_id=request.descriptor.identity.canonical_id,
        instrument_kind=InstrumentKind.CRYPTO_PAIR.value,
        asset_class=XaAssetClass.CRYPTO.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness=_timeliness_label(request.delayed, request.stale),
        admission="OBSERVATIONAL",
        status=status,
        reason=fx_note,
        domain_payload=payload,
        provenance=_base_provenance(request),
        execution_available=request.descriptor.tradability == Tradability.TRADABLE,
        risk_available=False,
    )


def _project_bond(request: RuntimeProjectionRequest) -> RuntimeDomainProjection:
    return RuntimeDomainProjection(
        instrument_id=request.descriptor.identity.canonical_id,
        instrument_kind=request.descriptor.identity.instrument_kind.value,
        asset_class=request.descriptor.identity.asset_class.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness=_timeliness_label(request.delayed, request.stale),
        admission="REFERENCE_ONLY",
        status=RuntimeDomainStatus.AVAILABLE,
        reason="EXECUTION_BLOCKED_REFERENCE_ONLY",
        domain_payload={
            "coupon": request.descriptor.coupon,
            "cusip": request.descriptor.identity.identity_key.get("security_id"),
            "isin": request.descriptor.identity.identity_key.get("isin"),
            "issuer": request.descriptor.issuer,
            "maturity_date": request.descriptor.maturity_date,
            "par_value": request.descriptor.par_value,
            "price_basis": request.bond_price_basis.value,
            "security_type": request.descriptor.security_type,
        },
        provenance=_base_provenance(request),
        execution_available=False,
        risk_available=False,
    )


def _project_commodity_or_proxy(
    request: RuntimeProjectionRequest,
    kind: InstrumentKind,
) -> RuntimeDomainProjection:
    tradable = request.descriptor.tradability == Tradability.TRADABLE
    status = RuntimeDomainStatus.AVAILABLE
    if kind == InstrumentKind.COMMODITY_ECONOMIC:
        admission = "REFERENCE_ONLY"
        execution_available = False
    elif kind == InstrumentKind.COMMODITY_SPOT:
        admission = "REFERENCE_ONLY"
        execution_available = False
    else:
        admission = "TRADABLE_PROXY" if tradable else "REFERENCE_ONLY"
        execution_available = tradable
    return RuntimeDomainProjection(
        instrument_id=request.descriptor.identity.canonical_id,
        instrument_kind=kind.value,
        asset_class=request.descriptor.identity.asset_class.value,
        provider=request.provider,
        source_time_ns=request.source_time_ns,
        received_time_ns=request.received_time_ns,
        freshness=_timeliness_label(request.delayed, request.stale),
        admission=admission,
        status=status,
        reason=None,
        domain_payload={
            "commodity_code": request.descriptor.commodity_code,
            "display_name": request.descriptor.display_name,
            "price": request.price,
        },
        provenance=_base_provenance(request),
        execution_available=execution_available,
        risk_available=False,
    )


__all__ = [
    "RuntimeDomainProjection",
    "RuntimeProjectionRequest",
    "build_api_projection",
    "probe_risk_admission",
    "project_portfolio_valuation",
    "project_runtime_domain",
    "project_runtime_from_store",
]
