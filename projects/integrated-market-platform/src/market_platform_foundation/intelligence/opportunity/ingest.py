"""Assemble operator review rows. Not a production scanner."""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts.opportunity import OpportunityV1, opportunity_v1_from_dict
from ..persistence.codec import PERSISTENCE_METADATA_FIELDS
from .clustering import OpportunityClusteringError, derive_thesis_identity
from .data_quality import project_opportunity_data_quality
from .family_lookup import (
    STATUS_DENIED,
    STATUS_UNAVAILABLE,
    ReviewFamilyResolution,
    resolve_review_family,
)
from .freshness import (
    OpportunityFreshnessPolicy,
    fail_closed_for_actionable,
)
from .lifecycle import OperatorLifecycleState, derive_lifecycle_from_assessment
from .provider_linkage_warnings import project_provider_linkage_warnings
from .read_model import OpportunitySummary, ftep_attention_candidate_to_summary
from .evidence_promotion import EVIDENCE_CLASS_CANDIDATE
from .types import AssessmentAction


_DISCOVER_KEYS = frozenset({"attention_score", "screen_ids", "matched_reasons"})


def _unavailable(*names: str) -> tuple[str, ...]:
    return names


def _instrument_fail_closed(instrument_id: str) -> bool:
    value = instrument_id.strip()
    if not value:
        return False
    if value in {"*", "UNKNOWN", "unknown"}:
        return True
    if any(ch.isspace() for ch in value):
        return True
    return False


def _summary_from_opportunity(
    opportunity: OpportunityV1,
    *,
    assessment_action: AssessmentAction | None,
    source: str,
    data_quality: Mapping[str, Any] | None = None,
    family_resolution: ReviewFamilyResolution | None = None,
) -> OpportunitySummary:
    instruments = opportunity.scope.instrument_ids
    instrument_id = instruments[0] if instruments else ""
    lifecycle = derive_lifecycle_from_assessment(assessment_action)
    quality = dict(data_quality or project_opportunity_data_quality(source=source))
    evaluation = quality.get("freshness_evaluation") or {}
    if fail_closed_for_actionable(evaluation):
        lifecycle = OperatorLifecycleState.INELIGIBLE
    resolution = family_resolution or resolve_review_family(opportunity.metadata)
    if resolution.status == STATUS_DENIED:
        lifecycle = OperatorLifecycleState.INELIGIBLE
    eligible = lifecycle == OperatorLifecycleState.ELIGIBLE
    unavailable = _unavailable()
    if opportunity.expected_net_edge is None:
        unavailable += ("expected_net_edge",)
    if opportunity.expected_return is None:
        unavailable += ("expected_return",)
    if resolution.status == STATUS_UNAVAILABLE:
        unavailable += ("strategy_family",)
    metadata: dict[str, Any] = {"adapter": "opportunity_v1_repo"}
    try:
        metadata["thesis_identity"] = derive_thesis_identity(opportunity)
    except OpportunityClusteringError:
        metadata["thesis_identity_status"] = "UNAVAILABLE"
        metadata["thesis_identity_reason"] = "UNDERLYING_THESIS_ID_INVALID"
    metadata["family_admission_status"] = resolution.status
    if resolution.reason_code:
        metadata["family_admission_reason"] = resolution.reason_code
    if resolution.admission_kind:
        metadata["family_admission_kind"] = resolution.admission_kind
    if resolution.definition_hash:
        metadata["family_definition_hash"] = resolution.definition_hash
    return OpportunitySummary(
        summary_id=opportunity.opportunity_id,
        instrument_id=instrument_id,
        headline=opportunity.reason_summary or opportunity.opportunity_id,
        opportunity_id=opportunity.opportunity_id,
        strategy_family=resolution.family_id,
        strategy_version=resolution.strategy_version,
        side=opportunity.side.value if opportunity.side is not None else None,
        valid_until_ns=opportunity.valid_until_ns,
        evidence_class=EVIDENCE_CLASS_CANDIDATE,
        eligibility_state=lifecycle.value,
        lifecycle_state=lifecycle.value,
        data_quality=quality,
        provider_linkage_warnings=project_provider_linkage_warnings(
            opportunity.quality.flags
        ),
        lineage_refs=tuple(
            {"kind": getattr(ref.kind, "value", ref.kind), "id": ref.id}
            for ref in opportunity.lineage_refs
        ),
        next_safe_action="OPEN_WORKSPACE" if eligible and instrument_id else "STOP",
        identity_kind="OPPORTUNITY_V1",
        accepted=eligible,
        unavailable_fields=unavailable,
        metadata=metadata,
    )


