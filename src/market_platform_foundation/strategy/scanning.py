"""Bounded, deterministic universal strategy scanning."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    StrategyConditionResult,
    StrategyMatch,
    StrategyMatchDisposition,
)
from ..intelligence.persistence.repository import IntelligenceRepository
from ..intelligence.quality import (
    DEFAULT_QUALITY_POLICY,
    DecisionAction,
    IntelligenceCapability,
    QualityPolicy,
    QualityAssessment,
    QualityDecision,
    RequirementSet,
    decide_quality,
    quality_state_for_action,
)
from ..intelligence.temporal import DEFAULT_TEMPORAL_POLICY, TemporalIntegrityPolicy
from ..providers.identity import InstrumentIdentity
from ..providers.planner import QueryPlan, QueryPlanner, QueryRequest
from .strategy_spec import StrategyDefinition


class ScanTriggerType(StrEnum):
    """Trigger metadata accepted by the one-pass scanner."""

    SCHEDULED = "SCHEDULED"
    EVENT = "EVENT"
    SESSION_OPEN = "SESSION_OPEN"
    PERIODIC = "PERIODIC"


@dataclass(frozen=True, slots=True)
class ScanTrigger:
    trigger_type: ScanTriggerType
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.trigger_type, ScanTriggerType):
            object.__setattr__(self, "trigger_type", ScanTriggerType(str(self.trigger_type)))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class PointInTimeUniverse:
    """Explicit, immutable instrument universe at one availability cutoff."""

    as_of_time_ns: int
    instruments: tuple[InstrumentIdentity, ...] = ()

    def __post_init__(self) -> None:
        _validate_timestamp(self.as_of_time_ns, "universe.as_of_time_ns")
        unique = {instrument.qualified_id(): instrument for instrument in self.instruments}
        object.__setattr__(
            self,
            "instruments",
            tuple(unique[key] for key in sorted(unique)),
        )


@dataclass(frozen=True, slots=True)
class CapabilityContextSnapshot:
    """PIT capability and context state supplied to a scan."""

    snapshot_id: str
    as_of_time_ns: int
    quality_assessment: QualityAssessment
    source_snapshot_ref: ContractReference | None = None
    source_evidence_refs: tuple[ContractReference, ...] = ()
    source_signal_refs: tuple[ContractReference, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)
    regime: str | None = None

    def __post_init__(self) -> None:
        if not str(self.snapshot_id).strip():
            raise ValueError("SCAN_SNAPSHOT_ID_REQUIRED")
        _validate_timestamp(self.as_of_time_ns, "capability_snapshot.as_of_time_ns")
        if self.quality_assessment.decision_time_ns != self.as_of_time_ns:
            raise ValueError("SCAN_QUALITY_SNAPSHOT_TIME_MISMATCH")
        if self.source_snapshot_ref is None:
            object.__setattr__(
                self,
                "source_snapshot_ref",
                ContractReference(kind="snapshot", id=self.snapshot_id),
            )
        elif self.source_snapshot_ref.kind != "snapshot":
            raise ValueError("SCAN_SNAPSHOT_REF_KIND_INVALID")
        object.__setattr__(self, "source_evidence_refs", _normalize_refs(self.source_evidence_refs))
        object.__setattr__(self, "source_signal_refs", _normalize_refs(self.source_signal_refs))
        object.__setattr__(self, "lineage_refs", _normalize_refs(self.lineage_refs))
        object.__setattr__(self, "context", _freeze_mapping(self.context))

    @property
    def quality(self) -> QualitySummary:
        from ..intelligence.quality import quality_summary_from_assessment

        return quality_summary_from_assessment(self.quality_assessment)


@dataclass(frozen=True, slots=True)
class ScanScope:
    account_id: str
    mode: str

    def __post_init__(self) -> None:
        if not str(self.account_id).strip():
            raise ValueError("SCAN_ACCOUNT_ID_REQUIRED")
        mode = str(self.mode).strip().lower()
        if mode not in {"research", "historical", "replay", "demo", "paper", "live"}:
            raise ValueError("SCAN_MODE_INVALID")
        object.__setattr__(self, "account_id", str(self.account_id))
        object.__setattr__(self, "mode", mode)


@dataclass(frozen=True, slots=True)
class ScanBudget:
    max_evaluations: int = 1_000
    max_cost_units: int = 1_000

    def __post_init__(self) -> None:
        if self.max_evaluations < 0 or self.max_cost_units < 0:
            raise ValueError("SCAN_BUDGET_INVALID")


@dataclass(frozen=True, slots=True)
class CheapScreenResult:
    eligible: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.eligible and not (self.reason and self.reason.strip()):
            raise ValueError("CHEAP_SCREEN_REASON_REQUIRED")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("CHEAP_SCREEN_REASON_INVALID")


@dataclass(frozen=True, slots=True)
class StrategyEvaluationResult:
    disposition: StrategyMatchDisposition
    condition_results: tuple[StrategyConditionResult, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    abstention_reasons: tuple[str, ...] = ()
    unavailability_reasons: tuple[str, ...] = ()
    regime: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, StrategyMatchDisposition):
            object.__setattr__(
                self,
                "disposition",
                StrategyMatchDisposition(str(self.disposition)),
            )


@dataclass(frozen=True, slots=True)
class StrategyRegistration:
    """A strategy evaluator and its declared Stage A admission needs."""

    strategy_id: str
    definition: StrategyDefinition
    evaluator: Callable[["StrategyEvaluationContext"], StrategyEvaluationResult]
    required_capabilities: tuple[str, ...] = ()
    cheap_screen: Callable[["StrategyEvaluationContext"], CheapScreenResult | bool] | None = None
    cost_units: int = 1
    failure_action: DecisionAction = DecisionAction.FAIL_CLOSED
    allow_degraded: bool = False

    def __post_init__(self) -> None:
        if not str(self.strategy_id).strip():
            raise ValueError("STRATEGY_ID_REQUIRED")
        object.__setattr__(
            self,
            "required_capabilities",
            tuple(sorted({str(value).strip() for value in self.required_capabilities if str(value).strip()})),
        )
        if self.cost_units <= 0:
            raise ValueError("STRATEGY_COST_UNITS_INVALID")
        if not isinstance(self.failure_action, DecisionAction):
            object.__setattr__(self, "failure_action", DecisionAction(str(self.failure_action)))


@dataclass(frozen=True, slots=True)
class ScanRequest:
    universe: PointInTimeUniverse
    capability_snapshot: CapabilityContextSnapshot
    strategies: tuple[StrategyRegistration, ...]
    scope: ScanScope
    trigger: ScanTrigger
    decision_time_ns: int
    expires_at_ns: int
    budget: ScanBudget = field(default_factory=ScanBudget)

    def __post_init__(self) -> None:
        _validate_timestamp(self.decision_time_ns, "scan.decision_time_ns")
        _validate_timestamp(self.expires_at_ns, "scan.expires_at_ns")
        if self.expires_at_ns <= self.decision_time_ns:
            raise ValueError("SCAN_EXPIRY_INVALID")
        if self.universe.as_of_time_ns != self.decision_time_ns:
            raise ValueError("SCAN_UNIVERSE_TIME_MISMATCH")
        if self.capability_snapshot.as_of_time_ns != self.decision_time_ns:
            raise ValueError("SCAN_CAPABILITY_TIME_MISMATCH")
        by_id = {registration.strategy_id for registration in self.strategies}
        if len(by_id) != len(self.strategies):
            raise ValueError("SCAN_STRATEGY_ID_DUPLICATE")
        object.__setattr__(
            self,
            "strategies",
            tuple(sorted(self.strategies, key=lambda registration: registration.strategy_id)),
        )


@dataclass(frozen=True, slots=True)
class StrategyEvaluationContext:
    instrument: InstrumentIdentity
    registration: StrategyRegistration
    capability_snapshot: CapabilityContextSnapshot
    quality_decision: QualityDecision
    query_plans: tuple[QueryPlan, ...]
    scan_id: str
    run_id: str


@dataclass(frozen=True, slots=True)
class ScanCounters:
    universe_count: int = 0
    candidate_count: int = 0
    stage_a_eligible: int = 0
    stage_a_rejected: int = 0
    stage_a_abstained: int = 0
    stage_a_unavailable: int = 0
    stage_b_screened: int = 0
    stage_b_rejected: int = 0
    evaluated: int = 0
    matched: int = 0
    rejected: int = 0
    abstained: int = 0
    unavailable: int = 0
    evaluation_failures: int = 0
    screening_failures: int = 0
    budget_exhausted: int = 0


@dataclass(frozen=True, slots=True)
class ScanResult:
    scan_id: str
    run_id: str
    matches: tuple[StrategyMatch, ...]
    counters: ScanCounters
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _StageAResult:
    disposition: StrategyMatchDisposition | None
    capability_state: Any
    quality: QualitySummary
    quality_decision: QualityDecision
    query_plans: tuple[QueryPlan, ...]
    reasons: tuple[str, ...] = ()


class UniversalStrategyScanner:
    """Runs one bounded scan pass; it owns no daemon or workflow state."""

    SCAN_POLICY_IDENTITY = "universal-scan/1"

    def __init__(
        self,
        *,
        query_planner: QueryPlanner | None,
        repository: IntelligenceRepository,
        temporal_policy: TemporalIntegrityPolicy | None = None,
        quality_policy: QualityPolicy | None = None,
    ) -> None:
        self.query_planner = query_planner
        self.repository = repository
        self.temporal_policy = temporal_policy or DEFAULT_TEMPORAL_POLICY
        self.quality_policy = quality_policy or DEFAULT_QUALITY_POLICY

    @classmethod
    def scan_id_for(cls, request: ScanRequest) -> str:
        return f"SCAN-{sha256_bytes(canonical_bytes(_request_identity(request)))[:32]}"

    @classmethod
    def run_id_for(cls, request: ScanRequest) -> str:
        body = {
            "scan_id": cls.scan_id_for(request),
            "trigger": {
                "metadata": _thaw(request.trigger.metadata),
                "type": request.trigger.trigger_type.value,
            },
        }
        return f"RUN-{sha256_bytes(canonical_bytes(body))[:32]}"

    def run(self, request: ScanRequest) -> ScanResult:
        scan_id = self.scan_id_for(request)
        run_id = self.run_id_for(request)
        counters = ScanCounters(universe_count=len(request.universe.instruments))
        matches: list[StrategyMatch] = []
        diagnostics: list[str] = []
        evaluations = 0
        cost_units = 0

        for instrument in request.universe.instruments:
            for registration in request.strategies:
                counters = _increment(counters, "candidate_count")
                stage_a = self._stage_a(request, instrument, registration)
                if stage_a.disposition is not None:
                    counters = _increment_stage_a(counters, stage_a.disposition)
                    counters = _increment(counters, _counter_for_disposition(stage_a.disposition))
                    matches.append(
                        self._build_match(
                            request,
                            instrument,
                            registration,
                            scan_id,
                            run_id,
                            stage_a.quality,
                            stage_a.capability_state,
                            stage_a.disposition,
                            stage_a.reasons,
                            stage="A",
                        )
                    )
                    continue

                counters = _increment(counters, "stage_a_eligible")
                context = StrategyEvaluationContext(
                    instrument=instrument,
                    registration=registration,
                    capability_snapshot=request.capability_snapshot,
                    quality_decision=stage_a.quality_decision,
                    query_plans=stage_a.query_plans,
                    scan_id=scan_id,
                    run_id=run_id,
                )
                if (
                    evaluations >= request.budget.max_evaluations
                    or cost_units + registration.cost_units > request.budget.max_cost_units
                ):
                    counters = _increment_many(counters, ("budget_exhausted",))
                    counters = _increment_stage_a(counters, StrategyMatchDisposition.UNAVAILABLE)
                    counters = _increment(counters, "unavailable")
                    matches.append(
                        self._build_match(
                            request,
                            instrument,
                            registration,
                            scan_id,
                            run_id,
                            stage_a.quality,
                            _availability("unavailable"),
                            StrategyMatchDisposition.UNAVAILABLE,
                            ("BUDGET_EXHAUSTED",),
                            stage="budget",
                        )
                    )
                    continue

                if registration.cheap_screen is not None:
                    try:
                        screen = registration.cheap_screen(context)
                        if isinstance(screen, bool):
                            screen = CheapScreenResult(
                                eligible=screen,
                                reason="CHEAP_SCREEN_REJECTED" if not screen else None,
                            )
                        if not isinstance(screen, CheapScreenResult):
                            raise TypeError("CHEAP_SCREEN_RESULT_INVALID")
                    except Exception as exc:  # coarse non-decision failure
                        counters = _increment(counters, "screening_failures")
                        diagnostics.append(
                            f"CHEAP_SCREEN_FAILURE:{registration.strategy_id}:{type(exc).__name__}"
                        )
                        continue
                    counters = _increment(counters, "stage_b_screened")
                    if not screen.eligible:
                        counters = _increment(counters, "stage_b_rejected")
                        counters = _increment(counters, "rejected")
                        matches.append(
                            self._build_match(
                                request,
                                instrument,
                                registration,
                                scan_id,
                                run_id,
                                stage_a.quality,
                                _availability("available"),
                                StrategyMatchDisposition.REJECTED,
                                (screen.reason or "CHEAP_SCREEN_REJECTED",),
                                stage="B",
                            )
                        )
                        continue

                evaluations += 1
                cost_units += registration.cost_units
                counters = _increment(counters, "evaluated")
                try:
                    evaluation = registration.evaluator(context)
                    if not isinstance(evaluation, StrategyEvaluationResult):
                        raise TypeError("EVALUATION_RESULT_INVALID")
                except Exception as exc:  # coarse non-decision failure
                    counters = _increment(counters, "evaluation_failures")
                    diagnostics.append(
                        f"EVALUATOR_FAILURE:{registration.strategy_id}:{type(exc).__name__}"
                    )
                    continue
                counters = _increment(counters, _counter_for_disposition(evaluation.disposition))
                matches.append(
                    self._build_match(
                        request,
                        instrument,
                        registration,
                        scan_id,
                        run_id,
                        stage_a.quality,
                        _availability("degraded" if registration.allow_degraded else "available"),
                        evaluation.disposition,
                        _reasons_for_evaluation(evaluation),
                        stage="EVAL",
                        condition_results=evaluation.condition_results,
                        regime=evaluation.regime,
                    )
                )

        ordered_matches = tuple(sorted(matches, key=lambda match: match.match_id))
        for match in ordered_matches:
            self.repository.put_strategy_match(match)
        return ScanResult(
            scan_id=scan_id,
            run_id=run_id,
            matches=ordered_matches,
            counters=counters,
            diagnostics=tuple(sorted(set(diagnostics))),
        )

    def _stage_a(
        self,
        request: ScanRequest,
        instrument: InstrumentIdentity,
        registration: StrategyRegistration,
    ) -> _StageAResult:
        quality = request.capability_snapshot.quality
        if (
            registration.definition.asset_class is not None
            and registration.definition.asset_class != instrument.asset_class.upper()
        ):
            quality_decision = _use_quality_decision(request.capability_snapshot.quality_assessment)
            return _StageAResult(
                StrategyMatchDisposition.REJECTED,
                _availability("available"),
                quality,
                quality_decision,
                (),
                ("ASSET_CLASS_INELIGIBLE",),
            )

        if quality.state == QualityState.INVALID:
            quality_decision = _use_quality_decision(request.capability_snapshot.quality_assessment)
            return _StageAResult(
                StrategyMatchDisposition.UNAVAILABLE,
                _availability("unavailable"),
                quality,
                quality_decision,
                (),
                ("SNAPSHOT_QUALITY_INVALID",),
            )

        plans: list[QueryPlan] = []
        for capability in registration.required_capabilities:
            if self.query_planner is None:
                return _StageAResult(
                    StrategyMatchDisposition.UNAVAILABLE,
                    _availability("unavailable"),
                    quality,
                    _use_quality_decision(request.capability_snapshot.quality_assessment),
                    tuple(plans),
                    (f"CAPABILITY_UNAVAILABLE:NO_QUERY_PLANNER:{capability}",),
                )
            try:
                plan = self.query_planner.plan(
                    QueryRequest(
                        capability_id=capability,
                        instrument=instrument,
                        as_of_time_ns=request.decision_time_ns,
                        freshness_max_age_ns=self.temporal_policy.max_age_for_category(capability),
                        license_purpose="RESEARCH_ONLY",
                        mode=request.scope.mode,
                        account_id=request.scope.account_id,
                    )
                )
            except Exception as exc:  # a planner failure has no evaluation decision
                return _StageAResult(
                    StrategyMatchDisposition.UNAVAILABLE,
                    _availability("unavailable"),
                    quality,
                    _use_quality_decision(request.capability_snapshot.quality_assessment),
                    tuple(plans),
                    (f"QUERY_PLAN_FAILURE:{capability}:{type(exc).__name__}",),
                )
            plans.append(plan)
            if not plan.selected_provider_ids:
                return _StageAResult(
                    StrategyMatchDisposition.UNAVAILABLE,
                    _availability("unavailable"),
                    quality,
                    _use_quality_decision(request.capability_snapshot.quality_assessment),
                    tuple(plans),
                    (f"CAPABILITY_UNAVAILABLE:{capability}",),
                )

        requirements = []
        for capability in registration.required_capabilities:
            try:
                canonical_capability = IntelligenceCapability(capability.upper())
            except ValueError:
                continue
            requirements.append(
                _capability_requirement(
                    canonical_capability,
                    failure_action=registration.failure_action,
                    allow_degraded=registration.allow_degraded,
                )
            )
        scoped_assessment = _assessment_for_instrument(
            request.capability_snapshot.quality_assessment,
            instrument,
        )
        quality_decision = (
            decide_quality(
                scoped_assessment,
                RequirementSet.of(*requirements),
                policy=self.quality_policy,
            )
            if requirements
            else _use_quality_decision(scoped_assessment)
        )
        if quality_decision.action == DecisionAction.FAIL_CLOSED:
            return _StageAResult(
                StrategyMatchDisposition.UNAVAILABLE,
                _availability("unavailable"),
                _quality_for_action(quality_decision),
                quality_decision,
                tuple(plans),
                tuple(quality_decision.reasons) or ("QUALITY_FAIL_CLOSED",),
            )
        if quality_decision.action == DecisionAction.ABSTAIN:
            return _StageAResult(
                StrategyMatchDisposition.ABSTAINED,
                _availability("degraded"),
                _quality_for_action(quality_decision),
                quality_decision,
                tuple(plans),
                tuple(quality_decision.reasons) or ("QUALITY_ABSTAIN",),
            )
        return _StageAResult(
            None,
            _availability("degraded" if quality_decision.action == DecisionAction.DEGRADE else "available"),
            _quality_for_action(quality_decision),
            quality_decision,
            tuple(plans),
        )

    def _build_match(
        self,
        request: ScanRequest,
        instrument: InstrumentIdentity,
        registration: StrategyRegistration,
        scan_id: str,
        run_id: str,
        quality: QualitySummary,
        capability_state: Any,
        disposition: StrategyMatchDisposition,
        reasons: tuple[str, ...],
        *,
        stage: str,
        condition_results: tuple[StrategyConditionResult, ...] = (),
        regime: str | None = None,
    ) -> StrategyMatch:
        context = {
            **_thaw(request.capability_snapshot.context),
            "account_id": request.scope.account_id,
            "mode": request.scope.mode,
            "scan_id": scan_id,
            "run_id": run_id,
            "stage": stage,
            "strategy_id": registration.strategy_id,
            "trigger_type": request.trigger.trigger_type.value,
            "trigger_metadata": _thaw(request.trigger.metadata),
            "instrument": instrument.to_dict(),
        }
        kwargs: dict[str, Any] = {
            "rejection_reasons": reasons if disposition == StrategyMatchDisposition.REJECTED else (),
            "abstention_reasons": reasons if disposition == StrategyMatchDisposition.ABSTAINED else (),
            "unavailability_reasons": reasons if disposition == StrategyMatchDisposition.UNAVAILABLE else (),
        }
        return StrategyMatch.create(
            strategy_id=registration.strategy_id,
            strategy_identity_hash=registration.definition.identity_hash,
            scope=IntelligenceScope(
                instrument_ids=(instrument.qualified_id(),),
                context_id=f"{request.scope.account_id}:{request.scope.mode}:{request.capability_snapshot.snapshot_id}",
            ),
            decision_time_ns=request.decision_time_ns,
            disposition=disposition,
            capability_state=capability_state,
            quality=quality,
            source_snapshot_ref=request.capability_snapshot.source_snapshot_ref,
            source_evidence_refs=request.capability_snapshot.source_evidence_refs,
            source_signal_refs=request.capability_snapshot.source_signal_refs,
            condition_results=condition_results,
            regime=regime or request.capability_snapshot.regime,
            context=context,
            valid_from_ns=request.decision_time_ns,
            expires_at_ns=request.expires_at_ns,
            lineage_refs=request.capability_snapshot.lineage_refs,
            correlation_id=run_id,
            **kwargs,
        )


def _request_identity(request: ScanRequest) -> dict[str, Any]:
    return {
        "decision_time_ns": request.decision_time_ns,
        "expires_at_ns": request.expires_at_ns,
        "universe": {
            "as_of_time_ns": request.universe.as_of_time_ns,
            "instruments": [
                instrument.to_dict() for instrument in request.universe.instruments
            ],
        },
        "capability_snapshot": {
            "as_of_time_ns": request.capability_snapshot.as_of_time_ns,
            "context": _thaw(request.capability_snapshot.context),
            "snapshot_id": request.capability_snapshot.snapshot_id,
            "quality": request.capability_snapshot.quality_assessment.to_dict(),
        },
        "scope": {
            "account_id": request.scope.account_id,
            "mode": request.scope.mode,
        },
        "strategies": [
            {
                "allow_degraded": registration.allow_degraded,
                "cost_units": registration.cost_units,
                "definition_hash": registration.definition.identity_hash,
                "required_capabilities": list(registration.required_capabilities),
                "strategy_id": registration.strategy_id,
            }
            for registration in request.strategies
        ],
        "budget": {
            "max_cost_units": request.budget.max_cost_units,
            "max_evaluations": request.budget.max_evaluations,
        },
        "policy_identity": UniversalStrategyScanner.SCAN_POLICY_IDENTITY,
    }


def _capability_requirement(
    capability: IntelligenceCapability,
    *,
    failure_action: DecisionAction,
    allow_degraded: bool,
) -> Any:
    from ..intelligence.quality import CapabilityRequirement

    return CapabilityRequirement(
        capability=capability,
        required=True,
        failure_action=failure_action,
        allow_degraded=allow_degraded,
    )


def _use_quality_decision(assessment: QualityAssessment) -> QualityDecision:
    return decide_quality(assessment, RequirementSet(), policy=DEFAULT_QUALITY_POLICY)


def _assessment_for_instrument(
    assessment: QualityAssessment,
    instrument: InstrumentIdentity,
) -> QualityAssessment:
    allowed_ids = {instrument.instrument_id, instrument.qualified_id()}
    return replace(
        assessment,
        capability_assessments=tuple(
            row
            for row in assessment.capability_assessments
            if row.instrument_id is None or row.instrument_id in allowed_ids
        ),
    )


def _quality_for_action(decision: QualityDecision) -> QualitySummary:
    return QualitySummary(
        state=quality_state_for_action(decision.action, decision.assessment),
        flags=decision.assessment.findings and tuple(
            finding.code for finding in decision.assessment.findings
        ) or (),
    )


def _reasons_for_evaluation(result: StrategyEvaluationResult) -> tuple[str, ...]:
    if result.disposition == StrategyMatchDisposition.REJECTED:
        return result.rejection_reasons or ("STRATEGY_REJECTED",)
    if result.disposition == StrategyMatchDisposition.ABSTAINED:
        return result.abstention_reasons or ("STRATEGY_ABSTAINED",)
    if result.disposition == StrategyMatchDisposition.UNAVAILABLE:
        return result.unavailability_reasons or ("STRATEGY_UNAVAILABLE",)
    return ()


def _counter_for_disposition(disposition: StrategyMatchDisposition) -> str:
    return {
        StrategyMatchDisposition.MATCHED: "matched",
        StrategyMatchDisposition.REJECTED: "rejected",
        StrategyMatchDisposition.ABSTAINED: "abstained",
        StrategyMatchDisposition.UNAVAILABLE: "unavailable",
        StrategyMatchDisposition.EXPIRED: "unavailable",
    }[disposition]


def _increment(counters: ScanCounters, field_name: str) -> ScanCounters:
    return _increment_many(counters, (field_name,))


def _increment_many(counters: ScanCounters, field_names: tuple[str, ...]) -> ScanCounters:
    values = {field_name: getattr(counters, field_name) + 1 for field_name in field_names}
    return replace(counters, **values)


def _increment_stage_a(
    counters: ScanCounters,
    disposition: StrategyMatchDisposition,
) -> ScanCounters:
    field_name = {
        StrategyMatchDisposition.REJECTED: "stage_a_rejected",
        StrategyMatchDisposition.ABSTAINED: "stage_a_abstained",
        StrategyMatchDisposition.UNAVAILABLE: "stage_a_unavailable",
        StrategyMatchDisposition.EXPIRED: "stage_a_unavailable",
    }.get(disposition)
    if field_name is None:
        return counters
    return _increment(counters, field_name)


def _availability(state: str) -> Any:
    from ..intelligence.quality.models import AvailabilityState

    return {
        "available": AvailabilityState.AVAILABLE,
        "degraded": AvailabilityState.DEGRADED,
        "unavailable": AvailabilityState.UNAVAILABLE,
    }[state]


def _normalize_refs(values: tuple[ContractReference, ...]) -> tuple[ContractReference, ...]:
    unique = {(ref.kind, ref.id, ref.schema_version): ref for ref in values}
    return tuple(unique[key] for key in sorted(unique))


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("SCAN_CONTEXT_INVALID")
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _validate_timestamp(value: int, field_name: str) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name.upper().replace('.', '_')}_INVALID")


__all__ = [
    "CapabilityContextSnapshot",
    "CheapScreenResult",
    "PointInTimeUniverse",
    "ScanBudget",
    "ScanCounters",
    "ScanRequest",
    "ScanResult",
    "ScanScope",
    "ScanTrigger",
    "ScanTriggerType",
    "StrategyEvaluationContext",
    "StrategyEvaluationResult",
    "StrategyRegistration",
    "UniversalStrategyScanner",
]
