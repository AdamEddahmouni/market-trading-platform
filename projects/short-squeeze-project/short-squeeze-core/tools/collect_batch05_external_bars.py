#!/usr/bin/env python3
"""Collect IBKR detection-context and forward-outcome bars for Batch 05 external symbols.

Requires a successful identity audit (``run_batch05_identity_audit.py``) and a live
IB Gateway session entitled to historical TRADES bars.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ibkr_historical_export import policy
from tools.ibkr_historical_export.batch3f05_external import (
    case_ids,
    cohort_boundary,
    load_discovery_document,
    request_specs,
    symbols,
)
from tools.ibkr_historical_export.collector import (
    collect_historical,
    probe_and_connect,
    qualify_contract,
    write_raw_artifacts,
    _run_preflight_for,
)
from tools.ibkr_historical_export.paths import default_private_root, PrivateLayout
from tools.ibkr_historical_export.serialization import canonical_json
from tools.ibkr_historical_export.statuses import ContractStatus, HistoricalStatus

AUDIT_PATH = (
    ROOT
    / "intake"
    / "batches"
    / "phase-3f-cohort-expansion-05-external"
    / "normalized"
    / "batch3f05_identity_audit.json"
)


def _session_factory():
    from tools.ibkr_historical_export.session import IbkrSession

    return IbkrSession()


def _approved_symbols(audit: dict, document: dict) -> list[str]:
    if audit.get("status") != "PASS":
        raise ValueError("identity audit did not PASS — run run_batch05_identity_audit.py first")
    approved = {
        row["symbol"]
        for row in audit.get("contract_resolutions") or []
        if row.get("contract_status") == ContractStatus.CONTRACT_RESOLVED.value
        and not row.get("blocked_conflicting_identity")
    }
    ordered = [sym for sym in symbols(document) if sym in approved]
    if not ordered:
        raise ValueError("no approved symbols in identity audit")
    return ordered


def collect_bars(
    *,
    discovery_path: Path | None = None,
    audit_path: Path | None = None,
    private_root: Path | None = None,
) -> dict:
    document = load_discovery_document(discovery_path)
    audit = json.loads((audit_path or AUDIT_PATH).read_text(encoding="utf-8"))
    symbol_list = _approved_symbols(audit, document)
    boundary = cohort_boundary(document)
    specs = request_specs(boundary)
    ids = case_ids(document)
    layout = PrivateLayout(private_root or default_private_root())
    layout.ensure()

    session, connection = probe_and_connect(_session_factory)
    if session is None:
        raise RuntimeError(f"IB Gateway connection failed: {connection.attempts}")

    req_counter = 8000
    per_symbol: list[dict] = []
    artifact_records: list[dict] = []
    request_manifest: list[dict] = []

    try:
        for symbol in symbol_list:
            req_counter += 1
            resolution = qualify_contract(session, req_counter, symbol)
            entry: dict = {
                "symbol": symbol,
                "case_id": ids[symbol],
                "contract_status": resolution.status.value,
                "resolved_con_id": (
                    resolution.resolved.con_id if resolution.resolved else None
                ),
                "requests": [],
            }
            if resolution.status is not ContractStatus.CONTRACT_RESOLVED or resolution.resolved is None:
                entry["error"] = resolution.reason
                per_symbol.append(entry)
                continue

            con_id = resolution.resolved.con_id
            for index, spec in enumerate(specs):
                req_counter += 10
                result = collect_historical(session, req_counter, spec, symbol, con_id)
                artifacts = write_raw_artifacts(layout, result)
                artifact_records.append(artifacts)
                request_manifest.append(
                    {
                        "symbol": symbol,
                        "case_id": ids[symbol],
                        "request_name": spec.request_name,
                        "status": result.status.value,
                        "bar_count": result.bar_count,
                        "first_timestamp_utc": result.first_timestamp_utc,
                        "last_timestamp_utc": result.last_timestamp_utc,
                    }
                )
                preflight_status, preflight_reasons = _run_preflight_for(
                    layout, result, spec, artifacts,
                )
                entry["requests"].append(
                    {
                        "request_name": spec.request_name,
                        "historical_status": result.status.value,
                        "bar_count": result.bar_count,
                        "preflight_status": preflight_status.value,
                        "preflight_reason_codes": preflight_reasons,
                    }
                )
                if index < len(specs) - 1:
                    time.sleep(policy.INTER_REQUEST_DELAY_S)
            per_symbol.append(entry)
    finally:
        session.shutdown()

    sha_manifest = {
        rec["csv_relative_path"]: {
            "sha256": rec["csv_sha256"],
            "byte_length": rec["csv_byte_length"],
        }
        for rec in artifact_records
    }
    layout.request_manifest.write_bytes(canonical_json(request_manifest))
    layout.artifact_manifest.write_bytes(canonical_json(artifact_records))
    existing_sha = {}
    if layout.sha256_manifest.exists():
        existing_sha = json.loads(layout.sha256_manifest.read_text(encoding="utf-8"))
    existing_sha.update(sha_manifest)
    layout.sha256_manifest.write_bytes(canonical_json(existing_sha))

    # Preserve frozen-cohort manifest rows when appending external symbols.
    from tools.merge_batch05_manifests import merge_manifests

    merge_manifests(layout.root)

    summary = {
        "batch": "ibkr-batch-05-external-batch3f05",
        "cohort_boundary": boundary.isoformat().replace("+00:00", "Z"),
        "symbols": per_symbol,
        "artifact_count": len(artifact_records),
    }
    out = layout.root / "batch3f05-external-collection-summary.json"
    out.write_bytes(canonical_json(summary))

    document["status"] = "BARS_COLLECTED"
    document["bar_collection_summary"] = str(out.relative_to(ROOT).as_posix())
    out_path = discovery_path or (
        ROOT
        / "intake"
        / "batches"
        / "phase-3f-cohort-expansion-05-external"
        / "normalized"
        / "batch3f05_external_discovery_rows.json"
    )
    out_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery-path", type=Path, default=None)
    parser.add_argument("--audit-path", type=Path, default=None)
    parser.add_argument("--private-root", type=Path, default=None)
    args = parser.parse_args()

    try:
        summary = collect_bars(
            discovery_path=args.discovery_path,
            audit_path=args.audit_path,
            private_root=args.private_root,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"collection failed: {exc}", file=sys.stderr)
        return 2

    ok = all(
        req.get("historical_status") == HistoricalStatus.HISTORICAL_REQUEST_SUCCESS.value
        for row in summary["symbols"]
        for req in row.get("requests") or []
    )
    print(f"collected {summary['artifact_count']} artifacts for {len(summary['symbols'])} symbols")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
