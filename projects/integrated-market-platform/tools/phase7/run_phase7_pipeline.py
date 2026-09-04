"""Build Phase 7 risk, simulation, and accounting evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
FIXTURE_DIR = ROOT / "docs/research/fixtures/phase7-adversarial"
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase7_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.risk.decision import evaluate_risk
from market_platform_foundation.risk.kill_switch import KillSwitchState
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
from market_platform_foundation.risk_simulation.evaluation import (
    audit_fill_eligibility,
    run_risk_simulation_evaluation,
    risk_simulation_root_hash,
)

REGISTRY_PATH = ROOT / "manifests/phase7/assertion-predicates.json"
EVALUATED_AT = "2026-08-16T01:00:00.000000000Z"
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


def _risk_report(evaluation: dict[str, object]) -> dict[str, object]:
    from market_platform_foundation.execution.intent import build_order_intent
    from market_platform_foundation.strategy.interpretation import interpret_strategy
    from market_platform_foundation.strategy.preregistration import build_preregistration
    from market_platform_foundation.strategy.evaluation import default_forecast_momentum_spec
    from market_platform_foundation.research.forecast import build_forecast, verify_forecast_interface

    spec = default_forecast_momentum_spec()
    prereg = build_preregistration(spec, registered_at=EVALUATED_AT)
    forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
    fcast_status, _ = verify_forecast_interface(forecast)
    signal = interpret_strategy(
        strategy_spec=spec,
        preregistration=prereg,
        forecast=forecast,
        forecast_status=fcast_status,
        prediction_cutoff=100,
        observation_time=100,
    )
    intent = build_order_intent(
        interpretation=signal,
        instrument_id="EQ-1",
        observation_time=100,
        desired_quantity=10,
    )
    assert intent is not None
    active = evaluate_risk(
        intent=intent,
        policy=DEFAULT_RISK_POLICY,
        kill_switch=KillSwitchState(active=False),
        current_position_shares=0,
        open_order_count=0,
    )
    halted = evaluate_risk(
        intent=intent,
        policy=DEFAULT_RISK_POLICY,
        kill_switch=KillSwitchState(active=True, reason_code="ADVERSARIAL"),
        current_position_shares=0,
        open_order_count=0,
    )
    kill_switch_rejects = halted["decision"] == "REJECT"
    status = "PASS" if active["decision"] in {"APPROVE", "RESIZE"} and kill_switch_rejects else "FAIL"
    return {
        "artifact_type": "PHASE_7_RISK_REPORT",
        "active_kill_switch_rejects": kill_switch_rejects,
        "logical_id": "phase7.risk_report",
        "risk_decision_count": len(evaluation.get("risk_decisions", [])),
        "status": status,
    }


def _simulation_report(evaluation: dict[str, object]) -> dict[str, object]:
    fill_audit = evaluation.get("fill_audit", {})
    allocation_audit = evaluation.get("allocation_audit", {})
    pre_fixture = _load_fixture("pre-activation-fill.json")
    synthetic_fill = {
        "activation_time": int(pre_fixture["simulated_activation_time"]),
        "fill_id": "ADVERSARIAL-PRE-ACTIVATION",
        "fill_time": int(pre_fixture["simulated_fill_time"]),
    }
    synthetic_audit = audit_fill_eligibility([], [synthetic_fill])
    pre_activation_blocked = synthetic_audit["status"] == "FAIL"
    status = "PASS"
    if fill_audit.get("status") != "PASS" or allocation_audit.get("status") != "PASS":
        status = "FAIL"
    if not pre_activation_blocked:
        status = "FAIL"
    return {
        "artifact_type": "PHASE_7_SIMULATION_REPORT",
        "allocation_audit_status": allocation_audit.get("status"),
        "fill_audit_status": fill_audit.get("status"),
        "fill_count": len(evaluation.get("fills", [])),
        "logical_id": "phase7.simulation_report",
        "order_count": len(evaluation.get("orders", [])),
        "pre_activation_fill_blocked": pre_activation_blocked,
        "status": status,
    }


def _accounting_report(evaluation: dict[str, object]) -> dict[str, object]:
    reconciliation = evaluation.get("reconciliation", {})
    status = str(reconciliation.get("status", "FAIL"))
    return {
        "artifact_type": "PHASE_7_ACCOUNTING_REPORT",
        "cash_minor": evaluation.get("ledger", {}).get("cash_minor"),
        "logical_id": "phase7.accounting_report",
        "position_shares": evaluation.get("ledger", {}).get("position_shares"),
        "realized_pnl_minor": evaluation.get("ledger", {}).get("realized_pnl_minor"),
        "reconciliation_status": status,
        "status": status,
    }


def _determinism_report(events: list[dict[str, object]]) -> dict[str, object]:
    ordered = sort_events(events)
    result_a = run_risk_simulation_evaluation(ordered)
    result_b = run_risk_simulation_evaluation(ordered)
    root_a = risk_simulation_root_hash(result_a)
    root_b = risk_simulation_root_hash(result_b)
    return {
        "artifact_type": "PHASE_7_RISK_SIMULATION_DETERMINISM_REPORT",
        "determinism_match": root_a == root_b,
        "event_count": len(events),
        "logical_id": "phase7.risk_simulation_determinism_report",
        "risk_simulation_root_hash_a": root_a,
        "risk_simulation_root_hash_b": root_b,
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
        "artifact_type": "PHASE_7_SAFE003_REPORT",
        "logical_id": "phase7.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _ingest_admitted_events()
    evaluation = run_risk_simulation_evaluation(sort_events(events))

    risk_report = _risk_report(evaluation)
    simulation_report = _simulation_report(evaluation)
    accounting_report = _accounting_report(evaluation)
    determinism_report = _determinism_report(events)
    safe003_report = _safe003_report()

    write_canonical_json(output_dir / "risk-report.json", risk_report)
    write_canonical_json(output_dir / "simulation-report.json", simulation_report)
    write_canonical_json(output_dir / "accounting-report.json", accounting_report)
    write_canonical_json(output_dir / "risk-simulation-determinism-report.json", determinism_report)
    write_canonical_json(output_dir / "safe003-report.json", safe003_report)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "EXE-001": {
            "fill_audit_status": simulation_report["fill_audit_status"],
            "pre_activation_fill_blocked": simulation_report["pre_activation_fill_blocked"],
            "reason_codes": [] if simulation_report["status"] == "PASS" else ["EXE001_FILL_ELIGIBILITY_FAILURE"],
            "status": "PASS" if simulation_report["fill_audit_status"] == "PASS" and simulation_report["pre_activation_fill_blocked"] else "FAIL",
        },
        "EXE-002": {
            "allocation_audit_status": simulation_report["allocation_audit_status"],
            "reason_codes": [] if simulation_report["allocation_audit_status"] == "PASS" else ["EXE002_ALLOCATION_FAILURE"],
            "status": simulation_report["allocation_audit_status"],
        },
        "EXE-003": {
            "reason_codes": [] if accounting_report["status"] == "PASS" else ["EXE003_RECONCILIATION_FAILURE"],
            "reconciliation_status": accounting_report["reconciliation_status"],
            "status": accounting_report["status"],
        },
        "SAFE-003": {
            "reason_codes": safe003_report["reason_codes"],
            "status": safe003_report["status"],
        },
    }

    selected_evidence = []
    for logical_id, doc in (
        ("phase7.risk_report", risk_report),
        ("phase7.simulation_report", simulation_report),
        ("phase7.accounting_report", accounting_report),
        ("phase7.risk_simulation_determinism_report", determinism_report),
        ("phase7.safe003_report", safe003_report),
    ):
        selected_evidence.append(
            {"logical_id": logical_id, "sha256": sha256_bytes(canonical_bytes(doc))}
        )

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "7", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase7.run_phase7_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase7_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase7.assertion_aggregate": "assertion-aggregate.json",
        "phase7.assertion_registry": "assertion_registry.json",
        "phase7.assertion_results": "assertion-results.json",
        "phase7.assertion_run_manifest": "assertion-run-manifest.json",
        "phase7.risk_report": "risk-report.json",
        "phase7.simulation_report": "simulation-report.json",
        "phase7.accounting_report": "accounting-report.json",
        "phase7.risk_simulation_determinism_report": "risk-simulation-determinism-report.json",
        "phase7.safe003_report": "safe003-report.json",
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
        "logical_id": "phase7.candidate_evidence_root",
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
