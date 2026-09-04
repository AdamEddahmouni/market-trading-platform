"""Bounded account-scoped opportunity comparison and capital allocation.

This module is a projection over OpportunityV1 and its required universal
economic sidecar.  It deliberately does not create proposals, risk decisions,
orders, or execution calls.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import inf
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    contract_reference_to_dict,
    normalize_unique_refs,
    validate_id,
    validate_timestamp_ns,
)
from ..contracts.opportunity import OpportunityV1
from .economic_assessment import (
    AccountActionability,
    EconomicUncertaintyV1,
    LiquidityState,
    MoneyMinorUnits,
    UniversalEconomicAssessmentV1,
)

COMPARATOR_IMPLEMENTATION_VERSION = "global-opportunity-comparator-v1"
ALLOCATOR_IMPLEMENTATION_VERSION = "greedy-capital-allocator-v1"


class OpportunityComparisonError(ValueError):
    """A comparison input crossed an account, mode, PIT, or unit boundary."""


class ComparisonReasonCode(StrEnum):
    SELECTED = "SELECTED"
    DUPLICATE_THESIS_SUPPRESSED = "DUPLICATE_THESIS_SUPPRESSED"
    INSUFFICIENT_ECONOMICS = "INSUFFICIENT_ECONOMICS"
    AMBIGUOUS_ECONOMICS = "AMBIGUOUS_ECONOMICS"
    NO_POSITIVE_EXPECTED_NET_PNL = "NO_POSITIVE_EXPECTED_NET_PNL"
    ACCOUNT_NOT_ACTIONABLE = "ACCOUNT_NOT_ACTIONABLE"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    INSUFFICIENT_BUYING_POWER = "INSUFFICIENT_BUYING_POWER"
    MAXIMUM_LOSS_BUDGET = "MAXIMUM_LOSS_BUDGET"
    PER_CANDIDATE_CAPITAL_LIMIT = "PER_CANDIDATE_CAPITAL_LIMIT"
    PER_CANDIDATE_LOSS_LIMIT = "PER_CANDIDATE_LOSS_LIMIT"
    CAPITAL_TIME_LIMIT = "CAPITAL_TIME_LIMIT"
    CAPITAL_TIME_UNAVAILABLE = "CAPITAL_TIME_UNAVAILABLE"
    NO_ELIGIBLE_OPPORTUNITIES = "NO_ELIGIBLE_OPPORTUNITIES"
    NO_ACTION = "NO_ACTION"


def _mode(value: str) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE", "PAPER": "PAPER"}.get(normalized, normalized)


def _sorted_refs(refs: Iterable[ContractReference]) -> tuple[ContractReference, ...]:
    return tuple(
        sorted(
            normalize_unique_refs(tuple(refs)),
            key=lambda ref: (ref.kind, ref.id, ref.schema_version),
        )
    )


def _validate_currency_scale(currency: str, scale: int) -> tuple[str, int]:
    normalized = str(currency).strip().upper()
    if len(normalized) != 3:
        raise OpportunityComparisonError("COMPARISON_CURRENCY_INVALID")
    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
        raise OpportunityComparisonError("COMPARISON_SCALE_INVALID")
    return normalized, scale


@dataclass(frozen=True, slots=True)
class OpportunityComparisonCandidateV1:
    """Immutable comparison input carrying one cluster expression and sidecar."""

    cluster_id: str
    opportunity: OpportunityV1
    economic_assessment: UniversalEconomicAssessmentV1

    def __post_init__(self) -> None:
        validate_id(self.cluster_id, field_name="cluster_id")
        if not isinstance(self.opportunity, OpportunityV1):
            raise OpportunityComparisonError("OPPORTUNITY_CANDIDATE_INVALID")
        if not isinstance(self.economic_assessment, UniversalEconomicAssessmentV1):
            raise OpportunityComparisonError("ECONOMIC_ASSESSMENT_REQUIRED")


@dataclass(frozen=True, slots=True)
class ComparisonConstraintsV1:
    """Account, mode, decision-time, and money-unit boundary for comparison."""

    account_id: str
    mode: str
    decision_time_ns: int
    currency: str
    scale: int

    def __post_init__(self) -> None:
        validate_id(self.account_id, field_name="account_id")
        if not str(self.mode).strip():
            raise OpportunityComparisonError("COMPARISON_MODE_REQUIRED")
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        currency, scale = _validate_currency_scale(self.currency, self.scale)
        object.__setattr__(self, "mode", _mode(self.mode))
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "scale", scale)


def comparison_constraints_to_dict(
    constraints: ComparisonConstraintsV1,
) -> dict[str, Any]:
    return {
        "account_id": constraints.account_id,
        "mode": constraints.mode,
        "decision_time_ns": constraints.decision_time_ns,
        "currency": constraints.currency,
        "scale": constraints.scale,
    }


@dataclass(frozen=True, slots=True)
class ComparisonVectorV1:
    """Transparent dimensions used by the documented comparator key."""

    actionability: AccountActionability
    expected_net_pnl_minor: int | None
    expected_return_bps: float | None
    maximum_loss_minor: int | None
    capital_required_minor: int | None
    buying_power_required_minor: int | None
    initial_margin_required_minor: int | None
    maintenance_margin_required_minor: int | None
    expected_hold_ns: int | None
    maximum_hold_ns: int | None
    capital_lock_ns: int | None
    fill_probability: float | None
    liquidity_state: LiquidityState | None
    uncertainty: EconomicUncertaintyV1 | None
    factor_refs: tuple[ContractReference, ...] = ()
    correlation_refs: tuple[ContractReference, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.actionability, AccountActionability):
            object.__setattr__(
                self, "actionability", AccountActionability(str(self.actionability))
            )
        if self.liquidity_state is not None and not isinstance(
            self.liquidity_state, LiquidityState
        ):
            object.__setattr__(
                self, "liquidity_state", LiquidityState(str(self.liquidity_state))
            )
        object.__setattr__(self, "factor_refs", _sorted_refs(self.factor_refs))
        object.__setattr__(self, "correlation_refs", _sorted_refs(self.correlation_refs))
        object.__setattr__(self, "lineage_refs", _sorted_refs(self.lineage_refs))

    @property
    def factor_correlation_refs(self) -> tuple[ContractReference, ...]:
        """Combined provenance view; factor and correlation dimensions stay separate."""
        return _sorted_refs((*self.factor_refs, *self.correlation_refs))

    @property
    def max_loss_minor(self) -> int | None:
        return self.maximum_loss_minor

    def lexicographic_key(
        self, *, cluster_id: str, opportunity_id: str
    ) -> tuple[Any, ...]:
        """The comparator's explicit order, from strongest to weakest.

        Ordering is actionability, expected net P&L, expected return, lower
        maximum loss, lower capital/buying-power use, shorter time locks,
        higher fill probability, liquidity state, lower interval uncertainty,
        then deterministic identifiers.  No aggregate or weighted score is
        computed.
        """
        uncertainty_width: float | int = inf
        uncertainty_confidence: float = -inf
        if self.uncertainty is not None:
            lower = self.uncertainty.net_pnl_lower
            upper = self.uncertainty.net_pnl_upper
            if lower is not None and upper is not None:
                uncertainty_width = upper.amount_minor - lower.amount_minor
            if self.uncertainty.confidence_probability is not None:
                uncertainty_confidence = -self.uncertainty.confidence_probability
        liquidity_order = {
            LiquidityState.AVAILABLE: 0,
            LiquidityState.CONSTRAINED: 1,
            LiquidityState.UNKNOWN: 2,
            LiquidityState.UNAVAILABLE: 3,
        }
        return (
            0 if self.actionability == AccountActionability.ACTIONABLE else 1,
            -(self.expected_net_pnl_minor if self.expected_net_pnl_minor is not None else -inf),
            -(self.expected_return_bps if self.expected_return_bps is not None else -inf),
            self.maximum_loss_minor if self.maximum_loss_minor is not None else inf,
            self.capital_required_minor if self.capital_required_minor is not None else inf,
            self.buying_power_required_minor
            if self.buying_power_required_minor is not None
            else inf,
            self.expected_hold_ns if self.expected_hold_ns is not None else inf,
            self.maximum_hold_ns if self.maximum_hold_ns is not None else inf,
            self.capital_lock_ns if self.capital_lock_ns is not None else inf,
            -(self.fill_probability if self.fill_probability is not None else -inf),
            liquidity_order.get(self.liquidity_state, 2),
            uncertainty_width,
            uncertainty_confidence,
            cluster_id,
            opportunity_id,
        )


def _comparison_money_to_dict(value: MoneyMinorUnits | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "amount_minor": value.amount_minor,
        "currency": value.currency,
        "scale": value.scale,
    }


def comparison_vector_to_dict(vector: ComparisonVectorV1) -> dict[str, Any]:
    uncertainty = None
    if vector.uncertainty is not None:
        uncertainty = {
            "net_pnl_lower": _comparison_money_to_dict(vector.uncertainty.net_pnl_lower),
            "net_pnl_upper": _comparison_money_to_dict(vector.uncertainty.net_pnl_upper),
            "confidence_probability": vector.uncertainty.confidence_probability,
            "method": vector.uncertainty.method,
        }
    return {
        "actionability": vector.actionability.value,
        "expected_net_pnl_minor": vector.expected_net_pnl_minor,
        "expected_return_bps": vector.expected_return_bps,
        "maximum_loss_minor": vector.maximum_loss_minor,
        "capital_required_minor": vector.capital_required_minor,
        "buying_power_required_minor": vector.buying_power_required_minor,
        "initial_margin_required_minor": vector.initial_margin_required_minor,
        "maintenance_margin_required_minor": vector.maintenance_margin_required_minor,
        "expected_hold_ns": vector.expected_hold_ns,
        "maximum_hold_ns": vector.maximum_hold_ns,
        "capital_lock_ns": vector.capital_lock_ns,
        "fill_probability": vector.fill_probability,
        "liquidity_state": (
            vector.liquidity_state.value if vector.liquidity_state is not None else None
        ),
        "uncertainty": uncertainty,
        "factor_refs": [contract_reference_to_dict(ref) for ref in vector.factor_refs],
        "correlation_refs": [
            contract_reference_to_dict(ref) for ref in vector.correlation_refs
        ],
        "lineage_refs": [contract_reference_to_dict(ref) for ref in vector.lineage_refs],
    }


@dataclass(frozen=True, slots=True)
class ComparisonEvaluationV1:
    candidate: OpportunityComparisonCandidateV1
    comparison_vector: ComparisonVectorV1
    eligible: bool
    reasons: tuple[ComparisonReasonCode, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonObservabilityV1:
    candidates_seen: int
    eligible_candidates: int
    excluded_candidates: int
    duplicate_thesis_suppressed: int
    insufficient_economics: int
    no_action: int


@dataclass(frozen=True, slots=True)
class OpportunityComparisonResultV1:
    account_id: str
    mode: str
    decision_time_ns: int
    currency: str
    scale: int
    eligible_candidates: tuple[OpportunityComparisonCandidateV1, ...]
    evaluations: tuple[ComparisonEvaluationV1, ...]
    counters: ComparisonObservabilityV1
    no_action_reasons: tuple[ComparisonReasonCode, ...] = ()

    @property
    def selected_candidates(self) -> tuple[OpportunityComparisonCandidateV1, ...]:
        return self.eligible_candidates

    @property
    def excluded_evaluations(self) -> tuple[ComparisonEvaluationV1, ...]:
        return tuple(item for item in self.evaluations if not item.eligible)

    @property
    def comparison_id(self) -> str:
        return f"CMP-{opportunity_comparison_identity_hash(self)}"

    @property
    def comparator_version(self) -> str:
        return COMPARATOR_IMPLEMENTATION_VERSION


def _metadata_refs(
    metadata: Mapping[str, Any], key: str, default_kind: str
) -> tuple[ContractReference, ...]:
    values = metadata.get(key, ())
    if values is None:
        return ()
    if isinstance(values, (str, ContractReference, Mapping)):
        values = (values,)
    refs: list[ContractReference] = []
    for value in values:
        if isinstance(value, ContractReference):
            refs.append(value)
        elif isinstance(value, Mapping):
            refs.append(
                ContractReference(
                    kind=str(value.get("kind", default_kind)),
                    id=str(value["id"]),
                    schema_version=str(value.get("schema_version", "1")),
                )
            )
        else:
            refs.append(ContractReference(kind=default_kind, id=str(value)))
    return _sorted_refs(refs)


def _money_amount(value: MoneyMinorUnits | None) -> int | None:
    return value.amount_minor if value is not None else None


def _vector(candidate: OpportunityComparisonCandidateV1) -> ComparisonVectorV1:
    sidecar = candidate.economic_assessment
    metadata = sidecar.metadata
    factor_refs = list(_metadata_refs(metadata, "factor_refs", "factor"))
    factor_refs.extend(
        ContractReference(kind="factor", id=exposure.factor_id)
        for exposure in sidecar.factor_exposures
        if ContractReference(kind="factor", id=exposure.factor_id) not in factor_refs
    )
    lineage = _sorted_refs(
        (
            *candidate.opportunity.lineage_refs,
            *sidecar.source_refs,
            *sidecar.lineage_refs,
            ContractReference(
                kind="opportunity", id=candidate.opportunity.opportunity_id
            ),
            ContractReference(
                kind="universal_economic_assessment", id=sidecar.assessment_id
            ),
        )
    )
    return ComparisonVectorV1(
        actionability=sidecar.account_actionability,
        expected_net_pnl_minor=_money_amount(sidecar.expected_net_pnl),
        expected_return_bps=sidecar.expected_return_bps,
        maximum_loss_minor=_money_amount(sidecar.maximum_loss),
        capital_required_minor=_money_amount(sidecar.capital_required),
        buying_power_required_minor=_money_amount(sidecar.buying_power_required),
        initial_margin_required_minor=_money_amount(sidecar.initial_margin_required),
        maintenance_margin_required_minor=_money_amount(sidecar.maintenance_margin_required),
        expected_hold_ns=sidecar.expected_hold_ns,
        maximum_hold_ns=sidecar.maximum_hold_ns,
        capital_lock_ns=sidecar.capital_lock_ns,
        fill_probability=sidecar.fill_probability,
        liquidity_state=sidecar.liquidity.state if sidecar.liquidity else None,
        uncertainty=sidecar.uncertainty,
        factor_refs=_sorted_refs(factor_refs),
        correlation_refs=_metadata_refs(metadata, "correlation_refs", "correlation"),
        lineage_refs=lineage,
    )


def _validate_candidate(
    candidate: OpportunityComparisonCandidateV1, constraints: ComparisonConstraintsV1
) -> None:
    opportunity = candidate.opportunity
    sidecar = candidate.economic_assessment
    if sidecar.scope != opportunity.scope:
        raise OpportunityComparisonError("ECONOMIC_ASSESSMENT_SCOPE_MISMATCH")
    if any(
        key in {"universal_score", "opaque_score", "economic_score"}
        for key in opportunity.metadata
    ):
        raise OpportunityComparisonError("OPAQUE_COMPARISON_SCORE_FORBIDDEN")
    if sidecar.account_id != constraints.account_id:
        raise OpportunityComparisonError("ECONOMIC_ASSESSMENT_ACCOUNT_SCOPE_MISMATCH")
    if _mode(sidecar.mode) != constraints.mode:
        raise OpportunityComparisonError("ECONOMIC_ASSESSMENT_MODE_SCOPE_MISMATCH")
    for key, expected in (("account_id", constraints.account_id), ("mode", constraints.mode)):
        value = opportunity.metadata.get(key)
        if value is not None and (
            _mode(str(value)) if key == "mode" else str(value)
        ) != expected:
            raise OpportunityComparisonError(f"OPPORTUNITY_{key.upper()}_SCOPE_MISMATCH")
    if opportunity.created_at_ns > constraints.decision_time_ns:
        raise OpportunityComparisonError("OPPORTUNITY_AFTER_DECISION")
    if opportunity.valid_until_ns is not None and constraints.decision_time_ns >= opportunity.valid_until_ns:
        raise OpportunityComparisonError("OPPORTUNITY_EXPIRED")
    if sidecar.assessed_at_ns > constraints.decision_time_ns:
        raise OpportunityComparisonError("ECONOMIC_ASSESSMENT_AFTER_DECISION")
    if sidecar.expires_at_ns is not None and constraints.decision_time_ns >= sidecar.expires_at_ns:
        raise OpportunityComparisonError("ECONOMIC_ASSESSMENT_EXPIRED")
    monies = (
        sidecar.expected_gross_pnl,
        sidecar.expected_net_pnl,
        sidecar.capital_required,
        sidecar.buying_power_required,
        sidecar.initial_margin_required,
        sidecar.maintenance_margin_required,
        sidecar.maximum_loss,
        sidecar.tail_loss,
    )
    if sidecar.uncertainty is not None:
        monies += (
            sidecar.uncertainty.net_pnl_lower,
            sidecar.uncertainty.net_pnl_upper,
        )
    monies += tuple(
        exposure.exposure for exposure in sidecar.factor_exposures if exposure.exposure
    )
    for money in monies:
        if money is not None and (money.currency, money.scale) != (
            constraints.currency,
            constraints.scale,
        ):
            raise OpportunityComparisonError("MONEY_CURRENCY_SCALE_MISMATCH")


def _economic_reasons(vector: ComparisonVectorV1) -> tuple[ComparisonReasonCode, ...]:
    reasons: list[ComparisonReasonCode] = []
    if (
        vector.expected_net_pnl_minor is None
        or vector.maximum_loss_minor is None
        or vector.capital_required_minor is None
    ):
        reasons.append(ComparisonReasonCode.INSUFFICIENT_ECONOMICS)
    if any(
        value is not None and value < 0
        for value in (
            vector.capital_required_minor,
            vector.buying_power_required_minor,
            vector.maximum_loss_minor,
        )
    ):
        reasons.append(ComparisonReasonCode.AMBIGUOUS_ECONOMICS)
    if vector.expected_net_pnl_minor is not None and vector.expected_net_pnl_minor <= 0:
        reasons.append(ComparisonReasonCode.NO_POSITIVE_EXPECTED_NET_PNL)
    if vector.actionability != AccountActionability.ACTIONABLE:
        reasons.append(ComparisonReasonCode.ACCOUNT_NOT_ACTIONABLE)
    return tuple(dict.fromkeys(reasons))


class GlobalOpportunityComparator:
    """Deterministically compare one account/mode/PIT candidate universe."""

    def compare(
        self,
        constraints: ComparisonConstraintsV1,
        candidates: Iterable[OpportunityComparisonCandidateV1],
    ) -> OpportunityComparisonResultV1:
        if not isinstance(constraints, ComparisonConstraintsV1):
            raise OpportunityComparisonError("COMPARISON_CONSTRAINTS_INVALID")
        normalized = tuple(candidates)
        if any(not isinstance(item, OpportunityComparisonCandidateV1) for item in normalized):
            raise OpportunityComparisonError("COMPARISON_CANDIDATE_INVALID")
        if len({item.opportunity.opportunity_id for item in normalized}) != len(normalized):
            raise OpportunityComparisonError("DUPLICATE_OPPORTUNITY_ID")

        evaluations: list[ComparisonEvaluationV1] = []
        by_cluster: dict[str, list[ComparisonEvaluationV1]] = defaultdict(list)
        insufficient = 0
        for candidate in normalized:
            _validate_candidate(candidate, constraints)
            vector = _vector(candidate)
            reasons = _economic_reasons(vector)
            if ComparisonReasonCode.INSUFFICIENT_ECONOMICS in reasons:
                insufficient += 1
            evaluation = ComparisonEvaluationV1(
                candidate=candidate,
                comparison_vector=vector,
                eligible=not reasons,
                reasons=reasons,
            )
            evaluations.append(evaluation)
            if evaluation.eligible:
                by_cluster[candidate.cluster_id].append(evaluation)

        winners: list[OpportunityComparisonCandidateV1] = []
        updated: dict[str, ComparisonEvaluationV1] = {
            item.candidate.opportunity.opportunity_id: item for item in evaluations
        }
        duplicate_count = 0
        for cluster_id, members in by_cluster.items():
            ordered = sorted(
                members,
                key=lambda item: item.comparison_vector.lexicographic_key(
                    cluster_id=cluster_id,
                    opportunity_id=item.candidate.opportunity.opportunity_id,
                ),
            )
            winners.append(ordered[0].candidate)
            for duplicate in ordered[1:]:
                duplicate_count += 1
                updated_id = duplicate.candidate.opportunity.opportunity_id
                updated[updated_id] = ComparisonEvaluationV1(
                    candidate=duplicate.candidate,
                    comparison_vector=duplicate.comparison_vector,
                    eligible=False,
                    reasons=(
                        *duplicate.reasons,
                        ComparisonReasonCode.DUPLICATE_THESIS_SUPPRESSED,
                    ),
                )

        winners.sort(
            key=lambda item: _vector(item).lexicographic_key(
                cluster_id=item.cluster_id,
                opportunity_id=item.opportunity.opportunity_id,
            )
        )
        ordered_evaluations = tuple(
            updated[key]
            for key in sorted(updated, key=lambda value: (value,))
        )
        no_action = (
            (ComparisonReasonCode.NO_ACTION, ComparisonReasonCode.NO_ELIGIBLE_OPPORTUNITIES)
            if not winners
            else ()
        )
        counters = ComparisonObservabilityV1(
            candidates_seen=len(normalized),
            eligible_candidates=len(winners),
            excluded_candidates=len(normalized) - len(winners),
            duplicate_thesis_suppressed=duplicate_count,
            insufficient_economics=insufficient,
            no_action=int(not winners),
        )
        return OpportunityComparisonResultV1(
            account_id=constraints.account_id,
            mode=constraints.mode,
            decision_time_ns=constraints.decision_time_ns,
            currency=constraints.currency,
            scale=constraints.scale,
            eligible_candidates=tuple(winners),
            evaluations=ordered_evaluations,
            counters=counters,
            no_action_reasons=no_action,
        )


@dataclass(frozen=True, slots=True)
class CapitalAllocationConstraintsV1:
    """Explicit account budgets consumed after comparison."""

    account_id: str
    mode: str
    decision_time_ns: int
    currency: str
    scale: int
    available_capital_minor: int
    available_buying_power_minor: int
    maximum_loss_budget_minor: int
    capital_time_budget_minor_ns: int | None = None
    max_capital_per_candidate_minor: int | None = None
    max_loss_per_candidate_minor: int | None = None

    def __post_init__(self) -> None:
        validate_id(self.account_id, field_name="account_id")
        if not str(self.mode).strip():
            raise OpportunityComparisonError("ALLOCATION_MODE_REQUIRED")
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        currency, scale = _validate_currency_scale(self.currency, self.scale)
        object.__setattr__(self, "mode", _mode(self.mode))
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "scale", scale)
        for name in (
            "available_capital_minor",
            "available_buying_power_minor",
            "maximum_loss_budget_minor",
            "capital_time_budget_minor_ns",
            "max_capital_per_candidate_minor",
            "max_loss_per_candidate_minor",
        ):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise OpportunityComparisonError(f"{name.upper()}_INVALID")


def allocation_constraints_to_dict(
    constraints: CapitalAllocationConstraintsV1,
) -> dict[str, Any]:
    return {
        "account_id": constraints.account_id,
        "mode": constraints.mode,
        "decision_time_ns": constraints.decision_time_ns,
        "currency": constraints.currency,
        "scale": constraints.scale,
        "available_capital_minor": constraints.available_capital_minor,
        "available_buying_power_minor": constraints.available_buying_power_minor,
        "maximum_loss_budget_minor": constraints.maximum_loss_budget_minor,
        "capital_time_budget_minor_ns": constraints.capital_time_budget_minor_ns,
        "max_capital_per_candidate_minor": constraints.max_capital_per_candidate_minor,
        "max_loss_per_candidate_minor": constraints.max_loss_per_candidate_minor,
    }


@dataclass(frozen=True, slots=True)
class CapitalAllocationIntentV1:
    """Immutable capital reservation intent; deliberately not an order/proposal."""

    allocation_id: str
    schema_version: str
    account_id: str
    mode: str
    decision_time_ns: int
    cluster_id: str
    opportunity_ref: ContractReference
    economic_assessment_ref: ContractReference
    requested_capital: MoneyMinorUnits
    requested_buying_power: MoneyMinorUnits
    requested_maximum_loss: MoneyMinorUnits
    capital_lock_ns: int
    reasons: tuple[ComparisonReasonCode, ...]
    lineage_refs: tuple[ContractReference, ...] = ()

    def __post_init__(self) -> None:
        validate_id(self.allocation_id, field_name="allocation_id")
        validate_id(self.account_id, field_name="account_id")
        validate_id(self.cluster_id, field_name="cluster_id")
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if self.capital_lock_ns < 0:
            raise OpportunityComparisonError("CAPITAL_LOCK_INVALID")
        for ref in (self.opportunity_ref, self.economic_assessment_ref):
            if not isinstance(ref, ContractReference):
                raise OpportunityComparisonError("ALLOCATION_REFERENCE_INVALID")
        for money in (
            self.requested_capital,
            self.requested_buying_power,
            self.requested_maximum_loss,
        ):
            if not isinstance(money, MoneyMinorUnits):
                raise OpportunityComparisonError("ALLOCATION_MONEY_INVALID")
        object.__setattr__(self, "lineage_refs", _sorted_refs(self.lineage_refs))

    @property
    def requested_capital_minor(self) -> int:
        return self.requested_capital.amount_minor

    @property
    def requested_buying_power_minor(self) -> int:
        return self.requested_buying_power.amount_minor

    @property
    def requested_maximum_loss_minor(self) -> int:
        return self.requested_maximum_loss.amount_minor


@dataclass(frozen=True, slots=True)
class AllocationEvaluationV1:
    opportunity_ref: ContractReference
    selected: bool
    reasons: tuple[ComparisonReasonCode, ...]


@dataclass(frozen=True, slots=True)
class AllocationObservabilityV1:
    candidates_seen: int
    selected_candidates: int
    excluded_candidates: int
    insufficient_capital: int
    insufficient_buying_power: int
    maximum_loss_budget: int
    capital_time_limit: int
    capital_time_unavailable: int
    no_action: int


@dataclass(frozen=True, slots=True)
class CapitalAllocationResultV1:
    account_id: str
    mode: str
    decision_time_ns: int
    currency: str
    scale: int
    allocations: tuple[CapitalAllocationIntentV1, ...]
    evaluations: tuple[AllocationEvaluationV1, ...]
    counters: AllocationObservabilityV1
    no_action_reasons: tuple[ComparisonReasonCode, ...] = ()

    @property
    def selected_intents(self) -> tuple[CapitalAllocationIntentV1, ...]:
        return self.allocations

    @property
    def reason_codes(self) -> tuple[ComparisonReasonCode, ...]:
        return self.no_action_reasons

    def reason_codes_for(self, opportunity_id: str) -> tuple[ComparisonReasonCode, ...]:
        for evaluation in self.evaluations:
            if evaluation.opportunity_ref.id == opportunity_id:
                return evaluation.reasons
        return ()


def _allocation_id(
    candidate: OpportunityComparisonCandidateV1,
    constraints: CapitalAllocationConstraintsV1,
) -> str:
    payload = {
        "account_id": constraints.account_id,
        "mode": constraints.mode,
        "decision_time_ns": constraints.decision_time_ns,
        "cluster_id": candidate.cluster_id,
        "opportunity_id": candidate.opportunity.opportunity_id,
        "assessment_id": candidate.economic_assessment.assessment_id,
    }
    return f"ALLOC-{sha256_bytes(canonical_bytes(payload))}"


class CapitalAllocator:
    """Greedy deterministic allocator over comparator-approved expressions."""

    def allocate(
        self,
        comparison: OpportunityComparisonResultV1,
        constraints: CapitalAllocationConstraintsV1,
    ) -> CapitalAllocationResultV1:
        if not isinstance(comparison, OpportunityComparisonResultV1):
            raise OpportunityComparisonError("COMPARISON_RESULT_INVALID")
        if not isinstance(constraints, CapitalAllocationConstraintsV1):
            raise OpportunityComparisonError("ALLOCATION_CONSTRAINTS_INVALID")
        if (
            comparison.account_id != constraints.account_id
            or comparison.mode != constraints.mode
            or comparison.decision_time_ns != constraints.decision_time_ns
            or comparison.currency != constraints.currency
            or comparison.scale != constraints.scale
        ):
            raise OpportunityComparisonError("ALLOCATION_SCOPE_MISMATCH")

        by_id = {
            item.candidate.opportunity.opportunity_id: item
            for item in comparison.evaluations
        }
        remaining_capital = constraints.available_capital_minor
        remaining_buying_power = constraints.available_buying_power_minor
        remaining_loss = constraints.maximum_loss_budget_minor
        remaining_capital_time = constraints.capital_time_budget_minor_ns
        allocations: list[CapitalAllocationIntentV1] = []
        evaluations: list[AllocationEvaluationV1] = []
        counts = {
            ComparisonReasonCode.INSUFFICIENT_CAPITAL: 0,
            ComparisonReasonCode.INSUFFICIENT_BUYING_POWER: 0,
            ComparisonReasonCode.MAXIMUM_LOSS_BUDGET: 0,
            ComparisonReasonCode.CAPITAL_TIME_LIMIT: 0,
            ComparisonReasonCode.CAPITAL_TIME_UNAVAILABLE: 0,
        }
        for candidate in comparison.eligible_candidates:
            evaluation = by_id[candidate.opportunity.opportunity_id]
            vector = evaluation.comparison_vector
            capital = vector.capital_required_minor
            maximum_loss = vector.maximum_loss_minor
            buying_power = vector.buying_power_required_minor
            if buying_power is None:
                # A sidecar without a separate margin estimate is explicitly
                # compared and allocated against its stated capital requirement.
                buying_power = capital
            reasons: list[ComparisonReasonCode] = []
            if capital is None or maximum_loss is None or buying_power is None:
                reasons.append(ComparisonReasonCode.INSUFFICIENT_ECONOMICS)
            elif constraints.max_capital_per_candidate_minor is not None and capital > constraints.max_capital_per_candidate_minor:
                reasons.append(ComparisonReasonCode.PER_CANDIDATE_CAPITAL_LIMIT)
            elif constraints.max_loss_per_candidate_minor is not None and maximum_loss > constraints.max_loss_per_candidate_minor:
                reasons.append(ComparisonReasonCode.PER_CANDIDATE_LOSS_LIMIT)
            elif capital > remaining_capital:
                reasons.append(ComparisonReasonCode.INSUFFICIENT_CAPITAL)
            elif buying_power > remaining_buying_power:
                reasons.append(ComparisonReasonCode.INSUFFICIENT_BUYING_POWER)
            elif maximum_loss > remaining_loss:
                reasons.append(ComparisonReasonCode.MAXIMUM_LOSS_BUDGET)
            elif remaining_capital_time is not None:
                if vector.capital_lock_ns is None:
                    reasons.append(ComparisonReasonCode.CAPITAL_TIME_UNAVAILABLE)
                elif capital * vector.capital_lock_ns > remaining_capital_time:
                    reasons.append(ComparisonReasonCode.CAPITAL_TIME_LIMIT)
            if reasons:
                for reason in reasons:
                    if reason in counts:
                        counts[reason] += 1
                evaluations.append(
                    AllocationEvaluationV1(
                        opportunity_ref=ContractReference(
                            kind="opportunity", id=candidate.opportunity.opportunity_id
                        ),
                        selected=False,
                        reasons=tuple(reasons),
                    )
                )
                continue
            assert capital is not None and maximum_loss is not None and buying_power is not None
            assert vector.capital_lock_ns is not None or remaining_capital_time is None
            sidecar = candidate.economic_assessment
            intent = CapitalAllocationIntentV1(
                allocation_id=_allocation_id(candidate, constraints),
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                account_id=constraints.account_id,
                mode=constraints.mode,
                decision_time_ns=constraints.decision_time_ns,
                cluster_id=candidate.cluster_id,
                opportunity_ref=ContractReference(
                    kind="opportunity", id=candidate.opportunity.opportunity_id
                ),
                economic_assessment_ref=ContractReference(
                    kind="universal_economic_assessment", id=sidecar.assessment_id
                ),
                requested_capital=MoneyMinorUnits(
                    capital, constraints.currency, constraints.scale
                ),
                requested_buying_power=MoneyMinorUnits(
                    buying_power, constraints.currency, constraints.scale
                ),
                requested_maximum_loss=MoneyMinorUnits(
                    maximum_loss, constraints.currency, constraints.scale
                ),
                capital_lock_ns=vector.capital_lock_ns or 0,
                reasons=(ComparisonReasonCode.SELECTED,),
                lineage_refs=vector.lineage_refs,
            )
            allocations.append(intent)
            evaluations.append(
                AllocationEvaluationV1(
                    opportunity_ref=intent.opportunity_ref,
                    selected=True,
                    reasons=intent.reasons,
                )
            )
            remaining_capital -= capital
            remaining_buying_power -= buying_power
            remaining_loss -= maximum_loss
            if remaining_capital_time is not None:
                remaining_capital_time -= capital * (vector.capital_lock_ns or 0)

        no_action = (
            (ComparisonReasonCode.NO_ACTION, ComparisonReasonCode.NO_ELIGIBLE_OPPORTUNITIES)
            if not allocations
            else ()
        )
        return CapitalAllocationResultV1(
            account_id=constraints.account_id,
            mode=constraints.mode,
            decision_time_ns=constraints.decision_time_ns,
            currency=constraints.currency,
            scale=constraints.scale,
            allocations=tuple(allocations),
            evaluations=tuple(
                sorted(evaluations, key=lambda item: item.opportunity_ref.id)
            ),
            counters=AllocationObservabilityV1(
                candidates_seen=len(comparison.eligible_candidates),
                selected_candidates=len(allocations),
                excluded_candidates=len(evaluations) - len(allocations),
                insufficient_capital=counts[ComparisonReasonCode.INSUFFICIENT_CAPITAL],
                insufficient_buying_power=counts[ComparisonReasonCode.INSUFFICIENT_BUYING_POWER],
                maximum_loss_budget=counts[ComparisonReasonCode.MAXIMUM_LOSS_BUDGET],
                capital_time_limit=counts[ComparisonReasonCode.CAPITAL_TIME_LIMIT],
                capital_time_unavailable=counts[
                    ComparisonReasonCode.CAPITAL_TIME_UNAVAILABLE
                ],
                no_action=int(not allocations),
            ),
            no_action_reasons=no_action,
        )


def compare_opportunities(
    *,
    constraints: ComparisonConstraintsV1,
    candidates: Iterable[OpportunityComparisonCandidateV1],
) -> OpportunityComparisonResultV1:
    """Functional entry point for the account-scoped comparator."""
    return GlobalOpportunityComparator().compare(constraints, candidates)


def allocate_capital(
    *,
    comparison: OpportunityComparisonResultV1,
    constraints: CapitalAllocationConstraintsV1,
) -> CapitalAllocationResultV1:
    """Functional entry point for the independent allocator."""
    return CapitalAllocator().allocate(comparison, constraints)


def opportunity_comparison_identity_payload(
    result: OpportunityComparisonResultV1,
) -> dict[str, Any]:
    return {
        "account_id": result.account_id,
        "mode": result.mode,
        "decision_time_ns": result.decision_time_ns,
        "currency": result.currency,
        "scale": result.scale,
        "comparator_version": COMPARATOR_IMPLEMENTATION_VERSION,
        "evaluations": [
            {
                "opportunity_id": evaluation.candidate.opportunity.opportunity_id,
                "cluster_id": evaluation.candidate.cluster_id,
                "eligible": evaluation.eligible,
                "reasons": [reason.value for reason in evaluation.reasons],
                "comparison_vector": comparison_vector_to_dict(
                    evaluation.comparison_vector
                ),
            }
            for evaluation in result.evaluations
        ],
    }


def opportunity_comparison_identity_hash(
    result: OpportunityComparisonResultV1,
) -> str:
    return sha256_bytes(canonical_bytes(opportunity_comparison_identity_payload(result)))


# Discoverable compatibility names without creating additional authorities.
ComparisonCandidateV1 = OpportunityComparisonCandidateV1
OpportunityComparisonInputV1 = OpportunityComparisonCandidateV1
OpportunityComparisonConstraintsV1 = ComparisonConstraintsV1
AccountComparisonConstraintsV1 = ComparisonConstraintsV1
GlobalOpportunityComparisonResultV1 = OpportunityComparisonResultV1
AllocationIntentV1 = CapitalAllocationIntentV1
CapitalAllocationBudgetV1 = CapitalAllocationConstraintsV1

__all__ = [
    "ALLOCATOR_IMPLEMENTATION_VERSION",
    "COMPARATOR_IMPLEMENTATION_VERSION",
    "AllocationEvaluationV1",
    "AllocationIntentV1",
    "AccountComparisonConstraintsV1",
    "allocate_capital",
    "CapitalAllocationBudgetV1",
    "CapitalAllocationConstraintsV1",
    "CapitalAllocationIntentV1",
    "CapitalAllocationResultV1",
    "CapitalAllocator",
    "ComparisonCandidateV1",
    "ComparisonConstraintsV1",
    "ComparisonEvaluationV1",
    "ComparisonObservabilityV1",
    "ComparisonReasonCode",
    "ComparisonVectorV1",
    "allocation_constraints_to_dict",
    "GlobalOpportunityComparator",
    "GlobalOpportunityComparisonResultV1",
    "compare_opportunities",
    "comparison_constraints_to_dict",
    "comparison_vector_to_dict",
    "opportunity_comparison_identity_hash",
    "opportunity_comparison_identity_payload",
    "OpportunityComparisonCandidateV1",
    "OpportunityComparisonConstraintsV1",
    "OpportunityComparisonError",
    "OpportunityComparisonInputV1",
    "OpportunityComparisonResultV1",
]
