"""Build Phase 5 capability-supported feature evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
FIXTURE_DIR = ROOT / "docs/research/fixtures/phase5-adversarial"
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.features.institutional import WHALE_FAMILIES, query_institutional_evidence
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase5_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.replay.feature_lifecycle import (
    run_feature_replay,
    run_feature_root_hash,
    verify_capability_surface,
    verify_pit_surface,
)

REGISTRY_PATH = ROOT / "manifests/phase5/assertion-predicates.json"
EVALUATED_AT = "2026-08-15T22:00:00.000000000Z"
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


def _feature_snapshot_report(events: list[dict[str, object]]) -> dict[str, object]:
    max_time = max(int(event["available_time"]) for event in events)
    state = run_feature_replay(
        events,
        clocks=[max_time],
        decision_times=[max_time],
        prediction_cutoff=max_time,
    )
    snapshot = state.feature_snapshots[-1]
    cap_status, cap_reasons = verify_capability_surface(snapshot)
    pit_status, pit_reasons = verify_pit_surface(snapshot)
    return {
        "artifact_type": "PHASE_5_FEATURE_SNAPSHOT_REPORT",
        "bar_feature_count": len(snapshot.get("bar_features", [])),
        "capability_status": cap_status,
        "capability_reason_codes": cap_reasons,
        "institutional_family_count": len(snapshot.get("institutional_evidence", [])),
        "logical_id": "phase5.feature_snapshot_report",
        "pit_status": pit_status,
        "pit_reason_codes": pit_reasons,
        "snapshot_hash": snapshot["snapshot_hash"],
    }


def _pit_adversarial_report() -> dict[str, object]:
    future_bar = _load_fixture("future-input-bar.json")
    early_cutoff = int(future_bar["available_time"]) - 1
    state = run_feature_replay(
        [future_bar],
        clocks=[int(future_bar["available_time"])],
        decision_times=[early_cutoff],
        prediction_cutoff=early_cutoff,
    )
    snapshot = state.feature_snapshots[-1]
    pit_status, pit_reasons = verify_pit_surface(snapshot)
    return {
        "artifact_type": "PHASE_5_PIT_ADVERSARIAL_REPORT",
        "future_bar_excluded": len(snapshot.get("bar_features", [])) == 0,
        "logical_id": "phase5.pit_adversarial_report",
        "rejected_future_input_count": len(state.rejected_future_inputs),
        "status": pit_status,
        "reason_codes": pit_reasons,
    }


def _whale_vocabulary_report() -> dict[str, object]:
    overclaim = _load_fixture("institutional-overclaim-request.json")
    cutoff = 2000000000000000000
    rows = [
        query_institutional_evidence(family, prediction_cutoff=cutoff) for family in WHALE_FAMILIES
    ]
    unavailable_count = sum(1 for row in rows if row["status"] == "unavailable")
    return {
        "artifact_type": "PHASE_5_WHALE_VOCABULARY_REPORT",
        "attempted_overclaim_status": overclaim.get("attempted_status"),
        "family_count": len(rows),
        "logical_id": "phase5.whale_vocabulary_report",
        "status": "PASS" if unavailable_count == len(WHALE_FAMILIES) else "FAIL",
        "unavailable_count": unavailable_count,
    }


def _feature_determinism_report(events: list[dict[str, object]]) -> dict[str, object]:
    max_time = max(int(event["available_time"]) for event in events)
    ordered = sort_events(events)
    state_a = run_feature_replay(
        ordered,
        clocks=[max_time],
        decision_times=[max_time],
        prediction_cutoff=max_time,
    )
    state_b = run_feature_replay(
        ordered,
        clocks=[max_time],
        decision_times=[max_time],
        prediction_cutoff=max_time,
    )
    root_a = run_feature_root_hash(state_a)
    root_b = run_feature_root_hash(state_b)
    return {
        "artifact_type": "PHASE_5_FEATURE_DETERMINISM_REPORT",
        "determinism_match": root_a == root_b,
        "event_count": len(events),
        "logical_id": "phase5.feature_determinism_report",
        "run_root_hash_a": root_a,
        "run_root_hash_b": root_b,
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
        "artifact_type": "PHASE_5_SAFE003_REPORT",
        "logical_id": "phase5.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _ingest_admitted_events()
    snapshot_report = _feature_snapshot_report(events)
    pit_report = _pit_adversarial_report()
    whale_report = _whale_vocabulary_report()
    determinism_report = _feature_determinism_report(events)
    safe003_report = _safe003_report()

    write_canonical_json(output_dir / "feature-snapshot-report.json", snapshot_report)
    write_canonical_json(output_dir / "pit-adversarial-report.json", pit_report)
    write_canonical_json(output_dir / "whale-vocabulary-report.json", whale_report)
    write_canonical_json(output_dir / "feature-determinism-report.json", determinism_report)
    write_canonical_json(output_dir / "safe003-report.json", safe003_report)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "CAP-001": {
            "reason_codes": snapshot_report["capability_reason_codes"],
            "status": snapshot_report["capability_status"],
        },
        "PIT-FEAT-001": {
            "future_bar_excluded": pit_report["future_bar_excluded"],
            "reason_codes": pit_report["reason_codes"],
            "status": pit_report["status"],
        },
        "WHALE-001": {
            "family_count": whale_report["family_count"],
            "reason_codes": [] if whale_report["status"] == "PASS" else ["WHALE001_NOT_ALL_UNAVAILABLE"],
            "status": whale_report["status"],
            "unavailable_count": whale_report["unavailable_count"],
        },
        "DET-001": {
            "reason_codes": [] if determinism_report["determinism_match"] else ["DET001_HASH_MISMATCH"],
            "run_root_hash": determinism_report["run_root_hash_a"],
            "status": "PASS" if determinism_report["determinism_match"] else "FAIL",
        },
        "SAFE-003": {
            "reason_codes": safe003_report["reason_codes"],
            "status": safe003_report["status"],
        },
    }

    selected_evidence = []
    for logical_id, doc in (
        ("phase5.feature_snapshot_report", snapshot_report),
        ("phase5.pit_adversarial_report", pit_report),
        ("phase5.whale_vocabulary_report", whale_report),
        ("phase5.feature_determinism_report", determinism_report),
        ("phase5.safe003_report", safe003_report),
    ):
        selected_evidence.append(
            {"logical_id": logical_id, "sha256": sha256_bytes(canonical_bytes(doc))}
        )

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "5", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase5.run_phase5_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase5_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase5.assertion_aggregate": "assertion-aggregate.json",
        "phase5.assertion_registry": "assertion_registry.json",
        "phase5.assertion_results": "assertion-results.json",
        "phase5.assertion_run_manifest": "assertion-run-manifest.json",
        "phase5.feature_determinism_report": "feature-determinism-report.json",
        "phase5.feature_snapshot_report": "feature-snapshot-report.json",
        "phase5.pit_adversarial_report": "pit-adversarial-report.json",
        "phase5.safe003_report": "safe003-report.json",
        "phase5.whale_vocabulary_report": "whale-vocabulary-report.json",
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
        "logical_id": "phase5.candidate_evidence_root",
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
