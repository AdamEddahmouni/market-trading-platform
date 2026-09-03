"""Build Phase 3 verified adapter evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import (
    COLLECTION_RELATIVE_PATH,
    EquityIntradayJsonlAdapter,
    PINNED_SHA256,
    SOURCE_OBJECT_ID,
    SUPPORTED_CAPABILITIES,
    verify_dependency_lock,
    verify_registry_integrity,
)
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase3_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.registry import registry_snapshot

REGISTRY_PATH = ROOT / "manifests/phase3/assertion-predicates.json"
LOCK_PATH = ROOT / "phase0-dependency-lock.json"
EVALUATED_AT = "2026-08-15T18:00:00.000000000Z"


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ingest_run_id = sha256_bytes(
        canonical_bytes({"collection_root_id": "ROOT-2E7C91F4", "source_object_id": SOURCE_OBJECT_ID})
    )
    adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
    source_path = COLLECTION_ROOT / COLLECTION_RELATIVE_PATH
    first_pass = adapter.ingest_collection(COLLECTION_ROOT)
    second_pass = adapter.ingest_path(source_path)

    adp001_reasons: list[str] = []
    if first_pass.conflict_count:
        adp001_reasons.append("ADP001_IDENTITY_CONFLICT")
    if first_pass.dangling_count:
        adp001_reasons.append("ADP001_DANGLING_PROVENANCE")
    if len(first_pass.provenance_index) != len(first_pass.canonical_events):
        adp001_reasons.append("ADP001_PROVENANCE_COUNT_MISMATCH")

    adp002_reasons: list[str] = []
    if second_pass.conflict_count:
        adp002_reasons.append("ADP002_IDENTITY_CONFLICT_ON_REINGEST")
    if second_pass.idempotent_replays != len(first_pass.canonical_events):
        adp002_reasons.append("ADP002_IDEMPOTENT_REPLAY_COUNT_MISMATCH")

    registry_ids = [row["registry_id"] for row in registry_snapshot()]
    safe002_status, safe002_reasons = verify_registry_integrity(registry_ids)
    safe001_status, safe001_reasons = verify_dependency_lock(LOCK_PATH)

    normalization_report = {
        "artifact_type": "PHASE_3_NORMALIZATION_REPORT",
        "canonical_event_count": len(first_pass.canonical_events),
        "logical_id": "phase3.normalization_report",
        "normalization_version": "phase3.equity-intraday-jsonl/1.0.0",
        "quarantined_count": len(first_pass.quarantined),
        "record_count": first_pass.record_count,
        "source_object_id": SOURCE_OBJECT_ID,
        "source_sha256": PINNED_SHA256,
    }
    provenance_report = {
        "artifact_type": "PHASE_3_PROVENANCE_REPORT",
        "dangling_count": first_pass.dangling_count,
        "logical_id": "phase3.provenance_report",
        "provenance_entry_count": len(first_pass.provenance_index),
    }
    coverage_report = {
        "artifact_type": "PHASE_3_COVERAGE_REPORT",
        "canonical_event_count": len(first_pass.canonical_events),
        "logical_id": "phase3.coverage_report",
        "record_count": first_pass.record_count,
        "unsupported_quarantine_count": len(first_pass.quarantined),
    }
    capability_report = {
        "artifact_type": "PHASE_3_CAPABILITY_REPORT",
        "claimed_capabilities": sorted(SUPPORTED_CAPABILITIES),
        "logical_id": "phase3.capability_report",
        "unsupported_capabilities_emitted": False,
    }
    idempotency_report = {
        "artifact_type": "PHASE_3_IDEMPOTENCY_REPORT",
        "first_pass_event_count": len(first_pass.canonical_events),
        "logical_id": "phase3.idempotency_report",
        "reingest_conflict_count": second_pass.conflict_count,
        "reingest_idempotent_replays": second_pass.idempotent_replays,
    }

    write_canonical_json(output_dir / "normalization-report.json", normalization_report)
    write_canonical_json(output_dir / "provenance-report.json", provenance_report)
    write_canonical_json(output_dir / "coverage-report.json", coverage_report)
    write_canonical_json(output_dir / "capability-report.json", capability_report)
    write_canonical_json(output_dir / "idempotency-report.json", idempotency_report)
    write_canonical_json(
        output_dir / "canonical-events-sample.json",
        {
            "event_count": len(first_pass.canonical_events),
            "logical_id": "phase3.canonical_events_sample",
            "sample": first_pass.canonical_events[:3],
        },
    )

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "ADP-001": {
            "conflict_count": first_pass.conflict_count,
            "dangling_count": first_pass.dangling_count,
            "reason_codes": adp001_reasons,
            "status": "PASS" if not adp001_reasons else "FAIL",
        },
        "ADP-002": {
            "idempotent_replays": second_pass.idempotent_replays,
            "reason_codes": adp002_reasons,
            "reingest_conflict_count": second_pass.conflict_count,
            "status": "PASS" if not adp002_reasons else "FAIL",
        },
        "SAFE-001": {"reason_codes": safe001_reasons, "status": safe001_status},
        "SAFE-002": {"reason_codes": safe002_reasons, "registry_ids": registry_ids, "status": safe002_status},
    }

    selected_evidence = []
    for logical_id, doc in (
        ("phase3.normalization_report", normalization_report),
        ("phase3.provenance_report", provenance_report),
        ("phase3.coverage_report", coverage_report),
        ("phase3.capability_report", capability_report),
        ("phase3.idempotency_report", idempotency_report),
    ):
        selected_evidence.append(
            {"logical_id": logical_id, "sha256": sha256_bytes(canonical_bytes(doc))}
        )

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "3", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase3.run_phase3_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase3_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase3.assertion_aggregate": "assertion-aggregate.json",
        "phase3.assertion_registry": "assertion_registry.json",
        "phase3.assertion_results": "assertion-results.json",
        "phase3.assertion_run_manifest": "assertion-run-manifest.json",
        "phase3.canonical_events_sample": "canonical-events-sample.json",
        "phase3.capability_report": "capability-report.json",
        "phase3.coverage_report": "coverage-report.json",
        "phase3.idempotency_report": "idempotency-report.json",
        "phase3.normalization_report": "normalization-report.json",
        "phase3.provenance_report": "provenance-report.json",
    }
    index_members = []
    for logical_id, filename in sorted(members.items()):
        path = output_dir / filename
        index_members.append(
            {
                "logical_id": logical_id,
                "repository_relative_path": str(path.relative_to(ROOT).as_posix()),
                "sha256": sha256_bytes(path.read_bytes()),
            }
        )
    candidate_body = {
        "candidate_evidence_root": sha256_bytes(canonical_bytes(index_members)),
        "index_members": index_members,
        "logical_id": "phase3.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "canonical_event_count": len(first_pass.canonical_events),
        "output_dir": str(output_dir),
        "run_id": run_id,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    report = build_evidence(Path(args.output_dir).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["aggregate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
