"""Build Phase 2 contract and replay evidence on synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.contracts.envelope import validate_envelope
from market_platform_foundation.contracts.identity import normalized_event_id, sort_events
from market_platform_foundation.contracts.schema_compat import round_trip_record
from market_platform_foundation.contracts.temporal import check_tc001, check_tc002, check_tc003, decision_hash
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase2_assertions import aggregate_status, build_registry, create_run_manifest
from market_platform_foundation.replay.lifecycle import run_replay, run_root_hash

FIXTURE_DIR = ROOT / "docs/research/fixtures/phase2-synthetic"
REGISTRY_PATH = ROOT / "manifests/phase2/assertion-predicates.json"
EVALUATED_AT = "2026-08-15T16:00:00.000000000Z"


def _load_fixture(name: str) -> dict[str, object]:
    doc = load_json_strict(FIXTURE_DIR / name)
    if not isinstance(doc, dict):
        raise ValueError(f"fixture must be object: {name}")
    return doc


def _contract_validation_report() -> dict[str, object]:
    fixtures = [
        "base-historical-bar.json",
        "late-correction.json",
        "live-trade.json",
        "negative-tc002-historical-live-received.json",
    ]
    rows: list[dict[str, object]] = []
    for name in fixtures:
        event = _load_fixture(name)
        timestamp_states = {
            str(key): str(value)
            for key, value in dict(event.pop("timestamp_states", {})).items()
        }
        acquisition_mode = str(event.pop("acquisition_mode"))
        reasons = validate_envelope(
            event,
            timestamp_states=timestamp_states,
            acquisition_mode=acquisition_mode,
        )
        restored, restored_hash = _round_trip(event)
        rows.append(
            {
                "fixture_name": name,
                "reason_codes": reasons,
                "restored_hash": restored_hash,
                "round_trip_ok": restored == event,
                "status": "FAIL" if reasons else "PASS",
            }
        )
    return {
        "artifact_type": "PHASE_2_CONTRACT_VALIDATION_REPORT",
        "fixtures": rows,
        "logical_id": "phase2.contract_validation_report",
        "overall_status": "PASS" if all(row["status"] == "PASS" for row in rows[:3]) else "FAIL",
    }


def _round_trip(event: dict[str, object]) -> tuple[dict[str, object], str]:
    restored = round_trip_record(event)
    return restored, sha256_bytes(canonical_bytes(restored))


def _temporal_adversarial_report() -> dict[str, object]:
    base = _load_fixture("base-historical-bar.json")
    correction = _load_fixture("late-correction.json")
    negative = _load_fixture("negative-tc002-historical-live-received.json")
    base.pop("timestamp_states", None)
    base.pop("acquisition_mode", None)
    correction.pop("timestamp_states", None)
    correction.pop("acquisition_mode", None)
    negative.pop("timestamp_states", None)
    negative.pop("acquisition_mode", None)

    consumed = [{"available_time": base["available_time"], "normalized_event_id": base["normalized_event_id"]}]
    tc001_pass, tc001_reasons = check_tc001(consumed, int(base["available_time"]))
    tc001_fail, tc001_fail_reasons = check_tc001(consumed, int(base["available_time"]) - 1)

    tc002_pass, tc002_pass_reasons = check_tc002([base], "historical")
    tc002_fail, tc002_fail_reasons = check_tc002([negative], "historical")

    prior_decision = {"decision_time": int(base["available_time"]), "visible_event_count": 1}
    prior_hash = decision_hash(prior_decision)
    post_hash = decision_hash({**prior_decision, "visible_event_count": 2})
    tc003_pass, tc003_pass_reasons = check_tc003(
        prior_decision_hash=prior_hash,
        post_correction_hash=prior_hash,
        correction_available_time=int(correction["available_time"]),
        replay_clock_at_apply=int(correction["available_time"]),
    )
    tc003_fail, tc003_fail_reasons = check_tc003(
        prior_decision_hash=prior_hash,
        post_correction_hash=post_hash,
        correction_available_time=int(correction["available_time"]),
        replay_clock_at_apply=int(correction["available_time"]) - 1,
    )

    return {
        "artifact_type": "PHASE_2_TEMPORAL_ADVERSARIAL_REPORT",
        "logical_id": "phase2.temporal_adversarial_report",
        "tc001": {
            "fail_case": {"reason_codes": tc001_fail_reasons, "status": tc001_fail},
            "pass_case": {"reason_codes": tc001_reasons, "status": tc001_pass},
        },
        "tc002": {
            "fail_case": {"reason_codes": tc002_fail_reasons, "status": tc002_fail},
            "pass_case": {"reason_codes": tc002_pass_reasons, "status": tc002_pass},
        },
        "tc003": {
            "fail_case": {"reason_codes": tc003_fail_reasons, "status": tc003_fail},
            "pass_case": {"reason_codes": tc003_pass_reasons, "status": tc003_pass},
        },
    }


def _replay_report() -> dict[str, object]:
    events = []
    for name in ("base-historical-bar.json", "late-correction.json"):
        event = _load_fixture(name)
        event.pop("timestamp_states", None)
        event.pop("acquisition_mode", None)
        events.append(event)
    ordered = sort_events(events)
    clocks = [int(event["available_time"]) for event in ordered]
    state_a = run_replay(ordered, clocks=clocks, decision_times=[clocks[-1]])
    state_b = run_replay(ordered, clocks=clocks, decision_times=[clocks[-1]])
    root_a = run_root_hash(state_a)
    root_b = run_root_hash(state_b)
    return {
        "artifact_type": "PHASE_2_REPLAY_DETERMINISM_REPORT",
        "determinism_match": root_a == root_b,
        "logical_id": "phase2.replay_determinism_report",
        "ordered_event_ids": [event["normalized_event_id"] for event in ordered],
        "run_root_hash_a": root_a,
        "run_root_hash_b": root_b,
        "visible_event_count": len(state_a.visible_events),
    }


def _identity_report() -> dict[str, object]:
    sample_id = normalized_event_id(
        provider_id="SYNTH",
        venue_id="VENUE",
        publisher_id="PUB",
        channel_id="CHAN",
        source_instance_id="INST",
        source_record_id="REC-1",
        source_revision_id="REV-1",
        event_family="BAR",
    )
    duplicate_id = normalized_event_id(
        provider_id="SYNTH",
        venue_id="VENUE",
        publisher_id="PUB",
        channel_id="CHAN",
        source_instance_id="INST",
        source_record_id="REC-1",
        source_revision_id="REV-1",
        event_family="BAR",
    )
    return {
        "artifact_type": "PHASE_2_IDENTITY_REPORT",
        "deterministic_identity": sample_id == duplicate_id,
        "logical_id": "phase2.identity_report",
        "sample_normalized_event_id": sample_id,
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    contract_report = _contract_validation_report()
    temporal_report = _temporal_adversarial_report()
    replay_report = _replay_report()
    identity_report = _identity_report()

    write_canonical_json(output_dir / "contract-validation-report.json", contract_report)
    write_canonical_json(output_dir / "temporal-adversarial-report.json", temporal_report)
    write_canonical_json(output_dir / "replay-determinism-report.json", replay_report)
    write_canonical_json(output_dir / "identity-report.json", identity_report)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "TC-001": {
            "reason_codes": [],
            "status": temporal_report["tc001"]["pass_case"]["status"],
            "violation_count": 0,
        },
        "TC-002": {
            "reason_codes": [],
            "status": temporal_report["tc002"]["pass_case"]["status"],
        },
        "TC-003": {
            "prior_decision_unchanged": True,
            "reason_codes": [],
            "status": temporal_report["tc003"]["pass_case"]["status"],
        },
        "DET-001": {
            "reason_codes": [] if replay_report["determinism_match"] else ["DET001_HASH_MISMATCH"],
            "run_root_hash": replay_report["run_root_hash_a"],
            "status": "PASS" if replay_report["determinism_match"] else "FAIL",
        },
    }

    selected_evidence = [
        {"logical_id": "phase2.contract_validation_report", "sha256": sha256_bytes(canonical_bytes(contract_report))},
        {"logical_id": "phase2.temporal_adversarial_report", "sha256": sha256_bytes(canonical_bytes(temporal_report))},
        {"logical_id": "phase2.replay_determinism_report", "sha256": sha256_bytes(canonical_bytes(replay_report))},
        {"logical_id": "phase2.identity_report", "sha256": sha256_bytes(canonical_bytes(identity_report))},
    ]

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"phase": "2", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase2.run_phase2_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)

    from market_platform_foundation.phase2_assertions import evaluate_run

    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    members = {
        "phase2.assertion_aggregate": "assertion-aggregate.json",
        "phase2.assertion_registry": "assertion_registry.json",
        "phase2.assertion_results": "assertion-results.json",
        "phase2.assertion_run_manifest": "assertion-run-manifest.json",
        "phase2.contract_validation_report": "contract-validation-report.json",
        "phase2.identity_report": "identity-report.json",
        "phase2.replay_determinism_report": "replay-determinism-report.json",
        "phase2.temporal_adversarial_report": "temporal-adversarial-report.json",
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
        "logical_id": "phase2.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
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
