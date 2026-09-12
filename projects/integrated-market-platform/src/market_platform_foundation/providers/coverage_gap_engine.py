"""Deterministic coverage-gap resolver (capability snapshot + campaign profile)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .capability_contract import (
    CapabilityAccessState,
    CapabilityMatrixSnapshot,
    CapabilitySupportLevel,
    CampaignRole,
    access_state_at_least,
    snapshot_from_dict,
)
from .capability_requirements import CampaignRequirementProfile, get_campaign_requirement_profile
from .capability_snapshot import build_capability_matrix_snapshot

DEFAULT_WAVE_A_DIR = Path("artifacts/wave-a-findings")


class GapDisposition(StrEnum):
    BLOCKING = "BLOCKING"
    DEFERRED = "DEFERRED"
    INFORMATIONAL = "INFORMATIONAL"
    SATISFIED = "SATISFIED"


@dataclass(frozen=True, slots=True)
class CoverageGap:
    gap_id: str
    disposition: GapDisposition
    source: str
    summary: str
    reason_code: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "evidence_refs": list(self.evidence_refs),
            "gap_id": self.gap_id,
            "reason_code": self.reason_code,
            "source": self.source,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class CoverageGapReport:
    profile_id: str
    campaign_slug: str
    disposition: GapDisposition
    gaps: tuple[CoverageGap, ...]
    blockers: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "blockers": list(self.blockers),
            "campaign_slug": self.campaign_slug,
            "disposition": self.disposition.value,
            "gaps": [row.to_dict() for row in self.gaps],
            "metadata": self.metadata,
            "profile_id": self.profile_id,
        }


_CLASSIFICATION_TO_DISPOSITION: dict[str, GapDisposition] = {
    "BLOCKER": GapDisposition.BLOCKING,
    "OWNER": GapDisposition.BLOCKING,
    "OWNER_RESOLVED": GapDisposition.SATISFIED,
    "DESIGN": GapDisposition.BLOCKING,
    "INTEGRATION": GapDisposition.BLOCKING,
    "BY_DESIGN": GapDisposition.INFORMATIONAL,
    "OPS": GapDisposition.INFORMATIONAL,
    "SCOPE": GapDisposition.INFORMATIONAL,
    "CLOSED": GapDisposition.SATISFIED,
}


def _code_gap_disposition(meta: Mapping[str, Any]) -> GapDisposition:
    classification = str(meta.get("classification", "")).strip().upper()
    if classification in {"CLOSED", "SATISFIED"}:
        return GapDisposition.SATISFIED
    status = str(meta.get("status", "")).strip().upper()
    if status in {"CLOSED", "SATISFIED", "RESOLVED"}:
        return GapDisposition.SATISFIED
    resolution = str(meta.get("resolution", "")).strip().upper()
    if resolution in {"CLOSED", "SATISFIED", "IMPLEMENTED"}:
        return GapDisposition.SATISFIED
    return GapDisposition.BLOCKING


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_wave_a_gap_catalog(repository_root: Path) -> dict[str, dict[str, Any]]:
    """Index Wave A gap rows by id from news inventory and FTEP campaign audit."""

    root = repository_root.resolve()
    catalog: dict[str, dict[str, Any]] = {}

    news_path = root / DEFAULT_WAVE_A_DIR / "news-data-inventory.json"
    if news_path.is_file():
        payload = _load_json(news_path)
        for row in payload.get("gaps", ()):
            gap_id = str(row.get("id", ""))
            if gap_id:
                catalog[gap_id] = {
                    "classification": str(row.get("classification", "BLOCKER")),
                    "summary": str(row.get("title", row.get("summary", ""))),
                    "source": "news-data-inventory",
                    "evidence_refs": tuple(str(item) for item in row.get("evidence", ())),
                }

    ftep_path = root / DEFAULT_WAVE_A_DIR / "ftep-campaign-audit.json"
    if ftep_path.is_file():
        payload = _load_json(ftep_path)
        for row in payload.get("code_gaps", ()):
            gap_id = str(row.get("id", ""))
            if gap_id:
                status = str(row.get("status", "")).strip().upper()
                classification = "CLOSED" if status in {"CLOSED", "SATISFIED", "RESOLVED"} else "INTEGRATION"
                catalog[gap_id] = {
                    "classification": classification,
                    "summary": str(row.get("title", row.get("summary", ""))),
                    "source": "ftep-campaign-audit.code_gaps",
                    "evidence_refs": tuple(str(item) for item in row.get("evidence", ())),
                    "status": status,
                    "resolution": str(row.get("resolution", "")).strip().upper(),
                }

    return catalog


def _provider_index(snapshot: CapabilityMatrixSnapshot) -> dict[str, Any]:
    return {row.provider_id: row for row in snapshot.providers}


def _capability_access(
    provider: Any,
    capability_id: str,
) -> tuple[CapabilityAccessState | None, CapabilitySupportLevel | None]:
    for entry in provider.capabilities:
        if entry.capability_id == capability_id:
            state = entry.access_state or provider.access_state
            return state, entry.support_level
    return None, None


def _evaluate_capability_requirement(
    requirement: Any,
    providers: Mapping[str, Any],
) -> CoverageGap:
    provider_id = requirement.provider_id
    if not provider_id or provider_id not in providers:
        return CoverageGap(
            gap_id=f"CAP-REQ-{requirement.requirement_id}",
            disposition=GapDisposition.BLOCKING,
            source="capability_requirement",
            summary=requirement.notes or requirement.requirement_id,
            reason_code="PROVIDER_NOT_IN_SNAPSHOT",
            evidence_refs=(f"provider_id={provider_id}",),
        )

    provider = providers[provider_id]
    access, support = _capability_access(provider, requirement.capability_id)
    if support == CapabilitySupportLevel.KNOWN_UNSUPPORTED:
        return CoverageGap(
            gap_id=f"CAP-REQ-{requirement.requirement_id}",
            disposition=GapDisposition.BLOCKING,
            source="capability_requirement",
            summary=requirement.notes or requirement.requirement_id,
            reason_code="CAPABILITY_KNOWN_UNSUPPORTED",
            evidence_refs=(f"{provider_id}/{requirement.capability_id}",),
        )
    if support == CapabilitySupportLevel.UNKNOWN or access is None:
        return CoverageGap(
            gap_id=f"CAP-REQ-{requirement.requirement_id}",
            disposition=GapDisposition.BLOCKING,
            source="capability_requirement",
            summary=requirement.notes or requirement.requirement_id,
            reason_code="CAPABILITY_UNKNOWN_OR_UNVERIFIED",
            evidence_refs=(f"{provider_id}/{requirement.capability_id}",),
        )
    if not access_state_at_least(access, requirement.minimum_access_state):
        return CoverageGap(
            gap_id=f"CAP-REQ-{requirement.requirement_id}",
            disposition=GapDisposition.BLOCKING,
            source="capability_requirement",
            summary=requirement.notes or requirement.requirement_id,
            reason_code="CAPABILITY_ACCESS_STATE_INSUFFICIENT",
            evidence_refs=(
                f"{provider_id}/{requirement.capability_id}",
                f"observed={access.value}",
                f"required>={requirement.minimum_access_state.value}",
            ),
        )

    return CoverageGap(
        gap_id=f"CAP-REQ-{requirement.requirement_id}",
        disposition=GapDisposition.SATISFIED,
        source="capability_requirement",
        summary=requirement.notes or requirement.requirement_id,
        reason_code="CAPABILITY_REQUIREMENT_MET",
        evidence_refs=(f"{provider_id}/{requirement.capability_id}",),
    )


def _evaluate_activation_gate_g_a6(snapshot: CapabilityMatrixSnapshot) -> CoverageGap:
    for record in snapshot.providers:
        if access_state_at_least(record.access_state, CapabilityAccessState.CAMPAIGN_BOUND):
            if record.campaign_role in {
                CampaignRole.AUTHORITY,
                CampaignRole.CHALLENGER,
                CampaignRole.CONTEXT_ONLY,
            }:
                return CoverageGap(
                    gap_id="G-A6",
                    disposition=GapDisposition.SATISFIED,
                    source="activation_gate",
                    summary="Market Data Capability Contract campaign binding evidenced.",
                    reason_code="G_A6_CAMPAIGN_BOUND_PRESENT",
                    evidence_refs=(record.provider_id,),
                )
    return CoverageGap(
        gap_id="G-A6",
        disposition=GapDisposition.BLOCKING,
        source="activation_gate",
        summary="No provider at CAMPAIGN_BOUND for campaign-scoped market data.",
        reason_code="G_A6_CAMPAIGN_BOUND_MISSING",
        evidence_refs=("docs/engineering/FTEP_ACTIVATION_GATES.md",),
    )


def resolve_coverage_gaps(
    *,
    profile: CampaignRequirementProfile,
    snapshot: CapabilityMatrixSnapshot,
    wave_a_catalog: Mapping[str, Mapping[str, Any]] | None = None,
) -> CoverageGapReport:
    """Resolve campaign-scoped gaps from profile requirements and Wave A catalog."""

    providers = _provider_index(snapshot)
    gaps: list[CoverageGap] = []

    for requirement in profile.capability_requirements:
        gaps.append(_evaluate_capability_requirement(requirement, providers))

    if "G-A6" in profile.activation_gate_ids:
        gaps.append(_evaluate_activation_gate_g_a6(snapshot))

    catalog = wave_a_catalog or {}
    for gap_id in profile.wave_a_gap_ids:
        meta = catalog.get(gap_id, {})
        classification = str(meta.get("classification", "BLOCKER"))
        disposition = _CLASSIFICATION_TO_DISPOSITION.get(classification, GapDisposition.BLOCKING)
        gaps.append(
            CoverageGap(
                gap_id=gap_id,
                disposition=disposition,
                source=str(meta.get("source", "wave_a_catalog")),
                summary=str(meta.get("summary", gap_id)),
                reason_code=f"WAVE_A_{classification}",
                evidence_refs=tuple(meta.get("evidence_refs", ())),
            )
        )

    for gap_id in profile.code_gap_ids:
        meta = catalog.get(gap_id, {})
        disposition = _code_gap_disposition(meta)
        reason = (
            "FTEP_CODE_GAP_CLOSED"
            if disposition == GapDisposition.SATISFIED
            else "FTEP_CODE_GAP_OPEN"
        )
        gaps.append(
            CoverageGap(
                gap_id=gap_id,
                disposition=disposition,
                source=str(meta.get("source", "ftep_code_gap")),
                summary=str(meta.get("summary", gap_id)),
                reason_code=reason,
                evidence_refs=tuple(meta.get("evidence_refs", ())),
            )
        )

    gaps.sort(key=lambda row: (row.disposition.value, row.gap_id))
    blockers = tuple(
        sorted(
            {
                row.gap_id
                for row in gaps
                if row.disposition == GapDisposition.BLOCKING
            }
        )
    )
    overall = GapDisposition.SATISFIED if not blockers else GapDisposition.BLOCKING
    return CoverageGapReport(
        profile_id=profile.profile_id,
        campaign_slug=profile.campaign_slug,
        disposition=overall,
        gaps=tuple(gaps),
        blockers=blockers,
        metadata={"gap_count": len(gaps), "blocker_count": len(blockers)},
    )


def resolve_coverage_gaps_for_campaign(
    profile_or_slug: str,
    *,
    repository_root: Path,
    snapshot: CapabilityMatrixSnapshot | None = None,
    readiness_report: Mapping[str, Any] | None = None,
) -> CoverageGapReport:
    profile = get_campaign_requirement_profile(profile_or_slug)
    catalog = load_wave_a_gap_catalog(repository_root)
    matrix = snapshot or build_capability_matrix_snapshot(
        repository_root=repository_root,
        readiness_report=readiness_report,
        observed_at="2026-09-11T23:00:00Z",
    )
    return resolve_coverage_gaps(profile=profile, snapshot=matrix, wave_a_catalog=catalog)


def snapshot_from_json_file(path: Path) -> CapabilityMatrixSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return snapshot_from_dict(payload)
