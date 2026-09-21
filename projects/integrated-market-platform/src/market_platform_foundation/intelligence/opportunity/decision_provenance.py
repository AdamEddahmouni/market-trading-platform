"""Opportunity decision provenance — thesis, invalidation, freshness, actionability.

Smallest operator-facing contract on the Discover/Radar → Opportunity Engine path.
Keeps deterministic facts and authority separate from AI-assisted notes.
Missing lineage stays distinguishable from lineage mismatch (RT-01 compatible).
Does not grant Live execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping

from ...discovery.models import DiscoveryCandidate
from ..contracts.common import ContractReference, contract_reference_from_dict, contract_reference_to_dict
from ..contracts.hypothesis import HypothesisV1
from ..contracts.opportunity import OpportunityV1
from ..contracts.strategy_match import StrategyMatch
from .types import AssessmentAction, OpportunityAssessmentV1

DECISION_PROVENANCE_SCHEMA_VERSION = "opportunity/decision_provenance/1.0.0"
DECISION_PROVENANCE_METADATA_KEY = "decision_provenance"

DEFAULT_DISCOVER_INVALIDATION = (
    "SCREEN_NO_LONGER_MATCHES",
    "PROVIDER_CAPTURE_SUPERSEDED",
    "INSTRUMENT_IDENTITY_CORRECTION",
)


class EvidenceHonesty(StrEnum):
    """Aligns with UI epistemic honesty (#366). Not an evidence-class upgrade."""

    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class OriginKind(StrEnum):
    STRATEGY_MATCH = "STRATEGY_MATCH"
    DISCOVER_SCREEN = "DISCOVER_SCREEN"
    ATTENTION = "ATTENTION"
    HYPOTHESIS = "HYPOTHESIS"
    FORECAST = "FORECAST"
    UNKNOWN = "UNKNOWN"


class LineageStatus(StrEnum):
    """PRESENT vs MISSING vs MISMATCH — do not collapse into one UNAVAILABLE token."""

    PRESENT = "PRESENT"
    MISSING = "MISSING"
    MISMATCH = "MISMATCH"


class ActionabilityStatus(StrEnum):
    ACTIONABLE = "ACTIONABLE"
    NOT_ACTIONABLE = "NOT_ACTIONABLE"
    UNKNOWN = "UNKNOWN"


class EvidenceBindingRole(StrEnum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    CONTEXT = "CONTEXT"
    ORIGIN = "ORIGIN"


@dataclass(frozen=True, slots=True)
class OpportunityEvidenceBinding:
    evidence_id: str
    kind: str
    honesty: EvidenceHonesty
    role: EvidenceBindingRole
    source_time_ns: int | None = None

    def __post_init__(self) -> None:
        if not str(self.evidence_id).strip():
            raise ValueError("EVIDENCE_BINDING_ID_REQUIRED")
        if not str(self.kind).strip():
            raise ValueError("EVIDENCE_BINDING_KIND_REQUIRED")
        if not isinstance(self.honesty, EvidenceHonesty):
            object.__setattr__(self, "honesty", EvidenceHonesty(str(self.honesty)))
        if not isinstance(self.role, EvidenceBindingRole):
            object.__setattr__(self, "role", EvidenceBindingRole(str(self.role)))


@dataclass(frozen=True, slots=True)
class OpportunityThesisStatement:
    statement: str
    honesty: EvidenceHonesty
    mechanism: str | None = None
    hypothesis_id: str | None = None
    invalidation_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.statement).strip():
            raise ValueError("THESIS_STATEMENT_REQUIRED")
        if not isinstance(self.honesty, EvidenceHonesty):
            object.__setattr__(self, "honesty", EvidenceHonesty(str(self.honesty)))
        if self.honesty is EvidenceHonesty.OBSERVED:
            raise ValueError("THESIS_CANNOT_BE_OBSERVED")
        cleaned = tuple(sorted({str(item).strip() for item in self.invalidation_criteria if str(item).strip()}))
        object.__setattr__(self, "invalidation_criteria", cleaned)


@dataclass(frozen=True, slots=True)
class FreshnessWindowRef:
    information_cutoff_ns: int | None = None
    valid_until_ns: int | None = None
    stale_after_ns: int | None = None
    policy_name: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class ActionabilityAudit:
    status: ActionabilityStatus
    still_actionable_reasons: tuple[str, ...] = ()
    no_longer_actionable_reasons: tuple[str, ...] = ()
    evidence_changed_ids: tuple[str, ...] = ()
    evaluated_at_ns: int | None = None
    lineage_status: LineageStatus = LineageStatus.PRESENT

    def __post_init__(self) -> None:
        if not isinstance(self.status, ActionabilityStatus):
            object.__setattr__(self, "status", ActionabilityStatus(str(self.status)))
        if not isinstance(self.lineage_status, LineageStatus):
            object.__setattr__(self, "lineage_status", LineageStatus(str(self.lineage_status)))
        object.__setattr__(
            self,
            "still_actionable_reasons",
            tuple(dict.fromkeys(str(item) for item in self.still_actionable_reasons if str(item).strip())),
        )
        object.__setattr__(
            self,
            "no_longer_actionable_reasons",
            tuple(dict.fromkeys(str(item) for item in self.no_longer_actionable_reasons if str(item).strip())),
        )
        object.__setattr__(
            self,
            "evidence_changed_ids",
            tuple(dict.fromkeys(str(item) for item in self.evidence_changed_ids if str(item).strip())),
        )


@dataclass(frozen=True, slots=True)
class OpportunityStateChangeAudit:
    to_state: str
    changed_at_ns: int
    reason_codes: tuple[str, ...] = ()
    from_state: str | None = None
    evidence_changed_ids: tuple[str, ...] = ()
    authority_class: str = "DETERMINISTIC"

    def __post_init__(self) -> None:
        if not str(self.to_state).strip():
            raise ValueError("STATE_CHANGE_TO_STATE_REQUIRED")
        if self.authority_class not in {"DETERMINISTIC", "OPERATOR", "AI_ASSISTED"}:
            raise ValueError("STATE_CHANGE_AUTHORITY_INVALID")
        if self.authority_class == "AI_ASSISTED":
            raise ValueError("AI_ASSISTED_CANNOT_AUTHORIZE_STATE_CHANGE")
        object.__setattr__(
            self,
            "reason_codes",
            tuple(dict.fromkeys(str(item) for item in self.reason_codes if str(item).strip())),
        )
        object.__setattr__(
            self,
            "evidence_changed_ids",
            tuple(dict.fromkeys(str(item) for item in self.evidence_changed_ids if str(item).strip())),
        )


@dataclass(frozen=True, slots=True)
class OpportunityDecisionProvenanceV1:
    """Structured answers for operator provenance questions on an admitted candidate."""

    schema_version: str
    origin_kind: OriginKind
    origin_refs: tuple[ContractReference, ...]
    actionability: ActionabilityAudit
    opportunity_id: str | None = None
    strategy_id: str | None = None
    strategy_family: str | None = None
    strategy_version: str | None = None
    strategy_identity_hash: str | None = None
    thesis: OpportunityThesisStatement | None = None
    evidence_bindings: tuple[OpportunityEvidenceBinding, ...] = ()
    freshness_window: FreshnessWindowRef | None = None
    ai_assisted_notes: tuple[str, ...] = ()
    state_changes: tuple[OpportunityStateChangeAudit, ...] = ()
    lineage_status: LineageStatus = LineageStatus.PRESENT
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != DECISION_PROVENANCE_SCHEMA_VERSION:
            raise ValueError("DECISION_PROVENANCE_SCHEMA_INVALID")
        if not isinstance(self.origin_kind, OriginKind):
            object.__setattr__(self, "origin_kind", OriginKind(str(self.origin_kind)))
        if not isinstance(self.lineage_status, LineageStatus):
            object.__setattr__(self, "lineage_status", LineageStatus(str(self.lineage_status)))
        if not isinstance(self.actionability, ActionabilityAudit):
            raise ValueError("ACTIONABILITY_AUDIT_REQUIRED")
        object.__setattr__(self, "origin_refs", tuple(self.origin_refs))
        object.__setattr__(self, "evidence_bindings", tuple(self.evidence_bindings))
        object.__setattr__(
            self,
            "ai_assisted_notes",
            tuple(str(item) for item in self.ai_assisted_notes if str(item).strip()),
        )
        object.__setattr__(self, "state_changes", tuple(self.state_changes))
        if not isinstance(self.metadata, dict):
            raise ValueError("DECISION_PROVENANCE_METADATA_INVALID")


def _honesty_for_kind(kind: str) -> EvidenceHonesty:
    normalized = str(kind).strip().lower()
    if normalized in {"evidence", "snapshot", "event", "discovery_capture"}:
        return EvidenceHonesty.OBSERVED
    if normalized in {"signal", "forecast", "hypothesis", "strategy_match", "discovery_screen"}:
        return EvidenceHonesty.DERIVED
    if normalized in {"model", "agent", "enrichment"}:
        return EvidenceHonesty.INFERRED
    return EvidenceHonesty.UNKNOWN


def _binding(
    *,
    evidence_id: str,
    kind: str,
    role: EvidenceBindingRole,
    honesty: EvidenceHonesty | None = None,
    source_time_ns: int | None = None,
) -> OpportunityEvidenceBinding:
    return OpportunityEvidenceBinding(
        evidence_id=str(evidence_id),
        kind=str(kind),
        honesty=honesty or _honesty_for_kind(kind),
        role=role,
        source_time_ns=source_time_ns,
    )


def _strategy_family(match: StrategyMatch, opportunity: OpportunityV1 | None) -> str | None:
    if opportunity is not None:
        value = opportunity.metadata.get("strategy_family")
        if isinstance(value, str) and value.strip():
            return value.strip()
    ctx = match.context if isinstance(match.context, Mapping) else {}
    value = ctx.get("strategy_family")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _strategy_version(opportunity: OpportunityV1 | None) -> str | None:
    if opportunity is None:
        return None
    value = opportunity.metadata.get("strategy_version")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _mechanism(opportunity: OpportunityV1 | None, hypothesis: HypothesisV1 | None) -> str | None:
    if opportunity is not None:
        value = opportunity.metadata.get("mechanism")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if hypothesis is not None and isinstance(hypothesis.mechanism, dict):
        name = hypothesis.mechanism.get("name") or hypothesis.mechanism.get("type")
        if isinstance(name, str) and name.strip():
            return name.strip()
        if hypothesis.hypothesis_type:
            return str(hypothesis.hypothesis_type)
    return None


def _lineage_status_for_match(match: StrategyMatch, opportunity: OpportunityV1 | None) -> LineageStatus:
    if opportunity is None:
        return LineageStatus.MISSING
    match_refs = [
        ref
        for ref in opportunity.lineage_refs
        if str(getattr(ref.kind, "value", ref.kind)).lower() == "strategy_match"
    ]
    if not match_refs and not opportunity.lineage_refs:
        return LineageStatus.MISSING
    if not match_refs:
        return LineageStatus.MISSING
    if any(ref.id == match.match_id for ref in match_refs):
        return LineageStatus.PRESENT
    return LineageStatus.MISMATCH


def _thesis_from_inputs(
    *,
    opportunity: OpportunityV1 | None,
    hypothesis: HypothesisV1 | None,
    invalidation_criteria: tuple[str, ...],
) -> OpportunityThesisStatement | None:
    statement = None
    if opportunity is not None and opportunity.reason_summary:
        statement = str(opportunity.reason_summary).strip()
    if not statement and hypothesis is not None and hypothesis.explanation:
        statement = str(hypothesis.explanation).strip()
    if not statement:
        return None
    criteria = list(invalidation_criteria)
    if hypothesis is not None:
        criteria.extend(hypothesis.invalidation_conditions)
    hypothesis_id = None
    if opportunity is not None and opportunity.source_hypothesis_refs:
        hypothesis_id = opportunity.source_hypothesis_refs[0].id
    elif hypothesis is not None:
        hypothesis_id = hypothesis.hypothesis_id
    return OpportunityThesisStatement(
        statement=statement,
        honesty=EvidenceHonesty.DERIVED,
        mechanism=_mechanism(opportunity, hypothesis),
        hypothesis_id=hypothesis_id,
        invalidation_criteria=tuple(criteria),
    )


def evaluate_actionability(
    provenance: OpportunityDecisionProvenanceV1,
    *,
    as_of_ns: int | None,
    lifecycle_state: str | None,
    freshness_status: str | None,
    assessment_action: AssessmentAction | str | None = None,
    evidence_changed_ids: tuple[str, ...] = (),
) -> ActionabilityAudit:
    """Deterministic still-actionable / no-longer-actionable reasons. Not Live authority."""

    still: list[str] = []
    no_longer: list[str] = []
    lineage = provenance.lineage_status

    if lineage == LineageStatus.MISSING:
        no_longer.append("LINEAGE_MISSING")
    elif lineage == LineageStatus.MISMATCH:
        no_longer.append("LINEAGE_MISMATCH")

    if provenance.origin_kind == OriginKind.DISCOVER_SCREEN:
        no_longer.append("DISCOVER_INVESTIGATE_ONLY")

    lifecycle = str(lifecycle_state or "").strip().upper()
    if lifecycle in {"INELIGIBLE", "DISMISSED", "EXPIRED"}:
        no_longer.append(f"LIFECYCLE_{lifecycle}")
    elif lifecycle in {"ELIGIBLE", "RANKED", "REVIEWED", "WATCHED", "NORMALIZED"}:
        still.append(f"LIFECYCLE_{lifecycle}")

    freshness = str(freshness_status or "").strip().upper()
    if freshness == "FRESH":
        still.append("FRESHNESS_FRESH")
    elif freshness in {"STALE", "DELAYED"}:
        no_longer.append(f"FRESHNESS_{freshness}")
    elif freshness in {"UNKNOWN", "NOT_APPLICABLE"}:
        no_longer.append(f"FRESHNESS_{freshness}")

    window = provenance.freshness_window
    if window is not None and window.valid_until_ns is not None and as_of_ns is not None:
        if as_of_ns >= int(window.valid_until_ns):
            no_longer.append("VALIDITY_WINDOW_EXPIRED")
        else:
            still.append("WITHIN_VALIDITY_WINDOW")

    action = None
    if assessment_action is not None:
        action = AssessmentAction(str(assessment_action))
        if action == AssessmentAction.EMIT:
            still.append("ASSESSMENT_EMIT")
        else:
            no_longer.append(f"ASSESSMENT_{action.value}")

    if provenance.thesis is not None and provenance.thesis.invalidation_criteria and evidence_changed_ids:
        still.append("THESIS_INVALIDATION_CRITERIA_ATTACHED")

    if no_longer:
        status = ActionabilityStatus.NOT_ACTIONABLE
        still = [code for code in still if code.startswith("THESIS_") or code.startswith("WITHIN_")]
    elif still:
        status = ActionabilityStatus.ACTIONABLE
    else:
        status = ActionabilityStatus.UNKNOWN

    return ActionabilityAudit(
        status=status,
        still_actionable_reasons=tuple(still),
        no_longer_actionable_reasons=tuple(no_longer),
        evidence_changed_ids=evidence_changed_ids,
        evaluated_at_ns=as_of_ns,
        lineage_status=lineage,
    )


def build_decision_provenance_from_strategy_match(
    *,
    match: StrategyMatch,
    opportunity: OpportunityV1 | None,
    assessment: OpportunityAssessmentV1 | None = None,
    hypothesis: HypothesisV1 | None = None,
    invalidation_criteria: tuple[str, ...] = (),
    freshness_status: str | None = None,
    stale_after_ns: int | None = None,
    freshness_policy_name: str | None = None,
    as_of_ns: int | None = None,
    lifecycle_state: str | None = None,
    ai_assisted_notes: tuple[str, ...] = (),
) -> OpportunityDecisionProvenanceV1:
    """Admit StrategyMatch → Opportunity provenance for operator auditability."""

    origin_refs: list[ContractReference] = [
        ContractReference(kind="strategy_match", id=match.match_id),
    ]
    if match.source_snapshot_ref is not None:
        origin_refs.append(match.source_snapshot_ref)

    bindings: list[OpportunityEvidenceBinding] = [
        _binding(
            evidence_id=match.match_id,
            kind="strategy_match",
            role=EvidenceBindingRole.ORIGIN,
            honesty=EvidenceHonesty.DERIVED,
            source_time_ns=match.decision_time_ns,
        )
    ]
    for ref in match.source_evidence_refs:
        bindings.append(
            _binding(
                evidence_id=ref.id,
                kind=str(getattr(ref.kind, "value", ref.kind)),
                role=EvidenceBindingRole.SUPPORTING,
                source_time_ns=match.decision_time_ns,
            )
        )
    for ref in match.source_signal_refs:
        bindings.append(
            _binding(
                evidence_id=ref.id,
                kind=str(getattr(ref.kind, "value", ref.kind)),
                role=EvidenceBindingRole.CONTEXT,
                source_time_ns=match.decision_time_ns,
            )
        )
    for ref in match.source_forecast_refs:
        bindings.append(
            _binding(
                evidence_id=ref.id,
                kind=str(getattr(ref.kind, "value", ref.kind)),
                role=EvidenceBindingRole.SUPPORTING,
                honesty=EvidenceHonesty.DERIVED,
                source_time_ns=match.decision_time_ns,
            )
        )
    if opportunity is not None:
        for ref in opportunity.source_hypothesis_refs:
            bindings.append(
                _binding(
                    evidence_id=ref.id,
                    kind="hypothesis",
                    role=EvidenceBindingRole.SUPPORTING,
                    honesty=EvidenceHonesty.DERIVED,
                    source_time_ns=opportunity.created_at_ns,
                )
            )
    if hypothesis is not None:
        for evidence_id in hypothesis.supporting_evidence_ids:
            bindings.append(
                _binding(
                    evidence_id=evidence_id,
                    kind="evidence",
                    role=EvidenceBindingRole.SUPPORTING,
                    honesty=EvidenceHonesty.OBSERVED,
                )
            )
        for evidence_id in hypothesis.contradicting_evidence_ids:
            bindings.append(
                _binding(
                    evidence_id=evidence_id,
                    kind="evidence",
                    role=EvidenceBindingRole.CONTRADICTING,
                    honesty=EvidenceHonesty.OBSERVED,
                )
            )
        origin_refs.append(ContractReference(kind="hypothesis", id=hypothesis.hypothesis_id))

    deduped: dict[tuple[str, str, str], OpportunityEvidenceBinding] = {}
    for binding in bindings:
        deduped[(binding.kind, binding.evidence_id, binding.role.value)] = binding

    lineage = _lineage_status_for_match(match, opportunity)
    thesis = _thesis_from_inputs(
        opportunity=opportunity,
        hypothesis=hypothesis,
        invalidation_criteria=invalidation_criteria,
    )
    valid_until = None
    info_cutoff = match.decision_time_ns
    if opportunity is not None and opportunity.valid_until_ns is not None:
        valid_until = opportunity.valid_until_ns
    elif match.expires_at_ns is not None:
        valid_until = match.expires_at_ns
    if assessment is not None and assessment.expires_at_ns is not None:
        valid_until = assessment.expires_at_ns
        info_cutoff = assessment.forecast_decision_time_ns

    window = FreshnessWindowRef(
        information_cutoff_ns=info_cutoff,
        valid_until_ns=valid_until,
        stale_after_ns=stale_after_ns,
        policy_name=freshness_policy_name,
        status=freshness_status,
    )
    draft = OpportunityDecisionProvenanceV1(
        schema_version=DECISION_PROVENANCE_SCHEMA_VERSION,
        origin_kind=OriginKind.STRATEGY_MATCH,
        origin_refs=tuple(origin_refs),
        opportunity_id=opportunity.opportunity_id if opportunity is not None else None,
        strategy_id=match.strategy_id,
        strategy_family=_strategy_family(match, opportunity),
        strategy_version=_strategy_version(opportunity),
        strategy_identity_hash=match.strategy_identity_hash,
        thesis=thesis,
        evidence_bindings=tuple(deduped.values()),
        freshness_window=window,
        actionability=ActionabilityAudit(
            status=ActionabilityStatus.UNKNOWN,
            lineage_status=lineage,
            evaluated_at_ns=as_of_ns,
        ),
        ai_assisted_notes=ai_assisted_notes,
        lineage_status=lineage,
    )
    action = assessment.assessment_action if assessment is not None else None
    lifecycle = lifecycle_state
    if lifecycle is None and action == AssessmentAction.EMIT:
        lifecycle = "ELIGIBLE"
    elif lifecycle is None and action is not None:
        lifecycle = "INELIGIBLE"
    actionability = evaluate_actionability(
        draft,
        as_of_ns=as_of_ns if as_of_ns is not None else match.decision_time_ns,
        lifecycle_state=lifecycle,
        freshness_status=freshness_status or ("FRESH" if action == AssessmentAction.EMIT else None),
        assessment_action=action,
    )
    return replace(draft, actionability=actionability)


def route_discovery_candidate_to_oe(
    candidate: DiscoveryCandidate,
    *,
    as_of_ns: int | None = None,
) -> OpportunityDecisionProvenanceV1:
    """Deterministic Discover/Radar → OE provenance route.

    Does **not** mint ``OpportunityV1``. Discover remains INVESTIGATE-only until a
    StrategyMatch admits the candidate through the governed bridge.
    """

    screen_ref = ContractReference(
        kind="discovery_screen",
        id=f"{candidate.screen_id}@{candidate.screen_version}",
    )
    bindings: list[OpportunityEvidenceBinding] = [
        _binding(
            evidence_id=f"{candidate.screen_id}@{candidate.screen_version}",
            kind="discovery_screen",
            role=EvidenceBindingRole.ORIGIN,
            honesty=EvidenceHonesty.DERIVED,
            source_time_ns=candidate.available_time_ns,
        )
    ]
    capture_id = None
    if isinstance(candidate.provenance, Mapping):
        raw_capture = candidate.provenance.get("capture_id") or candidate.provenance.get("raw_response_hash")
        if isinstance(raw_capture, str) and raw_capture.strip():
            capture_id = raw_capture.strip()
            bindings.append(
                _binding(
                    evidence_id=capture_id,
                    kind="discovery_capture",
                    role=EvidenceBindingRole.SUPPORTING,
                    honesty=EvidenceHonesty.OBSERVED,
                    source_time_ns=candidate.available_time_ns,
                )
            )
    for reason in candidate.matched_reasons:
        bindings.append(
            _binding(
                evidence_id=str(reason),
                kind="discovery_reason",
                role=EvidenceBindingRole.CONTEXT,
                honesty=EvidenceHonesty.DERIVED,
                source_time_ns=candidate.available_time_ns,
            )
        )

    thesis = OpportunityThesisStatement(
        statement=(
            f"Discover screen {candidate.screen_id} matched {candidate.instrument_id} "
            f"for investigation ({', '.join(candidate.matched_reasons) or 'no reasons'})."
        ),
        honesty=EvidenceHonesty.DERIVED,
        mechanism="discovery_screen_match",
        invalidation_criteria=DEFAULT_DISCOVER_INVALIDATION,
    )
    return OpportunityDecisionProvenanceV1(
        schema_version=DECISION_PROVENANCE_SCHEMA_VERSION,
        origin_kind=OriginKind.DISCOVER_SCREEN,
        origin_refs=(screen_ref,),
        opportunity_id=None,
        strategy_id=None,
        strategy_family=None,
        strategy_version=candidate.screen_version,
        thesis=thesis,
        evidence_bindings=tuple(bindings),
        freshness_window=FreshnessWindowRef(
            information_cutoff_ns=candidate.available_time_ns,
            valid_until_ns=None,
            status="NOT_APPLICABLE",
            policy_name="discover.investigate_only",
        ),
        actionability=ActionabilityAudit(
            status=ActionabilityStatus.NOT_ACTIONABLE,
            no_longer_actionable_reasons=("DISCOVER_INVESTIGATE_ONLY",),
            evaluated_at_ns=as_of_ns if as_of_ns is not None else candidate.available_time_ns,
            lineage_status=LineageStatus.MISSING,
        ),
        lineage_status=LineageStatus.MISSING,
        metadata={
            "instrument_id": candidate.instrument_id,
            "provider_symbol": candidate.provider_symbol,
            "screen_id": candidate.screen_id,
            "screen_version": candidate.screen_version,
            "candidate_role": "INVESTIGATE",
            "capture_id": capture_id,
        },
    )


def audit_opportunity_state_change(
    provenance: OpportunityDecisionProvenanceV1,
    *,
    to_lifecycle_state: str,
    actionability: ActionabilityAudit,
    changed_at_ns: int,
    from_lifecycle_state: str | None = None,
    ai_assisted_notes: tuple[str, ...] = (),
) -> OpportunityDecisionProvenanceV1:
    """Append a deterministic state-change audit. AI notes stay non-authoritative."""

    reasons = tuple(actionability.no_longer_actionable_reasons) or tuple(
        actionability.still_actionable_reasons
    )
    change = OpportunityStateChangeAudit(
        from_state=from_lifecycle_state,
        to_state=str(to_lifecycle_state),
        changed_at_ns=int(changed_at_ns),
        reason_codes=reasons,
        evidence_changed_ids=actionability.evidence_changed_ids,
        authority_class="DETERMINISTIC",
    )
    notes = tuple(dict.fromkeys([*provenance.ai_assisted_notes, *ai_assisted_notes]))
    return replace(
        provenance,
        actionability=actionability,
        state_changes=provenance.state_changes + (change,),
        ai_assisted_notes=notes,
    )


def attach_decision_provenance(
    opportunity: OpportunityV1,
    provenance: OpportunityDecisionProvenanceV1,
) -> OpportunityV1:
    """Attach provenance under metadata without mutating OpportunityV1 fields."""

    if provenance.opportunity_id and provenance.opportunity_id != opportunity.opportunity_id:
        raise ValueError("DECISION_PROVENANCE_OPPORTUNITY_ID_MISMATCH")
    bound = provenance if provenance.opportunity_id else replace(
        provenance, opportunity_id=opportunity.opportunity_id
    )
    metadata = dict(opportunity.metadata)
    metadata[DECISION_PROVENANCE_METADATA_KEY] = decision_provenance_to_dict(bound)
    return replace(opportunity, metadata=metadata)


def extract_decision_provenance(
    source: OpportunityV1 | Mapping[str, Any] | None,
) -> OpportunityDecisionProvenanceV1 | None:
    if source is None:
        return None
    if isinstance(source, OpportunityV1):
        payload = source.metadata.get(DECISION_PROVENANCE_METADATA_KEY)
    elif isinstance(source, Mapping):
        metadata = source.get("metadata") if isinstance(source.get("metadata"), Mapping) else source
        payload = None
        if isinstance(metadata, Mapping):
            payload = metadata.get(DECISION_PROVENANCE_METADATA_KEY)
        if payload is None:
            payload = source.get(DECISION_PROVENANCE_METADATA_KEY)
    else:
        return None
    if not isinstance(payload, Mapping):
        return None
    return decision_provenance_from_dict(dict(payload))


def _binding_to_dict(item: OpportunityEvidenceBinding) -> dict[str, Any]:
    body: dict[str, Any] = {
        "evidence_id": item.evidence_id,
        "kind": item.kind,
        "honesty": item.honesty.value,
        "role": item.role.value,
    }
    if item.source_time_ns is not None:
        body["source_time_ns"] = item.source_time_ns
    return body


def _binding_from_dict(payload: Mapping[str, Any]) -> OpportunityEvidenceBinding:
    return OpportunityEvidenceBinding(
        evidence_id=str(payload["evidence_id"]),
        kind=str(payload["kind"]),
        honesty=EvidenceHonesty(str(payload["honesty"])),
        role=EvidenceBindingRole(str(payload["role"])),
        source_time_ns=payload.get("source_time_ns"),
    )


def _thesis_to_dict(item: OpportunityThesisStatement) -> dict[str, Any]:
    body: dict[str, Any] = {
        "statement": item.statement,
        "honesty": item.honesty.value,
        "invalidation_criteria": list(item.invalidation_criteria),
    }
    if item.mechanism is not None:
        body["mechanism"] = item.mechanism
    if item.hypothesis_id is not None:
        body["hypothesis_id"] = item.hypothesis_id
    return body


def _thesis_from_dict(payload: Mapping[str, Any]) -> OpportunityThesisStatement:
    return OpportunityThesisStatement(
        statement=str(payload["statement"]),
        honesty=EvidenceHonesty(str(payload["honesty"])),
        mechanism=payload.get("mechanism"),
        hypothesis_id=payload.get("hypothesis_id"),
        invalidation_criteria=tuple(payload.get("invalidation_criteria") or ()),
    )


def _window_to_dict(item: FreshnessWindowRef) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if item.information_cutoff_ns is not None:
        body["information_cutoff_ns"] = item.information_cutoff_ns
    if item.valid_until_ns is not None:
        body["valid_until_ns"] = item.valid_until_ns
    if item.stale_after_ns is not None:
        body["stale_after_ns"] = item.stale_after_ns
    if item.policy_name is not None:
        body["policy_name"] = item.policy_name
    if item.status is not None:
        body["status"] = item.status
    return body


def _window_from_dict(payload: Mapping[str, Any]) -> FreshnessWindowRef:
    return FreshnessWindowRef(
        information_cutoff_ns=payload.get("information_cutoff_ns"),
        valid_until_ns=payload.get("valid_until_ns"),
        stale_after_ns=payload.get("stale_after_ns"),
        policy_name=payload.get("policy_name"),
        status=payload.get("status"),
    )


def _actionability_to_dict(item: ActionabilityAudit) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": item.status.value,
        "still_actionable_reasons": list(item.still_actionable_reasons),
        "no_longer_actionable_reasons": list(item.no_longer_actionable_reasons),
        "evidence_changed_ids": list(item.evidence_changed_ids),
        "lineage_status": item.lineage_status.value,
    }
    if item.evaluated_at_ns is not None:
        body["evaluated_at_ns"] = item.evaluated_at_ns
    return body


