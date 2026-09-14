"""Cold-path attach for precomputed research evidence artifacts to opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ..contracts.opportunity import OpportunityV1
from ..contracts.research_artifact_attachment import (
    OpportunityResearchArtifactAttachmentV1,
    opportunity_research_artifact_attachment_v1_from_dict,
)
from ..opportunity.research_artifact_evidence import (
    RESEARCH_EVIDENCE_ARTIFACT_LINEAGE_KIND,
    project_opportunity_research_artifact_evidence,
    resolve_attachment_artifact,
)
from ...research.edge_stats.precomputed_catalog import resolve_precomputed_research_artifact


class ResearchArtifactAttachmentPersistence(Protocol):
    def put_opportunity_research_artifact_attachment(
        self,
        record: OpportunityResearchArtifactAttachmentV1,
    ) -> Any: ...

    def list_opportunity_research_artifact_attachments(
        self,
        opportunity_id: str,
    ) -> tuple[OpportunityResearchArtifactAttachmentV1, ...]: ...


_PERSISTENCE_METHODS = (
    "put_opportunity_research_artifact_attachment",
    "list_opportunity_research_artifact_attachments",
)


def resolve_research_artifact_attachment_persistence(strategy_repository: Any) -> Any:
    if strategy_repository is None:
        raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_REPOSITORY_UNAVAILABLE")
    for method_name in _PERSISTENCE_METHODS:
        if not callable(getattr(strategy_repository, method_name, None)):
            raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_REPOSITORY_UNSUPPORTED")
    return strategy_repository


@dataclass(frozen=True)
class ResearchArtifactAttachmentResult:
    disposition: str
    attachment_id: str
    opportunity_id: str


class ResearchArtifactAttachmentRuntime:
    def __init__(
        self,
        repository: ResearchArtifactAttachmentPersistence,
        *,
        get_opportunity: Callable[[str], OpportunityV1 | None] | None = None,
    ) -> None:
        self._repository = repository
        self._get_opportunity = get_opportunity

    def attach(self, body: dict[str, Any]) -> ResearchArtifactAttachmentResult:
        record = opportunity_research_artifact_attachment_v1_from_dict(body)
        if self._get_opportunity is not None and self._get_opportunity(record.opportunity_id) is None:
            raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_OPPORTUNITY_NOT_FOUND")
        if resolve_precomputed_research_artifact(
            artifact_type=record.artifact_type,
            content_sha256=record.content_sha256,
        ) is None:
            raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_ARTIFACT_NOT_IN_CATALOG")
        if resolve_attachment_artifact(record) is None:
            raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_QUERY_HASH_MISMATCH")
        self._repository.put_opportunity_research_artifact_attachment(record)
        return ResearchArtifactAttachmentResult(
            disposition="ATTACHED",
            attachment_id=record.attachment_id,
            opportunity_id=record.opportunity_id,
        )

    def list_for_opportunity(self, opportunity_id: str) -> tuple[OpportunityResearchArtifactAttachmentV1, ...]:
        return self._repository.list_opportunity_research_artifact_attachments(str(opportunity_id))


def research_artifact_evidence_for_opportunity_detail(
    runtime: ResearchArtifactAttachmentRuntime,
    *,
    opportunity_id: str,
    base_lineage_refs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    base_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detail/evidence-only overlay — never used by rank/summary assembly."""

    attachments = runtime.list_for_opportunity(opportunity_id)
    lineage = list(base_lineage_refs)
    seen = {(str(item.get("kind")), str(item.get("id"))) for item in lineage if isinstance(item, dict)}
    for row in attachments:
        key = (RESEARCH_EVIDENCE_ARTIFACT_LINEAGE_KIND, row.attachment_id)
        if key in seen:
            continue
        seen.add(key)
        lineage.append({"kind": RESEARCH_EVIDENCE_ARTIFACT_LINEAGE_KIND, "id": row.attachment_id})
    metadata = dict(base_metadata or {})
    metadata["research_artifact_attachments"] = {
        "count": len(attachments),
        "attachment_ids": [row.attachment_id for row in attachments],
    }
    evidence = project_opportunity_research_artifact_evidence(attachments)
    return {
        "lineage_refs": lineage,
        "metadata": metadata,
        "research_artifact_evidence": evidence,
    }


__all__ = [
    "ResearchArtifactAttachmentResult",
    "ResearchArtifactAttachmentRuntime",
    "research_artifact_evidence_for_opportunity_detail",
    "resolve_research_artifact_attachment_persistence",
]
