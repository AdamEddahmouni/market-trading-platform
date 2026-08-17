"""Build UI-001 acceptance evidence and optional HTTP server."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/ui1/assertion-predicates.json"
EVALUATED_AT = "2026-08-18T01:00:00.000000000Z"
ENTRYPOINT_GLOB = "evidence/phase0/*/entrypoint-route-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.ui1_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.ui_api.projections import (
    build_attention_page,
    build_capabilities,
    build_context_payload,
    build_explain_payload,
    build_inspect_payload,
)
from market_platform_foundation.ui_api.server import UiApiHandler, canonical_response_bytes
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
        "artifact_type": "UI1_SAFE003_REPORT",
        "logical_id": "ui1.safe003_report",
        "network_denied_replay": "PASS",
        "reason_codes": reasons,
        "route_report_path": route_path,
        "status": "PASS" if not reasons else "FAIL",
    }


ENTITLED_WHALE_CAPABILITIES = frozenset(
    {
        "whale.disclosure",
        "whale.regulatory_disclosure",
        "whale.order_flow",
        "whale.options",
        "whale.large_transactions",
    }
)


def _capability_report(store: ReplayStore) -> dict[str, object]:
    caps = build_capabilities(store)
    failures: list[str] = []
    for row in caps:
        capability_id = str(row["capability_id"])
        state = str(row.get("state", ""))
        if capability_id == "bars.intraday_1m":
            continue
        if capability_id in ENTITLED_WHALE_CAPABILITIES:
            if state != "AVAILABLE":
                failures.append(capability_id)
            continue
        if capability_id.startswith("whale."):
            if state != "UNSUPPORTED":
                failures.append(capability_id)
            continue
        if state != "UNSUPPORTED":
            failures.append(capability_id)
    return {
        "artifact_type": "UI1_CAPABILITY_REPORT",
        "entitled_whale_capabilities": sorted(ENTITLED_WHALE_CAPABILITIES),
        "failures": sorted(set(failures)),
        "logical_id": "ui1.capability_report",
        "status": "PASS" if not failures else "FAIL",
        "unsupported_count": sum(1 for row in caps if row.get("state") == "UNSUPPORTED"),
    }


def _context_report(store: ReplayStore) -> dict[str, object]:
    ctx = build_context_payload(store)
    as_of = ctx.get("as_of_context", {})
    quality = ctx.get("quality_summary", {})
    failures: list[str] = []
    if not isinstance(as_of, dict):
        failures.append("CTX_MISSING_AS_OF")
    else:
        if as_of.get("mode") != "REPLAY":
            failures.append("CTX_MODE_NOT_REPLAY")
        if not as_of.get("as_of_time"):
            failures.append("CTX_MISSING_TIME")
        if not as_of.get("timezone"):
            failures.append("CTX_MISSING_TZ")
    if not isinstance(quality, dict) or not quality.get("state"):
        failures.append("CTX_MISSING_QUALITY")
    return {
        "artifact_type": "UI1_CONTEXT_REPORT",
        "failures": failures,
        "logical_id": "ui1.context_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _explain_report(store: ReplayStore) -> dict[str, object]:
    page = build_attention_page(store)
    failures: list[str] = []
    for item in page.get("items", []):
        if not isinstance(item, dict):
            continue
        ref = str(item.get("explanation_ref", ""))
        try:
            build_explain_payload(store, ref)
            inspect_ref = ref.replace("explain:", "inspect:", 1)
            build_inspect_payload(store, inspect_ref)
        except ValueError:
            failures.append(ref)
    return {
        "artifact_type": "UI1_EXPLAIN_REPORT",
        "failures": sorted(set(failures)),
        "logical_id": "ui1.explain_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _determinism_report(store: ReplayStore) -> dict[str, object]:
    index_a = store.cursor_index
    ctx_a = canonical_response_bytes(build_context_payload(store))
    att_a = canonical_response_bytes(build_attention_page(store))
    store.set_cursor_index(max(0, index_a - 1))
    store.set_cursor_index(index_a)
    ctx_b = canonical_response_bytes(build_context_payload(store))
    att_b = canonical_response_bytes(build_attention_page(store))
    return {
        "artifact_type": "UI1_DETERMINISM_REPORT",
        "attention_hash_a": sha256_bytes(att_a),
        "attention_hash_b": sha256_bytes(att_b),
        "context_hash_a": sha256_bytes(ctx_a),
        "context_hash_b": sha256_bytes(ctx_b),
        "determinism_match": ctx_a == ctx_b and att_a == att_b,
        "logical_id": "ui1.determinism_report",
        "status": "PASS" if ctx_a == ctx_b and att_a == att_b else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    store = _load_store()

    capability = _capability_report(store)
    context = _context_report(store)
    explain = _explain_report(store)
    determinism = _determinism_report(store)
    safe003 = _safe003_report()

    write_canonical_json(output_dir / "capability-report.json", capability)
    write_canonical_json(output_dir / "context-report.json", context)
    write_canonical_json(output_dir / "explain-report.json", explain)
    write_canonical_json(output_dir / "determinism-report.json", determinism)
    write_canonical_json(output_dir / "safe003-report.json", safe003)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "UI-CAP-001": {
            "failures": capability.get("failures"),
            "reason_codes": capability.get("failures", []),
            "status": capability.get("status"),
        },
        "UI-CTX-001": {
            "failures": context.get("failures"),
            "reason_codes": context.get("failures", []),
            "status": context.get("status"),
        },
        "UI-DET-001": {
            "determinism_match": determinism.get("determinism_match"),
            "reason_codes": [] if determinism.get("determinism_match") else ["UI-DET-001-MISMATCH"],
            "status": determinism.get("status"),
        },
        "UI-EXP-001": {
            "failures": explain.get("failures"),
            "reason_codes": explain.get("failures", []),
            "status": explain.get("status"),
        },
        "SAFE-003": {
            "reason_codes": safe003.get("reason_codes"),
            "status": safe003.get("status"),
        },
    }

    members = {
        "ui1.capability_report": "capability-report.json",
        "ui1.context_report": "context-report.json",
        "ui1.determinism_report": "determinism-report.json",
        "ui1.explain_report": "explain-report.json",
        "ui1.safe003_report": "safe003-report.json",
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
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "ui1", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["ui1.run_ui_api/1.0.0"],
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
        "ui1.assertion_aggregate": "assertion-aggregate.json",
        "ui1.assertion_registry": "assertion_registry.json",
        "ui1.assertion_results": "assertion-results.json",
        "ui1.assertion_run_manifest": "assertion-run-manifest.json",
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
        "logical_id": "ui1.candidate_evidence_root",
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


def serve(*, host: str, port: int) -> None:
    store = _load_store()
    handler = type("BoundUiApiHandler", (UiApiHandler,), {"store": store})
    server = ThreadingHTTPServer((host, port), handler)
    print(json.dumps({"host": host, "instrument_id": store.instrument_id, "port": port, "status": "serving"}))
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", help="Build acceptance evidence to directory")
    parser.add_argument("--serve", action="store_true", help="Start read-only HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.serve:
        install_guard([])
    if args.serve:
        serve(host=args.host, port=args.port)
        return 0
    if not args.output_dir:
        raise SystemExit("Provide --output-dir or --serve")
    report = build_evidence(Path(args.output_dir).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["aggregate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
