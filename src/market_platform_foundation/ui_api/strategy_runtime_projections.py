"""Read-only projections for the strategy-to-Paper profitability lineage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..intelligence.contracts.forecast import forecast_v1_to_dict
from ..intelligence.contracts.opportunity import opportunity_v1_to_dict
from ..intelligence.contracts.outcome import outcome_v1_to_dict
from ..intelligence.contracts.prediction_ledger import prediction_ledger_entry_v1_to_dict
from ..intelligence.contracts.strategy_match import strategy_match_to_dict
from ..intelligence.execution.serialization import (
    order_ready_v1_to_dict,
    paper_portfolio_snapshot_v1_to_dict,
    risk_decision_v1_to_dict,
    trade_proposal_v1_to_dict,
)
from ..intelligence.opportunity.allocation_persistence import allocation_decision_v1_to_dict
from ..intelligence.opportunity.economic_assessment import economic_assessment_v1_to_dict
from ..portfolio.attribution import attribution_v1_to_dict


SCHEMA_VERSION = "ui/paper-strategy-profitability/1.0.0"
TRACE_SCHEMA_VERSION = "ui/paper-strategy-trace/1.0.0"


def build_strategy_decision_trace_payload(
    *,
    repository: Any,
    ledger: Any,
    account_id: str,
    mode: str = "PAPER",
    allocation_decision_id: str,
    as_of_ns: int | None = None,
) -> dict[str, Any]:
    """Build the immutable strategy-to-Paper business lifecycle projection."""
    normalized_mode = _normalize_mode(mode)
    allocation = repository.get_allocation_decision(allocation_decision_id)
    if allocation is None:
        raise ValueError("ALLOCATION_DECISION_NOT_FOUND")
    if allocation.account_id != account_id or allocation.mode != normalized_mode:
        raise ValueError("STRATEGY_TRACE_SCOPE_MISMATCH")
    if as_of_ns is not None and allocation.decision_time_ns > as_of_ns:
        raise ValueError("ALLOCATION_AFTER_POINT_IN_TIME")

    active_as_of = as_of_ns if as_of_ns is not None else _latest_observation_ns((allocation,), ledger)
    match = (
        repository.get_strategy_match(allocation.strategy_match_ref.id)
        if allocation.strategy_match_ref is not None
        else None
    )
    forecast = _first_forecast(repository, allocation)
    opportunity = repository.get_opportunity(allocation.opportunity_ref.id)
    economics = repository.get_economic_assessment(allocation.economic_assessment_ref.id)
    order_ready_rows = tuple(
        item
        for item in repository.get_order_ready_by_allocation(allocation.allocation_decision_id)
        if item.decision_time_ns <= active_as_of
    )
    order_ready = max(
        order_ready_rows,
        key=lambda item: (item.decision_time_ns, item.order_ready_id),
        default=None,
    )
    orders = tuple(
        order
        for order in ledger.project_orders()
        if _contains_reference(order, "allocation_decision", allocation.allocation_decision_id)
        or _contains_reference(order, "allocation", allocation.allocation_decision_id)
    )
    order_ids = {str(order.get("order_id")) for order in orders}
    fills = tuple(
        fill
        for fill in ledger.project_fills()
        if str(fill.get("order_id")) in order_ids
        and int(fill.get("fill_time", fill.get("fill_time_ns", 0))) <= active_as_of
    )
    proposal, risk = _resolve_order_records(repository, orders)
    if order_ready is not None:
        if proposal is None:
            proposal = repository.get_trade_proposal(order_ready.trade_proposal_id)
        if risk is None:
            risk = repository.get_risk_decision(order_ready.risk_decision_id)

    position_events = tuple(
        event
        for event in getattr(ledger, "events", ())
        if event.get("event_type") == "PositionChanged"
        and isinstance(event.get("payload"), Mapping)
        and str(event["payload"].get("fill_id")) in {str(fill.get("fill_id")) for fill in fills}
        and int(event.get("available_time", event.get("event_time", 0))) <= active_as_of
    )
    attribution = _latest_complete_attribution(
        repository,
        allocation.allocation_decision_id,
        account_id=account_id,
        mode=normalized_mode,
        as_of_ns=active_as_of,
    )
    prediction_state, prediction_entry, prediction_outcome = _prediction_settlement_state(
        repository=repository,
        forecast=forecast,
        as_of_ns=active_as_of,
        explicit_as_of=as_of_ns is not None,
    )
    correlation_id = (
        match.correlation_id
        if match is not None and match.correlation_id
        else _find_value(orders, {"correlation_id"})
    )
    stages = [
        _trace_stage(
            "OPPORTUNITY",
            "AVAILABLE" if opportunity is not None else "INCOMPLETE",
            opportunity.opportunity_id if opportunity is not None else None,
            {
                "opportunity": opportunity_v1_to_dict(opportunity),
                "forecast": forecast_v1_to_dict(forecast) if forecast is not None else None,
                "strategy_match": (
                    strategy_match_to_dict(match) if match is not None else None
                ),
                "economic_assessment": (
                    economic_assessment_v1_to_dict(economics) if economics is not None else None
                ),
            }
            if opportunity is not None
            else {},
            id_field="opportunity_id",
        ),
        _trace_stage(
            "ALLOCATION",
            allocation.status.value,
            allocation.allocation_decision_id,
            {"allocation": allocation_decision_v1_to_dict(allocation)},
            id_field="allocation_decision_id",
        ),
        _trace_stage(
            "RISK_DECISION",
            risk.decision.value if risk is not None else "INCOMPLETE",
            risk.risk_decision_id if risk is not None else None,
            {"risk_decision": risk_decision_v1_to_dict(risk)} if risk is not None else {},
            id_field="risk_decision_id",
        ),
        _trace_stage(
            "ORDER_READY",
            order_ready.status.value if order_ready is not None else "INCOMPLETE",
            order_ready.order_ready_id if order_ready is not None else None,
            {"order_ready": order_ready_v1_to_dict(order_ready)}
            if order_ready is not None
            else {},
            id_field="order_ready_id",
        ),
        _trace_stage(
            "PAPER_FILL",
            "FILLED" if fills else "NOT_FILLED",
            str(fills[0].get("fill_id")) if fills else None,
            {"orders": list(orders), "fills": list(fills)},
            id_field="fill_id",
        ),
        _trace_stage(
            "PORTFOLIO_SETTLEMENT",
            "SETTLED" if position_events else "NOT_SETTLED",
            str(position_events[-1]["event_id"]) if position_events else None,
            {"events": list(position_events)},
            id_field="event_id",
        ),
        _trace_stage(
            "PREDICTION_SETTLEMENT",
            prediction_state,
            prediction_outcome.outcome_id if prediction_outcome is not None else (
                prediction_entry.ledger_entry_id if prediction_entry is not None else None
            ),
            {
                "prediction_ledger_entry": (
                    prediction_ledger_entry_v1_to_dict(prediction_entry)
                    if prediction_entry is not None
                    else None
                ),
                "prediction_outcome": (
                    outcome_v1_to_dict(prediction_outcome)
                    if prediction_outcome is not None
                    else None
                ),
            },
            id_field="prediction_outcome_id"
            if prediction_outcome is not None
            else "prediction_ledger_entry_id",
        ),
        _trace_stage(
            "ATTRIBUTION",
            "MATERIALIZED" if attribution is not None else "PENDING",
            attribution.attribution_id if attribution is not None else None,
            {"attribution": _attribution_payload(attribution)},
            id_field="attribution_id",
        ),
    ]
    quantities: dict[str, int] = {}
    if proposal is not None:
        quantities["proposal_requested_quantity"] = proposal.requested_quantity
        quantities["proposal_requested_notional_minor"] = proposal.requested_notional_minor
    if risk is not None:
        quantities["risk_approved_quantity"] = risk.approved_quantity
        quantities["risk_approved_notional_minor"] = risk.approved_notional_minor
    if order_ready is not None:
        quantities["submitted_quantity"] = order_ready.approved_quantity
    if fills:
        quantities["filled_quantity"] = sum(int(fill.get("fill_quantity", 0)) for fill in fills)
    if proposal is not None and proposal.metadata.get("allocation_desired_quantity") is not None:
        quantities["allocation_desired_quantity"] = int(
            proposal.metadata["allocation_desired_quantity"]
        )
    if proposal is not None and proposal.metadata.get("allocation_desired_notional_minor") is not None:
        quantities["allocation_desired_notional_minor"] = int(
            proposal.metadata["allocation_desired_notional_minor"]
        )

    missing = [stage["stage"] for stage in stages if stage["status"] == "INCOMPLETE"]
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "authority_boundary": "PAPER_OBSERVABILITY_READ_ONLY",
        "account_id": account_id,
        "mode": normalized_mode,
        "as_of_context": {
            "as_of_ns": active_as_of,
            "point_in_time": as_of_ns is not None,
        },
        "trace": {
            "trace_kind": "STRATEGY_DECISION",
            "correlation_id": correlation_id,
            "correlation": {
                "allocation_decision_id": allocation.allocation_decision_id,
                "strategy_match_id": match.match_id if match is not None else None,
                "forecast_id": forecast.forecast_id if forecast is not None else None,
                "opportunity_id": opportunity.opportunity_id if opportunity is not None else None,
                "trade_proposal_id": proposal.proposal_id if proposal is not None else None,
                "risk_decision_id": risk.risk_decision_id if risk is not None else None,
                "order_ready_id": order_ready.order_ready_id if order_ready is not None else None,
                "order_id": str(orders[0].get("order_id")) if orders else None,
                "fill_id": str(fills[0].get("fill_id")) if fills else None,
            },
            "quantities": quantities,
            "completeness": {
                "state": "INCOMPLETE" if missing else "COMPLETE",
                "missing_stages": missing,
            },
            "stages": stages,
            "settlement": {
                "portfolio": "SETTLED" if position_events else "NOT_SETTLED",
                "prediction": prediction_state,
            },
        },
    }


def _trace_stage(
    stage: str,
    status: str,
    identifier: str | None,
    metadata: dict[str, Any],
    *,
    id_field: str = "id",
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "ids": {id_field: identifier} if identifier is not None else {},
        "metadata": metadata,
    }


def _prediction_settlement_state(
    *,
    repository: Any,
    forecast: Any | None,
    as_of_ns: int,
    explicit_as_of: bool,
) -> tuple[str, Any | None, Any | None]:
    if forecast is None:
        return "UNAVAILABLE", None, None
    entries = repository.get_prediction_ledger_entries_by_forecast(forecast.forecast_id)
    if not entries:
        return "UNAVAILABLE", None, None
    entry = sorted(entries, key=lambda item: item.ledger_entry_id)[0]
    outcomes = repository.get_outcomes_by_forecast(entry.forecast_id)
    outcome = next(
        (
            item
            for item in outcomes
            if item.metadata.get("ledger_entry_id") == entry.ledger_entry_id
            and item.adjudicated_at_ns <= as_of_ns
        ),
        None,
    )
    if outcome is not None:
        return "SETTLED", entry, outcome
    if explicit_as_of and as_of_ns < entry.availability_cutoff_ns:
        return "NOT_DUE", entry, None
    return "PENDING", entry, None


def build_strategy_profitability_payload(
    *,
    repository: Any,
    ledger: Any,
    account_id: str,
    mode: str = "PAPER",
    allocation_decision_id: str | None = None,
    as_of_ns: int | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Build a deterministic, non-mutating Paper strategy observability payload."""
    normalized_mode = _normalize_mode(mode)
    if allocation_decision_id:
        allocation = repository.get_allocation_decision(allocation_decision_id)
        if allocation is None:
            raise ValueError("ALLOCATION_DECISION_NOT_FOUND")
        allocations = (allocation,)
    else:
        allocations = repository.query_allocation_decisions(
            account_id=account_id,
            mode=normalized_mode,
            decision_to_ns=as_of_ns,
            limit=limit,
        )

    active_as_of = as_of_ns if as_of_ns is not None else _latest_observation_ns(allocations, ledger)
    account = ledger.project_account()
    positions = ledger.project_positions()
    items = []
    for allocation in allocations:
        if allocation.account_id != account_id or allocation.mode != normalized_mode:
            raise ValueError("STRATEGY_PROFITABILITY_SCOPE_MISMATCH")
        if as_of_ns is not None and allocation.decision_time_ns > as_of_ns:
            raise ValueError("ALLOCATION_AFTER_POINT_IN_TIME")
        items.append(
            _build_item(
                repository=repository,
                ledger=ledger,
                allocation=allocation,
                account_id=account_id,
                mode=normalized_mode,
                as_of_ns=active_as_of,
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "authority_boundary": "PAPER_OBSERVABILITY_READ_ONLY",
        "account_id": account_id,
        "mode": normalized_mode,
        "as_of_context": {
            "as_of_ns": active_as_of,
            "point_in_time": as_of_ns is not None,
        },
        "attribution_semantics": {
            "pnl_source": "StrategyAttributionV1.trading_outcome",
            "materialization": "CUMULATIVE",
            "aggregation": "LATEST_COMPLETE_SNAPSHOT_ONLY",
            "portfolio_ledger_is_authoritative": True,
        },
        "data_health": {
            "state": "PASS" if items else "EMPTY",
            "detail": "No strategy-linked Paper allocations are available."
            if not items
            else "Strategy lineage resolved from immutable repository and Paper ledger records.",
        },
        "disclaimer": (
            "Strategy attribution is a P&L sidecar, not the authoritative Paper portfolio ledger. "
            "This endpoint never settles outcomes or submits orders."
        ),
        "account_ledger_pnl": {
            "currency": str(account.get("currency", "USD")),
            "realized_pnl_minor": int(account.get("realized_pnl_minor", 0)),
            "unrealized_pnl_minor": sum(
                int(position.get("unrealized_pnl_minor", 0)) for position in positions
            ),
        },
        "items": items,
        "total_count": len(items),
    }


def _build_item(
    *,
    repository: Any,
    ledger: Any,
    allocation: Any,
    account_id: str,
    mode: str,
    as_of_ns: int,
) -> dict[str, Any]:
    match = (
        repository.get_strategy_match(allocation.strategy_match_ref.id)
        if allocation.strategy_match_ref is not None
        else None
    )
    forecast = _first_forecast(repository, allocation)
    opportunity = repository.get_opportunity(allocation.opportunity_ref.id)
    economics = repository.get_economic_assessment(allocation.economic_assessment_ref.id)
    portfolio = repository.get_paper_portfolio_snapshot(allocation.portfolio_snapshot_ref.id)

    orders = tuple(
        order
        for order in ledger.project_orders()
        if _contains_reference(order, "allocation_decision", allocation.allocation_decision_id)
        or _contains_reference(order, "allocation", allocation.allocation_decision_id)
    )
    order_ids = {str(order.get("order_id")) for order in orders}
    fills = tuple(
        fill
        for fill in ledger.project_fills()
        if str(fill.get("order_id")) in order_ids
        and int(fill.get("fill_time", fill.get("fill_time_ns", 0))) <= as_of_ns
    )
    proposal, risk = _resolve_order_records(repository, orders)
    attribution = _latest_complete_attribution(
        repository,
        allocation.allocation_decision_id,
        account_id=account_id,
        mode=mode,
        as_of_ns=as_of_ns,
    )

    prediction_entry = None
    prediction_outcome = None
    settlement_state = "UNAVAILABLE"
    if forecast is not None:
        entries = repository.get_prediction_ledger_entries_by_forecast(forecast.forecast_id)
        prediction_entry = entries[0] if entries else None
        if prediction_entry is not None:
            outcomes = repository.get_outcomes_by_forecast(prediction_entry.forecast_id)
            prediction_outcome = next(
                (
                    item
                    for item in outcomes
                    if item.metadata.get("ledger_entry_id") == prediction_entry.ledger_entry_id
                    and item.adjudicated_at_ns <= as_of_ns
                ),
                None,
            )
            settlement_state = "SETTLED" if prediction_outcome is not None else "PENDING"

    return {
        "allocation": allocation_decision_v1_to_dict(allocation),
        "strategy_match": strategy_match_to_dict(match) if match is not None else None,
        "forecast": forecast_v1_to_dict(forecast) if forecast is not None else None,
        "economic_assessment": (
            economic_assessment_v1_to_dict(economics) if economics is not None else None
        ),
        "opportunity": opportunity_v1_to_dict(opportunity) if opportunity is not None else None,
        "portfolio_snapshot": (
            paper_portfolio_snapshot_v1_to_dict(portfolio) if portfolio is not None else None
        ),
        "proposal": trade_proposal_v1_to_dict(proposal) if proposal is not None else None,
        "risk_decision": risk_decision_v1_to_dict(risk) if risk is not None else None,
        "orders": list(orders),
        "fills": list(fills),
        "attribution": _attribution_payload(attribution),
        "prediction_ledger_entry": (
            prediction_ledger_entry_v1_to_dict(prediction_entry)
            if prediction_entry is not None
            else None
        ),
        "prediction_outcome": (
            outcome_v1_to_dict(prediction_outcome) if prediction_outcome is not None else None
        ),
        "settlement": {
            "state": settlement_state,
            "inspection_only": True,
        },
    }


def _first_forecast(repository: Any, allocation: Any) -> Any | None:
    for reference in allocation.forecast_refs:
        if reference.kind == "forecast":
            return repository.get_forecast(reference.id)
    return None


def _resolve_order_records(repository: Any, orders: tuple[Mapping[str, Any], ...]) -> tuple[Any | None, Any | None]:
    proposal = None
    risk = None
    for order in orders:
        proposal_id = _find_value(order, {"trade_proposal_id", "proposal_id"}) or _find_ref_id(
            order, {"trade_proposal", "proposal"}
        )
        risk_id = _find_value(order, {"risk_decision_id", "risk_id"}) or _find_ref_id(
            order, {"risk_decision", "risk"}
        )
        if proposal is None and proposal_id:
            proposal = repository.get_trade_proposal(proposal_id)
        if risk is None and risk_id:
            risk = repository.get_risk_decision(risk_id)
    return proposal, risk


def _attribution_payload(record: Any | None) -> dict[str, Any] | None:
    if record is None:
        return None
    payload = attribution_v1_to_dict(record)
    outcome = record.trading_outcome
    payload["trading_outcome"] = {
        "outcome_kind": outcome.outcome_kind.value,
        "realized_pnl_minor": outcome.realized_pnl_minor,
        "ending_position_quantity": outcome.ending_position_quantity,
        "ending_cost_basis_minor": outcome.ending_cost_basis_minor,
        "total_commission_minor": outcome.total_commission_minor,
        "total_fees_minor": outcome.total_fees_minor,
    }
    return payload


def _latest_complete_attribution(
    repository: Any,
    allocation_decision_id: str,
    *,
    account_id: str,
    mode: str,
    as_of_ns: int,
) -> Any | None:
    rows = repository.get_strategy_attributions_by_allocation(
        allocation_decision_id,
        account_id=account_id,
        mode=mode,
    )
    eligible = [
        row
        for row in rows
        if row.point_in_time_ns <= as_of_ns
        and row.fill_refs
        and all(fill.fill_time_ns <= as_of_ns for fill in row.fills)
    ]
    return max(
        eligible,
        key=lambda row: (
            len(row.fill_refs),
            max((fill.fill_time_ns for fill in row.fills), default=-1),
            row.attribution_id,
        ),
        default=None,
    )


def _find_value(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, Mapping):
        for key in keys:
            candidate = value.get(key)
            if candidate is not None and str(candidate).strip():
                return str(candidate)
        for nested in value.values():
            found = _find_value(nested, keys)
            if found:
                return found
    elif isinstance(value, (tuple, list, set)):
        for nested in value:
            found = _find_value(nested, keys)
            if found:
                return found
    return None


def _find_ref_id(value: Any, kinds: set[str]) -> str | None:
    if isinstance(value, Mapping):
        if str(value.get("kind", "")).strip() in kinds and value.get("id") is not None:
            return str(value["id"])
        for nested in value.values():
            found = _find_ref_id(nested, kinds)
            if found:
                return found
    elif isinstance(value, (tuple, list, set)):
        for nested in value:
            found = _find_ref_id(nested, kinds)
            if found:
                return found
    return None


def _contains_reference(value: Any, kind: str, identifier: str) -> bool:
    if isinstance(value, Mapping):
        if value.get("kind") == kind and str(value.get("id")) == identifier:
            return True
        return any(_contains_reference(item, kind, identifier) for item in value.values())
    if isinstance(value, (tuple, list, set)):
        return any(_contains_reference(item, kind, identifier) for item in value)
    return False


def _latest_observation_ns(allocations: tuple[Any, ...], ledger: Any) -> int:
    timestamps = [int(row.decision_time_ns) for row in allocations]
    timestamps.extend(
        int(event.get("available_time", event.get("event_time", 0)))
        for event in getattr(ledger, "events", ())
    )
    timestamps.extend(
        int(fill.get("fill_time", fill.get("fill_time_ns", 0)))
        for fill in ledger.project_fills()
    )
    return max(timestamps, default=0)


def _normalize_mode(value: Any) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE"}.get(normalized, normalized)
