"""Typed cross-asset pre-trade risk hook boundary (G3 / BL-0209).

One typed input/output contract for pre-trade risk evaluation that consumes
canonical G1 instrument identity and G2 portfolio/cash state instead of
inventing parallel ledgers. It is a *hook boundary*, not a second risk
engine: per-asset checks reuse the shared reason-code vocabulary from
``risk.financial`` and the canonical equity limits in ``risk.decision``, and
it deliberately fails closed wherever a safe margin/resource model does not
exist (futures notional is not settlement cash; uncovered options are not
silently margined) — G3 Invariant J, §64–66.

``evaluate_pretrade`` dispatches on canonical asset class / instrument kind:

- Equity / ETF / crypto spot: cash-funded buy enforces
  ``required_cash <= available_cash`` where available already subtracts
  working-order obligations; sell-side enforces owned quantity minus already
  reserved sell quantity.
- Long option: contracts x premium x multiplier + no invented margin for
  uncovered short options.
- Future: explicit ``UNSUPPORTED_RISK_MODEL`` (never equity arithmetic).
- Bond / reference / synthetic / continuous-series identities: rejected as
  non-executable before any financial math.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..portfolio.canonical import QuantityUnit
from .financial import (
    INSUFFICIENT_CASH,
    INSUFFICIENT_POSITION,
    INSUFFICIENT_SETTLEMENT_CURRENCY,
    REQUIRED_PRICE_MISSING,
    UNSUPPORTED_RISK_MODEL,
)
from .margin_facts import (
    INSUFFICIENT_MARGIN_CAPACITY,
    MARGIN_MISSING,
    MarginRequirementFacts,
    admit_margin_facts,
    required_margin_minor,
)

NON_EXECUTABLE_INSTRUMENT = "NON_EXECUTABLE_INSTRUMENT"

NON_EXECUTABLE_KINDS: frozenset[str] = frozenset(
    {
        "BOND",
        "COMMODITY_ECONOMIC",
        "COMMODITY_SPOT",
        "CONTINUOUS_SERIES",
        "CURRENCY_UNIT",
        "FX_PAIR",
        "FUTURE_FAMILY",
        "INDEX_BENCHMARK",
        "SOVEREIGN_SECURITY",
    }
)


@dataclass(frozen=True, slots=True)
class PreTradeRiskContext:
    """Canonical inputs a pre-trade risk hook may consume (G3 §64)."""

    operational_identity: str
    account_id: str
    mode: str
    instrument_id: str
    asset_class: str
    instrument_kind: str
    symbol: str = ""
    contract_multiplier: int = 1
    side: str = "BUY"
    quantity: int = 0
    quantity_unit: str = QuantityUnit.SHARES.value
    order_type: str = "MARKET"
    limit_price_minor: int | None = None
    reference_price_minor: int | None = None
    currency: str = "USD"
    account_currency: str = "USD"
    portfolio_cash_minor: int = 0
    position_quantity: int = 0
    working_obligations_minor: int = 0
    # G4 Phase 6: per-currency cash buckets (canonical portfolio). When
    # supplied, availability resolves the order's settlement-currency bucket
    # and that currency's working obligations; a missing bucket fails closed
    # (INSUFFICIENT_SETTLEMENT_CURRENCY) — never a silent 1:1 conversion.
    currency_cash_minor: dict[str, int] | None = None
    working_obligations_by_currency: dict[str, int] | None = None
    risk_policy_revision: str = ""
    source_time_ns: int | None = None
    margin_facts: MarginRequirementFacts | None = None
    margin_facts_revision: str = ""
    price_scale: int = 100


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Typed pre-trade risk decision output (G3 §64)."""

    accepted: bool
    decision: str
    reason_codes: list[str] = field(default_factory=list)
    required_cash_minor: int | None = None
    available_cash_minor: int | None = None
    estimated_position_delta: int = 0
    estimated_notional_minor: int | None = None
    unsupported_risk_model: bool = False
    required_settlement_currency: str = "USD"
    source_time_ns: int | None = None


