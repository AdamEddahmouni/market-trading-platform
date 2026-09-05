"""Materialize immutable strategy attribution from persisted Paper fills.

P0-4: attribution parity with the authoritative fill-driven ledger is an
enforced invariant. A re-materialization that would disagree with any already-
persisted attribution for the same allocation (changed accounting for a fill
it already covers, or a coverage regression) fails closed and records an
immutable parity-violation event before raising — it is never silently
absorbed. Growing an existing attribution with later fills (CUMULATIVE
semantics) is legitimate and is not a parity break.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..intelligence.contracts import (
    EventV1,
    QualityState,
    QualitySummary,
    SourceReference,
)
from ..intelligence.contracts.common import ContractReference
from .attribution import AttributionFillV1, StrategyAttributionV1


MATERIALIZATION_SEMANTICS = "CUMULATIVE"
COVERAGE_ALGORITHM_VERSION = "fill-set-coverage-v1"
PARITY_EVENT_TYPE = "ATTRIBUTION_PARITY_VIOLATION"
PARITY_EVENT_PREFIX = "ATTR-PARITY"


class AttributionMaterializationError(ValueError):
    """A strategy attribution join crossed an authority or scope boundary."""


def _authoritative_fill_payload(fill: AttributionFillV1) -> tuple[str, int, int, int, int, int]:
    """The fill accounting the authoritative ledger must agree on."""
    return (
        str(fill.fill_id),
        int(fill.fill_time_ns),
        str(fill.direction).upper(),
        int(fill.quantity),
        int(fill.price_minor),
        int(fill.commission_minor),
        int(fill.fees_minor),
    )


def _parity_violations(
    *,
    computed: StrategyAttributionV1,
    prior: StrategyAttributionV1,
    as_of_ns: int | None,
) -> tuple[str, ...]:
    """Return authoritative-accounting disagreements with one persisted record.

    CUMULATIVE semantics mean a newer record may cover strictly more fills
    than an earlier one; that growth is legitimate. Any fill the prior record
    already covered must either be absent (a coverage regression against the
    authoritative ledger) or byte-identical in its fill-driven accounting.
    Prior fills outside the current ``as_of_ns`` window are out of scope.
    """
    violations: list[str] = []
    prior_by_id = {fill.fill_id: fill for fill in prior.fills}
    computed_by_id = {fill.fill_id: fill for fill in computed.fills}
    for fill_id in sorted(prior_by_id):
        prior_fill = prior_by_id[fill_id]
        if as_of_ns is not None and prior_fill.fill_time_ns > as_of_ns:
            continue
        computed_fill = computed_by_id.get(fill_id)
        if computed_fill is None:
            violations.append(f"COVERAGE_REGRESSION:{fill_id}")
        elif _authoritative_fill_payload(prior_fill) != _authoritative_fill_payload(
            computed_fill
        ):
            violations.append(f"ACCOUNTING_MISMATCH:{fill_id}")
    return tuple(sorted(violations))


def _record_parity_violation_event(
    *,
    repository: Any,
    record: StrategyAttributionV1,
    prior: StrategyAttributionV1,
    violations: tuple[str, ...],
    account_id: str,
    mode: str,
) -> None:
    """Persist the immutable parity-violation event before raising."""
    payload = {
        "event_type": PARITY_EVENT_TYPE,
        "allocation_decision_id": record.allocation_ref.id,
        "persisted_attribution_id": prior.attribution_id,
        "recomputed_attribution_id": record.attribution_id,
        "account_id": account_id,
        "mode": mode,
        "instrument_id": record.instrument_id,
        "violations": list(violations),
        "persisted_fill_count": len(prior.fills),
        "recomputed_fill_count": len(record.fills),
    }
    digest = sha256_bytes(canonical_bytes(payload))
    event = EventV1(
        event_id=f"{PARITY_EVENT_PREFIX}-{digest}",
        schema_version="1",
        event_type=PARITY_EVENT_TYPE,
        event_time_ns=int(record.created_at_ns),
        available_time_ns=int(record.created_at_ns),
        payload=payload,
        quality=QualitySummary(state=QualityState.GOOD),
        source=SourceReference(
            provider_id="attribution_materializer",
            source_type="ATTRIBUTION",
            source_record_id=str(prior.attribution_id),
        ),
        instrument_id=record.instrument_id,
        lineage_refs=(
            ContractReference(kind="allocation_decision", id=record.allocation_ref.id),
            ContractReference(kind="strategy_attribution", id=prior.attribution_id),
        ),
    )
    repository.put_event(event)


def _enforce_attribution_parity(
    *,
    repository: Any,
    record: StrategyAttributionV1,
    resolved_allocation_id: str,
    account_id: str,
    mode: str,
    as_of_ns: int | None,
) -> None:
    """Fail closed when recomputation disagrees with any persisted attribution.

    Only repositories exposing per-allocation attribution lookup participate;
    identical recomputations (same attribution id) are the dedup path and are
    never flagged.
    """
    lookup = getattr(repository, "get_strategy_attributions_by_allocation", None)
    if lookup is None:
        return
    prior_records = lookup(
        resolved_allocation_id,
        account_id=account_id,
        mode=mode,
    )
    for prior in prior_records:
        if str(getattr(prior, "attribution_id", "")) == record.attribution_id:
            continue
        violations = _parity_violations(
            computed=record,
            prior=prior,
            as_of_ns=as_of_ns,
        )
        if not violations:
            continue
        _record_parity_violation_event(
            repository=repository,
            record=record,
            prior=prior,
            violations=violations,
            account_id=account_id,
            mode=mode,
        )
        raise AttributionMaterializationError(
            f"ATTRIBUTION_PARITY_VIOLATION:{';'.join(violations)}"
        )


def materialize_strategy_attribution(
    *,
    repository: Any,
    ledger: Any | None = None,
    paper_ledger: Any | None = None,
    allocation_decision_id: str | None = None,
    allocation_decision: Any | None = None,
    allocation: Any | None = None,
    proposal_id: str | None = None,
    proposal: Any | None = None,
    risk_decision_id: str | None = None,
    risk_decision: Any | None = None,
    account_id: str | None = None,
    mode: str | None = None,
    as_of_ns: int | None = None,
    initial_position_quantity: int = 0,
    initial_cost_basis_minor: int = 0,
) -> StrategyAttributionV1 | None:
    """Build and immutably persist the complete attribution for current fills.

    Only orders carrying the allocation/proposal/risk backend lineage are
    eligible.  Correlation IDs, symbols, and manually-created orders are not
    sufficient to create a strategy slice.
    """
    active_ledger = ledger or paper_ledger
    if active_ledger is None:
        raise AttributionMaterializationError("PAPER_LEDGER_REQUIRED")
    active_allocation = allocation_decision or allocation
    if active_allocation is None:
        if not allocation_decision_id:
            raise AttributionMaterializationError("ALLOCATION_DECISION_REQUIRED")
        active_allocation = repository.get_allocation_decision(allocation_decision_id)
    if active_allocation is None:
        raise AttributionMaterializationError("ALLOCATION_DECISION_NOT_FOUND")

    resolved_allocation_id = str(
        allocation_decision_id or active_allocation.allocation_decision_id
    )
    if str(active_allocation.allocation_decision_id) != resolved_allocation_id:
        raise AttributionMaterializationError("ALLOCATION_DECISION_ID_MISMATCH")
    if str(getattr(active_allocation.status, "value", active_allocation.status)) != "SELECTED":
        return None

    expected_account = str(account_id or active_allocation.account_id)
    expected_mode = _normalize_mode(mode or active_allocation.mode)
    if str(active_allocation.account_id) != expected_account:
        raise AttributionMaterializationError("ATTRIBUTION_ACCOUNT_SCOPE_MISMATCH")
    if _normalize_mode(active_allocation.mode) != expected_mode:
        raise AttributionMaterializationError("ATTRIBUTION_MODE_SCOPE_MISMATCH")

    match_ref = getattr(active_allocation, "strategy_match_ref", None)
    if match_ref is None:
        return None
    match_ref = _as_reference(match_ref)
    match = repository.get_strategy_match(match_ref.id)
    if match is None:
        return None

    opportunity_ref = _as_reference(active_allocation.opportunity_ref)
    opportunity = repository.get_opportunity(opportunity_ref.id)
    if opportunity is None:
        return None
    instrument_id = _instrument_id(opportunity)

    active_proposal = _resolve_record(
        proposal,
        proposal_id,
        repository,
        "get_trade_proposal",
        "TRADE_PROPOSAL_NOT_FOUND",
    )
    active_risk = _resolve_record(
        risk_decision,
        risk_decision_id,
        repository,
        "get_risk_decision",
        "RISK_DECISION_NOT_FOUND",
    )
    if active_proposal is not None and active_risk is not None:
        if str(active_risk.trade_proposal_id) != str(active_proposal.proposal_id):
            raise AttributionMaterializationError("PROPOSAL_RISK_LINEAGE_MISMATCH")

    target_lineage = _target_lineage(
        resolved_allocation_id,
        active_allocation,
        active_proposal,
        active_risk,
    )
    explicit_order_ids = {
        str(value)
        for value in getattr(active_allocation, "order_ids", ())
        if value
    }
    selected_orders = []
    for order in active_ledger.project_orders():
        order_id = str(order.get("order_id", ""))
        if order_id in explicit_order_ids or _has_target_lineage(order, target_lineage):
            selected_orders.append(order)
    selected_order_ids = {str(order.get("order_id")) for order in selected_orders}

    fills: list[AttributionFillV1] = []
    execution_refs: list[ContractReference] = []
    for order in selected_orders:
        order_id = str(order.get("order_id", ""))
        if order_id:
            execution_refs.append(ContractReference(kind="order", id=order_id))
    for fill in active_ledger.project_fills():
        order_id = str(fill.get("order_id", ""))
        if order_id not in selected_order_ids:
            continue
        fill_time_ns = int(fill.get("fill_time_ns", fill.get("fill_time", 0)))
        if fill_time_ns < int(active_allocation.decision_time_ns):
            raise AttributionMaterializationError("ATTRIBUTION_FILL_BEFORE_DECISION")
        if as_of_ns is not None and fill_time_ns > as_of_ns:
            continue
        if str(fill.get("instrument_id", instrument_id)) != instrument_id:
            raise AttributionMaterializationError("ATTRIBUTION_INSTRUMENT_SCOPE_MISMATCH")
        quantity = int(fill.get("fill_quantity", 0))
        price_minor = int(fill.get("fill_price_minor", 0))
        direction = _attribution_direction(fill.get("direction"))
        policy = getattr(active_ledger, "policy", {})
        fills.append(
            AttributionFillV1(
                fill_id=str(fill["fill_id"]),
                fill_time_ns=fill_time_ns,
                direction=direction,
                quantity=quantity,
                price_minor=price_minor,
                execution_ref=ContractReference(kind="order", id=order_id),
                commission_minor=int(
                    fill["commission_minor"]
                    if "commission_minor" in fill
                    else quantity * int(policy.get("commission_minor_per_share", 0))
                ),
                fees_minor=int(
                    fill["fees_minor"]
                    if "fees_minor" in fill
                    else policy.get("fee_minor_per_order", 0)
                ),
            )
        )

    if not fills:
        return None
    fills.sort(key=lambda item: (item.fill_time_ns, item.fill_id))

    if active_proposal is not None:
        allocation_quantity = int(active_proposal.requested_quantity)
    else:
        allocation_quantity = max(
            int(order.get("desired_quantity", order.get("quantity", 0)))
            for order in selected_orders
        )
    if allocation_quantity <= 0:
        allocation_quantity = sum(fill.quantity for fill in fills)
    if allocation_quantity <= 0:
        return None

    strategy_match_ref = ContractReference(kind="strategy_match", id=match.match_id)
    allocation_intent_ref = getattr(active_allocation, "allocation_intent_ref", None)
    if allocation_intent_ref is not None:
        allocation_intent_ref = _as_reference(allocation_intent_ref)
    execution_refs.extend(
        ref
        for ref in (
            ContractReference(kind="trade_proposal", id=str(active_proposal.proposal_id))
            if active_proposal is not None
            else None,
            ContractReference(kind="risk_decision", id=str(active_risk.risk_decision_id))
            if active_risk is not None
            else None,
        )
        if ref is not None
    )
    fill_times = [fill.fill_time_ns for fill in fills]
    record = StrategyAttributionV1.create(
        schema_version="1",
        account_id=expected_account,
        mode=expected_mode,
        instrument_id=instrument_id,
        allocation_ref=ContractReference(
            kind="allocation_decision",
            id=resolved_allocation_id,
        ),
        intent_ref=allocation_intent_ref,
        opportunity_ref=opportunity_ref,
        cluster_thesis_ref=_as_reference(active_allocation.cluster_ref),
        strategy_match_ref=strategy_match_ref,
        strategy_id=str(match.strategy_id),
        strategy_identity_hash=str(match.strategy_identity_hash),
        allocation_quantity=allocation_quantity,
        allocation_direction=_attribution_direction(
            getattr(opportunity.side, "value", opportunity.side)
        ),
        allocation_time_ns=int(active_allocation.decision_time_ns),
        point_in_time_ns=int(active_allocation.decision_time_ns),
        fills=tuple(fills),
        execution_refs=tuple(execution_refs),
        forecast_refs=tuple(
            _as_reference(ref) for ref in getattr(active_allocation, "forecast_refs", ())
        ),
        materialization_semantics=MATERIALIZATION_SEMANTICS,
        coverage_algorithm_version=COVERAGE_ALGORITHM_VERSION,
        initial_position_quantity=int(initial_position_quantity),
        initial_cost_basis_minor=int(initial_cost_basis_minor),
        created_at_ns=max(int(active_allocation.decision_time_ns), max(fill_times)),
    )
    _enforce_attribution_parity(
        repository=repository,
        record=record,
        resolved_allocation_id=resolved_allocation_id,
        account_id=expected_account,
        mode=expected_mode,
        as_of_ns=as_of_ns,
    )
    result = repository.put_strategy_attribution(record)
    if getattr(result, "value", result) == "ALREADY_PRESENT":
        existing = repository.get_strategy_attribution(record.attribution_id)
        return existing or record
    return record


def get_latest_complete_strategy_attribution(
    repository: Any,
    allocation_decision_id: str,
    *,
    account_id: str,
    mode: str,
    as_of_ns: int | None = None,
) -> StrategyAttributionV1 | None:
    """Return the greatest cumulative covered-fill snapshot, never a sum."""
    rows = repository.get_strategy_attributions_by_allocation(
        allocation_decision_id,
        account_id=account_id,
        mode=mode,
        as_of_ns=as_of_ns,
    )
    rows = tuple(row for row in rows if row.fill_refs)
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            len(row.fill_refs),
            max((fill.fill_time_ns for fill in row.fills), default=-1),
            row.attribution_id,
        ),
    )


def _resolve_record(
    record: Any | None,
    record_id: str | None,
    repository: Any,
    getter_name: str,
    missing_code: str,
) -> Any | None:
    if record is not None:
        return record
    if record_id is None:
        return None
    getter = getattr(repository, getter_name, None)
    if getter is None:
        raise AttributionMaterializationError(missing_code)
    resolved = getter(record_id)
    if resolved is None:
        raise AttributionMaterializationError(missing_code)
    return resolved


def _target_lineage(
    allocation_id: str,
    allocation: Any,
    proposal: Any | None,
    risk: Any | None,
) -> set[tuple[str, str]]:
    values = {
        ("allocation_decision", allocation_id),
        ("allocation", allocation_id),
    }
    intent_ref = getattr(allocation, "allocation_intent_ref", None)
    if intent_ref is not None:
        ref = _as_reference(intent_ref)
        values.add((ref.kind, ref.id))
    if proposal is not None:
        values.update(
            {
                ("trade_proposal", str(proposal.proposal_id)),
                ("proposal", str(proposal.proposal_id)),
            }
        )
    if risk is not None:
        values.update(
            {
                ("risk_decision", str(risk.risk_decision_id)),
                ("risk", str(risk.risk_decision_id)),
            }
        )
    return values


def _has_target_lineage(order: Mapping[str, Any], targets: set[tuple[str, str]]) -> bool:
    for key, value in order.items():
        if key in {
            "lineage_refs",
            "lineage",
            "backend_lineage",
            "backend_lineage_refs",
            "decision_source_snapshot",
        }:
            if _nested_refs_match(value, targets):
                return True
        elif key in {
            "allocation_decision_id",
            "allocation_id",
            "trade_proposal_id",
            "proposal_id",
            "risk_decision_id",
        }:
            if any(identifier == str(value) for _, identifier in targets):
                return True
        elif key in {
            "allocation_decision_ref",
            "allocation_ref",
            "trade_proposal_ref",
            "proposal_ref",
            "risk_decision_ref",
        }:
            if _nested_refs_match(value, targets):
                return True
    return False


def _nested_refs_match(value: Any, targets: set[tuple[str, str]]) -> bool:
    if isinstance(value, ContractReference):
        return (value.kind, value.id) in targets
    if isinstance(value, Mapping):
        if "kind" in value and "id" in value:
            if (str(value["kind"]), str(value["id"])) in targets:
                return True
        return any(_nested_refs_match(item, targets) for item in value.values())
    if isinstance(value, (tuple, list, set)):
        return any(_nested_refs_match(item, targets) for item in value)
    return False


def _as_reference(value: Any) -> ContractReference:
    if isinstance(value, ContractReference):
        return value
    if isinstance(value, Mapping):
        return ContractReference(
            kind=str(value["kind"]),
            id=str(value["id"]),
            schema_version=str(value.get("schema_version", "1")),
        )
    raise AttributionMaterializationError("ATTRIBUTION_REFERENCE_INVALID")


def _instrument_id(opportunity: Any) -> str:
    scope = getattr(opportunity, "scope", None)
    instruments = getattr(scope, "instrument_ids", ()) if scope is not None else ()
    if not instruments:
        raise AttributionMaterializationError("ATTRIBUTION_INSTRUMENT_SCOPE_MISSING")
    if len(instruments) != 1:
        raise AttributionMaterializationError("ATTRIBUTION_INSTRUMENT_SCOPE_AMBIGUOUS")
    return str(instruments[0])


def _attribution_direction(value: Any) -> str:
    normalized = str(getattr(value, "value", value)).strip().upper()
    if normalized in {"BUY", "LONG"}:
        return "LONG"
    if normalized in {"SELL", "SHORT"}:
        return "SHORT"
    raise AttributionMaterializationError("ATTRIBUTION_DIRECTION_INVALID")


def _normalize_mode(value: Any) -> str:
    normalized = str(getattr(value, "value", value)).strip().upper()
    return {"LIVE": "ACTUAL_LIVE"}.get(normalized, normalized)


__all__ = [
    "AttributionMaterializationError",
    "COVERAGE_ALGORITHM_VERSION",
    "MATERIALIZATION_SEMANTICS",
    "get_latest_complete_strategy_attribution",
    "materialize_strategy_attribution",
]
