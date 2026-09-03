"""Bounded, account-scoped thesis clustering for OpportunityV1 candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import (
    ContractReference,
    IntelligenceScope,
    contract_reference_to_dict,
    normalize_unique_refs,
    validate_id,
    validate_timestamp_ns,
    scope_to_dict,
)
from ..contracts.opportunity import OpportunityV1
from ..contracts.strategy_match import StrategyMatch, StrategyMatchDisposition
from .economic_assessment import UniversalEconomicAssessmentV1


class OpportunityClusteringError(ValueError):
    """A clustering request contains invalid or contaminated lineage."""


StrategyMatchInput = StrategyMatch | ContractReference


def _mode(value: str) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE", "PAPER": "PAPER"}.get(normalized, normalized)


def _sorted_refs(refs: tuple[ContractReference, ...] | list[ContractReference]) -> tuple[ContractReference, ...]:
    return tuple(
        sorted(
            normalize_unique_refs(refs),
            key=lambda ref: (ref.kind, ref.id, ref.schema_version),
        )
    )


@dataclass(frozen=True, slots=True)
class OpportunityClusterCandidate:
    """One explicit opportunity/match/sidecar lineage unit."""

    opportunity: OpportunityV1
    strategy_match: StrategyMatchInput
    economic_assessment: UniversalEconomicAssessmentV1 | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity, OpportunityV1):
            raise OpportunityClusteringError("OPPORTUNITY_CANDIDATE_INVALID")
        if not isinstance(self.strategy_match, (StrategyMatch, ContractReference)):
            raise OpportunityClusteringError("STRATEGY_MATCH_INPUT_INVALID")
        if isinstance(self.strategy_match, ContractReference):
            if self.strategy_match.kind != "strategy_match":
                raise OpportunityClusteringError("STRATEGY_MATCH_REFERENCE_KIND_INVALID")
        if self.economic_assessment is not None and not isinstance(
            self.economic_assessment, UniversalEconomicAssessmentV1
        ):
            raise OpportunityClusteringError("ECONOMIC_ASSESSMENT_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class OpportunityClusteringRequest:
    """Immutable account/mode/PIT boundary for one clustering projection."""

    account_id: str
    mode: str
    decision_time_ns: int
    candidates: tuple[OpportunityClusterCandidate, ...]
    strategy_match_records: tuple[StrategyMatch, ...] = ()

    def __post_init__(self) -> None:
        validate_id(self.account_id, field_name="account_id")
        if not str(self.mode).strip():
            raise OpportunityClusteringError("CLUSTERING_MODE_REQUIRED")
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "strategy_match_records", tuple(self.strategy_match_records))
        if any(not isinstance(item, OpportunityClusterCandidate) for item in self.candidates):
            raise OpportunityClusteringError("CLUSTERING_CANDIDATE_INVALID")
        if any(not isinstance(item, StrategyMatch) for item in self.strategy_match_records):
            raise OpportunityClusteringError("STRATEGY_MATCH_RECORD_INVALID")

    @property
    def opportunities(self) -> tuple[OpportunityV1, ...]:
        """Expose source opportunities without collapsing or rewriting them."""
        return tuple(candidate.opportunity for candidate in self.candidates)

    @property
    def strategy_matches(self) -> tuple[StrategyMatch, ...]:
        """Expose supplied StrategyMatch records for callers using that name."""
        return self.strategy_match_records


@dataclass(frozen=True, slots=True)
class OpportunityClusterMemberV1:
    """Reference-only member record retaining all upstream lineage."""

    opportunity_ref: ContractReference
    strategy_match_ref: ContractReference
    strategy_id: str
    economic_assessment_ref: ContractReference | None = None
    forecast_refs: tuple[ContractReference, ...] = ()
    hypothesis_refs: tuple[ContractReference, ...] = ()
    expression_refs: tuple[ContractReference, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    is_duplicate: bool = False
    duplicate_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_id(self.strategy_id, field_name="strategy_id")
        object.__setattr__(self, "forecast_refs", _sorted_refs(self.forecast_refs))
        object.__setattr__(self, "hypothesis_refs", _sorted_refs(self.hypothesis_refs))
        object.__setattr__(self, "expression_refs", _sorted_refs(self.expression_refs))
        object.__setattr__(self, "lineage_refs", _sorted_refs(self.lineage_refs))


@dataclass(frozen=True, slots=True)
class OpportunityClusterV1:
    """Immutable thesis cluster; it is neither a score nor an allocation."""

    cluster_id: str
    thesis_id: str
    account_id: str
    mode: str
    decision_time_ns: int
    member_refs: tuple[ContractReference, ...]
    member_strategy_ids: tuple[str, ...]
    expression_refs: tuple[ContractReference, ...]
    members: tuple[OpportunityClusterMemberV1, ...]
    duplicate_count: int
    reasons: tuple[str, ...]

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def duplicate_exposure_count(self) -> int:
        return self.duplicate_count

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return self.reasons


@dataclass(frozen=True, slots=True)
class OpportunityClusteringResult:
    """Deterministic projection of a clustering request."""

    account_id: str
    mode: str
    decision_time_ns: int
    clusters: tuple[OpportunityClusterV1, ...]

    @property
    def opportunities(self) -> tuple[ContractReference, ...]:
        return tuple(ref for cluster in self.clusters for ref in cluster.member_refs)


@dataclass(frozen=True, slots=True)
class DuplicateExposureEntry:
    """Duplicate-view row with no capital, rank, or execution semantics."""

    cluster_id: str
    opportunity_ref: ContractReference
    strategy_match_ref: ContractReference
    strategy_id: str
    expression_refs: tuple[ContractReference, ...]
    is_duplicate: bool
    reasons: tuple[str, ...]

    @property
    def duplicate_reasons(self) -> tuple[str, ...]:
        return self.reasons


@dataclass(frozen=True, slots=True)
class DuplicateExposureView:
    """Read-only exposure projection over source cluster members."""

    account_id: str
    mode: str
    decision_time_ns: int
    members: tuple[DuplicateExposureEntry, ...]

    @property
    def entries(self) -> tuple[DuplicateExposureEntry, ...]:
        return self.members


def _fallback_identity_payload(opportunity: OpportunityV1) -> dict[str, Any]:
    return {
        "scope": scope_to_dict(opportunity.scope),
        "opportunity_type": opportunity.opportunity_type,
        "side": opportunity.side.value if opportunity.side is not None else None,
        "forecast_refs": [
            contract_reference_to_dict(ref)
            for ref in _sorted_refs(opportunity.source_forecast_refs)
        ],
        "hypothesis_refs": [
            contract_reference_to_dict(ref)
            for ref in _sorted_refs(opportunity.source_hypothesis_refs)
        ],
    }


def _explicit_thesis_id(opportunity: OpportunityV1) -> str | None:
    value = opportunity.metadata.get("underlying_thesis_id")
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise OpportunityClusteringError("UNDERLYING_THESIS_ID_INVALID")
    return text


def derive_thesis_identity(opportunity: OpportunityV1) -> str:
    """Derive identity from explicit thesis metadata or canonical opportunity scope."""
    explicit = _explicit_thesis_id(opportunity)
    if explicit is not None:
        return f"underlying:{explicit}"
    digest = sha256_bytes(canonical_bytes(_fallback_identity_payload(opportunity)))
    return f"fallback:{digest}"


def _thesis_reason(opportunity: OpportunityV1) -> str:
    if _explicit_thesis_id(opportunity) is not None:
        return "EXPLICIT_UNDERLYING_THESIS_ID"
    return "FALLBACK_CANONICAL_OPPORTUNITY_IDENTITY"


def _as_expression_ref(value: Any) -> ContractReference:
    if isinstance(value, ContractReference):
        return value
    if isinstance(value, Mapping):
        ref = ContractReference(
            kind=str(value.get("kind", "trade_expression")),
            id=str(value["id"]),
            schema_version=str(value.get("schema_version", "1")),
        )
        return ref
    return ContractReference(kind="trade_expression", id=str(value))


def _expression_refs(opportunity: OpportunityV1) -> tuple[ContractReference, ...]:
    metadata = opportunity.metadata
    values: Any = metadata.get("expression_refs")
    if values is None:
        values = metadata.get("expression_ref", metadata.get("trade_expression_ref"))
    if values is None and metadata.get("expression_id") is not None:
        values = metadata["expression_id"]
    if values is None:
        return (ContractReference(kind="trade_expression", id=opportunity.opportunity_id),)
    if isinstance(values, (str, ContractReference, Mapping)):
        values = (values,)
    return _sorted_refs([_as_expression_ref(value) for value in values])


def _resolve_match(
    candidate: OpportunityClusterCandidate,
    request: OpportunityClusteringRequest,
) -> StrategyMatch:
    if isinstance(candidate.strategy_match, StrategyMatch):
        return candidate.strategy_match
    matches = {
        record.match_id: record for record in request.strategy_match_records
    }
    try:
        return matches[candidate.strategy_match.id]
    except KeyError as exc:
        raise OpportunityClusteringError("STRATEGY_MATCH_RECORD_NOT_SUPPLIED") from exc


def _metadata_scope_check(opportunity: OpportunityV1, request: OpportunityClusteringRequest) -> None:
    for key, expected in (
        ("account_id", request.account_id),
        ("mode", _mode(request.mode)),
    ):
        value = opportunity.metadata.get(key)
        if value is not None and (
            _mode(str(value)) if key == "mode" else str(value)
        ) != expected:
            raise OpportunityClusteringError(f"OPPORTUNITY_{key.upper()}_SCOPE_MISMATCH")


def _validate_candidate(
    candidate: OpportunityClusterCandidate,
    match: StrategyMatch,
    request: OpportunityClusteringRequest,
) -> None:
    opportunity = candidate.opportunity
    if match.disposition != StrategyMatchDisposition.MATCHED:
        raise OpportunityClusteringError("STRATEGY_MATCH_NOT_MATCHED")
    if match.scope != opportunity.scope:
        raise OpportunityClusteringError("MATCH_OPPORTUNITY_SCOPE_MISMATCH")
    _metadata_scope_check(opportunity, request)
    context = match.context
    if str(context.get("account_id", "")) != request.account_id:
        raise OpportunityClusteringError("STRATEGY_MATCH_ACCOUNT_SCOPE_MISMATCH")
    if _mode(str(context.get("mode", ""))) != _mode(request.mode):
        raise OpportunityClusteringError("STRATEGY_MATCH_MODE_SCOPE_MISMATCH")
    if opportunity.created_at_ns > request.decision_time_ns:
        raise OpportunityClusteringError("OPPORTUNITY_AFTER_DECISION")
    if opportunity.valid_until_ns is not None and request.decision_time_ns >= opportunity.valid_until_ns:
        raise OpportunityClusteringError("OPPORTUNITY_EXPIRED")
    if match.decision_time_ns > request.decision_time_ns:
        raise OpportunityClusteringError("STRATEGY_MATCH_AFTER_DECISION")
    if match.valid_from_ns is not None and match.valid_from_ns > request.decision_time_ns:
        raise OpportunityClusteringError("STRATEGY_MATCH_NOT_YET_VALID")
    if match.expires_at_ns is not None and request.decision_time_ns >= match.expires_at_ns:
        raise OpportunityClusteringError("STRATEGY_MATCH_EXPIRED")

    sidecar = candidate.economic_assessment
    if sidecar is None:
        return
    if sidecar.scope != opportunity.scope:
        raise OpportunityClusteringError("ECONOMIC_ASSESSMENT_SCOPE_MISMATCH")
    if str(sidecar.account_id) != request.account_id:
        raise OpportunityClusteringError("ECONOMIC_ASSESSMENT_ACCOUNT_SCOPE_MISMATCH")
    if _mode(sidecar.mode) != _mode(request.mode):
        raise OpportunityClusteringError("ECONOMIC_ASSESSMENT_MODE_SCOPE_MISMATCH")
    if sidecar.assessed_at_ns > request.decision_time_ns:
        raise OpportunityClusteringError("ECONOMIC_ASSESSMENT_AFTER_DECISION")
    if sidecar.expires_at_ns is not None and request.decision_time_ns >= sidecar.expires_at_ns:
        raise OpportunityClusteringError("ECONOMIC_ASSESSMENT_EXPIRED")


def _member(
    candidate: OpportunityClusterCandidate,
    match: StrategyMatch,
    *,
    is_duplicate: bool,
) -> OpportunityClusterMemberV1:
    opportunity = candidate.opportunity
    opportunity_ref = ContractReference(kind="opportunity", id=opportunity.opportunity_id)
    match_ref = ContractReference(kind="strategy_match", id=match.match_id)
    forecasts = _sorted_refs(
        list(opportunity.source_forecast_refs) + list(match.source_forecast_refs)
    )
    hypotheses = _sorted_refs(opportunity.source_hypothesis_refs)
    expressions = _expression_refs(opportunity)
    sidecar_ref = (
        ContractReference(
            kind="universal_economic_assessment",
            id=candidate.economic_assessment.assessment_id,
        )
        if candidate.economic_assessment is not None
        else None
    )
    lineage = _sorted_refs(
        list(opportunity.lineage_refs)
        + list(match.lineage_refs)
        + list(opportunity.source_forecast_refs)
        + list(opportunity.source_hypothesis_refs)
        + list(match.source_forecast_refs)
        + list(match.source_evidence_refs)
        + list(match.source_signal_refs)
        + [opportunity_ref, match_ref]
        + list(expressions)
    )
    if candidate.economic_assessment is not None:
        assert sidecar_ref is not None
        lineage = _sorted_refs(
            list(lineage)
            + [sidecar_ref]
            + list(candidate.economic_assessment.source_refs)
            + list(candidate.economic_assessment.lineage_refs)
        )
    return OpportunityClusterMemberV1(
        opportunity_ref=opportunity_ref,
        strategy_match_ref=match_ref,
        strategy_id=match.strategy_id,
        economic_assessment_ref=sidecar_ref,
        forecast_refs=forecasts,
        hypothesis_refs=hypotheses,
        expression_refs=expressions,
        lineage_refs=lineage,
        is_duplicate=is_duplicate,
        duplicate_reasons=("DUPLICATE_THESIS_EXPOSURE",) if is_duplicate else (),
    )


def _cluster_id(
    *,
    account_id: str,
    mode: str,
    decision_time_ns: int,
    thesis_id: str,
    members: tuple[OpportunityClusterMemberV1, ...],
) -> str:
    payload = {
        "account_id": account_id,
        "mode": mode,
        "decision_time_ns": decision_time_ns,
        "thesis_id": thesis_id,
        "members": [
            {
                "opportunity_ref": contract_reference_to_dict(member.opportunity_ref),
                "strategy_match_ref": contract_reference_to_dict(member.strategy_match_ref),
                "strategy_id": member.strategy_id,
                "expression_refs": [
                    contract_reference_to_dict(ref) for ref in member.expression_refs
                ],
            }
            for member in members
        ],
    }
    return f"OCL-{sha256_bytes(canonical_bytes(payload))}"


def build_opportunity_clusters(
    request: OpportunityClusteringRequest,
) -> OpportunityClusteringResult:
    """Validate and project candidates into deterministic thesis clusters."""
    if not isinstance(request, OpportunityClusteringRequest):
        raise OpportunityClusteringError("CLUSTERING_REQUEST_INVALID")
    seen_opportunities: set[str] = set()
    seen_matches: set[str] = set()
    grouped: dict[str, list[tuple[OpportunityClusterCandidate, StrategyMatch]]] = defaultdict(list)
    for candidate in request.candidates:
        match = _resolve_match(candidate, request)
        if candidate.opportunity.opportunity_id in seen_opportunities:
            raise OpportunityClusteringError("DUPLICATE_OPPORTUNITY_ID")
        if match.match_id in seen_matches:
            raise OpportunityClusteringError("DUPLICATE_STRATEGY_MATCH_ID")
        seen_opportunities.add(candidate.opportunity.opportunity_id)
        seen_matches.add(match.match_id)
        _validate_candidate(candidate, match, request)
        grouped[derive_thesis_identity(candidate.opportunity)].append((candidate, match))

    clusters: list[OpportunityClusterV1] = []
    normalized_mode = _mode(request.mode)
    for thesis_id, items in grouped.items():
        items.sort(key=lambda item: (item[0].opportunity.opportunity_id, item[1].match_id))
        members = tuple(
            _member(candidate, match, is_duplicate=index > 0)
            for index, (candidate, match) in enumerate(items)
        )
        strategy_ids = tuple(sorted({member.strategy_id for member in members}))
        expressions = _sorted_refs(
            [ref for member in members for ref in member.expression_refs]
        )
        reasons = [_thesis_reason(items[0][0].opportunity)]
        if len(members) > 1:
            reasons.append("DUPLICATE_THESIS_EXPOSURE")
        if len(strategy_ids) > 1:
            reasons.append("MULTIPLE_STRATEGIES_SAME_THESIS")
        if len(expressions) > 1:
            reasons.append("MULTIPLE_TRADE_EXPRESSIONS_SAME_THESIS")
        clusters.append(
            OpportunityClusterV1(
                cluster_id=_cluster_id(
                    account_id=request.account_id,
                    mode=normalized_mode,
                    decision_time_ns=request.decision_time_ns,
                    thesis_id=thesis_id,
                    members=members,
                ),
                thesis_id=thesis_id,
                account_id=request.account_id,
                mode=normalized_mode,
                decision_time_ns=request.decision_time_ns,
                member_refs=tuple(member.opportunity_ref for member in members),
                member_strategy_ids=strategy_ids,
                expression_refs=expressions,
                members=members,
                duplicate_count=sum(member.is_duplicate for member in members),
                reasons=tuple(reasons),
            )
        )
    clusters.sort(key=lambda cluster: cluster.cluster_id)
    return OpportunityClusteringResult(
        account_id=request.account_id,
        mode=normalized_mode,
        decision_time_ns=request.decision_time_ns,
        clusters=tuple(clusters),
    )


def duplicate_exposure_view(
    result: OpportunityClusteringResult,
) -> DuplicateExposureView:
    """Return duplicate flags while retaining every source opportunity."""
    if not isinstance(result, OpportunityClusteringResult):
        raise OpportunityClusteringError("CLUSTERING_RESULT_INVALID")
    entries = tuple(
        DuplicateExposureEntry(
            cluster_id=cluster.cluster_id,
            opportunity_ref=member.opportunity_ref,
            strategy_match_ref=member.strategy_match_ref,
            strategy_id=member.strategy_id,
            expression_refs=member.expression_refs,
            is_duplicate=member.is_duplicate,
            reasons=member.duplicate_reasons,
        )
        for cluster in result.clusters
        for member in cluster.members
    )
    return DuplicateExposureView(
        account_id=result.account_id,
        mode=result.mode,
        decision_time_ns=result.decision_time_ns,
        members=entries,
    )


__all__ = [
    "DuplicateExposureEntry",
    "DuplicateExposureView",
    "OpportunityClusterCandidate",
    "OpportunityClusterMemberV1",
    "OpportunityClusteringError",
    "OpportunityClusteringRequest",
    "OpportunityClusteringResult",
    "OpportunityClusterV1",
    "build_opportunity_clusters",
    "derive_thesis_identity",
    "duplicate_exposure_view",
]
