"""Offline historical-bar preflight orchestration and readiness report.

Preflight wraps the Batch 03 ``local_bar_intake`` primitives in a fixed order and
produces a deterministic readiness report. It performs no acquisition, no network
access, no credential access, no case association, and no outcome work. A
``READY_FOR_FUTURE_ASSOCIATION`` result means only that the local bundle passed the
current intake and normalization checks -- never that the data is accurate, the
license is legally sufficient, a particular historical case is covered, an outcome
window is complete, or that any later phase may run.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from ..models import _FrozenAcquisitionModel, _aware_utc
from ..local_bar_intake.artifact_validation import read_artifact_bytes, validate_artifact_bytes
from ..local_bar_intake.models import (
    ColumnMappingProfile,
    IntakeManifest,
    SCHEMA_VERSION,
)
from ..local_bar_intake.normalization import normalize_from_bytes
from ..local_bar_intake.semantics import (
    BarInterval,
    BarSession,
    IntakeReasonCode,
    IntakeValidationStatus,
    PriceAdjustmentSemantics,
    TimestampSemantics,
    VolumeAdjustmentSemantics,
)


PREFLIGHT_CONTRACT_VERSION = "phase_3d_submission_kit_preflight.v1"


class PreflightStatus(StrEnum):
    """Explicit readiness verdict for a locally validated bundle."""

    READY_FOR_FUTURE_ASSOCIATION = "READY_FOR_FUTURE_ASSOCIATION"
    NOT_READY_QUARANTINED = "NOT_READY_QUARANTINED"
    NOT_READY_REJECTED = "NOT_READY_REJECTED"


class PreflightReport(_FrozenAcquisitionModel):
    """Deterministic readiness report. Booleans below stay false by construction."""

    schema_version: str = SCHEMA_VERSION
    preflight_contract_version: str = PREFLIGHT_CONTRACT_VERSION
    bundle_id: str
    artifact_id: str
    profile_id: str
    status: PreflightStatus
    reason_codes: tuple[IntakeReasonCode, ...] = ()
    artifact_sha256: str
    artifact_byte_length: int = Field(ge=0)
    provider_name: str
    provider_product_or_export_name: str
    user_entitlement_assertion: str
    retrieval_time: datetime
    export_time: datetime
    canonical_symbol: str
    provider_symbol: str
    market_or_venue: str
    bar_interval: BarInterval
    event_timezone: str
    timestamp_semantics: TimestampSemantics
    session_coverage: BarSession
    price_adjustment_semantics: PriceAdjustmentSemantics
    volume_adjustment_semantics: VolumeAdjustmentSemantics
    expected_start_time: datetime
    expected_end_time: datetime
    observed_start_time: datetime | None = None
    observed_end_time: datetime | None = None
    normalized_bar_count: int = Field(ge=0)
    rejected_row_count: int = Field(ge=0)
    quarantined_row_count: int = Field(ge=0)
    diagnostic_count: int = Field(ge=0)
    # Readiness is preparation for future authorized work only.
    ready_for_case_association: bool
    # The following five are structurally impossible in this batch and stay false.
    case_association_performed: bool = False
    outcome_capture_performed: bool = False
    phase_3a_records_created: bool = False
    phase_3b_records_created: bool = False
    phase_3e_started: bool = False
    deterministic_id: str | None = None

    @field_validator("reason_codes")
    @classmethod
    def _sort_codes(cls, value: tuple[IntakeReasonCode, ...]) -> tuple[IntakeReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @field_validator(
        "retrieval_time", "export_time", "expected_start_time", "expected_end_time",
        "observed_start_time", "observed_end_time",
    )
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)


def run_preflight_from_bytes(
    manifest: IntakeManifest,
    profile: ColumnMappingProfile,
    content: bytes | None,
) -> PreflightReport:
    """Validate and normalize raw bytes, then build the readiness report.

    Filesystem-free entry point so the whole workflow is deterministically
    testable without touching disk. ``content`` is ``None`` when the artifact is
    absent (which surfaces ``ARTIFACT_MISSING``).
    """
    artifact_report = validate_artifact_bytes(manifest, content)
    outcome = normalize_from_bytes(manifest, profile, content)
    diagnostics = outcome.diagnostics

    reasons: set[IntakeReasonCode] = set(artifact_report.reason_codes)
    reasons.update(diagnostics.bundle_reason_codes)

    artifact_rejected = artifact_report.status is not IntakeValidationStatus.ACCEPTED
    normalization = diagnostics.status
    if artifact_rejected or normalization is IntakeValidationStatus.REJECTED:
        status = PreflightStatus.NOT_READY_REJECTED
    elif normalization is IntakeValidationStatus.QUARANTINED:
        status = PreflightStatus.NOT_READY_QUARANTINED
    else:
        status = PreflightStatus.READY_FOR_FUTURE_ASSOCIATION

    observed_start = None
    observed_end = None
    if outcome.bar_set is not None and outcome.bar_set.bars:
        observed_start = min(bar.event_start_time for bar in outcome.bar_set.bars)
        observed_end = max(bar.event_end_time for bar in outcome.bar_set.bars)

    ready = status is PreflightStatus.READY_FOR_FUTURE_ASSOCIATION
    return PreflightReport(
        bundle_id=manifest.bundle_id,
        artifact_id=f"{manifest.bundle_id}::raw",
        profile_id=profile.profile_id,
        status=status,
        reason_codes=tuple(reasons),
        artifact_sha256=manifest.artifact_sha256,
        artifact_byte_length=manifest.artifact_byte_length,
        provider_name=manifest.provider_name,
        provider_product_or_export_name=manifest.provider_product_or_export_name,
        user_entitlement_assertion=manifest.user_entitlement_assertion,
        retrieval_time=manifest.retrieval_time,
        export_time=manifest.export_time,
        canonical_symbol=manifest.canonical_symbol,
        provider_symbol=manifest.provider_symbol,
        market_or_venue=manifest.market_or_venue,
        bar_interval=manifest.bar_interval,
        event_timezone=manifest.event_timezone,
        timestamp_semantics=manifest.timestamp_semantics,
        session_coverage=manifest.session_coverage,
        price_adjustment_semantics=manifest.price_adjustment_semantics,
        volume_adjustment_semantics=manifest.volume_adjustment_semantics,
        expected_start_time=manifest.expected_start_time,
        expected_end_time=manifest.expected_end_time,
        observed_start_time=observed_start,
        observed_end_time=observed_end,
        normalized_bar_count=0 if outcome.bar_set is None else len(outcome.bar_set.bars),
        rejected_row_count=diagnostics.rejected_count,
        quarantined_row_count=diagnostics.quarantined_count,
        diagnostic_count=len(diagnostics.row_diagnostics),
        ready_for_case_association=ready,
    )


def run_preflight(
    root: Path,
    manifest: IntakeManifest,
    profile: ColumnMappingProfile,
) -> PreflightReport:
    """Validate and normalize an on-disk bundle, then build the readiness report.

    The absolute ``root`` is used only to read bytes; it never enters the report's
    deterministic identity.
    """
    return run_preflight_from_bytes(manifest, profile, read_artifact_bytes(root, manifest))


def hash_file(path: Path) -> dict:
    """Offline SHA-256 and byte length for an operator-supplied file.

    Emits the file's basename only; the absolute path is never included so this
    view is safe to paste into a manifest workflow and never leaks a machine path.
    """
    content = path.read_bytes()
    return {
        "file_name": path.name,
        "byte_length": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


__all__ = [
    "PREFLIGHT_CONTRACT_VERSION",
    "PreflightStatus",
    "PreflightReport",
    "run_preflight",
    "run_preflight_from_bytes",
    "hash_file",
]