def _actionability_from_dict(payload: Mapping[str, Any]) -> ActionabilityAudit:
    return ActionabilityAudit(
        status=ActionabilityStatus(str(payload["status"])),
        still_actionable_reasons=tuple(payload.get("still_actionable_reasons") or ()),
        no_longer_actionable_reasons=tuple(payload.get("no_longer_actionable_reasons") or ()),
        evidence_changed_ids=tuple(payload.get("evidence_changed_ids") or ()),
        evaluated_at_ns=payload.get("evaluated_at_ns"),
        lineage_status=LineageStatus(str(payload.get("lineage_status", LineageStatus.PRESENT.value))),
    )


def _state_change_to_dict(item: OpportunityStateChangeAudit) -> dict[str, Any]:
    body: dict[str, Any] = {
        "to_state": item.to_state,
        "changed_at_ns": item.changed_at_ns,
        "reason_codes": list(item.reason_codes),
        "evidence_changed_ids": list(item.evidence_changed_ids),
        "authority_class": item.authority_class,
    }
    if item.from_state is not None:
        body["from_state"] = item.from_state
    return body


def _state_change_from_dict(payload: Mapping[str, Any]) -> OpportunityStateChangeAudit:
    return OpportunityStateChangeAudit(
        to_state=str(payload["to_state"]),
        changed_at_ns=int(payload["changed_at_ns"]),
        reason_codes=tuple(payload.get("reason_codes") or ()),
        from_state=payload.get("from_state"),
        evidence_changed_ids=tuple(payload.get("evidence_changed_ids") or ()),
        authority_class=str(payload.get("authority_class", "DETERMINISTIC")),
    )


