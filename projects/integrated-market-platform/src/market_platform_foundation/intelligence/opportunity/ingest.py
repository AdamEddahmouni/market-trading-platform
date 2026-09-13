"""Assemble operator review rows. Not a production scanner."""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts.opportunity import OpportunityV1, opportunity_v1_from_dict
from ..persistence.codec import PERSISTENCE_METADATA_FIELDS
from .data_quality import project_opportunity_data_quality
from .lifecycle import OperatorLifecycleState, derive_lifecycle_from_assessment
from .read_model import OpportunitySummary, ftep_attention_candidate_to_summary
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
) -> OpportunitySummary:
    instruments = opportunity.scope.instrument_ids
    instrument_id = instruments[0] if instruments else ""
    lifecycle = derive_lifecycle_from_assessment(assessment_action)
    eligible = lifecycle == OperatorLifecycleState.ELIGIBLE
    unavailable = _unavailable()
    if opportunity.expected_net_edge is None:
        unavailable += ("expected_net_edge",)
    if opportunity.expected_return is None:
        unavailable += ("expected_return",)
    return OpportunitySummary(
        summary_id=opportunity.opportunity_id,
        instrument_id=instrument_id,
        headline=opportunity.reason_summary or opportunity.opportunity_id,
        opportunity_id=opportunity.opportunity_id,
        side=opportunity.side.value if opportunity.side is not None else None,
        valid_until_ns=opportunity.valid_until_ns,
        evidence_class="CANDIDATE",
        eligibility_state=lifecycle.value,
        lifecycle_state=lifecycle.value,
        data_quality=project_opportunity_data_quality(source=source),
        lineage_refs=tuple(
            {"kind": getattr(ref.kind, "value", ref.kind), "id": ref.id}
            for ref in opportunity.lineage_refs
        ),
        next_safe_action="OPEN_WORKSPACE" if eligible and instrument_id else "STOP",
        identity_kind="OPPORTUNITY_V1",
        accepted=eligible,
        unavailable_fields=unavailable,
        metadata={"adapter": "opportunity_v1_repo"},
    )


def _opportunities_from_repository(repository: Any) -> tuple[OpportunityV1, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    documents = stores.get("opportunities") or {}
    rows: list[OpportunityV1] = []
    for document in documents.values():
        if isinstance(document, OpportunityV1):
            rows.append(document)
            continue
        if isinstance(document, dict):
            payload = {
                key: value
                for key, value in document.items()
                if key not in PERSISTENCE_METADATA_FIELDS
            }
            rows.append(opportunity_v1_from_dict(payload))
    return tuple(rows)


def assemble_opportunity_review_rows(
    *,
    opportunities: tuple[OpportunityV1, ...] = (),
    assessments_by_opportunity: Mapping[str, AssessmentAction | str] | None = None,
    attention_rows: tuple[Mapping[str, Any], ...] = (),
    repository: Any | None = None,
    source: str = "REPLAY",
) -> tuple[OpportunitySummary, ...]:
    collected: list[OpportunitySummary] = []
    minted = list(opportunities)
    if repository is not None:
        minted.extend(_opportunities_from_repository(repository))
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
        if assessments_by_opportunity:
            raw = assessments_by_opportunity.get(opportunity.opportunity_id)
            if raw is not None:
                action = AssessmentAction(str(raw))
        collected.append(
            _summary_from_opportunity(
                opportunity,
                assessment_action=action,
                source=source,
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
                eligibility_state="UNAVAILABLE",
                lifecycle_state=OperatorLifecycleState.NORMALIZED.value,
                data_quality=project_opportunity_data_quality(source=source),
                next_safe_action="OPEN_WORKSPACE" if summary.instrument_id else "NONE",
                unavailable_fields=_unavailable(
                    "opportunity_id",
                    "strategy_family",
                    "expected_net_edge",
                    "evidence_class",
                ),
            )
        )
    return tuple(collected)
