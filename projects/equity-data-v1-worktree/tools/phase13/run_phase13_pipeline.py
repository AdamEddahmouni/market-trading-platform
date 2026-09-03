"""Build Phase 13 order_book whale family acceptance evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/phase13/assertion-predicates.json"
FIXTURE_MANIFEST = ROOT / "tests/fixtures/providers/order_book/admission_manifest.json"
EVALUATED_AT = "2026-08-19T12:00:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.features.institutional import (
    NO_ENTITLED_SOURCE,
    ORDER_BOOK_FAMILY,
    configure_institutional_ledger,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase13_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.providers.adapters.fixture_order_book import (
    DEFAULT_ORDER_BOOK_FIXTURE,
    FixtureOrderBookProvider,
)
from market_platform_foundation.providers.projections import build_workspace_order_book_payload
from market_platform_foundation.providers.whale_ledger import WHALE_ENTITLED_ORDER_BOOK, build_combined_fixture_ledger
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
        "artifact_type": "PHASE_13_SAFE003_REPORT",
        "logical_id": "phase13.safe003_report",
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
        for claim in ("visible_liquidity", "top_n_depth_imbalance", "ofi_derivation", "snapshot_provenance"):
            if claim not in claims:
                failures.append(f"MISSING_{claim}")
    return {
        "artifact_type": "PHASE_13_FIXTURE_REPORT",
        "failures": failures,
        "logical_id": "phase13.fixture_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _order_book_report() -> dict[str, object]:
    first = FixtureOrderBookProvider(fixture_path=DEFAULT_ORDER_BOOK_FIXTURE)
    second = FixtureOrderBookProvider(fixture_path=DEFAULT_ORDER_BOOK_FIXTURE)
    first_ids = [row["normalized_event_id"] for row in first.build_envelopes()]
    second_ids = [row["normalized_event_id"] for row in second.build_envelopes()]
    deterministic = first_ids == second_ids and len(first_ids) > 0
    return {
        "artifact_type": "PHASE_13_ORDER_BOOK_REPORT",
        "deterministic_envelope_ids": deterministic,
        "event_count": len(first_ids),
        "logical_id": "phase13.order_book_report",
        "status": "PASS" if deterministic else "FAIL",
    }


def _pit_report() -> dict[str, object]:
    cutoff = iso_to_epoch_ns("2026-07-21T20:30:02.000000000Z")
    provider = FixtureOrderBookProvider(fixture_path=DEFAULT_ORDER_BOOK_FIXTURE)
    result = provider.fetch_order_book("NVDA", as_of_time_ns=cutoff)
    return {
        "artifact_type": "PHASE_13_PIT_REPORT",
        "event_count": len(result.events),
        "logical_id": "phase13.pit_report",
        "status": "PASS" if result.status == "available" and len(result.events) == 3 else "FAIL",
    }


def _whale_report() -> dict[str, object]:
    ledger = build_combined_fixture_ledger()
    configure_institutional_ledger(ledger)
    cutoff = iso_to_epoch_ns("2026-07-21T21:01:09.000000000Z")
    nvda = query_institutional_evidence(
        ORDER_BOOK_FAMILY,
        prediction_cutoff=cutoff,
        instrument_id="NVDA",
    )
    biya = query_institutional_evidence(
        ORDER_BOOK_FAMILY,
        prediction_cutoff=cutoff,
        instrument_id="BIYA",
    )
    failures: list[str] = []
    if nvda.get("status") != "available" or nvda.get("reason_code") != WHALE_ENTITLED_ORDER_BOOK:
        failures.append("NVDA_UNAVAILABLE")
    if biya.get("status") != "unavailable" or biya.get("reason_code") != NO_ENTITLED_SOURCE:
        failures.append("BIYA_OVERCLAIM")
    configure_institutional_ledger(None)
    return {
        "artifact_type": "PHASE_13_WHALE_REPORT",
        "failures": failures,
        "logical_id": "phase13.whale_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _ui_report() -> dict[str, object]:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    caps = build_capabilities(store)
    by_id = {row["capability_id"]: row for row in caps}
    failures: list[str] = []
    if by_id.get("whale.order_book", {}).get("state") != "AVAILABLE":
        failures.append("WHALE_CAPABILITY")
    if by_id.get("depth.L2", {}).get("state") != "AVAILABLE":
        failures.append("DEPTH_CAPABILITY")
    payload = build_workspace_order_book_payload(
        "NVDA",
        as_of_context={"mode": "REPLAY"},
        prediction_cutoff=store.prediction_cutoff(),
    )
    if not payload.get("available") or not payload.get("research_only"):
        failures.append("PAYLOAD")
    return {
        "artifact_type": "PHASE_13_UI_REPORT",
        "failures": failures,
        "logical_id": "phase13.ui_report",
        "status": "PASS" if not failures else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture = _fixture_report()
    order_book = _order_book_report()
    pit = _pit_report()
    whale = _whale_report()
    ui = _ui_report()
    safe003 = _safe003_report()

    write_canonical_json(output_dir / "fixture-report.json", fixture)
    write_canonical_json(output_dir / "order-book-report.json", order_book)
    write_canonical_json(output_dir / "pit-report.json", pit)
    write_canonical_json(output_dir / "whale-report.json", whale)
    write_canonical_json(output_dir / "ui-report.json", ui)
    write_canonical_json(output_dir / "safe003-report.json", safe003)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "P13-FIX-001": {"failures": fixture.get("failures"), "reason_codes": fixture.get("failures", []), "status": fixture.get("status")},
        "P13-OB-001": {"reason_codes": [] if order_book.get("status") == "PASS" else ["P13-OB-001-FAIL"], "status": order_book.get("status")},
        "P13-PIT-001": {"reason_codes": [] if pit.get("status") == "PASS" else ["P13-PIT-001-FAIL"], "status": pit.get("status")},
        "P13-WHALE-001": {"failures": whale.get("failures"), "reason_codes": whale.get("failures", []), "status": whale.get("status")},
        "P13-UI-001": {"failures": ui.get("failures"), "reason_codes": ui.get("failures", []), "status": ui.get("status")},
        "SAFE-003": {"reason_codes": safe003.get("reason_codes"), "status": safe003.get("status")},
    }

    members = {
        "phase13.fixture_report": "fixture-report.json",
        "phase13.order_book_report": "order-book-report.json",
        "phase13.pit_report": "pit-report.json",
        "phase13.safe003_report": "safe003-report.json",
        "phase13.ui_report": "ui-report.json",
        "phase13.whale_report": "whale-report.json",
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
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "phase13", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase13.run_phase13_pipeline/1.0.0"],
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
        "phase13.assertion_aggregate": "assertion-aggregate.json",
        "phase13.assertion_registry": "assertion_registry.json",
        "phase13.assertion_results": "assertion-results.json",
        "phase13.assertion_run_manifest": "assertion-run-manifest.json",
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
        "logical_id": "phase13.candidate_evidence_root",
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
