"""Build Phase 14 futures_positioning whale family acceptance evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/phase14/assertion-predicates.json"
FIXTURE_MANIFEST = ROOT / "tests/fixtures/providers/futures/admission_manifest.json"
EVALUATED_AT = "2026-08-17T22:50:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.features.institutional import (
    FUTURES_FAMILY,
    NO_ENTITLED_SOURCE,
    configure_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase14_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.providers.adapters.fixture_futures import (
    DEFAULT_FUTURES_FIXTURE,
    FixtureFuturesProvider,
)
from market_platform_foundation.providers.projections import build_workspace_futures_payload
from market_platform_foundation.providers.whale_ledger import WHALE_ENTITLED_FUTURES, build_combined_fixture_ledger
from market_platform_foundation.ui_api.projections import build_capabilities
from market_platform_foundation.ui_api.store import ReplayStore


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
        "artifact_type": "PHASE_14_SAFE003_REPORT",
        "logical_id": "phase14.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def _fixture_report() -> dict[str, object]:
    manifest = load_json_strict(FIXTURE_MANIFEST)
    failures: list[str] = []
    if manifest.get("status") != "ADMITTED":
        failures.append("NOT_ADMITTED")
    claims = manifest.get("capability_claims", [])
    if not isinstance(claims, list):
        failures.append("CLAIMS_INVALID")
    else:
        for claim in (
            "visible_liquidity",
            "contract_roll_metadata",
            "rth_session_gate",
            "depth_imbalance_signal",
        ):
            if claim not in claims:
                failures.append(f"MISSING_{claim}")
    return {
        "artifact_type": "PHASE_14_FIXTURE_REPORT",
        "failures": failures,
        "logical_id": "phase14.fixture_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _futures_report() -> dict[str, object]:
    first = FixtureFuturesProvider(fixture_path=DEFAULT_FUTURES_FIXTURE)
    second = FixtureFuturesProvider(fixture_path=DEFAULT_FUTURES_FIXTURE)
    first_ids = [row["normalized_event_id"] for row in first.build_envelopes()]
    second_ids = [row["normalized_event_id"] for row in second.build_envelopes()]
    deterministic = first_ids == second_ids and len(first_ids) > 0
    return {
        "artifact_type": "PHASE_14_FUTURES_REPORT",
        "deterministic_envelope_ids": deterministic,
        "event_count": len(first_ids),
        "logical_id": "phase14.futures_report",
        "status": "PASS" if deterministic else "FAIL",
    }


def _pit_report() -> dict[str, object]:
    cutoff = iso_to_epoch_ns("2025-06-02T14:41:02.000000000Z")
    provider = FixtureFuturesProvider(fixture_path=DEFAULT_FUTURES_FIXTURE)
    result = provider.fetch_futures_depth("ES", as_of_time_ns=cutoff)
    return {
        "artifact_type": "PHASE_14_PIT_REPORT",
        "event_count": len(result.events),
        "logical_id": "phase14.pit_report",
        "status": "PASS" if result.status == "available" and len(result.events) == 3 else "FAIL",
    }


def _whale_report() -> dict[str, object]:
    ledger = build_combined_fixture_ledger()
    configure_institutional_ledger(ledger)
    cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
    es = query_institutional_evidence(
        FUTURES_FAMILY,
        prediction_cutoff=cutoff,
        instrument_id="ES",
    )
    nvda = query_institutional_evidence(
        FUTURES_FAMILY,
        prediction_cutoff=cutoff,
        instrument_id="NVDA",
    )
    failures: list[str] = []
    if es.get("status") != "available" or es.get("reason_code") != WHALE_ENTITLED_FUTURES:
        failures.append("ES_UNAVAILABLE")
    if nvda.get("status") != "unavailable" or nvda.get("reason_code") != NO_ENTITLED_SOURCE:
        failures.append("NVDA_OVERCLAIM")
    configure_institutional_ledger(None)
    return {
        "artifact_type": "PHASE_14_WHALE_REPORT",
        "failures": failures,
        "logical_id": "phase14.whale_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _ui_report() -> dict[str, object]:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    caps = build_capabilities(store)
    by_id = {row["capability_id"]: row for row in caps}
    failures: list[str] = []
    if by_id.get("whale.futures_positioning", {}).get("state") != "AVAILABLE":
        failures.append("WHALE_CAPABILITY")
    payload = build_workspace_futures_payload(
        "ES",
        as_of_context={"mode": "REPLAY"},
        prediction_cutoff=store.prediction_cutoff(),
    )
    if not payload.get("available") or not payload.get("research_only"):
        failures.append("PAYLOAD")
    return {
        "artifact_type": "PHASE_14_UI_REPORT",
        "failures": failures,
        "logical_id": "phase14.ui_report",
        "status": "PASS" if not failures else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture = _fixture_report()
    futures = _futures_report()
    pit = _pit_report()
    whale = _whale_report()
    ui = _ui_report()
    safe003 = _safe003_report()

    write_canonical_json(output_dir / "fixture-report.json", fixture)
    write_canonical_json(output_dir / "futures-report.json", futures)
    write_canonical_json(output_dir / "pit-report.json", pit)
    write_canonical_json(output_dir / "whale-report.json", whale)
    write_canonical_json(output_dir / "ui-report.json", ui)
    write_canonical_json(output_dir / "safe003-report.json", safe003)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "P14-FIX-001": {"failures": fixture.get("failures"), "reason_codes": fixture.get("failures", []), "status": fixture.get("status")},
        "P14-FUT-001": {"reason_codes": [] if futures.get("status") == "PASS" else ["P14-FUT-001-FAIL"], "status": futures.get("status")},
        "P14-PIT-001": {"reason_codes": [] if pit.get("status") == "PASS" else ["P14-PIT-001-FAIL"], "status": pit.get("status")},
        "P14-WHALE-001": {"failures": whale.get("failures"), "reason_codes": whale.get("failures", []), "status": whale.get("status")},
        "P14-UI-001": {"failures": ui.get("failures"), "reason_codes": ui.get("failures", []), "status": ui.get("status")},
        "SAFE-003": {"reason_codes": safe003.get("reason_codes"), "status": safe003.get("status")},
    }

    members = {
        "phase14.fixture_report": "fixture-report.json",
        "phase14.futures_report": "futures-report.json",
        "phase14.pit_report": "pit-report.json",
        "phase14.safe003_report": "safe003-report.json",
        "phase14.ui_report": "ui-report.json",
        "phase14.whale_report": "whale-report.json",
    }
    selected_evidence = []
    for logical_id, filename in sorted(members.items()):
        path = output_dir / filename
        selected_evidence.append({"logical_id": logical_id, "sha256": sha256_bytes(path.read_bytes())})

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "phase14", "root_id": "ROOT-FUTURES-LANE"})),
        "tool_versions": ["phase14.run_phase14_pipeline/1.0.0"],
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
        "phase14.assertion_aggregate": "assertion-aggregate.json",
        "phase14.assertion_registry": "assertion_registry.json",
        "phase14.assertion_results": "assertion-results.json",
        "phase14.assertion_run_manifest": "assertion-run-manifest.json",
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
        "logical_id": "phase14.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "output_dir": str(output_dir),
        "run_id": run_id,
    }


def main() -> int:
    install_guard([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report = build_evidence(Path(args.output_dir).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["aggregate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