def decision_provenance_to_dict(record: OpportunityDecisionProvenanceV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": record.schema_version,
        "origin_kind": record.origin_kind.value,
        "origin_refs": [contract_reference_to_dict(ref) for ref in record.origin_refs],
        "actionability": _actionability_to_dict(record.actionability),
        "evidence_bindings": [_binding_to_dict(item) for item in record.evidence_bindings],
        "ai_assisted_notes": list(record.ai_assisted_notes),
        "state_changes": [_state_change_to_dict(item) for item in record.state_changes],
        "lineage_status": record.lineage_status.value,
    }
    if record.opportunity_id is not None:
        body["opportunity_id"] = record.opportunity_id
    if record.strategy_id is not None:
        body["strategy_id"] = record.strategy_id
    if record.strategy_family is not None:
        body["strategy_family"] = record.strategy_family
    if record.strategy_version is not None:
        body["strategy_version"] = record.strategy_version
    if record.strategy_identity_hash is not None:
        body["strategy_identity_hash"] = record.strategy_identity_hash
    if record.thesis is not None:
        body["thesis"] = _thesis_to_dict(record.thesis)
    if record.freshness_window is not None:
        body["freshness_window"] = _window_to_dict(record.freshness_window)
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def decision_provenance_from_dict(payload: Mapping[str, Any]) -> OpportunityDecisionProvenanceV1:
    thesis_payload = payload.get("thesis")
    window_payload = payload.get("freshness_window")
    return OpportunityDecisionProvenanceV1(
        schema_version=str(payload.get("schema_version", DECISION_PROVENANCE_SCHEMA_VERSION)),
        origin_kind=OriginKind(str(payload["origin_kind"])),
        origin_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("origin_refs") or [])
        ),
        actionability=_actionability_from_dict(payload["actionability"]),
        opportunity_id=payload.get("opportunity_id"),
        strategy_id=payload.get("strategy_id"),
        strategy_family=payload.get("strategy_family"),
        strategy_version=payload.get("strategy_version"),
        strategy_identity_hash=payload.get("strategy_identity_hash"),
        thesis=_thesis_from_dict(thesis_payload) if isinstance(thesis_payload, Mapping) else None,
        evidence_bindings=tuple(
            _binding_from_dict(item) for item in (payload.get("evidence_bindings") or [])
        ),
        freshness_window=(
            _window_from_dict(window_payload) if isinstance(window_payload, Mapping) else None
        ),
        ai_assisted_notes=tuple(payload.get("ai_assisted_notes") or ()),
        state_changes=tuple(
            _state_change_from_dict(item) for item in (payload.get("state_changes") or [])
        ),
        lineage_status=LineageStatus(str(payload.get("lineage_status", LineageStatus.PRESENT.value))),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "DECISION_PROVENANCE_METADATA_KEY",
    "DECISION_PROVENANCE_SCHEMA_VERSION",
    "ActionabilityAudit",
    "ActionabilityStatus",
    "EvidenceBindingRole",
    "EvidenceHonesty",
    "FreshnessWindowRef",
    "LineageStatus",
    "OpportunityDecisionProvenanceV1",
    "OpportunityEvidenceBinding",
    "OpportunityStateChangeAudit",
    "OpportunityThesisStatement",
    "OriginKind",
    "attach_decision_provenance",
    "audit_opportunity_state_change",
    "build_decision_provenance_from_strategy_match",
    "decision_provenance_from_dict",
    "decision_provenance_to_dict",
    "evaluate_actionability",
    "extract_decision_provenance",
    "route_discovery_candidate_to_oe",
]
