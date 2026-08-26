"""Deterministic proposal and pre-trade risk engine (BUILD 22)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractKind, ContractReference, OpportunitySide, QualityState
from ..contracts.forecast import ForecastV1
from ..contracts.opportunity import OpportunityV1
from ..contracts.trade_proposal import TradeProposalV1
from .errors import DirectForecastTradeForbidden, LiveExecutionForbidden, OpportunityGateError
from .exposure import (
    compute_exposure,
    projected_positions_after_trade,
    snapshot_exposure,
    symbol_position_quantity,
)
from .identity import derive_risk_decision_id, derive_trade_proposal_id
from .sizing import (
    reference_price_for_side,
    size_fixed_fraction_nav_with_caps,
    validate_position_interaction,
)
from .types import (
    ExecutionPolicyV1,
    ExposureSnapshot,
    MarketQuoteV1,
    PaperExecutionResult,
    PaperPortfolioSnapshotV1,
    RiskDecisionKind,
    RiskDecisionV1,
    RiskReasonCode,
)


_GATE_REASON_MAP = {
    "OPPORTUNITY_EXPIRED": RiskReasonCode.OPPORTUNITY_EXPIRED,
    "OPPORTUNITY_MODE_NOT_ALLOWED": RiskReasonCode.OPPORTUNITY_MODE_NOT_ALLOWED,
    "OPPORTUNITY_SIDE_INVALID": RiskReasonCode.OPPORTUNITY_SIDE_INVALID,
    "QUALITY_NOT_ELIGIBLE": RiskReasonCode.QUALITY_NOT_ELIGIBLE,
    "PORTFOLIO_STATE_STALE": RiskReasonCode.PORTFOLIO_STATE_STALE,
    "PORTFOLIO_SNAPSHOT_FUTURE": RiskReasonCode.PORTFOLIO_INVALID,
}


def _gate_reason_code(message: str) -> RiskReasonCode:
    return _GATE_REASON_MAP.get(message, RiskReasonCode.FAIL_CLOSED)


def opportunity_side_to_order_side(side: OpportunitySide) -> str:
    if side == OpportunitySide.LONG:
        return "BUY"
    if side == OpportunitySide.SHORT:
        return "SELL"
    raise OpportunityGateError("OPPORTUNITY_SIDE_INVALID")


def _validate_opportunity_gate(
    opportunity: OpportunityV1,
    *,
    decision_time_ns: int,
    scenario_id: str | None,
) -> None:
    if opportunity.created_at_ns > decision_time_ns:
        raise OpportunityGateError("OPPORTUNITY_TIME_INVALID")
    if opportunity.valid_until_ns is not None and decision_time_ns >= opportunity.valid_until_ns:
        raise OpportunityGateError("OPPORTUNITY_EXPIRED")
    if opportunity.side is None or opportunity.side == OpportunitySide.NEUTRAL:
        raise OpportunityGateError("OPPORTUNITY_SIDE_INVALID")
    if opportunity.quality.state in {QualityState.INVALID}:
        raise OpportunityGateError("QUALITY_NOT_ELIGIBLE")
    meta_scenario = opportunity.metadata.get("scenario_id")
    if scenario_id is not None and meta_scenario is not None and meta_scenario != scenario_id:
        raise OpportunityGateError("OPPORTUNITY_MODE_NOT_ALLOWED")


def _validate_portfolio_snapshot(
    portfolio: PaperPortfolioSnapshotV1,
    *,
    policy: ExecutionPolicyV1,
    decision_time_ns: int,
) -> None:
    if portfolio.captured_at_ns > decision_time_ns:
        raise OpportunityGateError("PORTFOLIO_SNAPSHOT_FUTURE")
    if policy.max_portfolio_snapshot_age_ns is not None:
        age = decision_time_ns - portfolio.captured_at_ns
        if age > policy.max_portfolio_snapshot_age_ns:
            raise OpportunityGateError("PORTFOLIO_STATE_STALE")


def _daily_loss_blocks_trade(
    portfolio: PaperPortfolioSnapshotV1,
    policy: ExecutionPolicyV1,
    *,
    side: str,
    instrument_id: str,
) -> bool:
    if policy.daily_loss_limit_fraction is None:
        return False
    if portfolio.start_of_day_equity_minor is None or portfolio.start_of_day_equity_minor <= 0:
        return False
    loss_fraction = (
        portfolio.start_of_day_equity_minor - portfolio.equity_minor
    ) / portfolio.start_of_day_equity_minor
    if loss_fraction < policy.daily_loss_limit_fraction:
        return False
    # block risk-increasing trades only
    current_qty = symbol_position_quantity(portfolio.positions, instrument_id=instrument_id)
    if side == "BUY" and current_qty >= 0:
        return True
    if side == "SELL" and current_qty <= 0:
        return True
    return False


class PreTradeRiskEngine:
    """Deterministic BUILD 22 risk evaluation."""

    def build_proposal(
        self,
        *,
        opportunity: OpportunityV1,
        policy: ExecutionPolicyV1,
        portfolio: PaperPortfolioSnapshotV1,
        quote: MarketQuoteV1,
        proposal_time_ns: int,
        instrument_id: str,
        symbol: str,
        scenario_id: str | None = None,
    ) -> TradeProposalV1:
        if isinstance(opportunity, ForecastV1):
            raise DirectForecastTradeForbidden("FORECAST_TO_TRADE_FORBIDDEN")
        if policy.mode.value != "PAPER":
            raise LiveExecutionForbidden("LIVE_POLICY_REJECTED")

        _validate_opportunity_gate(opportunity, decision_time_ns=proposal_time_ns, scenario_id=scenario_id)
        _validate_portfolio_snapshot(portfolio, policy=policy, decision_time_ns=proposal_time_ns)
        if quote.available_time_ns > proposal_time_ns:
            raise OpportunityGateError("QUOTE_NOT_PIT_SAFE")

        side = opportunity_side_to_order_side(opportunity.side)
        reference_price_minor = reference_price_for_side(
            bid_minor=quote.bid_minor,
            ask_minor=quote.ask_minor,
            side=side,
        )
        sizing = size_fixed_fraction_nav_with_caps(
            policy=policy,
            portfolio=portfolio,
            instrument_id=instrument_id,
            symbol=symbol,
            side=side,
            reference_price_minor=reference_price_minor,
        )
        permitted_qty, _ = validate_position_interaction(
            policy=policy,
            portfolio=portfolio,
            instrument_id=instrument_id,
            side=side,
            quantity=sizing.quantity,
        )
        quantity = min(sizing.quantity, permitted_qty)
        notional = quantity * reference_price_minor
        expires_at_ns = opportunity.valid_until_ns or proposal_time_ns
        proposal_id = derive_trade_proposal_id(
            opportunity_id=opportunity.opportunity_id,
            execution_policy_id=policy.execution_policy_id,
            instrument_id=instrument_id,
            side=side,
            requested_quantity=quantity,
            reference_price_minor=reference_price_minor,
            proposal_time_ns=proposal_time_ns,
        )
        return TradeProposalV1(
            proposal_id=proposal_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            opportunity_id=opportunity.opportunity_id,
            execution_policy_id=policy.execution_policy_id,
            instrument_id=instrument_id,
            side=side,
            requested_quantity=quantity,
            requested_notional_minor=notional,
            reference_price_minor=reference_price_minor,
            proposal_time_ns=proposal_time_ns,
            expires_at_ns=expires_at_ns,
            execution_mode="PAPER",
            opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id=opportunity.opportunity_id),
            lineage_refs=(
                ContractReference(kind="execution_policy", id=policy.execution_policy_id),
                ContractReference(kind="portfolio_snapshot", id=portfolio.snapshot_id),
            ),
            metadata={
                "symbol": symbol,
                "sizing_capped_by": list(sizing.capped_by),
            },
        )

    def assess(
        self,
        *,
        proposal: TradeProposalV1,
        opportunity: OpportunityV1,
        policy: ExecutionPolicyV1,
        portfolio: PaperPortfolioSnapshotV1,
        decision_time_ns: int,
        symbol: str,
        submitted_opportunity_ids: frozenset[str] = frozenset(),
    ) -> RiskDecisionV1:
        reason_codes: list[RiskReasonCode] = []
        approved_qty = proposal.requested_quantity
        decision = RiskDecisionKind.APPROVE

        try:
            _validate_opportunity_gate(opportunity, decision_time_ns=decision_time_ns, scenario_id=portfolio.scenario_id)
            _validate_portfolio_snapshot(portfolio, policy=policy, decision_time_ns=decision_time_ns)
        except OpportunityGateError as exc:
            return self._finalize(
                proposal=proposal,
                policy=policy,
                portfolio=portfolio,
                decision_time_ns=decision_time_ns,
                approved_quantity=0,
                decision=RiskDecisionKind.FAIL_CLOSED,
                reason_codes=[_gate_reason_code(str(exc))],
            )

        if opportunity.opportunity_id in submitted_opportunity_ids:
            return self._finalize(
                proposal=proposal,
                policy=policy,
                portfolio=portfolio,
                decision_time_ns=decision_time_ns,
                approved_quantity=0,
                decision=RiskDecisionKind.REJECT,
                reason_codes=[RiskReasonCode.DUPLICATE_OPPORTUNITY],
            )

        open_symbol = sum(1 for order in portfolio.open_orders if order.instrument_id == proposal.instrument_id)
        if open_symbol >= policy.max_open_orders_per_symbol:
            reason_codes.append(RiskReasonCode.MAX_OPEN_ORDERS)
            decision = RiskDecisionKind.REJECT
            approved_qty = 0
        if len(portfolio.open_orders) >= policy.max_total_open_orders:
            reason_codes.append(RiskReasonCode.MAX_OPEN_ORDERS)
            decision = RiskDecisionKind.REJECT
            approved_qty = 0

        if _daily_loss_blocks_trade(portfolio, policy, side=proposal.side, instrument_id=proposal.instrument_id):
            return self._finalize(
                proposal=proposal,
                policy=policy,
                portfolio=portfolio,
                decision_time_ns=decision_time_ns,
                approved_quantity=0,
                decision=RiskDecisionKind.REJECT,
                reason_codes=[RiskReasonCode.DAILY_LOSS_LIMIT],
            )

        if proposal.requested_quantity < policy.minimum_quantity:
            return self._finalize(
                proposal=proposal,
                policy=policy,
                portfolio=portfolio,
                decision_time_ns=decision_time_ns,
                approved_quantity=0,
                decision=RiskDecisionKind.REJECT,
                reason_codes=[RiskReasonCode.REQUESTED_SIZE_TOO_SMALL],
            )
        if proposal.requested_notional_minor < policy.minimum_trade_notional_minor:
            return self._finalize(
                proposal=proposal,
                policy=policy,
                portfolio=portfolio,
                decision_time_ns=decision_time_ns,
                approved_quantity=0,
                decision=RiskDecisionKind.REJECT,
                reason_codes=[RiskReasonCode.REQUESTED_SIZE_TOO_SMALL],
            )

        permitted_qty, interaction_reasons = validate_position_interaction(
            policy=policy,
            portfolio=portfolio,
            instrument_id=proposal.instrument_id,
            side=proposal.side,
            quantity=proposal.requested_quantity,
        )
        if interaction_reasons:
            mapped = []
            for code in interaction_reasons:
                if code == "SHORT_NOT_ALLOWED":
                    mapped.append(RiskReasonCode.SHORT_NOT_ALLOWED)
                elif code == "POSITION_REVERSAL_NOT_ALLOWED":
                    mapped.append(RiskReasonCode.POSITION_REVERSAL_NOT_ALLOWED)
            if permitted_qty <= 0:
                return self._finalize(
                    proposal=proposal,
                    policy=policy,
                    portfolio=portfolio,
                    decision_time_ns=decision_time_ns,
                    approved_quantity=0,
                    decision=RiskDecisionKind.REJECT,
                    reason_codes=mapped or [RiskReasonCode.RISK_REJECTED],
                )
            if permitted_qty < approved_qty:
                approved_qty = permitted_qty
                decision = RiskDecisionKind.REDUCE
                reason_codes.extend(mapped)
                reason_codes.append(RiskReasonCode.SIZE_REDUCED)

        pre = snapshot_exposure(portfolio)
        projected = projected_positions_after_trade(
            portfolio.positions,
            instrument_id=proposal.instrument_id,
            symbol=symbol,
            side=proposal.side,
            quantity=approved_qty,
            reference_price_minor=proposal.reference_price_minor,
        )
        post = compute_exposure(projected)
        max_gross = int(portfolio.equity_minor * policy.max_gross_exposure_fraction)
        max_net = int(portfolio.equity_minor * policy.max_net_exposure_fraction)
        if post.gross_exposure_minor > max_gross:
            if policy.allow_size_reduction:
                excess = post.gross_exposure_minor - max_gross
                reduce_qty = min(approved_qty, excess // proposal.reference_price_minor + 1)
                approved_qty = max(0, approved_qty - reduce_qty)
                decision = RiskDecisionKind.REDUCE if approved_qty > 0 else RiskDecisionKind.REJECT
                reason_codes.append(RiskReasonCode.MAX_GROSS_EXPOSURE)
                reason_codes.append(RiskReasonCode.SIZE_REDUCED)
            else:
                decision = RiskDecisionKind.REJECT
                approved_qty = 0
                reason_codes.append(RiskReasonCode.MAX_GROSS_EXPOSURE)
        if approved_qty > 0 and abs(post.net_exposure_minor) > max_net:
            if policy.allow_size_reduction:
                approved_qty = max(0, approved_qty // 2)
                decision = RiskDecisionKind.REDUCE if approved_qty > 0 else RiskDecisionKind.REJECT
                reason_codes.append(RiskReasonCode.MAX_NET_EXPOSURE)
                reason_codes.append(RiskReasonCode.SIZE_REDUCED)
            else:
                decision = RiskDecisionKind.REJECT
                approved_qty = 0
                reason_codes.append(RiskReasonCode.MAX_NET_EXPOSURE)

        if proposal.side == "BUY":
            required_cash = approved_qty * proposal.reference_price_minor
            available = portfolio.cash_minor - portfolio.reserved_cash_minor
            if required_cash > available:
                if policy.allow_size_reduction and proposal.reference_price_minor > 0:
                    approved_qty = available // proposal.reference_price_minor
                    decision = RiskDecisionKind.REDUCE if approved_qty >= policy.minimum_quantity else RiskDecisionKind.REJECT
                    if approved_qty < policy.minimum_quantity:
                        approved_qty = 0
                    reason_codes.append(RiskReasonCode.INSUFFICIENT_PAPER_CASH)
                    reason_codes.append(RiskReasonCode.SIZE_REDUCED)
                else:
                    decision = RiskDecisionKind.REJECT
                    approved_qty = 0
                    reason_codes.append(RiskReasonCode.INSUFFICIENT_PAPER_CASH)

        if decision == RiskDecisionKind.APPROVE:
            reason_codes.append(RiskReasonCode.RISK_APPROVED)
        elif decision == RiskDecisionKind.REJECT and RiskReasonCode.RISK_REJECTED not in reason_codes:
            reason_codes.append(RiskReasonCode.RISK_REJECTED)

        projected = projected_positions_after_trade(
            portfolio.positions,
            instrument_id=proposal.instrument_id,
            symbol=symbol,
            side=proposal.side,
            quantity=approved_qty,
            reference_price_minor=proposal.reference_price_minor,
        )
        post = compute_exposure(projected)
        return self._finalize(
            proposal=proposal,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=decision_time_ns,
            approved_quantity=approved_qty,
            decision=decision,
            reason_codes=reason_codes,
            pre_trade=pre,
            post_trade=post,
        )

    def _finalize(
        self,
        *,
        proposal: TradeProposalV1,
        policy: ExecutionPolicyV1,
        portfolio: PaperPortfolioSnapshotV1,
        decision_time_ns: int,
        approved_quantity: int,
        decision: RiskDecisionKind,
        reason_codes: list[RiskReasonCode],
        pre_trade: ExposureSnapshot | None = None,
        post_trade: ExposureSnapshot | None = None,
    ) -> RiskDecisionV1:
        risk_decision_id = derive_risk_decision_id(
            trade_proposal=proposal,
            execution_policy_id=policy.execution_policy_id,
            portfolio_snapshot_id=portfolio.snapshot_id,
            decision_time_ns=decision_time_ns,
        )
        approved_notional = approved_quantity * proposal.reference_price_minor
        unique_codes = tuple(dict.fromkeys(reason_codes))
        return RiskDecisionV1(
            risk_decision_id=risk_decision_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            trade_proposal_id=proposal.proposal_id,
            opportunity_id=proposal.opportunity_id,
            execution_policy_id=policy.execution_policy_id,
            portfolio_snapshot_id=portfolio.snapshot_id,
            decision_time_ns=decision_time_ns,
            requested_quantity=proposal.requested_quantity,
            requested_notional_minor=proposal.requested_notional_minor,
            approved_quantity=approved_quantity,
            approved_notional_minor=approved_notional,
            decision=decision,
            reason_codes=unique_codes,
            pre_trade_exposure=pre_trade,
            post_trade_exposure=post_trade,
            lineage_refs=proposal.lineage_refs,
            metadata={"requested_preserved": True},
        )


class PaperExecutionOrchestrator:
    """End-to-end BUILD 22 paper path: opportunity → proposal → risk → paper ledger."""

    def __init__(self, *, risk_engine: PreTradeRiskEngine | None = None) -> None:
        self._risk = risk_engine or PreTradeRiskEngine()

    def execute_paper(
        self,
        *,
        opportunity: OpportunityV1,
        policy: ExecutionPolicyV1,
        portfolio: PaperPortfolioSnapshotV1,
        quote: MarketQuoteV1,
        ledger: Any,
        bars: list[dict[str, Any]],
        decision_time_ns: int,
        instrument_id: str,
        symbol: str,
        execution_authority: str,
        submitted_opportunity_ids: frozenset[str] = frozenset(),
    ) -> PaperExecutionResult:
        from ...operating_modes import PAPER_EXECUTION_AUTHORITIES

        if execution_authority not in PAPER_EXECUTION_AUTHORITIES:
            raise LiveExecutionForbidden("EXECUTION_AUTHORITY_LIVE")
        if execution_authority == "AUTHORIZED" and ledger.execution_mode == "LIVE":
            raise LiveExecutionForbidden("EXECUTION_MODE_LIVE")

        proposal = self._risk.build_proposal(
            opportunity=opportunity,
            policy=policy,
            portfolio=portfolio,
            quote=quote,
            proposal_time_ns=decision_time_ns,
            instrument_id=instrument_id,
            symbol=symbol,
            scenario_id=portfolio.scenario_id,
        )
        risk = self._risk.assess(
            proposal=proposal,
            opportunity=opportunity,
            policy=policy,
            portfolio=portfolio,
            decision_time_ns=decision_time_ns,
            symbol=symbol,
            submitted_opportunity_ids=submitted_opportunity_ids,
        )
        if risk.decision not in {RiskDecisionKind.APPROVE, RiskDecisionKind.REDUCE} or risk.approved_quantity <= 0:
            return PaperExecutionResult(proposal=proposal, risk_decision=risk, paper_submit=None)

        from ...paper.execution import submit_interactive_order
        from .identity import derive_paper_order_idempotency_key

        idempotency_key = derive_paper_order_idempotency_key(risk.risk_decision_id)
        submit = submit_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol=symbol,
            instrument_id=instrument_id,
            side=proposal.side,
            quantity=risk.approved_quantity,
            observation_time=decision_time_ns,
            client_order_id=risk.risk_decision_id,
            idempotency_key=idempotency_key,
            correlation_id=opportunity.opportunity_id,
        )
        return PaperExecutionResult(proposal=proposal, risk_decision=risk, paper_submit=submit)


__all__ = [
    "PaperExecutionOrchestrator",
    "PreTradeRiskEngine",
    "opportunity_side_to_order_side",
]
