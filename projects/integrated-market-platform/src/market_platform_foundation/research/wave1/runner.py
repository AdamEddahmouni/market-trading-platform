"""Run all eight preregistered Wave 1 families."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters.export_dataset import examples_from_export_stub, validation_manifest_from_export
from .config import Wave1FrozenRegistry, load_frozen_registry
from .export_gate import assess_research_export_pit, oos_evaluation_authorized
from .harness import evaluate_family
from .reproducibility import deterministic_run_id, examples_fingerprint, run_fingerprint
from .reports import WAVE1_REPORT_SCHEMA_VERSION, Wave1RunReport, wave1_run_report_to_dict


def run_wave1_registry(
    examples: list[dict[str, Any]],
    *,
    registry: Wave1FrozenRegistry | None = None,
    export_manifest: dict[str, Any] | None = None,
    allow_oos: bool = False,
    seed: int = 20260914,
) -> Wave1RunReport:
    reg = registry or load_frozen_registry()
    validation_manifest = None
    pit_status = "PIT-UNKNOWN"
    evidence_class = None
    export_fp = None
    oos_mode = "IN_SAMPLE_ONLY"
    if export_manifest is not None:
        validation_manifest = validation_manifest_from_export(export_manifest)
        assessment = assess_research_export_pit(
            export_manifest,
            validation_dataset_manifest=validation_manifest,
        )
        pit_status = assessment.status
        evidence_class = assessment.evidence_class
        export_fp = assessment.export_fingerprint
        if allow_oos and oos_evaluation_authorized(assessment):
            oos_mode = "OOS_PIT_PASS"
    ex_fp = examples_fingerprint(examples)
    family_ids = tuple(f.family_id for f in reg.families)
    run_fp = run_fingerprint(
        registry_fingerprint=reg.registry_fingerprint,
        export_fingerprint=export_fp,
        examples_fingerprint_value=ex_fp,
        family_ids=family_ids,
        oos_mode=oos_mode,
    )
    run_id = deterministic_run_id(run_fp)
    results = [
        evaluate_family(
            family,
            examples,
            export_manifest=export_manifest,
            validation_dataset_manifest=validation_manifest,
            allow_oos=allow_oos,
            seed=seed + index,
        )
        for index, family in enumerate(reg.families)
    ]
    return Wave1RunReport(
        schema_version=WAVE1_REPORT_SCHEMA_VERSION,
        run_id=run_id,
        run_fingerprint=run_fp,
        registry_fingerprint=reg.registry_fingerprint,
        export_fingerprint=export_fp,
        oos_mode=oos_mode,
        pit_status=pit_status,
        evidence_class=evidence_class,
        family_results=tuple(results),
        metadata={
            "examples_fingerprint": ex_fp,
            "family_count": len(results),
            "program_track": reg.program_track,
            "wave": reg.wave,
        },
    )


def run_wave1_from_export_stub(
    export_manifest: dict[str, Any],
    *,
    registry_path: Path | None = None,
    allow_oos: bool = False,
    seed: int = 20260914,
) -> Wave1RunReport:
    registry = load_frozen_registry(registry_path)
    examples = examples_from_export_stub(export_manifest)
    return run_wave1_registry(
        examples,
        registry=registry,
        export_manifest=export_manifest,
        allow_oos=allow_oos,
        seed=seed,
    )


__all__ = ["run_wave1_from_export_stub", "run_wave1_registry", "wave1_run_report_to_dict"]
