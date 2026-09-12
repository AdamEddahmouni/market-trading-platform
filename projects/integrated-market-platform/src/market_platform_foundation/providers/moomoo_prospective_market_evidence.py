"""Moomoo probe receipts → prospective campaign market-evidence disposition."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from .capability_requirements import (
    FTEP_V1_001_ES_NEWS_PROFILE,
    FTEP_V1_002_US_EQUITY_NEWS_PROFILE,
    CampaignRequirementProfile,
    get_campaign_requirement_profile,
)

_PROBE_SUMMARY_GLOB = "provider-probe-moomoo-summary-*.json"


class ProspectiveMarketEvidenceDisposition(StrEnum):
    SAMPLE_VERIFIED = "SAMPLE_VERIFIED"
    NOT_ENTITLED = "NOT_ENTITLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProspectiveMarketEvidenceAssessment:
    campaign_slug: str
    capability_id: str
    disposition: ProspectiveMarketEvidenceDisposition
    evidence_path: str | None
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_slug": self.campaign_slug,
            "capability_id": self.capability_id,
            "disposition": self.disposition.value,
            "evidence_path": self.evidence_path,
            "notes": self.notes,
        }


_CAMPAIGN_PRIMARY_CAPABILITY: dict[str, str] = {
    FTEP_V1_001_ES_NEWS_PROFILE.campaign_slug: "US_FUTURES_QUOTE",
    FTEP_V1_002_US_EQUITY_NEWS_PROFILE.campaign_slug: "US_EQUITY_L1",
}


def _latest_probe_summary(repository_root: Path) -> tuple[Path | None, Mapping[str, Any] | None]:
    probe_dir = repository_root / "artifacts/ftep-v1-activation"
    if not probe_dir.is_dir():
        return None, None
    candidates = sorted(
        probe_dir.glob(_PROBE_SUMMARY_GLOB),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None, None
    path = candidates[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, None
    return path, payload if isinstance(payload, dict) else None


def assess_moomoo_prospective_market_evidence(
    profile_or_slug: str,
    *,
    repository_root: Path,
) -> ProspectiveMarketEvidenceAssessment:
    profile = get_campaign_requirement_profile(profile_or_slug)
    capability_id = _CAMPAIGN_PRIMARY_CAPABILITY.get(profile.campaign_slug, "US_EQUITY_L1")
    path, summary = _latest_probe_summary(repository_root)
    rel = (
        str(path.relative_to(repository_root)).replace("\\", "/") if path is not None else None
    )
    if summary is None:
        return ProspectiveMarketEvidenceAssessment(
            campaign_slug=profile.campaign_slug,
            capability_id=capability_id,
            disposition=ProspectiveMarketEvidenceDisposition.UNKNOWN,
            evidence_path=rel,
            notes="No dated Moomoo probe summary artifact found.",
        )

    entitlement = summary.get("entitlement")
    row: Mapping[str, Any] | None = None
    if isinstance(entitlement, dict):
        row = entitlement.get(capability_id)
    if not isinstance(row, dict):
        suitability = summary.get("campaign_suitability")
        if isinstance(suitability, dict):
            key = (
                "ES_PROSPECTIVE_MARKET_EVIDENCE"
                if capability_id == "US_FUTURES_QUOTE"
                else "US_EQUITY_PROSPECTIVE_MARKET_EVIDENCE"
            )
            label = str(suitability.get(key) or "")
            if label == "SAMPLE_VERIFIED" or label == "ENTITLED":
                return ProspectiveMarketEvidenceAssessment(
                    campaign_slug=profile.campaign_slug,
                    capability_id=capability_id,
                    disposition=ProspectiveMarketEvidenceDisposition.SAMPLE_VERIFIED,
                    evidence_path=rel,
                    notes="Campaign suitability row from probe summary.",
                )
            if label == "NOT_ENTITLED":
                return ProspectiveMarketEvidenceAssessment(
                    campaign_slug=profile.campaign_slug,
                    capability_id=capability_id,
                    disposition=ProspectiveMarketEvidenceDisposition.NOT_ENTITLED,
                    evidence_path=rel,
                    notes=str(suitability.get("disposition") or ""),
                )
        return ProspectiveMarketEvidenceAssessment(
            campaign_slug=profile.campaign_slug,
            capability_id=capability_id,
            disposition=ProspectiveMarketEvidenceDisposition.UNKNOWN,
            evidence_path=rel,
            notes=f"Capability {capability_id} missing from probe summary.",
        )

    if row.get("verified_receiving") or row.get("entitled"):
        return ProspectiveMarketEvidenceAssessment(
            campaign_slug=profile.campaign_slug,
            capability_id=capability_id,
            disposition=ProspectiveMarketEvidenceDisposition.SAMPLE_VERIFIED,
            evidence_path=rel,
            notes=str(row.get("reason_code") or "entitled"),
        )
    return ProspectiveMarketEvidenceAssessment(
        campaign_slug=profile.campaign_slug,
        capability_id=capability_id,
        disposition=ProspectiveMarketEvidenceDisposition.NOT_ENTITLED,
        evidence_path=rel,
        notes=str(row.get("reason_code") or row.get("notes") or "not_entitled"),
    )


def assess_campaign_market_evidence(
    profile: CampaignRequirementProfile,
    *,
    repository_root: Path,
) -> ProspectiveMarketEvidenceAssessment:
    return assess_moomoo_prospective_market_evidence(
        profile.campaign_slug,
        repository_root=repository_root,
    )


__all__ = [
    "ProspectiveMarketEvidenceAssessment",
    "ProspectiveMarketEvidenceDisposition",
    "assess_campaign_market_evidence",
    "assess_moomoo_prospective_market_evidence",
]
