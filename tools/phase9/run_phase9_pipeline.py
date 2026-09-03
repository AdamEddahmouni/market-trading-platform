"""Build Phase 9 provider and whale ledger acceptance evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/phase9/assertion-predicates.json"
EVALUATED_AT = "2026-08-16T22:00:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.features.institutional import (
    NO_ENTITLED_SOURCE,
    REGULATORY_DISCLOSURE_FAMILY,
    WHALE_FAMILIES,
    configure_institutional_ledger,
    query_all_institutional,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase9_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.providers.adapters.edgar_disclosure import DEFAULT_FIXTURE, FixtureEdgarDisclosureProvider
from market_platform_foundation.providers.composition import get_provider_composition
from market_platform_foundation.providers.contracts import EXECUTION_DISABLED, PROVIDER_UNAVAILABLE
from market_platform_foundation.providers.projections import build_workspace_disclosure_payload
from market_platform_foundation.providers.stubs import (
    DisabledPaperExecutionProvider,
    UnconfiguredDisclosureProvider,
    UnconfiguredEquityQuoteProvider,
    UnconfiguredOptionChainProvider,
)
from market_platform_foundation.providers.whale_ledger import WHALE_ENTITLED_DISCLOSURE, build_ledger_from_edgar_fixture
from market_platform_foundation.replay.feature_lifecycle import verify_capability_surface
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
        "artifact_type": "PHASE_9_SAFE003_REPORT",
        "logical_id": "phase9.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


def _provider_report() -> dict[str, object]:
    failures: list[str] = []
    disclosure = UnconfiguredDisclosureProvider()
    if disclosure.fetch_disclosures("BIYA").reason_code != PROVIDER_UNAVAILABLE:
        failures.append("DISCLOSURE_STUB")
    quote = UnconfiguredEquityQuoteProvider()
    if quote.fetch_quote("BIYA").reason_code != PROVIDER_UNAVAILABLE:
        failures.append("QUOTE_STUB")
    chain = UnconfiguredOptionChainProvider()
    if chain.fetch_chain("BIYA").reason_code != PROVIDER_UNAVAILABLE:
        failures.append("OPTION_STUB")
    execution = DisabledPaperExecutionProvider(enabled=False)
    if execution.place_order({}).reason_code != EXECUTION_DISABLED:
        failures.append("EXECUTION_STUB")
    composition = get_provider_composition()
    if composition.disclosure.provider_id != "stub.disclosure.unconfigured":
        failures.append("DEFAULT_COMPOSITION")
    return {
        "artifact_type": "PHASE_9_PROVIDER_REPORT",
        "failures": sorted(set(failures)),
        "logical_id": "phase9.provider_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _ledger_report() -> dict[str, object]:
    first = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
    second = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
    deterministic = first.root_hash() == second.root_hash()
    return {
        "artifact_type": "PHASE_9_LEDGER_REPORT",
        "deterministic_root_hash": deterministic,
        "event_count": len(first.events),
        "logical_id": "phase9.ledger_report",
        "root_hash": first.root_hash(),
        "status": "PASS" if deterministic and len(first.events) > 0 else "FAIL",
    }


def _pit_report() -> dict[str, object]:
    cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
    ledger = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE, as_of_time_ns=cutoff)
    events = ledger.query_events(
        family="regulatory_disclosure",
        instrument_id="BIYA",
        prediction_cutoff=cutoff,
    )
    accession_numbers = {
        str(event["disclosure_event"]["accession_number"])
        for event in events
        if isinstance(event.get("disclosure_event"), dict)
    }
    provider = FixtureEdgarDisclosureProvider(fixture_path=DEFAULT_FIXTURE)
    envelopes = provider.build_envelopes()
    revisions = [
        (str(row["source_record_id"]), str(row["source_revision_id"]))
        for row in envelopes
        if str(row["source_record_id"]) == "0001849639-26-000010"
    ]
    failures: list[str] = []
    if "0001849639-26-000010" not in accession_numbers:
        failures.append("BASE_FILING_MISSING")
    if "0001849639-26-000099" in accession_numbers:
        failures.append("FUTURE_FILING_INCLUDED")
    if revisions != [("0001849639-26-000010", "1"), ("0001849639-26-000010", "2")]:
        failures.append("AMENDMENT_ORDER")
    return {
        "artifact_type": "PHASE_9_PIT_REPORT",
        "failures": failures,
        "logical_id": "phase9.pit_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _whale_report() -> dict[str, object]:
    ledger = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
    configure_institutional_ledger(ledger)
    cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
    disclosure = query_institutional_evidence(
        REGULATORY_DISCLOSURE_FAMILY,
        prediction_cutoff=cutoff,
        instrument_id="BIYA",
    )
    failures: list[str] = []
    if disclosure.get("status") != "available":
        failures.append("DISCLOSURE_UNAVAILABLE")
    if disclosure.get("reason_code") != WHALE_ENTITLED_DISCLOSURE:
        failures.append("DISCLOSURE_REASON")
    for family in WHALE_FAMILIES:
        if family == REGULATORY_DISCLOSURE_FAMILY:
            continue
        row = query_institutional_evidence(family, prediction_cutoff=cutoff)
        if row.get("status") != "unavailable" or row.get("reason_code") != NO_ENTITLED_SOURCE:
            failures.append(f"FAMILY_{family}")
    institutional = query_all_institutional(prediction_cutoff=cutoff, instrument_id="BIYA")
    snapshot = {
        "bar_features": [],
        "institutional_evidence": institutional,
        "prediction_cutoff": cutoff,
    }
    cap_status, cap_reasons = verify_capability_surface(snapshot)
    if cap_status != "PASS":
        failures.extend(cap_reasons)
    configure_institutional_ledger(None)
    return {
        "artifact_type": "PHASE_9_WHALE_REPORT",
        "failures": sorted(set(failures)),
        "logical_id": "phase9.whale_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _ui_report() -> dict[str, object]:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    caps = build_capabilities(store)
    by_id = {row["capability_id"]: row for row in caps}
    failures: list[str] = []
    if by_id.get("whale.disclosure", {}).get("state") != "AVAILABLE":
        failures.append("WHALE_DISCLOSURE_CAP")
    if by_id.get("whale.regulatory_disclosure", {}).get("state") != "AVAILABLE":
        failures.append("WHALE_REGULATORY_CAP")
    if by_id.get("whale.order_flow", {}).get("state") != "UNSUPPORTED":
        failures.append("WHALE_ORDER_FLOW_CAP")
    payload = build_workspace_disclosure_payload(
        "BIYA",
        as_of_context={"mode": "REPLAY"},
        prediction_cutoff=store.prediction_cutoff(),
    )
    if not payload.get("available"):
        failures.append("DISCLOSURE_PAYLOAD")
    if not payload.get("research_only"):
        failures.append("RESEARCH_ONLY")
    if "disclosure_lag_note" not in payload:
        failures.append("LAG_NOTE")
    if int(payload.get("event_count", 0)) <= 0:
        failures.append("EVENT_COUNT")
    return {
        "artifact_type": "PHASE_9_UI_REPORT",
        "failures": sorted(set(failures)),
        "logical_id": "phase9.ui_report",
        "status": "PASS" if not failures else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = _provider_report()
    ledger = _ledger_report()
    pit = _pit_report()
    whale = _whale_report()
    ui = _ui_report()
    safe003 = _safe003_report()

    write_canonical_json(output_dir / "provider-report.json", provider)
    write_canonical_json(output_dir / "ledger-report.json", ledger)
    write_canonical_json(output_dir / "pit-report.json", pit)
    write_canonical_json(output_dir / "whale-report.json", whale)
    write_canonical_json(output_dir / "ui-report.json", ui)
    write_canonical_json(output_dir / "safe003-report.json", safe003)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "P9-PROV-001": {
            "failures": provider.get("failures"),
            "reason_codes": provider.get("failures", []),
            "status": provider.get("status"),
        },
        "P9-LEDGER-001": {
            "deterministic_root_hash": ledger.get("deterministic_root_hash"),
            "reason_codes": [] if ledger.get("status") == "PASS" else ["P9-LEDGER-001-FAIL"],
            "status": ledger.get("status"),
        },
        "P9-PIT-001": {
            "failures": pit.get("failures"),
            "reason_codes": pit.get("failures", []),
            "status": pit.get("status"),
        },
        "P9-WHALE-001": {
            "failures": whale.get("failures"),
            "reason_codes": whale.get("failures", []),
            "status": whale.get("status"),
        },
        "P9-UI-001": {
            "failures": ui.get("failures"),
            "reason_codes": ui.get("failures", []),
            "status": ui.get("status"),
        },
        "SAFE-003": {
            "reason_codes": safe003.get("reason_codes"),
            "status": safe003.get("status"),
        },
    }

    members = {
        "phase9.ledger_report": "ledger-report.json",
        "phase9.pit_report": "pit-report.json",
        "phase9.provider_report": "provider-report.json",
        "phase9.safe003_report": "safe003-report.json",
        "phase9.ui_report": "ui-report.json",
        "phase9.whale_report": "whale-report.json",
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
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "phase9", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["phase9.run_phase9_pipeline/1.0.0"],
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
        "phase9.assertion_aggregate": "assertion-aggregate.json",
        "phase9.assertion_registry": "assertion_registry.json",
        "phase9.assertion_results": "assertion-results.json",
        "phase9.assertion_run_manifest": "assertion-run-manifest.json",
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
        "logical_id": "phase9.candidate_evidence_root",
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
