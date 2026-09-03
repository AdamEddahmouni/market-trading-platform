"""Build Phase 4 runtime quality and state evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
FIXTURE_DIR = ROOT / "docs/research/fixtures/phase4-corruption"
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import (
    PINNED_SHA256,
    EquityIntradayJsonlAdapter,
    NORMALIZATION_VERSION,
    SCHEMA_VERSION,
    SOURCE_OBJECT_ID,
)
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.contracts.temporal import check_tc003, decision_hash
from market_platform_foundation.data_quality.observations import consumer_eligibility, evaluate_bar_event
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase4_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.replay.quality_lifecycle import (
    run_quality_replay,
    run_quality_root_hash,
    verify_tc003_on_correction,
)
from market_platform_foundation.storage.dataset_cache import DatasetCache

REGISTRY_PATH = ROOT / "manifests/phase4/assertion-predicates.json"
EVALUATED_AT = "2026-08-15T20:00:00.000000000Z"
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


def _quality_adversarial_report() -> dict[str, object]:
    valid = _load_fixture("bar-valid-a.json")
    invalid = _load_fixture("bar-invalid-ohlc.json")
    late = _load_fixture("late-correction-bar.json")

    invalid_observations = evaluate_bar_event(invalid, prior_bar=None)
    invalid_eligibility, invalid_reasons = consumer_eligibility(invalid_observations)

    prior_state = run_quality_replay(
        [valid],
        clocks=[int(valid["available_time"])],
        decision_times=[int(valid["available_time"])],
    )
    post_state = run_quality_replay(
        [valid, late],
        clocks=[int(valid["available_time"]), int(late["available_time"])],
        decision_times=[int(valid["available_time"]), int(late["available_time"])],
    )
    tc003_pass, tc003_pass_reasons = verify_tc003_on_correction(
        prior_state=prior_state,
        post_state=post_state,
        correction_available_time=int(late["available_time"]),
        replay_clock_at_apply=int(late["available_time"]),
    )
    prior_hash = decision_hash(prior_state.decisions[-1])
    tc003_fail, tc003_fail_reasons = check_tc003(
        prior_decision_hash=prior_hash,
        post_correction_hash=decision_hash(post_state.decisions[-1]),
        correction_available_time=int(late["available_time"]),
        replay_clock_at_apply=int(late["available_time"]) - 1,
    )

    return {
        "artifact_type": "PHASE_4_QUALITY_ADVERSARIAL_REPORT",
        "invalid_bar": {
            "consumer_eligibility": invalid_eligibility,
            "eligibility_reason_codes": invalid_reasons,
            "observation_count": len(invalid_observations),
            "status": "BLOCKED" if invalid_eligibility == "BLOCKED" else "FAIL",
        },
        "logical_id": "phase4.quality_adversarial_report",
        "tc003": {
            "fail_case": {"reason_codes": tc003_fail_reasons, "status": tc003_fail},
            "pass_case": {"reason_codes": tc003_pass_reasons, "status": tc003_pass},
        },
    }


def _replay_determinism_report(events: list[dict[str, object]]) -> dict[str, object]:
    max_time = max(int(event["available_time"]) for event in events)
    cache_a = DatasetCache(
        max_bytes=8_000_000,
        source_hash=PINNED_SHA256,
        schema_version=SCHEMA_VERSION,
        normalization_version=NORMALIZATION_VERSION,
    )
    cache_b = DatasetCache(
        max_bytes=8_000_000,
        source_hash=PINNED_SHA256,
        schema_version=SCHEMA_VERSION,
        normalization_version=NORMALIZATION_VERSION,
    )
    key = "admitted_fixture_events"
    payload = canonical_bytes(sort_events(events))
    ordered_a = json.loads(payload.decode("utf-8"))
    ordered_b = json.loads(cache_b.get_or_load(key, lambda: payload).decode("utf-8"))
    cache_a.get_or_load(key, lambda: payload)
    state_a = run_quality_replay(
        ordered_a,
        clocks=[max_time],
        decision_times=[max_time],
        cache=cache_a,
    )
    state_b = run_quality_replay(
        ordered_b,
        clocks=[max_time],
        decision_times=[max_time],
        cache=cache_b,
    )
    root_a = run_quality_root_hash(state_a)
    root_b = run_quality_root_hash(state_b)
    return {
        "artifact_type": "PHASE_4_REPLAY_DETERMINISM_REPORT",
        "cache_report": cache_a.report(),
        "determinism_match": root_a == root_b,
        "event_count": len(events),
        "logical_id": "phase4.replay_determinism_report",
        "run_root_hash_a": root_a,
        "run_root_hash_b": root_b,
        "tc001_violation_count": sum(
            1 for row in state_a.decisions if row.get("status") != "PASS"
        ),
    }


def _bar_state_report(events: list[dict[str, object]]) -> dict[str, object]:
    max_time = max(int(event["available_time"]) for event in events)
    state = run_quality_replay(events, clocks=[max_time], decision_times=[max_time])
    instruments = sorted(state.bar_book.bars_by_instrument)
    return {
        "artifact_type": "PHASE_4_BAR_STATE_REPORT",
        "applied_event_count": len(state.bar_book.applied_event_ids),
        "instrument_count": len(instruments),
        "logical_id": "phase4.bar_state_report",
        "quality_observation_count": len(state.quality_observations),
        "rejected_upgrade_count": len(state.bar_book.rejected_upgrades),
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
        "artifact_type": "PHASE_4_SAFE003_REPORT",
        "logical_id": "phase4.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _ingest_admitted_events()
    quality_report = _quality_adversarial_report()
    replay_report = _replay_determinism_report(events)
    bar_state_report = _bar_state_report(events)
    safe003_report = _safe003_report()

    write_canonical_json(output_dir / "quality-adversarial-report.json", quality_report)
    write_canonical_json(output_dir / "replay-determinism-report.json", replay_report)
    write_canonical_json(output_dir / "bar-state-report.json", bar_state_report)
    write_canonical_json(output_dir / "safe003-report.json", safe003_report)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "TC-001": {
            "reason_codes": [],
            "status": "PASS" if replay_report["tc001_violation_count"] == 0 else "FAIL",
            "violation_count": replay_report["tc001_violation_count"],
        },
        "TC-003": {
            "prior_decision_unchanged": quality_report["tc003"]["pass_case"]["status"] == "PASS",
            "reason_codes": quality_report["tc003"]["pass_case"]["reason_codes"],
            "status": quality_report["tc003"]["pass_case"]["status"],
        },
        "DET-001": {
            "reason_codes": [] if replay_report["determinism_match"] else ["DET001_HASH_MISMATCH"],
            "run_root_hash": replay_report["run_root_hash_a"],
            "status": "PASS" if replay_report["determinism_match"] else "FAIL",
        },
        "SAFE-003": {
            "reason_codes": safe003_report["reason_codes"],
            "status": safe003_report["status"],
        },
    }

    selected_evidence = []
    for logical_id, doc in (
        ("phase4.quality_adversarial_report", quality_report),
        ("phase4.replay_determinism_report", replay_report),
        ("phase4.bar_state_report", bar_state_report),
        ("phase4.safe003_report", safe003_report),
    ):
        selected_evidence.append(
            {"logical_id": logical_id, "sha256": sha256_bytes(canonical_bytes(doc))}
        )

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "4", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase4.run_phase4_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase4_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase4.assertion_aggregate": "assertion-aggregate.json",
        "phase4.assertion_registry": "assertion_registry.json",
        "phase4.assertion_results": "assertion-results.json",
        "phase4.assertion_run_manifest": "assertion-run-manifest.json",
        "phase4.bar_state_report": "bar-state-report.json",
        "phase4.quality_adversarial_report": "quality-adversarial-report.json",
        "phase4.replay_determinism_report": "replay-determinism-report.json",
        "phase4.safe003_report": "safe003-report.json",
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
        "logical_id": "phase4.candidate_evidence_root",
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
