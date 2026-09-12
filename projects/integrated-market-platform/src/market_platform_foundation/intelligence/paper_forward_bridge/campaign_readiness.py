"""Campaign readiness evaluator — preflight + capability gap engine (fail-closed)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from ...providers.capability_contract import CapabilityMatrixSnapshot
from ...providers.coverage_gap_engine import (
    CoverageGapReport,
    GapDisposition,
    resolve_coverage_gaps_for_campaign,
)
from .preflight import ForwardTestPreflightResult, PreflightDisposition, run_forward_test_preflight


class CampaignReadinessDisposition(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True, slots=True)
class CampaignReadinessResult:
    disposition: CampaignReadinessDisposition
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    campaign_slug: str
    preflight: ForwardTestPreflightResult
    coverage_gaps: CoverageGapReport
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "blockers": list(self.blockers),
            "campaign_slug": self.campaign_slug,
            "coverage_gaps": self.coverage_gaps.to_dict(),
            "disposition": self.disposition.value,
            "manifest_fingerprint": self.preflight.manifest_fingerprint,
            "manifest_status": self.preflight.manifest_status,
            "metadata": self.metadata,
            "preflight_disposition": self.preflight.disposition.value,
            "preflight_blockers": list(self.preflight.blockers),
            "warnings": list(self.warnings),
        }


def evaluate_campaign_readiness(
    campaign_slug: str,
    *,
    repository_root: Path,
    mode: str = "PAPER",
    run_kind: str = "FORWARD_TEST",
    campaigns_root_override: Path | None = None,
    snapshot: CapabilityMatrixSnapshot | None = None,
    readiness_report: Mapping[str, Any] | None = None,
    profile_id: str | None = None,
) -> CampaignReadinessResult:
    """Compose manifest preflight and provider coverage gaps; fail closed on any blocker."""

    profile_key = profile_id or campaign_slug
    preflight = run_forward_test_preflight(
        campaign_slug=campaign_slug,
        mode=mode,
        run_kind=run_kind,
        campaigns_root_override=campaigns_root_override,
    )
    gap_report = resolve_coverage_gaps_for_campaign(
        profile_key,
        repository_root=repository_root,
        snapshot=snapshot,
        readiness_report=readiness_report,
    )

    blockers: list[str] = list(preflight.blockers)
    for gap_id in gap_report.blockers:
        blockers.append(f"COVERAGE_GAP:{gap_id}")

    warnings = list(preflight.warnings)
    if gap_report.disposition == GapDisposition.BLOCKING:
        warnings.append("coverage_gap_engine_reported_blockers")

    unique_blockers = tuple(dict.fromkeys(blockers))
    disposition = (
        CampaignReadinessDisposition.READY
        if not unique_blockers
        else CampaignReadinessDisposition.NOT_READY
    )
    return CampaignReadinessResult(
        disposition=disposition,
        blockers=unique_blockers,
        warnings=tuple(warnings),
        campaign_slug=campaign_slug,
        preflight=preflight,
        coverage_gaps=gap_report,
        metadata={
            "profile_id": gap_report.profile_id,
            "coverage_gap_disposition": gap_report.disposition.value,
        },
    )


def assert_campaign_readiness_ready(result: CampaignReadinessResult) -> None:
    if result.disposition != CampaignReadinessDisposition.READY:
        raise ValueError(
            "CAMPAIGN_READINESS_FAILED:" + ",".join(result.blockers)
        )
