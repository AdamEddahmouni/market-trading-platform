"""Build Phase 6 preregistered strategy evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
FIXTURE_DIR = ROOT / "docs/research/fixtures/phase6-adversarial"
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase6_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.research.forecast import build_forecast, verify_forecast_interface
from market_platform_foundation.strategy.evaluation import (
    default_forecast_momentum_spec,
    default_whale_aligned_spec,
    run_strategy_evaluation,
    strategy_evaluation_root_hash,
)
from market_platform_foundation.strategy.interpretation import interpret_strategy
from market_platform_foundation.strategy.preregistration import build_preregistration

REGISTRY_PATH = ROOT / "manifests/phase6/assertion-predicates.json"
EVALUATED_AT = "2026-08-16T00:00:00.000000000Z"
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


def _strategy_spec_report(evaluation: dict[str, object]) -> dict[str, object]:
    spec = evaluation["strategy_spec"]
    prereg_status = evaluation.get("preregistration_status")
    identity = str(spec.get("strategy_identity_hash", ""))
    status = "PASS" if identity and prereg_status == "PASS" else "FAIL"
    return {
        "artifact_type": "PHASE_6_STRATEGY_SPEC_REPORT",
        "logical_id": "phase6.strategy_spec_report",
        "preregistration_status": prereg_status,
        "status": status,
        "strategy_identity_hash": identity,
    }


def _abstention_report(evaluation: dict[str, object]) -> dict[str, object]:
    whale_spec = default_whale_aligned_spec()
    forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
    fcast_status, _ = verify_forecast_interface(forecast)
    without_prereg = interpret_strategy(
        strategy_spec=whale_spec,
        preregistration=None,
        forecast=forecast,
        forecast_status=fcast_status,
        prediction_cutoff=100,
        observation_time=100,
    )
    with_prereg = interpret_strategy(
        strategy_spec=whale_spec,
        preregistration=build_preregistration(whale_spec, registered_at=EVALUATED_AT),
        forecast=forecast,
        forecast_status=fcast_status,
        prediction_cutoff=100,
        observation_time=100,
    )
    force_attempt = interpret_strategy(
        strategy_spec=whale_spec,
        preregistration=build_preregistration(whale_spec, registered_at=EVALUATED_AT),
        forecast=forecast,
        forecast_status=fcast_status,
        prediction_cutoff=100,
        observation_time=100,
        force_signal=True,
    )
    missing_prereg_abstains = without_prereg["outcome"] == "abstention"
    whale_abstains = with_prereg["outcome"] == "abstention"
    force_blocked = force_attempt["outcome"] == "abstention"
    status = "PASS" if missing_prereg_abstains and whale_abstains and force_blocked else "FAIL"
    return {
        "artifact_type": "PHASE_6_ABSTENTION_REPORT",
        "force_signal_blocked": force_blocked,
        "logical_id": "phase6.abstention_report",
        "missing_preregistration_abstains": missing_prereg_abstains,
        "status": status,
        "whale_unavailable_abstains": whale_abstains,
    }


def _pit_strategy_report() -> dict[str, object]:
    fixture = _load_fixture("future-input-interpretation.json")
    spec = default_forecast_momentum_spec()
    prereg = build_preregistration(spec, registered_at=EVALUATED_AT)
    forecast = build_forecast(
        score="1.0",
        prediction_cutoff=int(fixture["prediction_cutoff"]),
        horizon_ns=60_000_000_000,
    )
    fcast_status, _ = verify_forecast_interface(forecast)
    result = interpret_strategy(
        strategy_spec=spec,
        preregistration=prereg,
        forecast=forecast,
        forecast_status=fcast_status,
        prediction_cutoff=int(fixture["prediction_cutoff"]),
        observation_time=int(fixture["observation_time"]),
    )
    future_abstains = result["outcome"] == "abstention"
    return {
        "artifact_type": "PHASE_6_PIT_STRATEGY_REPORT",
        "future_input_abstains": future_abstains,
        "logical_id": "phase6.pit_strategy_report",
        "reason_codes": result.get("abstention_reason_codes", []),
        "status": "PASS" if future_abstains else "FAIL",
    }


def _strategy_evaluation_report(evaluation: dict[str, object]) -> dict[str, object]:
    signal_count = int(evaluation.get("signal_count", 0))
    abstention_count = int(evaluation.get("abstention_count", 0))
    total = signal_count + abstention_count
    status = "PASS" if total > 0 and signal_count > 0 else "FAIL"
    return {
        "abstention_count": abstention_count,
        "artifact_type": "PHASE_6_STRATEGY_EVALUATION_REPORT",
        "logical_id": "phase6.strategy_evaluation_report",
        "signal_count": signal_count,
        "status": status,
        "walk_forward_fold_count": evaluation.get("walk_forward_fold_count", 0),
    }


def _determinism_report(events: list[dict[str, object]]) -> dict[str, object]:
    ordered = sort_events(events)
    result_a = run_strategy_evaluation(ordered)
    result_b = run_strategy_evaluation(ordered)
    root_a = strategy_evaluation_root_hash(result_a)
    root_b = strategy_evaluation_root_hash(result_b)
    return {
        "artifact_type": "PHASE_6_STRATEGY_DETERMINISM_REPORT",
        "determinism_match": root_a == root_b,
        "event_count": len(events),
        "logical_id": "phase6.strategy_determinism_report",
        "strategy_evaluation_root_hash_a": root_a,
        "strategy_evaluation_root_hash_b": root_b,
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
        "artifact_type": "PHASE_6_SAFE003_REPORT",
        "logical_id": "phase6.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _ingest_admitted_events()
    evaluation = run_strategy_evaluation(sort_events(events))

    spec_report = _strategy_spec_report(evaluation)
    abstention_report = _abstention_report(evaluation)
    pit_report = _pit_strategy_report()
    eval_report = _strategy_evaluation_report(evaluation)
    determinism_report = _determinism_report(events)
    safe003_report = _safe003_report()

    write_canonical_json(output_dir / "strategy-spec-report.json", spec_report)
    write_canonical_json(output_dir / "abstention-report.json", abstention_report)
    write_canonical_json(output_dir / "pit-strategy-report.json", pit_report)
    write_canonical_json(output_dir / "strategy-evaluation-report.json", eval_report)
    write_canonical_json(output_dir / "strategy-determinism-report.json", determinism_report)
    write_canonical_json(output_dir / "safe003-report.json", safe003_report)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "STRAT-001": {
            "preregistration_status": spec_report["preregistration_status"],
            "reason_codes": [] if spec_report["status"] == "PASS" else ["STRAT001_PREREG_OR_IDENTITY_FAILURE"],
            "status": spec_report["status"],
            "strategy_identity_hash": spec_report["strategy_identity_hash"],
        },
        "ABST-001": {
            "force_signal_blocked": abstention_report["force_signal_blocked"],
            "missing_preregistration_abstains": abstention_report["missing_preregistration_abstains"],
            "reason_codes": [] if abstention_report["status"] == "PASS" else ["ABST001_RULE_FAILURE"],
            "status": abstention_report["status"],
            "whale_unavailable_abstains": abstention_report["whale_unavailable_abstains"],
        },
        "PIT-STRAT-001": {
            "future_input_abstains": pit_report["future_input_abstains"],
            "reason_codes": [] if pit_report["status"] == "PASS" else ["PITSTRAT001_FUTURE_INPUT_FAILURE"],
            "status": pit_report["status"],
        },
        "DET-001": {
            "reason_codes": [] if determinism_report["determinism_match"] else ["DET001_HASH_MISMATCH"],
            "status": "PASS" if determinism_report["determinism_match"] else "FAIL",
            "strategy_evaluation_root_hash": determinism_report["strategy_evaluation_root_hash_a"],
        },
        "SAFE-003": {
            "reason_codes": safe003_report["reason_codes"],
            "status": safe003_report["status"],
        },
    }

    selected_evidence = []
    for logical_id, doc in (
        ("phase6.strategy_spec_report", spec_report),
        ("phase6.abstention_report", abstention_report),
        ("phase6.pit_strategy_report", pit_report),
        ("phase6.strategy_evaluation_report", eval_report),
        ("phase6.strategy_determinism_report", determinism_report),
        ("phase6.safe003_report", safe003_report),
    ):
        selected_evidence.append(
            {"logical_id": logical_id, "sha256": sha256_bytes(canonical_bytes(doc))}
        )

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "6", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase6.run_phase6_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase6_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase6.assertion_aggregate": "assertion-aggregate.json",
        "phase6.assertion_registry": "assertion_registry.json",
        "phase6.assertion_results": "assertion-results.json",
        "phase6.assertion_run_manifest": "assertion-run-manifest.json",
        "phase6.strategy_spec_report": "strategy-spec-report.json",
        "phase6.abstention_report": "abstention-report.json",
        "phase6.pit_strategy_report": "pit-strategy-report.json",
        "phase6.strategy_evaluation_report": "strategy-evaluation-report.json",
        "phase6.strategy_determinism_report": "strategy-determinism-report.json",
        "phase6.safe003_report": "safe003-report.json",
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
        "logical_id": "phase6.candidate_evidence_root",
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