def _without_storage_keys(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key not in PERSISTENCE_METADATA_FIELDS}


def _opportunities_from_repository(repository: Any) -> tuple[OpportunityV1, ...]:
    lister = getattr(repository, "list_opportunities", None)
    if callable(lister):
        listed = lister()
        if listed is not None:
            return tuple(listed)
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    documents = stores.get("opportunities") or {}
    getter = getattr(repository, "get_opportunity", None)
    rows: list[OpportunityV1] = []
    for record_id, document in documents.items():
        if isinstance(document, OpportunityV1):
            rows.append(document)
            continue
        if callable(getter):
            loaded = getter(str(record_id))
            if loaded is not None:
                rows.append(loaded)
                continue
        if isinstance(document, dict):
            rows.append(opportunity_v1_from_dict(_without_storage_keys(document)))
    return tuple(rows)


def assessments_from_repository(repository: Any) -> dict[str, AssessmentAction]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return {}
    from .serialization import opportunity_assessment_v1_from_dict

    actions: dict[str, AssessmentAction] = {}
    for document in (stores.get("opportunity_assessments") or {}).values():
        record = document
        if isinstance(document, dict):
            try:
                record = opportunity_assessment_v1_from_dict(_without_storage_keys(document))
            except (TypeError, ValueError, KeyError):
                continue
        opportunity_id = getattr(record, "opportunity_id", None)
        action = getattr(record, "assessment_action", None)
        if opportunity_id and action is not None:
            actions[str(opportunity_id)] = AssessmentAction(str(action))
    return actions


def assemble_opportunity_review_rows(
    *,
    opportunities: tuple[OpportunityV1, ...] = (),
    assessments_by_opportunity: Mapping[str, AssessmentAction | str] | None = None,
    attention_rows: tuple[Mapping[str, Any], ...] = (),
    repository: Any | None = None,
    source: str = "REPLAY",
    as_of_time_ns: int | None = None,
    last_source_time_ns: int | None = None,
    runtime_capability: Mapping[str, Any] | None = None,
    session_state: str | None = None,
    book_validity: str | None = None,
    freshness_policy: OpportunityFreshnessPolicy | None = None,
    strategy_family_registry: Any | None = None,
) -> tuple[OpportunitySummary, ...]:
    collected: list[OpportunitySummary] = []
    minted = list(opportunities)
    actions = dict(assessments_by_opportunity or {})
    quality = project_opportunity_data_quality(
        source=source,
        as_of_time_ns=as_of_time_ns,
        last_source_time_ns=last_source_time_ns,
        runtime_capability=runtime_capability,
        session_state=session_state,
        book_validity=book_validity,
        freshness_policy=freshness_policy,
    )
    if repository is not None:
        minted.extend(_opportunities_from_repository(repository))
        for opportunity_id, action in assessments_from_repository(repository).items():
            actions.setdefault(opportunity_id, action)
    seen_ids: set[str] = set()
    for opportunity in minted:
        if opportunity.opportunity_id in seen_ids:
            continue
        seen_ids.add(opportunity.opportunity_id)
        instruments = opportunity.scope.instrument_ids
        instrument_id = instruments[0] if instruments else ""
        if _instrument_fail_closed(instrument_id):
            continue
        action = None
        raw = actions.get(opportunity.opportunity_id)
        if raw is not None:
            action = AssessmentAction(str(raw))
        collected.append(
            _summary_from_opportunity(
                opportunity,
                assessment_action=action,
                source=source,
                data_quality=quality,
                family_resolution=resolve_review_family(
                    opportunity.metadata,
                    registry=strategy_family_registry,
                ),
            )
        )
    for row in attention_rows:
        if _DISCOVER_KEYS.intersection(row.keys()):
            continue
        instrument_id = str(row.get("instrument_id") or row.get("symbol") or "")
        if _instrument_fail_closed(instrument_id):
            continue
        summary = ftep_attention_candidate_to_summary(row)
        from dataclasses import replace

        collected.append(
            replace(
                summary,
                identity_kind="NOT_OPPORTUNITY_V1",
                evidence_class=None,
                accepted=False,
                eligibility_state="UNAVAILABLE",
                lifecycle_state=OperatorLifecycleState.NORMALIZED.value,
                data_quality=quality,
                next_safe_action="STOP",
                unavailable_fields=_unavailable(
                    "opportunity_id",
                    "strategy_family",
                    "expected_net_edge",
                    "evidence_class",
                ),
            )
        )
    return tuple(collected)