def _reject(
    *,
    context: PreTradeRiskContext,
    reason: str,
    decision: str = "REJECT",
    unsupported_risk_model: bool = False,
) -> RiskDecision:
    if context.currency_cash_minor is not None:
        bucket = context.currency_cash_minor.get(str(context.currency).upper())
        if bucket is not None:
            obligations = (context.working_obligations_by_currency or {}).get(str(context.currency).upper(), 0)
            available = max(0, int(bucket) - int(obligations))
        else:
            available = 0
    else:
        available = max(0, context.portfolio_cash_minor - context.working_obligations_minor)
    return RiskDecision(
        accepted=False,
        decision=decision,
        reason_codes=[reason],
        required_cash_minor=None,
        available_cash_minor=available,
        estimated_position_delta=(
            context.quantity if context.side.upper() == "BUY" else -context.quantity
        ),
        unsupported_risk_model=unsupported_risk_model,
        required_settlement_currency=context.currency,
        source_time_ns=context.source_time_ns,
    )


def evaluate_pretrade(context: PreTradeRiskContext) -> RiskDecision:
    """Evaluate one order intent against canonical portfolio/risk state.

    Pure and deterministic: given the same context, returns the same
    decision. Never invents margin (G3 Invariant J) and never consumes
    balances other than those passed in the context (G3 §22).
    """
    side = str(context.side).upper()
    kind = str(context.instrument_kind).upper()
    asset_class = str(context.asset_class).upper()

    if kind in NON_EXECUTABLE_KINDS or asset_class == "BOND":
        return _reject(context=context, reason=NON_EXECUTABLE_INSTRUMENT)

    if context.currency_cash_minor is not None:
        # G4 Phase 6: per-currency availability. The settlement-currency
        # bucket must exist; a missing bucket fails closed with the funding
        # reason (rule 9: unknown FX must NOT silently convert 1:1).
        order_currency = str(context.currency).upper()
        bucket = context.currency_cash_minor.get(order_currency)
        if bucket is None:
            return _reject(context=context, reason=INSUFFICIENT_SETTLEMENT_CURRENCY)
        currency_obligations = (context.working_obligations_by_currency or {}).get(order_currency, 0)
        available_cash = max(0, int(bucket) - int(currency_obligations))
    else:
        if str(context.currency).upper() != str(context.account_currency).upper():
            return _reject(context=context, reason=INSUFFICIENT_SETTLEMENT_CURRENCY)
        available_cash = max(0, context.portfolio_cash_minor - context.working_obligations_minor)

    if context.quantity <= 0:
        return _reject(context=context, reason="RISK_INVALID_INTENT")

    if kind == "FUTURE_CONTRACT":
        # Futures never use equity notional as settlement cash (G3 §30).
        admission = admit_margin_facts(
            context.margin_facts,
            instrument_id=context.instrument_id,
            order_currency=context.currency,
            observation_time_ns=int(context.source_time_ns or 0),
        )
        if not admission.admitted:
            return _reject(
                context=context,
                reason=admission.code,
                unsupported_risk_model=admission.code in {MARGIN_MISSING, UNSUPPORTED_RISK_MODEL},
            )
        facts = admission.facts
        assert facts is not None
        if side == "SELL" and context.position_quantity >= context.quantity:
            return RiskDecision(
                accepted=True,
                decision="APPROVE",
                reason_codes=[],
                available_cash_minor=available_cash,
                estimated_position_delta=-context.quantity,
                required_settlement_currency=context.currency,
                source_time_ns=context.source_time_ns,
            )
        required_margin = required_margin_minor(
            facts=facts,
            contracts=context.quantity,
            scale=context.price_scale,
        )
        if required_margin > available_cash:
            return RiskDecision(
                accepted=False,
                decision="REJECT",
                reason_codes=[INSUFFICIENT_MARGIN_CAPACITY],
                required_cash_minor=required_margin,
                available_cash_minor=available_cash,
                estimated_position_delta=(
                    context.quantity if side == "BUY" else -context.quantity
                ),
                required_settlement_currency=facts.currency,
                source_time_ns=context.source_time_ns,
            )
        return RiskDecision(
            accepted=True,
            decision="APPROVE",
            reason_codes=[],
            required_cash_minor=required_margin,
            available_cash_minor=available_cash,
            estimated_position_delta=(
                context.quantity if side.upper() == "BUY" else -context.quantity
            ),
            required_settlement_currency=facts.currency,
            source_time_ns=context.source_time_ns,
        )

    if kind == "OPTION_CONTRACT":
        if side == "SELL":
            owned = max(0, context.position_quantity)
            if context.quantity > owned:
                return _reject(
                    context=context,
                    reason=UNSUPPORTED_RISK_MODEL,
                    unsupported_risk_model=True,
                )
            return RiskDecision(
                accepted=True,
                decision="APPROVE",
                reason_codes=[],
                available_cash_minor=available_cash,
                estimated_position_delta=-context.quantity,
                required_settlement_currency=context.currency,
                source_time_ns=context.source_time_ns,
            )
        price_minor = _effective_price_minor(context)
        if price_minor is None:
            return _reject(context=context, reason=REQUIRED_PRICE_MISSING)
        required = context.quantity * price_minor * context.contract_multiplier
        return _buy_or_sell_decision(context, required, available_cash)

    if kind in {"TRADABLE_SECURITY", "ETF_FUND", "CRYPTO_PAIR"}:
        price_minor = _effective_price_minor(context)
        if price_minor is None:
            return _reject(context=context, reason=REQUIRED_PRICE_MISSING)
        required = context.quantity * price_minor * context.contract_multiplier
        if side == "SELL":
            available_to_sell = max(0, context.position_quantity)
            if context.quantity > available_to_sell:
                return _reject(context=context, reason=INSUFFICIENT_POSITION)
            return RiskDecision(
                accepted=True,
                decision="APPROVE",
                reason_codes=[],
                required_cash_minor=required,
                available_cash_minor=available_cash,
                estimated_position_delta=-context.quantity,
                estimated_notional_minor=required,
                required_settlement_currency=context.currency,
                source_time_ns=context.source_time_ns,
            )
        return _buy_or_sell_decision(context, required, available_cash)

    return _reject(
        context=context,
        reason=UNSUPPORTED_RISK_MODEL,
        unsupported_risk_model=True,
    )


