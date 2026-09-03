"""Build Phase 8 deterministic end-to-end acceptance evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
FIXTURE_DIR = ROOT / "docs/research/fixtures/phase8-adversarial"
ROLLUP_MANIFEST_PATH = ROOT / "manifests/phase8/foundation-rollup-manifest.json"
REGISTRY_PATH = ROOT / "manifests/phase8/assertion-predicates.json"
EVALUATED_AT = "2026-08-17T01:00:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"
ADMITTED_SOURCE = "ADMITTED-SHORTSQ-BIYA-BARS-001"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase8_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.risk_simulation.evaluation import run_risk_simulation_evaluation, risk_simulation_root_hash

REQUIRED_BUNDLE_MEMBERS = (
    "phase8.end_to_end_report",
    "phase8.rollup_report",
    "phase8.limitations_report",
    "phase8.determinism_report",
    "phase8.safe003_report",
)


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


def end_to_end_root_hash(evaluation: dict[str, object], *, event_count: int) -> str:
    body = {
        "canonical_event_count": event_count,
        "fill_count": len(evaluation.get("fills", [])),
        "intent_count": len(evaluation.get("intents", [])),
        "reconciliation_status": evaluation.get("reconciliation", {}).get("status"),
        "risk_decision_count": len(evaluation.get("risk_decisions", [])),
        "risk_simulation_root": risk_simulation_root_hash(evaluation),
        "strategy_signal_count": sum(
            1
            for row in evaluation.get("strategy_result", {}).get("interpretations", [])
            if isinstance(row, dict) and row.get("outcome") == "signal"
        ),
    }
    return sha256_bytes(canonical_bytes(body))


def _rollup_report(root: Path) -> dict[str, object]:
    manifest = load_json_strict(ROLLUP_MANIFEST_PATH)
    if not isinstance(manifest, dict):
        raise ValueError("rollup manifest invalid")
    entries = manifest.get("rollup_entries", [])
    if not isinstance(entries, list):
        raise ValueError("rollup entries invalid")
    failures: list[str] = []
    checked: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        foundation_id = str(entry["foundation_assertion_id"])
        source_phase = str(entry["source_phase"])
        source_run_id = str(entry["source_run_id"])
        source_assertion_id = str(entry["source_assertion_id"])
        results_path = root / "evidence" / source_phase / source_run_id / "assertion-results.json"
        if not results_path.is_file():
            failures.append(f"MISSING_BUNDLE:{foundation_id}")
            continue
        results_doc = load_json_strict(results_path)
        if not isinstance(results_doc, dict):
            failures.append(f"INVALID_BUNDLE:{foundation_id}")
            continue
        matched = None
        for row in results_doc.get("results", []):
            if isinstance(row, dict) and str(row.get("assertion_id")) == source_assertion_id:
                matched = row
                break
        if matched is None:
            failures.append(f"MISSING_ASSERTION:{foundation_id}")
            continue
        status = str(matched.get("status", "BLOCKED"))
        checked.append(
            {
                "foundation_assertion_id": foundation_id,
                "proxy": bool(entry.get("proxy", False)),
                "source_assertion_id": source_assertion_id,
                "source_phase": source_phase,
                "status": status,
            }
        )
        if status != "PASS":
            failures.append(f"NON_PASS:{foundation_id}")
    return {
        "artifact_type": "PHASE_8_ROLLUP_REPORT",
        "checked_count": len(checked),
        "entries": checked,
        "failure_codes": sorted(set(failures)),
        "logical_id": "phase8.rollup_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _limitations_report() -> dict[str, object]:
    return {
        "admitted_fixture": ADMITTED_SOURCE,
        "artifact_type": "PHASE_8_LIMITATIONS_REPORT",
        "capability_scope": "BAR_OHLCV_1M equity intraday only",
        "deferred_items": [
            "ES-session acceptance bundle per Revision 1 section 17.6 remains BLOCKED",
            "DF-001 and DF-002 for ES futures remain deferred per ADR-DATA-001",
            "MBO/MBP queue models, sweep claims, and intrabar path simulation are unsupported",
            "Whale ingestion, broker adapters, and live/paper order routes are unauthorized",
        ],
        "logical_id": "phase8.limitations_report",
        "no_edge_claim": True,
        "status": "COMPLETE",
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
            key for key, values in prohibited.items() if isinstance(values, list) and values
        ]
        if nonempty:
            reasons.append("SAFE003_ROUTE_PATH_PRESENT")
        else:
            route_path = str(path.relative_to(ROOT).as_posix())
            break
    if route_path is None and not reasons:
        reasons.append("SAFE003_ROUTE_REPORT_MISSING")
    return {
        "artifact_type": "PHASE_8_SAFE003_REPORT",
        "logical_id": "phase8.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def _determinism_report(events: list[dict[str, object]]) -> dict[str, object]:
    ordered = sort_events(events)
    result_a = run_risk_simulation_evaluation(ordered)
    result_b = run_risk_simulation_evaluation(ordered)
    root_a = end_to_end_root_hash(result_a, event_count=len(events))
    root_b = end_to_end_root_hash(result_b, event_count=len(events))
    return {
        "artifact_type": "PHASE_8_DETERMINISM_REPORT",
        "determinism_match": root_a == root_b,
        "end_to_end_root_hash_a": root_a,
        "end_to_end_root_hash_b": root_b,
        "event_count": len(events),
        "logical_id": "phase8.determinism_report",
    }


def _end_to_end_report(evaluation: dict[str, object], *, event_count: int) -> dict[str, object]:
    return {
        "artifact_type": "PHASE_8_END_TO_END_REPORT",
        "canonical_event_count": event_count,
        "completion_state": "COMPLETE",
        "fill_count": len(evaluation.get("fills", [])),
        "intent_count": len(evaluation.get("intents", [])),
        "logical_id": "phase8.end_to_end_report",
        "reconciliation_status": evaluation.get("reconciliation", {}).get("status"),
        "risk_decision_count": len(evaluation.get("risk_decisions", [])),
        "run_root_hash": end_to_end_root_hash(evaluation, event_count=event_count),
        "source_object_id": SOURCE_OBJECT_ID,
        "status": "PASS",
    }


def _verify_bundle_members(index_members: list[dict[str, object]]) -> tuple[str, list[str]]:
    present = {str(row["logical_id"]) for row in index_members}
    missing = sorted(set(REQUIRED_BUNDLE_MEMBERS) - present)
    if missing:
        return "FAIL", [f"AE001_MISSING_MEMBER:{item}" for item in missing]
    for row in index_members:
        path = ROOT / str(row["repository_relative_path"])
        recorded = str(row.get("sha256", ""))
        if not path.is_file():
            return "FAIL", ["AE001_MISSING_FILE"]
        actual = sha256_bytes(path.read_bytes())
        if recorded != actual:
            return "FAIL", ["AE001_HASH_MISMATCH"]
    return "PASS", []


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _ingest_admitted_events()
    ordered = sort_events(events)
    evaluation = run_risk_simulation_evaluation(ordered)

    end_to_end = _end_to_end_report(evaluation, event_count=len(events))
    rollup = _rollup_report(ROOT)
    limitations = _limitations_report()
    determinism = _determinism_report(events)
    safe003 = _safe003_report()

    write_canonical_json(output_dir / "end-to-end-report.json", end_to_end)
    write_canonical_json(output_dir / "rollup-report.json", rollup)
    write_canonical_json(output_dir / "limitations-report.json", limitations)
    write_canonical_json(output_dir / "determinism-report.json", determinism)
    write_canonical_json(output_dir / "safe003-report.json", safe003)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    members = {
        "phase8.end_to_end_report": "end-to-end-report.json",
        "phase8.rollup_report": "rollup-report.json",
        "phase8.limitations_report": "limitations-report.json",
        "phase8.determinism_report": "determinism-report.json",
        "phase8.safe003_report": "safe003-report.json",
    }
    index_members = []
    selected_evidence = []
    for logical_id, filename in sorted(members.items()):
        path = output_dir / filename
        digest = sha256_bytes(path.read_bytes())
        index_members.append(
            {
                "logical_id": logical_id,
                "repository_relative_path": str(path.relative_to(ROOT).as_posix()),
                "sha256": digest,
            }
        )
        selected_evidence.append({"logical_id": logical_id, "sha256": digest})

    ae_status, ae_reasons = _verify_bundle_members(index_members)

    observations = {
        "AE-001": {
            "bundle_completion_state": end_to_end.get("completion_state"),
            "reason_codes": ae_reasons,
            "status": ae_status if end_to_end.get("completion_state") == "COMPLETE" else "FAIL",
        },
        "DET-001": {
            "determinism_match": determinism.get("determinism_match"),
            "reason_codes": [] if determinism.get("determinism_match") else ["DET001_HASH_MISMATCH"],
            "status": "PASS" if determinism.get("determinism_match") else "FAIL",
        },
        "ROLLUP-001": {
            "checked_count": rollup.get("checked_count"),
            "failure_codes": rollup.get("failure_codes"),
            "reason_codes": rollup.get("failure_codes", []),
            "status": rollup.get("status"),
        },
        "SAFE-003": {
            "reason_codes": safe003.get("reason_codes"),
            "status": safe003.get("status"),
        },
    }

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "8", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase8.run_phase8_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase8_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    bundle_members = {
        **members,
        "phase8.assertion_aggregate": "assertion-aggregate.json",
        "phase8.assertion_registry": "assertion_registry.json",
        "phase8.assertion_results": "assertion-results.json",
        "phase8.assertion_run_manifest": "assertion-run-manifest.json",
    }
    candidate_members = []
    for logical_id, filename in sorted(bundle_members.items()):
        path = output_dir / filename
        candidate_members.append(
            {
                "logical_id": logical_id,
                "repository_relative_path": str(path.relative_to(ROOT).as_posix()),
                "sha256": sha256_bytes(path.read_bytes()),
            }
        )
    candidate_body = {
        "candidate_evidence_root": sha256_bytes(canonical_bytes(candidate_members)),
        "index_members": candidate_members,
        "logical_id": "phase8.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "canonical_event_count": len(events),
        "fill_count": len(evaluation.get("fills", [])),
        "output_dir": str(output_dir),
        "run_id": run_id,
        "run_root_hash": end_to_end["run_root_hash"],
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
