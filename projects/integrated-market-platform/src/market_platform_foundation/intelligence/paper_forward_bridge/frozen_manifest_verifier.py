"""Frozen activation manifest verification (fingerprint + prospective blockers)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ...providers.coverage_gap_engine import GapDisposition, resolve_coverage_gaps_for_campaign
from .activation import (
    ActivationManifest,
    ActivationManifestError,
    ActivationManifestStatus,
    compute_manifest_fingerprint,
    load_activation_manifest,
)
from .preflight import PreflightDisposition, run_forward_test_preflight

_EXPECTED_FTEP_V1_001_FINGERPRINT = (
    "69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C"
)


class FrozenProspectiveDisposition(StrEnum):
    VERIFIED_FROZEN_READY_FOR_PREFLIGHT = "VERIFIED_FROZEN_READY_FOR_PREFLIGHT"
    FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT = "FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT"
    FROZEN_BLOCKED_COVERAGE_GAPS = "FROZEN_BLOCKED_COVERAGE_GAPS"
    NOT_FROZEN = "NOT_FROZEN"
    MANIFEST_INVALID = "MANIFEST_INVALID"


@dataclass(frozen=True, slots=True)
class FrozenManifestVerificationResult:
    campaign_slug: str
    manifest_status: str
    fingerprint: str
    fingerprint_verified: bool
    preflight_disposition: str
    prospective_disposition: FrozenProspectiveDisposition
    coverage_gap_blockers: tuple[str, ...]
    blockers: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "blockers": list(self.blockers),
            "campaign_slug": self.campaign_slug,
            "coverage_gap_blockers": list(self.coverage_gap_blockers),
            "fingerprint": self.fingerprint,
            "fingerprint_verified": self.fingerprint_verified,
            "manifest_status": self.manifest_status,
            "metadata": self.metadata,
            "preflight_disposition": self.preflight_disposition,
            "prospective_disposition": self.prospective_disposition.value,
        }


def verify_frozen_campaign_manifest(
    campaign_slug: str,
    *,
    repository_root: Path,
    expected_fingerprint: str | None = None,
    readiness_report: dict[str, Any] | None = None,
) -> FrozenManifestVerificationResult:
    """Verify frozen manifest integrity and classify prospective activation blockers."""

    blockers: list[str] = []
    manifest: ActivationManifest | None = None
    fingerprint = ""
    try:
        manifest = load_activation_manifest(campaign_slug)
        fingerprint = compute_manifest_fingerprint(manifest.raw)
        stored = manifest.manifest_fingerprint
        if stored and stored.upper() != fingerprint:
            blockers.append("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")
    except ActivationManifestError as exc:
        return FrozenManifestVerificationResult(
            campaign_slug=campaign_slug,
            manifest_status="",
            fingerprint="",
            fingerprint_verified=False,
            preflight_disposition="",
            prospective_disposition=FrozenProspectiveDisposition.MANIFEST_INVALID,
            coverage_gap_blockers=(),
            blockers=(str(exc),),
            metadata={"error": str(exc)},
        )

    expected = (expected_fingerprint or manifest.manifest_fingerprint or "").upper()
    fingerprint_verified = bool(expected) and fingerprint.upper() == expected
    if expected and not fingerprint_verified:
        blockers.append("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")

    status = manifest.status.value if manifest else ""
    if manifest.status != ActivationManifestStatus.FROZEN:
        return FrozenManifestVerificationResult(
            campaign_slug=campaign_slug,
            manifest_status=status,
            fingerprint=fingerprint,
            fingerprint_verified=fingerprint_verified,
            preflight_disposition="",
            prospective_disposition=FrozenProspectiveDisposition.NOT_FROZEN,
            coverage_gap_blockers=(),
            blockers=tuple(blockers),
            metadata={},
        )

    preflight = run_forward_test_preflight(campaign_slug=campaign_slug, mode="PAPER")
    if preflight.disposition != PreflightDisposition.READY:
        blockers.extend(preflight.blockers)

    gap_report = resolve_coverage_gaps_for_campaign(
        campaign_slug,
        repository_root=repository_root,
        readiness_report=readiness_report,
    )
    coverage_blockers = tuple(gap_report.blockers)
    entitlement_blockers = tuple(
        gap_id
        for gap_id in coverage_blockers
        if gap_id.startswith("CAP-REQ-futures.")
        or gap_id.startswith("CAP-REQ-equity.")
        or "ENTITLEMENT" in gap_id
    )

    prospective = FrozenProspectiveDisposition.VERIFIED_FROZEN_READY_FOR_PREFLIGHT
    if gap_report.disposition == GapDisposition.BLOCKING:
        if entitlement_blockers or any(
            "futures.es_quote" in item or "equity.us_l1" in item for item in coverage_blockers
        ):
            prospective = FrozenProspectiveDisposition.FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT
        else:
            prospective = FrozenProspectiveDisposition.FROZEN_BLOCKED_COVERAGE_GAPS
        blockers.extend(f"COVERAGE_GAP:{gap_id}" for gap_id in coverage_blockers)

    return FrozenManifestVerificationResult(
        campaign_slug=campaign_slug,
        manifest_status=status,
        fingerprint=fingerprint,
        fingerprint_verified=fingerprint_verified,
        preflight_disposition=preflight.disposition.value,
        prospective_disposition=prospective,
        coverage_gap_blockers=coverage_blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        metadata={
            "expected_fingerprint": expected,
            "coverage_gap_disposition": gap_report.disposition.value,
        },
    )


def verify_ftep_v1_001_frozen_manifest(
    repository_root: Path,
    *,
    readiness_report: dict[str, Any] | None = None,
) -> FrozenManifestVerificationResult:
    return verify_frozen_campaign_manifest(
        "FTEP-V1-001",
        repository_root=repository_root,
        expected_fingerprint=_EXPECTED_FTEP_V1_001_FINGERPRINT,
        readiness_report=readiness_report,
    )


__all__ = [
    "FrozenManifestVerificationResult",
    "FrozenProspectiveDisposition",
    "verify_frozen_campaign_manifest",
    "verify_ftep_v1_001_frozen_manifest",
]
