"""Evidence contribution model for BUILD 13 hypothesis engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts import ExpertDomain, QualitySummary


class ContributionStance(StrEnum):
    SUPPORTS = "SUPPORTS"
    OPPOSES = "OPPOSES"
    CONTEXT = "CONTEXT"


@dataclass(frozen=True, slots=True)
class HypothesisContribution:
    evidence_ref: str
    factor: str
    stance: ContributionStance
    expert_domain: ExpertDomain
    quality: QualitySummary
    source_signature_id: str
    provenance_group_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ContributionStance", "HypothesisContribution"]
