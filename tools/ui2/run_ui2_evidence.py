"""Build UI-002 expanded research UI acceptance evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/ui2/assertion-predicates.json"
EVALUATED_AT = "2026-08-18T12:00:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.ui2_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.ui_api.projections import (
    build_research_models_payload,
    build_research_simulation_payload,
    build_workspace_institutional_flow_payload,
)
from market_platform_foundation.ui_api.server import canonical_response_bytes
from market_platform_foundation.ui_api.store import ReplayStore


def _load_store() -> ReplayStore:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    return store


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
        nonempty = [key for key, values in prohibited.items() if isinstance(values, list) and values]
        if nonempty:
            reasons.append("SAFE003_ROUTE_PATH_PRESENT")
        else:
            route_path = str(path.relative_to(ROOT).as_posix())
            break
    if route_path is None and not reasons:
        reasons.append("SAFE003_ROUTE_REPORT_MISSING")
    return {
        "artifact_type": "UI2_SAFE003_REPORT",
        "logical_id": "ui2.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def _determinism_report(store: ReplayStore) -> dict[str, object]:
    index_a = store.cursor_index
    models_a = canonical_response_bytes(build_research_models_payload(store))
    sim_a = canonical_response_bytes(build_research_simulation_payload(store))
    store.set_cursor_index(max(0, index_a - 1))
    store.set_cursor_index(index_a)
    models_b = canonical_response_bytes(build_research_models_payload(store))
    sim_b = canonical_response_bytes(build_research_simulation_payload(store))
    match = models_a == models_b and sim_a == sim_b
    return {
        "artifact_type": "UI2_DETERMINISM_REPORT",
        "determinism_match": match,
        "logical_id": "ui2.determinism_report",
        "models_hash_a": sha256_bytes(models_a),
        "models_hash_b": sha256_bytes(models_b),
        "simulation_hash_a": sha256_bytes(sim_a),
        "simulation_hash_b": sha256_bytes(sim_b),
        "status": "PASS" if match else "FAIL",
    }


def _institutional_flow_report(store: ReplayStore) -> dict[str, object]:
    payload = build_workspace_institutional_flow_payload(store, store.instrument_id)
    families = payload.get("families", [])
    failures: list[str] = []
    if not isinstance(families, list) or len(families) != 8:
        failures.append("IF_FAMILY_COUNT_NOT_EIGHT")
    for row in families if isinstance(families, list) else []:
        if not isinstance(row, dict):
            failures.append("IF_FAMILY_ROW_INVALID")
            continue
        if not row.get("family_id") or not row.get("route_path"):
            failures.append(f"IF_MISSING_FIELDS:{row.get('family_id', 'unknown')}")
        if row.get("available") and row.get("reason"):
            failures.append(f"IF_AVAILABLE_WITH_REASON:{row.get('family_id')}")
    return {
        "artifact_type": "UI2_INSTITUTIONAL_FLOW_REPORT",
        "failures": sorted(set(failures)),
        "family_count": len(families) if isinstance(families, list) else 0,
        "logical_id": "ui2.institutional_flow_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _simulation_boundary_report(store: ReplayStore) -> dict[str, object]:
    payload = build_research_simulation_payload(store)
    failures: list[str] = []
    if payload.get("authority_boundary") != "READ_ONLY_SIMULATION":
        failures.append("SIM_BOUNDARY_MISMATCH")
    if payload.get("mode_label") != "SIMULATION":
        failures.append("SIM_MODE_LABEL_MISSING")
    safe = _safe003_report()
    if safe.get("status") != "PASS":
        failures.append("SAFE003_FAILED")
    return {
        "artifact_type": "UI2_SIMULATION_BOUNDARY_REPORT",
        "authority_boundary": payload.get("authority_boundary"),
        "failures": sorted(set(failures)),
        "logical_id": "ui2.simulation_boundary_report",
        "status": "PASS" if not failures else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    store = _load_store()

    determinism = _determinism_report(store)
    institutional = _institutional_flow_report(store)
    simulation = _simulation_boundary_report(store)
    safe003 = _safe003_report()

    write_canonical_json(output_dir / "determinism-report.json", determinism)
    write_canonical_json(output_dir / "institutional-flow-report.json", institutional)
    write_canonical_json(output_dir / "simulation-boundary-report.json", simulation)
    write_canonical_json(output_dir / "safe003-report.json", safe003)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "UI-RES-001": {
            "determinism_match": determinism.get("determinism_match"),
            "reason_codes": [] if determinism.get("determinism_match") else ["UI-RES-001-MISMATCH"],
            "status": determinism.get("status"),
        },
        "UI-RES-002": {
            "failures": institutional.get("failures"),
            "reason_codes": institutional.get("failures", []),
            "status": institutional.get("status"),
        },
        "UI-RES-003": {
            "failures": simulation.get("failures"),
            "reason_codes": simulation.get("failures", []),
            "status": simulation.get("status"),
        },
        "SAFE-003": {
            "reason_codes": safe003.get("reason_codes"),
            "status": safe003.get("status"),
        },
    }

    members = {
        "ui2.determinism_report": "determinism-report.json",
        "ui2.institutional_flow_report": "institutional-flow-report.json",
        "ui2.simulation_boundary_report": "simulation-boundary-report.json",
        "ui2.safe003_report": "safe003-report.json",
    }
    selected_evidence = []
    for logical_id, filename in sorted(members.items()):
        path = output_dir / filename
        digest = sha256_bytes(path.read_bytes())
        selected_evidence.append({"logical_id": logical_id, "sha256": digest})

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "ui2", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["ui2.run_ui2_evidence/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)
    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    bundle_members = {
        **members,
        "ui2.assertion_aggregate": "assertion-aggregate.json",
        "ui2.assertion_registry": "assertion_registry.json",
        "ui2.assertion_results": "assertion-results.json",
        "ui2.assertion_run_manifest": "assertion-run-manifest.json",
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
        "logical_id": "ui2.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "instrument_id": store.instrument_id,
        "output_dir": str(output_dir),
        "run_id": run_id,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="Build acceptance evidence to directory")
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    report = build_evidence(Path(args.output_dir).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["aggregate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
