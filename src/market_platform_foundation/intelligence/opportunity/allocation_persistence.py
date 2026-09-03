"""Immutable, decision-set-aware persistence for capital allocation outcomes."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    contract_reference_from_dict,
    contract_reference_to_dict,
    normalize_unique_refs,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from .comparison import (
    ALLOCATOR_IMPLEMENTATION_VERSION,
    COMPARATOR_IMPLEMENTATION_VERSION,
    AllocationEvaluationV1,
    CapitalAllocationConstraintsV1,
    CapitalAllocationIntentV1,
    CapitalAllocationResultV1,
    ComparisonConstraintsV1,
    ComparisonReasonCode,
    ComparisonVectorV1,
    OpportunityComparisonResultV1,
    allocation_constraints_to_dict,
    comparison_constraints_to_dict,
    comparison_vector_to_dict,
)
from .economic_assessment import MoneyMinorUnits


ALLOCATION_DECISION_IMPLEMENTATION_VERSION = "allocation-decision-sidecar-v1"


class AllocationPersistenceError(ValueError):
    """An allocation sidecar input crossed an immutable scope boundary."""


class AllocationDecisionStatus(StrEnum):
    SELECTED = "SELECTED"
    NOT_SELECTED = "NOT_SELECTED"
    NO_ALLOCATION = "NO_ALLOCATION"


def _mode(value: str) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE", "PAPER": "PAPER"}.get(normalized, normalized)


def _money_to_dict(value: MoneyMinorUnits | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "amount_minor": value.amount_minor,
        "currency": value.currency,
        "scale": value.scale,
        "unit": "MINOR_UNITS",
    }


def _money_from_dict(value: Mapping[str, Any] | None) -> MoneyMinorUnits | None:
    if value is None:
        return None
    if value.get("unit") != "MINOR_UNITS":
        raise AllocationPersistenceError("ALLOCATION_MONEY_UNIT_INVALID")
    return MoneyMinorUnits(
        int(value["amount_minor"]),
        str(value["currency"]),
        int(value["scale"]),
    )


def _zero_money(currency: str, scale: int) -> MoneyMinorUnits:
    return MoneyMinorUnits(0, currency, scale)


def _refs_to_dict(refs: tuple[ContractReference, ...]) -> list[dict[str, Any]]:
    return [contract_reference_to_dict(ref) for ref in refs]


def _refs_from_dict(values: list[Mapping[str, Any]] | None) -> tuple[ContractReference, ...]:
    return tuple(contract_reference_from_dict(value) for value in (values or ()))


def _constraint_matches(
    left: ComparisonConstraintsV1 | CapitalAllocationConstraintsV1,
    right: ComparisonConstraintsV1 | CapitalAllocationConstraintsV1,
) -> bool:
    return (
        left.account_id == right.account_id
        and left.mode == right.mode
        and left.decision_time_ns == right.decision_time_ns
        and left.currency == right.currency
        and left.scale == right.scale
    )


@dataclass(frozen=True, slots=True)
class CapitalAllocationDecisionV1:
    """Durable projection of one allocator-evaluated candidate."""

    allocation_decision_id: str
    schema_version: str
    decision_set_id: str
    status: AllocationDecisionStatus
    account_id: str
    mode: str
    decision_time_ns: int
    currency: str
    scale: int
    opportunity_ref: ContractReference
    cluster_ref: ContractReference
    economic_assessment_ref: ContractReference
    strategy_match_ref: ContractReference | None
    forecast_refs: tuple[ContractReference, ...]
    allocation_intent_ref: ContractReference | None
    portfolio_snapshot_ref: ContractReference
    comparison_id: str
    comparator_version: str
    allocator_version: str
    rank: int
    competing_opportunity_refs: tuple[ContractReference, ...]
    comparison_constraints: ComparisonConstraintsV1
    allocation_constraints: CapitalAllocationConstraintsV1
    comparison_vector: ComparisonVectorV1
    requested_capital: MoneyMinorUnits | None
    requested_buying_power: MoneyMinorUnits | None
    requested_maximum_loss: MoneyMinorUnits | None
    allocated_capital: MoneyMinorUnits
    allocated_buying_power: MoneyMinorUnits
    allocated_maximum_loss: MoneyMinorUnits
    reason_codes: tuple[ComparisonReasonCode, ...]
    lineage_refs: tuple[ContractReference, ...] = ()
    source_refs: tuple[ContractReference, ...] = ()
    implementation_version: str = ALLOCATION_DECISION_IMPLEMENTATION_VERSION

    def __post_init__(self) -> None:
        validate_id(self.allocation_decision_id, field_name="allocation_decision_id")
        validate_schema_version(self.schema_version)
        validate_id(self.decision_set_id, field_name="decision_set_id")
        validate_id(self.account_id, field_name="account_id")
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if not str(self.mode).strip():
            raise AllocationPersistenceError("ALLOCATION_MODE_REQUIRED")
        object.__setattr__(self, "mode", _mode(self.mode))
        if self.rank < 1:
            raise AllocationPersistenceError("ALLOCATION_RANK_INVALID")
        if not isinstance(self.status, AllocationDecisionStatus):
            object.__setattr__(self, "status", AllocationDecisionStatus(str(self.status)))
        for ref in (
            self.opportunity_ref,
            self.cluster_ref,
            self.economic_assessment_ref,
            self.portfolio_snapshot_ref,
        ):
            if not isinstance(ref, ContractReference):
                raise AllocationPersistenceError("ALLOCATION_REFERENCE_INVALID")
        if self.strategy_match_ref is not None and not isinstance(
            self.strategy_match_ref, ContractReference
        ):
            raise AllocationPersistenceError("STRATEGY_MATCH_REFERENCE_INVALID")
        if self.allocation_intent_ref is not None and not isinstance(
            self.allocation_intent_ref, ContractReference
        ):
            raise AllocationPersistenceError("ALLOCATION_INTENT_REFERENCE_INVALID")
        if self.status is AllocationDecisionStatus.SELECTED and self.allocation_intent_ref is None:
            raise AllocationPersistenceError("SELECTED_INTENT_REFERENCE_REQUIRED")
        if self.status is not AllocationDecisionStatus.NO_ALLOCATION and not self.reason_codes:
            raise AllocationPersistenceError("ALLOCATION_REASON_REQUIRED")
        for money in (
            self.requested_capital,
            self.requested_buying_power,
            self.requested_maximum_loss,
            self.allocated_capital,
            self.allocated_buying_power,
            self.allocated_maximum_loss,
        ):
            if money is not None and (money.currency, money.scale) != (
                self.currency,
                self.scale,
            ):
                raise AllocationPersistenceError("ALLOCATION_MONEY_SCOPE_MISMATCH")
        object.__setattr__(
            self,
            "competing_opportunity_refs",
            tuple(self.competing_opportunity_refs),
        )
        object.__setattr__(
            self,
            "forecast_refs",
            tuple(sorted(normalize_unique_refs(self.forecast_refs), key=_ref_key)),
        )
        object.__setattr__(
            self,
            "lineage_refs",
            tuple(sorted(normalize_unique_refs(self.lineage_refs), key=_ref_key)),
        )
        object.__setattr__(
            self,
            "source_refs",
            tuple(sorted(normalize_unique_refs(self.source_refs), key=_ref_key)),
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                code
                if isinstance(code, ComparisonReasonCode)
                else ComparisonReasonCode(str(code))
                for code in self.reason_codes
            ),
        )

    @property
    def requested_capital_minor(self) -> int | None:
        return self.requested_capital.amount_minor if self.requested_capital else None

    @property
    def requested_buying_power_minor(self) -> int | None:
        return self.requested_buying_power.amount_minor if self.requested_buying_power else None

    @property
    def requested_maximum_loss_minor(self) -> int | None:
        return (
            self.requested_maximum_loss.amount_minor
            if self.requested_maximum_loss
            else None
        )

    @property
    def allocated_capital_minor(self) -> int:
        return self.allocated_capital.amount_minor

    @property
    def allocated_buying_power_minor(self) -> int:
        return self.allocated_buying_power.amount_minor

    @property
    def allocated_maximum_loss_minor(self) -> int:
        return self.allocated_maximum_loss.amount_minor


def _ref_key(ref: ContractReference) -> tuple[str, str, str]:
    return ref.kind, ref.id, ref.schema_version


def _decision_set_payload(
    comparison: OpportunityComparisonResultV1,
    comparison_constraints: ComparisonConstraintsV1,
    allocation_constraints: CapitalAllocationConstraintsV1,
    allocator_version: str,
) -> dict[str, Any]:
    evaluations = {
        item.candidate.opportunity.opportunity_id: item
        for item in comparison.evaluations
    }
    ordered_candidates = []
    for candidate in comparison.eligible_candidates:
        opportunity_id = candidate.opportunity.opportunity_id
        evaluation = evaluations[opportunity_id]
        ordered_candidates.append(
            {
                "opportunity_id": opportunity_id,
                "cluster_id": candidate.cluster_id,
                "comparison_vector": comparison_vector_to_dict(
                    evaluation.comparison_vector
                ),
            }
        )
    return {
        "ordered_allocator_candidates": ordered_candidates,
        "comparison_constraints": comparison_constraints_to_dict(comparison_constraints),
        "allocation_constraints": allocation_constraints_to_dict(allocation_constraints),
        "account_id": comparison_constraints.account_id,
        "mode": comparison_constraints.mode,
        "decision_time_ns": comparison_constraints.decision_time_ns,
        "currency": comparison_constraints.currency,
        "scale": comparison_constraints.scale,
        "allocator_version": allocator_version,
    }


def allocation_decision_set_id(
    comparison: OpportunityComparisonResultV1,
    comparison_constraints: ComparisonConstraintsV1,
    allocation_constraints: CapitalAllocationConstraintsV1,
    *,
    allocator_version: str = ALLOCATOR_IMPLEMENTATION_VERSION,
) -> str:
    """Derive the stable identity for a complete allocator input set."""
    payload = _decision_set_payload(
        comparison,
        comparison_constraints,
        allocation_constraints,
        allocator_version,
    )
    return f"ALSET-{sha256_bytes(canonical_bytes(payload))}"


def _lineage_refs(candidate: Any, extra: tuple[ContractReference, ...] = ()) -> tuple[ContractReference, ...]:
    return tuple(
        sorted(
            normalize_unique_refs(
                (
                    *candidate.opportunity.lineage_refs,
                    *candidate.economic_assessment.source_refs,
                    *candidate.economic_assessment.lineage_refs,
                    *extra,
                )
            ),
            key=_ref_key,
        )
    )


def _forecast_refs(
    candidate: Any,
    overrides: Mapping[str, tuple[ContractReference, ...] | ContractReference] | None,
) -> tuple[ContractReference, ...]:
    opportunity_id = candidate.opportunity.opportunity_id
    selected = overrides.get(opportunity_id) if overrides else None
    if selected is None:
        selected = candidate.opportunity.source_forecast_refs
    if isinstance(selected, ContractReference):
        selected = (selected,)
    return tuple(sorted(normalize_unique_refs(tuple(selected)), key=_ref_key))


def _strategy_match_ref(
    candidate: Any,
    overrides: Mapping[str, ContractReference] | None,
) -> ContractReference | None:
    opportunity_id = candidate.opportunity.opportunity_id
    if overrides and opportunity_id in overrides:
        return overrides[opportunity_id]
    for ref in (
        *candidate.opportunity.lineage_refs,
        *candidate.economic_assessment.lineage_refs,
    ):
        if ref.kind in {"strategy_match", "strategy_match_v1"}:
            return ref
    return None


def _allocation_evaluation(
    allocation: CapitalAllocationResultV1,
    opportunity_id: str,
) -> AllocationEvaluationV1:
    for evaluation in allocation.evaluations:
        if evaluation.opportunity_ref.id == opportunity_id:
            return evaluation
    raise AllocationPersistenceError("ALLOCATOR_EVALUATION_MISSING")


def _intent_by_opportunity(
    allocation: CapitalAllocationResultV1,
) -> dict[str, CapitalAllocationIntentV1]:
    return {intent.opportunity_ref.id: intent for intent in allocation.allocations}


def build_allocation_decisions(
    comparison: OpportunityComparisonResultV1,
    allocation: CapitalAllocationResultV1,
    comparison_constraints: ComparisonConstraintsV1 | None = None,
    allocation_constraints: CapitalAllocationConstraintsV1 | None = None,
    portfolio_snapshot_ref: ContractReference | None = None,
    *,
    strategy_match_refs: Mapping[str, ContractReference] | None = None,
    forecast_refs: Mapping[str, tuple[ContractReference, ...] | ContractReference] | None = None,
    allocator_version: str = ALLOCATOR_IMPLEMENTATION_VERSION,
    comparator_version: str = COMPARATOR_IMPLEMENTATION_VERSION,
) -> tuple[CapitalAllocationDecisionV1, ...]:
    """Materialize only candidates that the allocator actually evaluated."""
    if not isinstance(comparison, OpportunityComparisonResultV1):
        raise AllocationPersistenceError("COMPARISON_RESULT_INVALID")
    if not isinstance(allocation, CapitalAllocationResultV1):
        raise AllocationPersistenceError("ALLOCATION_RESULT_INVALID")
    if not isinstance(comparison_constraints, ComparisonConstraintsV1):
        raise AllocationPersistenceError("COMPARISON_CONSTRAINTS_REQUIRED")
    if not isinstance(allocation_constraints, CapitalAllocationConstraintsV1):
        raise AllocationPersistenceError("ALLOCATION_CONSTRAINTS_REQUIRED")
    if not isinstance(portfolio_snapshot_ref, ContractReference):
        raise AllocationPersistenceError("PORTFOLIO_SNAPSHOT_REFERENCE_REQUIRED")
    if not _constraint_matches(comparison, comparison_constraints):
        raise AllocationPersistenceError("COMPARISON_SCOPE_MISMATCH")
    if not _constraint_matches(allocation, allocation_constraints):
        raise AllocationPersistenceError("ALLOCATION_SCOPE_MISMATCH")
    if not _constraint_matches(comparison_constraints, allocation_constraints):
        raise AllocationPersistenceError("CONSTRAINT_SCOPE_MISMATCH")
    evaluations = {
        item.candidate.opportunity.opportunity_id: item
        for item in comparison.evaluations
    }
    intents = _intent_by_opportunity(allocation)
    evaluated_ids = tuple(
        candidate.opportunity.opportunity_id for candidate in comparison.eligible_candidates
    )
    allocator_evaluation_ids = {
        evaluation.opportunity_ref.id for evaluation in allocation.evaluations
    }
    if allocator_evaluation_ids != set(evaluated_ids):
        raise AllocationPersistenceError("ALLOCATOR_INPUT_SET_MISMATCH")
    if set(intents) - set(evaluated_ids):
        raise AllocationPersistenceError("ALLOCATOR_INTENT_OUTSIDE_INPUT_SET")
    if any(
        _allocation_evaluation(allocation, opportunity_id).selected
        != (opportunity_id in intents)
        for opportunity_id in evaluated_ids
    ):
        raise AllocationPersistenceError("ALLOCATOR_SELECTION_MISMATCH")

    decision_set_id = allocation_decision_set_id(
        comparison,
        comparison_constraints,
        allocation_constraints,
        allocator_version=allocator_version,
    )
    by_id = {
        item.candidate.opportunity.opportunity_id: item for item in comparison.evaluations
    }
    ordered_refs = tuple(
        ContractReference(kind="opportunity", id=opportunity_id)
        for opportunity_id in evaluated_ids
    )
    no_allocation = not allocation.allocations
    decisions: list[CapitalAllocationDecisionV1] = []
    for rank, candidate in enumerate(comparison.eligible_candidates, start=1):
        opportunity_id = candidate.opportunity.opportunity_id
        evaluation = by_id[opportunity_id]
        allocation_evaluation = _allocation_evaluation(allocation, opportunity_id)
        intent = intents.get(opportunity_id)
        status = (
            AllocationDecisionStatus.NO_ALLOCATION
            if no_allocation
            else (
                AllocationDecisionStatus.SELECTED
                if intent is not None
                else AllocationDecisionStatus.NOT_SELECTED
            )
        )
        vector = evaluation.comparison_vector
        requested_capital = (
            intent.requested_capital
            if intent is not None
            else (
                MoneyMinorUnits(vector.capital_required_minor, comparison.currency, comparison.scale)
                if vector.capital_required_minor is not None
                else None
            )
        )
        requested_buying_power = (
            intent.requested_buying_power
            if intent is not None
            else (
                MoneyMinorUnits(
                    vector.buying_power_required_minor,
                    comparison.currency,
                    comparison.scale,
                )
                if vector.buying_power_required_minor is not None
                else requested_capital
            )
        )
        requested_maximum_loss = (
            intent.requested_maximum_loss
            if intent is not None
            else (
                MoneyMinorUnits(
                    vector.maximum_loss_minor,
                    comparison.currency,
                    comparison.scale,
                )
                if vector.maximum_loss_minor is not None
                else None
            )
        )
        allocated_capital = requested_capital if intent is not None else _zero_money(
            comparison.currency, comparison.scale
        )
        allocated_buying_power = requested_buying_power if intent is not None else _zero_money(
            comparison.currency, comparison.scale
        )
        allocated_maximum_loss = requested_maximum_loss if intent is not None else _zero_money(
            comparison.currency, comparison.scale
        )
        extra_lineage_refs = (
            (
                tuple(evaluation.comparison_vector.lineage_refs)
                + (tuple(intent.lineage_refs) if intent is not None else ())
            )
        )
        lineage = _lineage_refs(candidate, extra_lineage_refs)
        strategy_match_ref = _strategy_match_ref(candidate, strategy_match_refs)
        forecasts = _forecast_refs(candidate, forecast_refs)
        reason_codes = tuple(
            dict.fromkeys(
                (
                    *allocation_evaluation.reasons,
                    *(allocation.no_action_reasons if no_allocation else ()),
                )
            )
        )
        record = CapitalAllocationDecisionV1(
            allocation_decision_id="ALDEC-PENDING",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            decision_set_id=decision_set_id,
            status=status,
            account_id=comparison.account_id,
            mode=comparison.mode,
            decision_time_ns=comparison.decision_time_ns,
            currency=comparison.currency,
            scale=comparison.scale,
            opportunity_ref=ContractReference(kind="opportunity", id=opportunity_id),
            cluster_ref=ContractReference(kind="cluster", id=candidate.cluster_id),
            economic_assessment_ref=ContractReference(
                kind="universal_economic_assessment",
                id=candidate.economic_assessment.assessment_id,
            ),
            strategy_match_ref=strategy_match_ref,
            forecast_refs=forecasts,
            allocation_intent_ref=(
                ContractReference(kind="capital_allocation_intent", id=intent.allocation_id)
                if intent is not None
                else None
            ),
            portfolio_snapshot_ref=portfolio_snapshot_ref,
            comparison_id=comparison.comparison_id,
            comparator_version=comparator_version,
            allocator_version=allocator_version,
            rank=rank,
            competing_opportunity_refs=ordered_refs,
            comparison_constraints=comparison_constraints,
            allocation_constraints=allocation_constraints,
            comparison_vector=vector,
            requested_capital=requested_capital,
            requested_buying_power=requested_buying_power,
            requested_maximum_loss=requested_maximum_loss,
            allocated_capital=allocated_capital,
            allocated_buying_power=allocated_buying_power,
            allocated_maximum_loss=allocated_maximum_loss,
            reason_codes=reason_codes,
            lineage_refs=lineage,
            source_refs=(
                ContractReference(kind="comparison", id=comparison.comparison_id),
                *candidate.economic_assessment.source_refs,
            ),
        )
        identity = allocation_decision_identity_hash(record)
        object.__setattr__(record, "allocation_decision_id", f"ALDEC-{identity}")
        decisions.append(record)
    return tuple(decisions)


def _decision_body(
    record: CapitalAllocationDecisionV1,
    *,
    include_id: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": record.schema_version,
        "decision_set_id": record.decision_set_id,
        "status": record.status.value,
        "account_id": record.account_id,
        "mode": record.mode,
        "decision_time_ns": record.decision_time_ns,
        "currency": record.currency,
        "scale": record.scale,
        "opportunity_ref": contract_reference_to_dict(record.opportunity_ref),
        "cluster_ref": contract_reference_to_dict(record.cluster_ref),
        "economic_assessment_ref": contract_reference_to_dict(record.economic_assessment_ref),
        "strategy_match_ref": (
            contract_reference_to_dict(record.strategy_match_ref)
            if record.strategy_match_ref
            else None
        ),
        "forecast_refs": _refs_to_dict(record.forecast_refs),
        "allocation_intent_ref": (
            contract_reference_to_dict(record.allocation_intent_ref)
            if record.allocation_intent_ref
            else None
        ),
        "portfolio_snapshot_ref": contract_reference_to_dict(record.portfolio_snapshot_ref),
        "comparison_id": record.comparison_id,
        "comparator_version": record.comparator_version,
        "allocator_version": record.allocator_version,
        "rank": record.rank,
        "competing_opportunity_refs": _refs_to_dict(record.competing_opportunity_refs),
        "comparison_constraints": comparison_constraints_to_dict(record.comparison_constraints),
        "allocation_constraints": allocation_constraints_to_dict(record.allocation_constraints),
        "comparison_vector": comparison_vector_to_dict(record.comparison_vector),
        "requested_capital": _money_to_dict(record.requested_capital),
        "requested_buying_power": _money_to_dict(record.requested_buying_power),
        "requested_maximum_loss": _money_to_dict(record.requested_maximum_loss),
        "allocated_capital": _money_to_dict(record.allocated_capital),
        "allocated_buying_power": _money_to_dict(record.allocated_buying_power),
        "allocated_maximum_loss": _money_to_dict(record.allocated_maximum_loss),
        "reason_codes": [code.value for code in record.reason_codes],
        "lineage_refs": _refs_to_dict(record.lineage_refs),
        "source_refs": _refs_to_dict(record.source_refs),
        "implementation_version": record.implementation_version,
    }
    if include_id:
        body["allocation_decision_id"] = record.allocation_decision_id
    return body


def allocation_decision_identity_hash(record: CapitalAllocationDecisionV1) -> str:
    return sha256_bytes(canonical_bytes(_decision_body(record, include_id=False)))


def allocation_decision_v1_to_dict(record: CapitalAllocationDecisionV1) -> dict[str, Any]:
    body = _decision_body(record)
    body["identity_hash"] = allocation_decision_identity_hash(record)
    return body


def _vector_from_dict(payload: Mapping[str, Any]) -> ComparisonVectorV1:
    from .economic_assessment import EconomicUncertaintyV1

    uncertainty_payload = payload.get("uncertainty")
    uncertainty = None
    if uncertainty_payload is not None:
        uncertainty = EconomicUncertaintyV1(
            net_pnl_lower=_money_from_dict(uncertainty_payload.get("net_pnl_lower")),
            net_pnl_upper=_money_from_dict(uncertainty_payload.get("net_pnl_upper")),
            confidence_probability=uncertainty_payload.get("confidence_probability"),
            method=str(uncertainty_payload.get("method", "UNSPECIFIED")),
        )
    from .economic_assessment import AccountActionability, LiquidityState

    return ComparisonVectorV1(
        actionability=AccountActionability(str(payload["actionability"])),
        expected_net_pnl_minor=payload.get("expected_net_pnl_minor"),
        expected_return_bps=payload.get("expected_return_bps"),
        maximum_loss_minor=payload.get("maximum_loss_minor"),
        capital_required_minor=payload.get("capital_required_minor"),
        buying_power_required_minor=payload.get("buying_power_required_minor"),
        initial_margin_required_minor=payload.get("initial_margin_required_minor"),
        maintenance_margin_required_minor=payload.get("maintenance_margin_required_minor"),
        expected_hold_ns=payload.get("expected_hold_ns"),
        maximum_hold_ns=payload.get("maximum_hold_ns"),
        capital_lock_ns=payload.get("capital_lock_ns"),
        fill_probability=payload.get("fill_probability"),
        liquidity_state=(
            LiquidityState(str(payload["liquidity_state"]))
            if payload.get("liquidity_state") is not None
            else None
        ),
        uncertainty=uncertainty,
        factor_refs=_refs_from_dict(payload.get("factor_refs")),
        correlation_refs=_refs_from_dict(payload.get("correlation_refs")),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
    )


def allocation_decision_v1_from_dict(
    payload: Mapping[str, Any],
) -> CapitalAllocationDecisionV1:
    allowed = {field.name for field in fields(CapitalAllocationDecisionV1)} | {"identity_hash"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise AllocationPersistenceError(f"UNKNOWN_FIELDS:{','.join(unknown)}")
    record = CapitalAllocationDecisionV1(
        allocation_decision_id=str(payload["allocation_decision_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        decision_set_id=str(payload["decision_set_id"]),
        status=AllocationDecisionStatus(str(payload["status"])),
        account_id=str(payload["account_id"]),
        mode=str(payload["mode"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        currency=str(payload["currency"]),
        scale=int(payload["scale"]),
        opportunity_ref=contract_reference_from_dict(payload["opportunity_ref"]),
        cluster_ref=contract_reference_from_dict(payload["cluster_ref"]),
        economic_assessment_ref=contract_reference_from_dict(
            payload["economic_assessment_ref"]
        ),
        strategy_match_ref=(
            contract_reference_from_dict(payload["strategy_match_ref"])
            if payload.get("strategy_match_ref")
            else None
        ),
        forecast_refs=_refs_from_dict(payload.get("forecast_refs")),
        allocation_intent_ref=(
            contract_reference_from_dict(payload["allocation_intent_ref"])
            if payload.get("allocation_intent_ref")
            else None
        ),
        portfolio_snapshot_ref=contract_reference_from_dict(
            payload["portfolio_snapshot_ref"]
        ),
        comparison_id=str(payload["comparison_id"]),
        comparator_version=str(payload["comparator_version"]),
        allocator_version=str(payload["allocator_version"]),
        rank=int(payload["rank"]),
        competing_opportunity_refs=_refs_from_dict(
            payload.get("competing_opportunity_refs")
        ),
        comparison_constraints=ComparisonConstraintsV1(
            **{
                key: payload["comparison_constraints"][key]
                for key in (
                    "account_id",
                    "mode",
                    "decision_time_ns",
                    "currency",
                    "scale",
                )
            }
        ),
        allocation_constraints=CapitalAllocationConstraintsV1(
            **payload["allocation_constraints"]
        ),
        comparison_vector=_vector_from_dict(payload["comparison_vector"]),
        requested_capital=_money_from_dict(payload.get("requested_capital")),
        requested_buying_power=_money_from_dict(payload.get("requested_buying_power")),
        requested_maximum_loss=_money_from_dict(payload.get("requested_maximum_loss")),
        allocated_capital=_money_from_dict(payload["allocated_capital"])
        or _zero_money(str(payload["currency"]), int(payload["scale"])),
        allocated_buying_power=_money_from_dict(payload["allocated_buying_power"])
        or _zero_money(str(payload["currency"]), int(payload["scale"])),
        allocated_maximum_loss=_money_from_dict(payload["allocated_maximum_loss"])
        or _zero_money(str(payload["currency"]), int(payload["scale"])),
        reason_codes=tuple(
            ComparisonReasonCode(str(value)) for value in payload.get("reason_codes", ())
        ),
        lineage_refs=_refs_from_dict(payload.get("lineage_refs")),
        source_refs=_refs_from_dict(payload.get("source_refs")),
        implementation_version=str(
            payload.get("implementation_version", ALLOCATION_DECISION_IMPLEMENTATION_VERSION)
        ),
    )
    serialized_hash = payload.get("identity_hash")
    if serialized_hash is not None and serialized_hash != allocation_decision_identity_hash(record):
        raise AllocationPersistenceError("ALLOCATION_DECISION_IDENTITY_HASH_MISMATCH")
    return record


__all__ = [
    "ALLOCATION_DECISION_IMPLEMENTATION_VERSION",
    "AllocationDecisionStatus",
    "AllocationPersistenceError",
    "CapitalAllocationDecisionV1",
    "allocation_decision_identity_hash",
    "allocation_decision_set_id",
    "allocation_decision_v1_from_dict",
    "allocation_decision_v1_to_dict",
    "build_allocation_decisions",
]
