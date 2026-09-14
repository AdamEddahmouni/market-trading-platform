"""Research export PIT gate — OOS is blocked until Track D marks export PIT-PASS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dataset_manifest_gate import require_clean_validation_dataset_manifest_dict
from .errors import Wave1ExportGateError

PIT_PASS_STATUS = "PIT-PASS"
NON_EMPIRICAL_EVIDENCE_CLASS = "NON_EMPIRICAL_FIXTURE"


@dataclass(frozen=True, slots=True)
class ResearchExportPitAssessment:
    status: str
    evidence_class: str | None
    pit_codes: tuple[str, ...]
    export_fingerprint: str | None
    validation_dataset_fingerprint: str | None


def _export_metadata(export_manifest: dict[str, Any]) -> dict[str, Any]:
    meta = export_manifest.get("metadata")
    if isinstance(meta, dict):
        return meta
    pit_block = export_manifest.get("pit_assessment")
    if isinstance(pit_block, dict):
        return pit_block
    return {}


def assess_research_export_pit(
    export_manifest: dict[str, Any],
    *,
    validation_dataset_manifest: dict[str, Any] | None = None,
) -> ResearchExportPitAssessment:
    """Assess whether an export may authorize Wave 1 OOS evaluation."""
    meta = _export_metadata(export_manifest)
    status = str(meta.get("pit_status") or meta.get("status") or "PIT-UNKNOWN")
    evidence_class = meta.get("evidence_class")
    if evidence_class is not None:
        evidence_class = str(evidence_class)
    pit_codes: list[str] = []
    if evidence_class == NON_EMPIRICAL_EVIDENCE_CLASS:
        pit_codes.append("NON_EMPIRICAL_FIXTURE")
    if validation_dataset_manifest is not None:
        try:
            require_clean_validation_dataset_manifest_dict(validation_dataset_manifest)
        except Wave1ExportGateError as exc:
            pit_codes.append(exc.code)
        except Exception as exc:  # noqa: BLE001 — surface as pit code, not crash assess
            pit_codes.append(f"VALIDATION_DATASET_MANIFEST:{type(exc).__name__}")
    export_fp = export_manifest.get("export_fingerprint")
    ds_fp = None
    ds_summary = export_manifest.get("dataset_manifest")
    if isinstance(ds_summary, dict):
        ds_fp = ds_summary.get("dataset_fingerprint")
    if validation_dataset_manifest is not None:
        ds_fp = ds_fp or validation_dataset_manifest.get("dataset_fingerprint")
    if status != PIT_PASS_STATUS:
        pit_codes.append("EXPORT_NOT_PIT_PASS")
    return ResearchExportPitAssessment(
        status=status,
        evidence_class=evidence_class,
        pit_codes=tuple(pit_codes),
        export_fingerprint=str(export_fp) if export_fp else None,
        validation_dataset_fingerprint=str(ds_fp) if ds_fp else None,
    )


def require_pit_pass_for_oos(
    export_manifest: dict[str, Any],
    *,
    validation_dataset_manifest: dict[str, Any] | None = None,
) -> ResearchExportPitAssessment:
    assessment = assess_research_export_pit(
        export_manifest,
        validation_dataset_manifest=validation_dataset_manifest,
    )
    if assessment.status != PIT_PASS_STATUS:
        raise Wave1ExportGateError(
            "W1_OOS_BLOCKED_EXPORT_NOT_PIT_PASS",
            details={
                "status": assessment.status,
                "pit_codes": list(assessment.pit_codes),
            },
        )
    if assessment.evidence_class == NON_EMPIRICAL_EVIDENCE_CLASS:
        raise Wave1ExportGateError(
            "W1_OOS_BLOCKED_NON_EMPIRICAL_FIXTURE",
            details={"evidence_class": assessment.evidence_class},
        )
    if assessment.pit_codes:
        raise Wave1ExportGateError(
            "W1_OOS_BLOCKED_PIT_CODES",
            details={"pit_codes": list(assessment.pit_codes)},
        )
    return assessment