def _buy_or_sell_decision(
    context: PreTradeRiskContext,
    required_cash: int,
    available_cash: int,
) -> RiskDecision:
    notional = required_cash
    if required_cash > available_cash:
        return RiskDecision(
            accepted=False,
            decision="REJECT",
            reason_codes=[INSUFFICIENT_CASH],
            required_cash_minor=required_cash,
            available_cash_minor=available_cash,
            estimated_position_delta=(
                context.quantity if context.side.upper() == "BUY" else -context.quantity
            ),
            estimated_notional_minor=notional,
            required_settlement_currency=context.currency,
            source_time_ns=context.source_time_ns,
        )
    return RiskDecision(
        accepted=True,
        decision="APPROVE",
        reason_codes=[],
        required_cash_minor=required_cash,
        available_cash_minor=available_cash,
        estimated_position_delta=(
            context.quantity if context.side.upper() == "BUY" else -context.quantity
        ),
        estimated_notional_minor=notional,
        required_settlement_currency=context.currency,
        source_time_ns=context.source_time_ns,
    )


def _effective_price_minor(context: PreTradeRiskContext) -> int | None:
    if str(context.order_type).upper() == "LIMIT" and context.limit_price_minor is not None:
        return int(context.limit_price_minor)
    if context.reference_price_minor is not None:
        return int(context.reference_price_minor)
    return None


__all__ = [
    "NON_EXECUTABLE_INSTRUMENT",
    "PreTradeRiskContext",
    "RiskDecision",
    "evaluate_pretrade",
]