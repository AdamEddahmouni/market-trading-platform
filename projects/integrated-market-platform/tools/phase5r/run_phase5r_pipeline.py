"""Build Phase 5R research/model infrastructure evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
FIXTURE_DIR = ROOT / "docs/research/fixtures/phase5r-adversarial"
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase5r_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.research.baseline_naive import NaiveLastValueModel
from market_platform_foundation.research.dataset_manifest import materialize_dataset_rows
from market_platform_foundation.research.evaluation import evaluation_root_hash, run_walk_forward_evaluation
from market_platform_foundation.research.targets import (
    DEFAULT_HORIZON_NS,
    build_target_rows,
    verify_label_availability,
)

REGISTRY_PATH = ROOT / "manifests/phase5r/assertion-predicates.json"
EVALUATED_AT = "2026-08-15T23:00:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"


def _load_fixture(name: str) -> dict[str, object]:
    doc = load_json_strict(FIXTURE_DIR / name)
    if not isinstance(doc, dict):
        raise ValueError(f"fixture must be object: {name}")
    return doc


def _ingest_admitted_events() -> list[dict[str, object]]:
    ingest_run_id = sha256_bytes(
        canonical_bytes({"collection_root_id": "ROOT-2E7C91F4", "source_object_id": SOURCE_OBJECT_ID})
    )
    adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
    result = adapter.ingest_collection(COLLECTION_ROOT)
    return result.canonical_events


def _dataset_manifest_report(evaluation: dict[str, object]) -> dict[str, object]:
    manifest = evaluation["dataset_manifest"]
    fingerprint = str(manifest.get("dataset_fingerprint", ""))
    row_count = int(evaluation.get("dataset_row_count", 0))
    status = "PASS" if fingerprint and row_count > 0 else "FAIL"
    return {
        "artifact_type": "PHASE_5R_DATASET_MANIFEST_REPORT",
        "dataset_fingerprint": fingerprint,
        "logical_id": "phase5r.dataset_manifest_report",
        "row_count": row_count,
        "status": status,
    }


def _walk_forward_report(evaluation: dict[str, object]) -> dict[str, object]:
    fold_ok = evaluation.get("fold_pit_status") == "PASS"
    label_ok = evaluation.get("label_status") == "PASS"
    status = "PASS" if fold_ok and label_ok else "FAIL"
    return {
        "artifact_type": "PHASE_5R_WALK_FORWARD_REPORT",
        "fold_count": evaluation.get("fold_count", 0),
        "fold_pit_reason_codes": evaluation.get("fold_pit_reason_codes", []),
        "fold_pit_status": evaluation.get("fold_pit_status"),
        "label_reason_codes": evaluation.get("label_reason_codes", []),
        "label_status": evaluation.get("label_status"),
        "logical_id": "phase5r.walk_forward_report",
        "status": status,
        "target_count": evaluation.get("target_count", 0),
    }


def _model_identity_report(evaluation: dict[str, object]) -> dict[str, object]:
    artifact = evaluation["artifact"]
    identity = evaluation["model_identity"]
    dataset_fp = str(evaluation["dataset_manifest"]["dataset_fingerprint"])
    model = NaiveLastValueModel()
    model.load_from_artifact(artifact)
    reloaded = model.artifact_body(dataset_fingerprint=dataset_fp)
    hash_match = str(reloaded["artifact_bytes_hash"]) == str(artifact["artifact_bytes_hash"])
    return {
        "artifact_type": "PHASE_5R_MODEL_IDENTITY_REPORT",
        "artifact_bytes_hash": str(artifact["artifact_bytes_hash"]),
        "logical_id": "phase5r.model_identity_report",
        "model_identity_hash": str(identity["model_identity_hash"]),
        "reload_artifact_hash_match": hash_match,
        "status": "PASS" if hash_match else "FAIL",
    }


def _forecast_interface_report(evaluation: dict[str, object]) -> dict[str, object]:
    predictions = evaluation.get("predictions", [])
    if not isinstance(predictions, list):
        predictions = []
    statuses = [
        str(row.get("forecast_status", "FAIL"))
        for row in predictions
        if isinstance(row, dict)
    ]
    all_pass = bool(statuses) and all(status == "PASS" for status in statuses)
    return {
        "artifact_type": "PHASE_5R_FORECAST_INTERFACE_REPORT",
        "forecast_count": len(statuses),
        "logical_id": "phase5r.forecast_interface_report",
        "status": "PASS" if all_pass else "FAIL",
    }


def _evaluation_determinism_report(events: list[dict[str, object]]) -> dict[str, object]:
    ordered = sort_events(events)
    result_a = run_walk_forward_evaluation(ordered)
    result_b = run_walk_forward_evaluation(ordered)
    root_a = evaluation_root_hash(result_a)
    root_b = evaluation_root_hash(result_b)
    return {
        "artifact_type": "PHASE_5R_EVALUATION_DETERMINISM_REPORT",
        "determinism_match": root_a == root_b,
        "event_count": len(events),
        "evaluation_root_hash_a": root_a,
        "evaluation_root_hash_b": root_b,
        "logical_id": "phase5r.evaluation_determinism_report",
    }


def _pit_adversarial_report() -> dict[str, object]:
    early_bar = _load_fixture("early-label-bar.json")
    horizon_ns = DEFAULT_HORIZON_NS
    future_time = int(early_bar["available_time"]) + horizon_ns
    future_bar = dict(early_bar)
    future_bar["available_time"] = future_time
    future_bar["event_time"] = future_time - 1
    future_bar["historical_ingested_time"] = future_time
    future_bar["source_record_id"] = "BAR-EARLY-LABEL-FUTURE"
    future_bar["normalized_event_id"] = "00000000-0000-5000-8000-000000000111"
    rows = materialize_dataset_rows([early_bar, future_bar])
    targets = build_target_rows(rows, horizon_ns=horizon_ns)
    adversarial_targets: list[dict[str, object]] = []
    for target in targets:
        row = dict(target)
        row["prediction_cutoff"] = int(row["label_available_time"])
        adversarial_targets.append(row)
    label_status, label_reasons = verify_label_availability(adversarial_targets, horizon_ns=horizon_ns)
    leakage_detected = label_status == "FAIL"
    return {
        "artifact_type": "PHASE_5R_PIT_ADVERSARIAL_REPORT",
        "adversarial_cutoff_at_label": True,
        "label_leakage_detected": leakage_detected,
        "logical_id": "phase5r.pit_adversarial_report",
        "reason_codes": label_reasons,
        "status": "PASS" if leakage_detected else "FAIL",
    }


def _safe003_report() -> dict[str, object]:
    reasons: list[str] = []
    route_path: str | None = None
    for path in sorted(ROOT.glob(ENTRYPOINT_GLOB)):
        doc = load_json_strict(path)
        if not isinstance(doc, dict):
            continue
        content = doc.get("content", {})
        if not isinstance(content, dict):
            continue
        prohibited = content.get("prohibited_routes", {})
        if not isinstance(prohibited, dict):
            continue
        nonempty = [
            key
            for key, values in prohibited.items()
            if isinstance(values, list) and values
        ]
        if nonempty:
            reasons.append("SAFE003_ROUTE_PATH_PRESENT")
        else:
            route_path = str(path.relative_to(ROOT).as_posix())
            break
    if route_path is None and not reasons:
        reasons.append("SAFE003_ROUTE_REPORT_MISSING")
    return {
        "artifact_type": "PHASE_5R_SAFE003_REPORT",
        "logical_id": "phase5r.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _ingest_admitted_events()
    evaluation = run_walk_forward_evaluation(sort_events(events))

    dataset_report = _dataset_manifest_report(evaluation)
    walk_forward_report = _walk_forward_report(evaluation)
    model_report = _model_identity_report(evaluation)
    forecast_report = _forecast_interface_report(evaluation)
    determinism_report = _evaluation_determinism_report(events)
    pit_report = _pit_adversarial_report()
    safe003_report = _safe003_report()

    write_canonical_json(output_dir / "dataset-manifest-report.json", dataset_report)
    write_canonical_json(output_dir / "walk-forward-report.json", walk_forward_report)
    write_canonical_json(output_dir / "model-identity-report.json", model_report)
    write_canonical_json(output_dir / "forecast-interface-report.json", forecast_report)
    write_canonical_json(output_dir / "evaluation-determinism-report.json", determinism_report)
    write_canonical_json(output_dir / "pit-adversarial-report.json", pit_report)
    write_canonical_json(output_dir / "safe003-report.json", safe003_report)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "DATASET-001": {
            "dataset_fingerprint": dataset_report["dataset_fingerprint"],
            "reason_codes": [] if dataset_report["status"] == "PASS" else ["DATASET001_MANIFEST_INVALID"],
            "row_count": dataset_report["row_count"],
            "status": dataset_report["status"],
        },
        "MODEL-001": {
            "reason_codes": [] if model_report["status"] == "PASS" else ["MODEL001_RELOAD_MISMATCH"],
            "reload_artifact_hash_match": model_report["reload_artifact_hash_match"],
            "status": model_report["status"],
        },
        "PIT-WF-001": {
            "label_leakage_detected": pit_report["label_leakage_detected"],
            "reason_codes": (
                []
                if walk_forward_report["status"] == "PASS" and pit_report["status"] == "PASS"
                else ["PITWF001_BOUNDARY_OR_LABEL_FAILURE"]
            ),
            "status": (
                "PASS"
                if walk_forward_report["status"] == "PASS" and pit_report["status"] == "PASS"
                else "FAIL"
            ),
        },
        "FCAST-001": {
            "forecast_count": forecast_report["forecast_count"],
            "reason_codes": [] if forecast_report["status"] == "PASS" else ["FCAST001_INTERFACE_FAILURE"],
            "status": forecast_report["status"],
        },
        "DET-001": {
            "evaluation_root_hash": determinism_report["evaluation_root_hash_a"],
            "reason_codes": [] if determinism_report["determinism_match"] else ["DET001_HASH_MISMATCH"],
            "status": "PASS" if determinism_report["determinism_match"] else "FAIL",
        },
        "SAFE-003": {
            "reason_codes": safe003_report["reason_codes"],
            "status": safe003_report["status"],
        },
    }

    selected_evidence = []
    for logical_id, doc in (
        ("phase5r.dataset_manifest_report", dataset_report),
        ("phase5r.walk_forward_report", walk_forward_report),
        ("phase5r.model_identity_report", model_report),
        ("phase5r.forecast_interface_report", forecast_report),
        ("phase5r.evaluation_determinism_report", determinism_report),
        ("phase5r.pit_adversarial_report", pit_report),
        ("phase5r.safe003_report", safe003_report),
    ):
        selected_evidence.append(
            {"logical_id": logical_id, "sha256": sha256_bytes(canonical_bytes(doc))}
        )

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "5r", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase5r.run_phase5r_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase5r_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase5r.assertion_aggregate": "assertion-aggregate.json",
        "phase5r.assertion_registry": "assertion_registry.json",
        "phase5r.assertion_results": "assertion-results.json",
        "phase5r.assertion_run_manifest": "assertion-run-manifest.json",
        "phase5r.dataset_manifest_report": "dataset-manifest-report.json",
        "phase5r.walk_forward_report": "walk-forward-report.json",
        "phase5r.model_identity_report": "model-identity-report.json",
        "phase5r.forecast_interface_report": "forecast-interface-report.json",
        "phase5r.evaluation_determinism_report": "evaluation-determinism-report.json",
        "phase5r.pit_adversarial_report": "pit-adversarial-report.json",
        "phase5r.safe003_report": "safe003-report.json",
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
        "logical_id": "phase5r.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "canonical_event_count": len(events),
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
