"""Research Export v1 — immutable PIT package builder and loaders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes, write_canonical_json
from ..intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..intelligence.validation.dataset_manifest import (
    build_validation_dataset_manifest,
    require_clean_validation_dataset_manifest,
)
from ..intelligence.validation.serialization import validation_dataset_manifest_v1_to_dict
from ..intelligence.validation.temporal_knowledge import DEFAULT_TEMPORAL_KNOWLEDGE_POLICY
from ..intelligence.validation.types import (
    HoldoutSpec,
    StatisticalPlan,
    ValidationExample,
    ValidationPlanV1,
)
from .export_v1_audit import run_leakage_firewall, run_pit_audit
from .export_v1_profiles import (
    PROFILE_EVENT_MACRO,
    PROFILE_MARKET_TECHNICAL,
    build_event_macro_tables,
    build_market_technical_tables,
)

# Re-export profile codes for callers/tests.
PROFILE_A = PROFILE_MARKET_TECHNICAL
PROFILE_C = PROFILE_EVENT_MACRO
from .pit_export import build_research_export_manifest, research_export_fingerprint

EXPORT_SCHEMA_VERSION = "1.0.0"
RESEARCH_EXPORT_IMPLEMENTATION = "research_export_v1/1.0.0"
RESEARCH_EXPORT_EXPERIMENT_ID = "RESEARCH-EXPORT-V1"
EXPORT_OPERATOR_PIT_STATUS_PENDING = "PIT-PENDING"
EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE = "NON_EMPIRICAL_FIXTURE"
MATLAB_HANDOFF_CONTRACT = "research_export_v1_matlab_handoff/1.0.0"


def default_export_operator_metadata() -> dict[str, Any]:
    """Operator-facing PIT classification for fixture-built exports (not Wave 1 OOS authorization)."""
    return {
        "pit_status": EXPORT_OPERATOR_PIT_STATUS_PENDING,
        "evidence_class": EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE,
        "pit_classification_note": (
            "Fixture-backed Research Export v1 build; pit_audit PASS does not authorize Wave 1 OOS."
        ),
    }


def producing_code_sha256() -> str:
    root = Path(__file__).resolve().parent
    chunks = [
        root.joinpath("export_v1_audit.py").read_bytes(),
        root.joinpath("export_v1_profiles.py").read_bytes(),
        Path(__file__).read_bytes(),
    ]
    return sha256_bytes(b"".join(chunks)).upper()


def _table_content_hash(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_bytes(rows))


def _research_validation_plan(*, horizon_ns: int, decision_start_ns: int, decision_end_ns: int) -> ValidationPlanV1:
    holdout = HoldoutSpec(
        holdout_start_ns=decision_start_ns,
        holdout_end_ns=decision_end_ns,
        selector_ref="research_export_v1",
    )
    stats = StatisticalPlan(
        block_length=2,
        replicate_count=50,
        seed=8193,
        confidence_level=0.95,
        minimum_paired_sample=2,
    )
    plan = ValidationPlanV1(
        validation_plan_id="PENDING",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        experiment_id=RESEARCH_EXPORT_EXPERIMENT_ID,
        candidate_ids=("research-export-wrap",),
        candidate_artifact_hashes=(producing_code_sha256(),),
        control_ref="research_export_baseline",
        target_kind="RESEARCH_EXPORT",
        horizon_ns=horizon_ns,
        mode="OFFLINE_RESEARCH",
        validation_method="PIT_DATASET_WRAP",
        walk_forward_spec=None,
        purge_ns=0,
        embargo_ns=0,
        holdout_spec=holdout,
        primary_metric="pit_audit_pass_rate",
        guardrail_metrics=(),
        statistical_plan=stats,
        temporal_knowledge_policy=DEFAULT_TEMPORAL_KNOWLEDGE_POLICY,
        minimum_paired_sample=2,
        scenario_id="research-export-v1",
        metadata={"research_export": True},
    )
    from ..intelligence.validation.identity import derive_validation_plan_id

    resolved_id = derive_validation_plan_id(plan)
    return ValidationPlanV1(
        validation_plan_id=resolved_id,
        schema_version=plan.schema_version,
        experiment_id=plan.experiment_id,
        candidate_ids=plan.candidate_ids,
        candidate_artifact_hashes=plan.candidate_artifact_hashes,
        control_ref=plan.control_ref,
        target_kind=plan.target_kind,
        horizon_ns=plan.horizon_ns,
        mode=plan.mode,
        validation_method=plan.validation_method,
        walk_forward_spec=plan.walk_forward_spec,
        purge_ns=plan.purge_ns,
        embargo_ns=plan.embargo_ns,
        holdout_spec=plan.holdout_spec,
        primary_metric=plan.primary_metric,
        guardrail_metrics=plan.guardrail_metrics,
        statistical_plan=plan.statistical_plan,
        temporal_knowledge_policy=plan.temporal_knowledge_policy,
        minimum_paired_sample=plan.minimum_paired_sample,
        scenario_id=plan.scenario_id,
        implementation_version=plan.implementation_version,
        metadata=dict(plan.metadata),
    )


def _validation_examples_from_outcomes(
    outcomes: list[dict[str, Any]],
    *,
    horizon_ns: int,
) -> tuple[ValidationExample, ...]:
    examples: list[ValidationExample] = []
    for index, row in enumerate(outcomes):
        decision_ns = int(row["decision_at_ns"])
        label_ns = int(row["label_available_time_ns"])
        forward = row.get("forward_return")
        if forward is not None:
            binary = 1 if float(forward) > 0 else 0
        else:
            actual = row.get("actual")
            binary = 1 if actual is not None and float(actual) > 0 else 0
        example_id = str(row.get("event_id") or row.get("instrument_id") or index)
        label_time = label_ns if label_ns > decision_ns else decision_ns + max(horizon_ns, 1)
        examples.append(
            ValidationExample(
                example_id=f"rex-{example_id}-{decision_ns}",
                snapshot_id=f"snap-{example_id}-{decision_ns}",
                decision_time_ns=decision_ns,
                label_available_time_ns=label_time,
                binary_label=binary,
                candidate_probability=0.5,
                control_probability=0.5,
                forecast_id=f"fc-{example_id}",
                outcome_id=f"out-{example_id}",
            )
        )
    return tuple(examples)


def derive_export_id(manifest_body: dict[str, Any]) -> str:
    payload = dict(manifest_body)
    payload.pop("export_id", None)
    payload.pop("manifest_hash", None)
    digest = sha256_bytes(canonical_bytes(payload))
    return f"RESEXP-{digest.upper()}"


def manifest_hash(manifest_body: dict[str, Any]) -> str:
    payload = dict(manifest_body)
    payload.pop("manifest_hash", None)
    return sha256_bytes(canonical_bytes(payload)).upper()


@dataclass(frozen=True, slots=True)
class ResearchExportV1Package:
    manifest: dict[str, Any]
    tables: dict[str, list[dict[str, Any]]]

    def to_dict(self) -> dict[str, Any]:
        return {"manifest": self.manifest, "tables": self.tables}


def build_research_export_v1(
    *,
    profile: str,
    repository_head_sha: str | None = None,
    created_at_ns: int = 178_735_680_000_000_000,
) -> ResearchExportV1Package:
    if profile == PROFILE_MARKET_TECHNICAL:
        context, tables, _sources = build_market_technical_tables()
    elif profile == PROFILE_EVENT_MACRO:
        context, tables, _sources = build_event_macro_tables()
    else:
        raise ValueError(f"UNSUPPORTED_PROFILE:{profile}")

    table_hashes = {name: _table_content_hash(rows) for name, rows in sorted(tables.items())}
    row_counts = {name: len(rows) for name, rows in tables.items()}
    excluded = len(tables.get("audit_exclusions") or [])

    pit_audit = run_pit_audit(
        market_observations=list(tables.get("market_observations") or []),
        feature_snapshots=list(tables.get("feature_snapshots") or []),
        realized_outcomes=list(tables.get("realized_outcomes") or []),
        instrument_rows=list(tables.get("instruments") or []),
        information_events=list(tables.get("information_events") or []) or None,
    )
    leakage = run_leakage_firewall(
        list(tables.get("feature_snapshots") or []),
        list(tables.get("realized_outcomes") or []),
    )

    materialized_rows = [
        {
            "available_time": row["decision_at_ns"],
            "capability": "research_export_v1",
            "feature_id": "decision_anchor",
            "instrument_id": row["instrument_id"],
            "prediction_cutoff": row["decision_at_ns"],
            "value": "0",
        }
        for row in tables.get("feature_snapshots") or []
    ]
    from .dataset_manifest import build_dataset_manifest

    dataset_manifest = build_dataset_manifest(materialized_rows, member_filename="research-export-v1-rows.jsonl")
    pit_binding = build_research_export_manifest(
        dataset_manifest,
        source_sha256=str(context["source_sha256"]),
        prediction_cutoff_ns=int(context["decision_cutoff_ns"]),
        experiment_binding=dict(context["experiment_binding"]),
        repository_head_sha=repository_head_sha,
    )

    plan = _research_validation_plan(
        horizon_ns=int(context.get("horizon_ns") or 1),
        decision_start_ns=int(context["decision_start_ns"]),
        decision_end_ns=int(context["decision_end_ns"]),
    )
    validation_examples = _validation_examples_from_outcomes(
        list(tables.get("realized_outcomes") or []),
        horizon_ns=int(context.get("horizon_ns") or 1),
    )
    validation_manifest = build_validation_dataset_manifest(
        plan,
        fold_or_holdout_ref=f"research-export-{profile.lower()}",
        examples=validation_examples,
        decision_start_ns=int(context["decision_start_ns"]),
        decision_end_ns=int(context["decision_end_ns"]),
        extra_metadata={
            "research_export_profile": profile,
            "source_fixture": context["source_fixture"],
        },
    )
    if pit_audit["status"] == "PASS" and leakage["status"] == "PASS":
        require_clean_validation_dataset_manifest(validation_manifest)

    manifest_body: dict[str, Any] = {
        "created_at_ns": created_at_ns,
        "dataset_manifest": dataset_manifest,
        "decision_cutoff_ns": int(context["decision_cutoff_ns"]),
        "evidence_mode": "OFFLINE_RESEARCH",
        "excluded_row_count": excluded,
        "experiment_id": RESEARCH_EXPORT_EXPERIMENT_ID,
        "export_profile": profile,
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "implementation_version": RESEARCH_EXPORT_IMPLEMENTATION,
        "leakage_firewall": leakage,
        "pit_audit": pit_audit,
        "pit_export_binding": pit_binding,
        "producing_code_sha256": producing_code_sha256(),
        "row_counts": row_counts,
        "source_fixture_paths": [context["source_fixture"]],
        "source_sha256": str(context["source_sha256"]),
        "table_content_hashes": table_hashes,
        "temporal_policy": {
            "decision_field": "decision_at_ns",
            "earliest_usable_field": "earliest_usable_at_ns",
            "observed_field": "observed_at_ns",
            "source_field": "source_time_ns",
        },
        "validation_dataset_manifest": validation_dataset_manifest_v1_to_dict(validation_manifest),
        "metadata": default_export_operator_metadata(),
    }
    if repository_head_sha:
        manifest_body["repository_head_sha"] = repository_head_sha.strip().lower()
    manifest_body["export_fingerprint"] = research_export_fingerprint(
        {
            "export_schema_version": EXPORT_SCHEMA_VERSION,
            "pit_export_binding": pit_binding,
            "source_sha256": context["source_sha256"],
        }
    )
    export_id = derive_export_id(manifest_body)
    manifest_body["export_id"] = export_id
    manifest_body["manifest_hash"] = manifest_hash(manifest_body)
    return ResearchExportV1Package(manifest=manifest_body, tables=tables)


def write_research_export_v1_package(output_dir: Path, package: ResearchExportV1Package) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "research_export_manifest.json"
    write_canonical_json(manifest_path, package.manifest)
    for table_name, rows in sorted(package.tables.items()):
        table_path = output_dir / f"{table_name}.json"
        write_canonical_json(table_path, rows)
    parity = build_matlab_parity_reference(package)
    write_canonical_json(output_dir / "matlab_parity_reference.json", parity)
    validation_payload = package.manifest.get("validation_dataset_manifest")
    if isinstance(validation_payload, dict):
        write_canonical_json(output_dir / "validation_dataset_manifest.json", validation_payload)
    handoff = build_matlab_handoff_manifest(package)
    write_canonical_json(output_dir / "matlab_handoff_manifest.json", handoff)
    return manifest_path


def load_research_export_v1_package(package_dir: Path) -> ResearchExportV1Package:
    manifest_path = package_dir / "research_export_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("RESEARCH_EXPORT_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tables: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(package_dir.glob("*.json")):
        if path.name in {
            "research_export_manifest.json",
            "matlab_parity_reference.json",
            "matlab_handoff_manifest.json",
            "validation_dataset_manifest.json",
        }:
            continue
        tables[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    package = ResearchExportV1Package(manifest=manifest, tables=tables)
    verify_research_export_v1_package(package)
    return package


def verify_research_export_v1_package(package: ResearchExportV1Package) -> None:
    manifest = package.manifest
    if manifest.get("export_id") != derive_export_id(manifest):
        raise ValueError("EXPORT_ID_MISMATCH")
    if manifest.get("manifest_hash") != manifest_hash(manifest):
        raise ValueError("MANIFEST_HASH_MISMATCH")
    stored_hashes = manifest.get("table_content_hashes") or {}
    for name, rows in package.tables.items():
        if name not in stored_hashes:
            continue
        if stored_hashes[name] != _table_content_hash(rows):
            raise ValueError(f"TABLE_HASH_MISMATCH:{name}")
    pit_audit = run_pit_audit(
        market_observations=list(package.tables.get("market_observations") or []),
        feature_snapshots=list(package.tables.get("feature_snapshots") or []),
        realized_outcomes=list(package.tables.get("realized_outcomes") or []),
        instrument_rows=list(package.tables.get("instruments") or []),
        information_events=list(package.tables.get("information_events") or []) or None,
    )
    if pit_audit["status"] != manifest.get("pit_audit", {}).get("status"):
        raise ValueError("PIT_AUDIT_STATUS_DRIFT")
    if manifest.get("pit_audit", {}).get("status") == "FAIL":
        return
    validation_payload = manifest.get("validation_dataset_manifest")
    if validation_payload:
        from ..intelligence.validation.serialization import validation_dataset_manifest_v1_from_dict

        wrapped = validation_dataset_manifest_v1_from_dict(validation_payload)
        require_clean_validation_dataset_manifest(wrapped)


def build_matlab_handoff_manifest(package: ResearchExportV1Package) -> dict[str, Any]:
    """Entry-point manifest for MATLAB jsondecode loaders (tables remain per-table JSON files)."""
    validation_payload = package.manifest.get("validation_dataset_manifest")
    return {
        "export_id": package.manifest.get("export_id"),
        "export_profile": package.manifest.get("export_profile"),
        "manifest_file": "research_export_manifest.json",
        "matlab_handoff_contract": MATLAB_HANDOFF_CONTRACT,
        "metadata": package.manifest.get("metadata"),
        "parity_reference_file": "matlab_parity_reference.json",
        "table_files": {name: f"{name}.json" for name in sorted(package.tables.keys())},
        "validation_dataset_manifest": validation_payload,
        "validation_dataset_manifest_file": "validation_dataset_manifest.json",
    }


def load_matlab_handoff_manifest(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "matlab_handoff_manifest.json"
    if not path.is_file():
        raise ValueError("MATLAB_HANDOFF_MANIFEST_MISSING")
    return json.loads(path.read_text(encoding="utf-8"))


def build_matlab_parity_reference(package: ResearchExportV1Package) -> dict[str, Any]:
    """Reference statistics for MATLAB/Python parity (no MATLAB runtime required)."""
    features = package.tables.get("feature_snapshots") or []
    outcomes = package.tables.get("realized_outcomes") or []
    close_sum = 0.0
    close_count = 0
    for row in features:
        values = row.get("feature_values") or {}
        if "bar_close" in values:
            close_sum += float(values["bar_close"])
            close_count += 1
    forward_sum = 0.0
    forward_count = 0
    for row in outcomes:
        if row.get("forward_return") is not None:
            forward_sum += float(row["forward_return"])
            forward_count += 1
    macro_actual_sum = 0.0
    macro_count = 0
    for row in outcomes:
        if row.get("actual") is not None:
            macro_actual_sum += float(row["actual"])
            macro_count += 1
    return {
        "export_id": package.manifest.get("export_id"),
        "matlab_loader_contract": "research_export_v1_matlab_parity/1.0.0",
        "reference_statistics": {
            "feature_row_count": len(features),
            "outcome_row_count": len(outcomes),
            "bar_close_sum": close_sum,
            "bar_close_count": close_count,
            "forward_return_sum": forward_sum,
            "forward_return_count": forward_count,
            "macro_actual_sum": macro_actual_sum,
            "macro_actual_count": macro_count,
        },
    }


def matlab_parity_check(package: ResearchExportV1Package, reference: dict[str, Any]) -> bool:
    computed = build_matlab_parity_reference(package)
    return computed["reference_statistics"] == reference.get("reference_statistics")


__all__ = [
    "EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE",
    "EXPORT_OPERATOR_PIT_STATUS_PENDING",
    "EXPORT_SCHEMA_VERSION",
    "MATLAB_HANDOFF_CONTRACT",
    "PROFILE_A",
    "PROFILE_C",
    "PROFILE_EVENT_MACRO",
    "PROFILE_MARKET_TECHNICAL",
    "ResearchExportV1Package",
    "build_matlab_handoff_manifest",
    "build_matlab_parity_reference",
    "build_research_export_v1",
    "default_export_operator_metadata",
    "derive_export_id",
    "load_matlab_handoff_manifest",
    "load_research_export_v1_package",
    "manifest_hash",
    "matlab_parity_check",
    "producing_code_sha256",
    "verify_research_export_v1_package",
    "write_research_export_v1_package",
]
