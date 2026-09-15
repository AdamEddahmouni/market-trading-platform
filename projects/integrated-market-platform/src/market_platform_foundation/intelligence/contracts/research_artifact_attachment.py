"""Opportunity research-artifact attachments (evidence context, not prediction authority)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import dataclass_field_names, reject_unknown_keys, validate_id

RESEARCH_ARTIFACT_ATTACHMENT_SCHEMA_ID = "intelligence/opportunity/research_artifact_attachment/1.0.0"


@dataclass(frozen=True)
class OpportunityResearchArtifactAttachmentV1:
    """Links a precomputed governed research artifact to an existing opportunity."""

    attachment_id: str
    opportunity_id: str
    artifact_type: str
    content_sha256: str
    query_version_hash: str | None
    attached_at: str
    schema_id: str = RESEARCH_ARTIFACT_ATTACHMENT_SCHEMA_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.attachment_id,
            "opportunity_id": self.opportunity_id,
            "artifact_type": self.artifact_type,
            "content_sha256": self.content_sha256,
            "query_version_hash": self.query_version_hash,
            "attached_at": self.attached_at,
            "schema_id": self.schema_id,
        }


_ALLOWED = dataclass_field_names(OpportunityResearchArtifactAttachmentV1)


def opportunity_research_artifact_attachment_v1_from_dict(
    payload: dict[str, Any],
) -> OpportunityResearchArtifactAttachmentV1:
    reject_unknown_keys(payload, _ALLOWED)
    validate_id(payload.get("attachment_id"), field_name="attachment_id")
    validate_id(payload.get("opportunity_id"), field_name="opportunity_id")
    artifact_type = str(payload.get("artifact_type") or "")
    if not artifact_type:
        raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_ARTIFACT_TYPE_REQUIRED")
    content_sha256 = str(payload.get("content_sha256") or "").upper()
    if len(content_sha256) != 64:
        raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_CONTENT_SHA256_INVALID")
    query_version_hash = payload.get("query_version_hash")
    if query_version_hash is not None:
        query_version_hash = str(query_version_hash)
    return OpportunityResearchArtifactAttachmentV1(
        attachment_id=str(payload["attachment_id"]),
        opportunity_id=str(payload["opportunity_id"]),
        artifact_type=artifact_type,
        content_sha256=content_sha256,
        query_version_hash=query_version_hash,
        attached_at=str(payload.get("attached_at") or ""),
        schema_id=str(payload.get("schema_id") or RESEARCH_ARTIFACT_ATTACHMENT_SCHEMA_ID),
    )


__all__ = [
    "OpportunityResearchArtifactAttachmentV1",
    "RESEARCH_ARTIFACT_ATTACHMENT_SCHEMA_ID",
    "opportunity_research_artifact_attachment_v1_from_dict",
]
