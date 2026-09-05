#!/usr/bin/env python3
"""IBKR contract identity audit for Phase 3F Batch 05 external discovery symbols.

Qualifies each preregistered symbol against a live IB Gateway session, builds
``identity-review`` resolutions, and records contract candidates under the private
``ibkr-batch-05`` intake root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from squeeze_core.acquisition.identity_resolution import resolve_identity
from squeeze_core.acquisition.models import IdentityClaim, IdentityState

from tools.ibkr_historical_export.batch3f05_external import (
    DISCOVERY_ROWS_PATH,
    case_ids,
    load_discovery_document,
    symbols,
)
from tools.ibkr_historical_export.collector import probe_and_connect, qualify_contract
from tools.ibkr_historical_export.paths import default_private_root, PrivateLayout
from tools.ibkr_historical_export.serialization import canonical_json
from tools.ibkr_historical_export.statuses import ContractStatus

SOURCE_DISCOVERY = "batch3f05_external_discovery_rows"
SOURCE_IBKR = "ibkr-contract-resolution"
AUDIT_OUT = (
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


def _identity_claims(row: dict, resolution) -> tuple[IdentityClaim, ...]:
    claims = [
        IdentityClaim(
            source_artifact_id=SOURCE_DISCOVERY,
            symbol=str(row["ticker"]).strip().upper(),
        ),
    ]
    resolved = resolution.resolved
    if resolved is not None:
        issuer = resolved.long_name.strip() if resolved.long_name else None
        exchange = resolved.primary_exchange.strip() if resolved.primary_exchange else None
        claims.append(
            IdentityClaim(
                source_artifact_id=SOURCE_IBKR,
                symbol=str(row["ticker"]).strip().upper(),
                issuer_name=issuer,
                exchange=exchange,
                security_type="COMMON_STOCK",
                provider_identifier=f"ibkr:conId:{resolved.con_id}",
            )
        )
    return tuple(claims)


def _blocked_identity(state: IdentityState, contract_status: ContractStatus) -> bool:
    if state is IdentityState.CONFLICTED:
        return True
    if contract_status is ContractStatus.CONTRACT_AMBIGUOUS:
        return True
    return False


def run_audit(
    *,
    discovery_path: Path | None = None,
    private_root: Path | None = None,
    dry_run: bool = False,
) -> dict:
    document = load_discovery_document(discovery_path)
    symbol_list = symbols(document)
    if not symbol_list:
        raise ValueError("discovery document has no symbol rows")

    layout = PrivateLayout(private_root or default_private_root())
    layout.ensure()
    ids = case_ids(document)

    if dry_run:
        return {
            "status": "DRY_RUN",
            "symbols": list(symbol_list),
            "case_ids": ids,
        }

    session, connection = probe_and_connect(_session_factory)
    if session is None:
        raise RuntimeError(f"IB Gateway connection failed: {connection.attempts}")

    resolutions_out: list[dict] = []
    contract_rows: list[dict] = []
    req_id = 7000
    all_resolved = True

    try:
        for row in document.get("rows") or []:
            symbol = str(row["ticker"]).strip().upper()
            req_id += 1
            resolution = qualify_contract(session, req_id, symbol)
            identity = resolve_identity(_identity_claims(row, resolution))
            blocked = _blocked_identity(identity.state, resolution.status)
            if resolution.status is not ContractStatus.CONTRACT_RESOLVED or blocked:
                all_resolved = False

            layout.contract_candidates(symbol).write_bytes(
                canonical_json(
                    {
                        "requested_symbol": symbol,
                        "case_id": ids[symbol],
                        "status": resolution.status.value,
                        "reason": resolution.reason,
                        "resolved": resolution.resolved.as_dict() if resolution.resolved else None,
                        "candidates": [c.as_dict() for c in resolution.candidates],
                    }
                )
            )

            contract_rows.append(
                {
                    "symbol": symbol,
                    "case_id": ids[symbol],
                    "contract_status": resolution.status.value,
                    "contract_reason": resolution.reason,
                    "resolved_con_id": resolution.resolved.con_id if resolution.resolved else None,
                    "resolved_primary_exchange": (
                        resolution.resolved.primary_exchange if resolution.resolved else None
                    ),
                    "identity_state": identity.state.value,
                    "blocked_conflicting_identity": blocked,
                }
            )
            resolutions_out.append(identity.model_dump(mode="json"))
    finally:
        session.shutdown()

    out_path = discovery_path or DISCOVERY_ROWS_PATH
    discovery_ref = (
        out_path.relative_to(ROOT).as_posix()
        if out_path.is_relative_to(ROOT)
        else str(out_path)
    )

    audit = {
        "document": "phase_3f_batch_05_external_identity_audit",
        "schema_version": "1.0.0",
        "status": "PASS" if all_resolved else "FAIL",
        "discovery_artifact": discovery_ref,
        "symbols": list(symbol_list),
        "case_ids": ids,
        "contract_resolutions": contract_rows,
        "identity_review": {
            "schema_version": "1.0.0",
            "resolutions": resolutions_out,
        },
    }

    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    document["status"] = (
        "IDENTITY_AUDIT_COMPLETE" if all_resolved else "IDENTITY_AUDIT_FAILED"
    )
    document["identity_audit_artifact"] = (
        AUDIT_OUT.relative_to(ROOT).as_posix()
        if AUDIT_OUT.is_relative_to(ROOT)
        else str(AUDIT_OUT)
    )
    out_path = discovery_path or DISCOVERY_ROWS_PATH
    out_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--discovery-path",
        type=Path,
        default=None,
        help="Override discovery rows JSON (default: batch3f05_external_discovery_rows.json)",
    )
    parser.add_argument("--private-root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="List symbols without IBKR")
    args = parser.parse_args()

    try:
        audit = run_audit(
            discovery_path=args.discovery_path,
            private_root=args.private_root,
            dry_run=args.dry_run,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"identity audit failed: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(audit, indent=2))
        return 0

    print(f"Wrote {AUDIT_OUT.resolve()}")
    print(f"status={audit['status']} symbols={','.join(audit['symbols'])}")
    for row in audit["contract_resolutions"]:
        flag = "BLOCKED" if row["blocked_conflicting_identity"] else "OK"
        print(
            f"  {row['symbol']}: contract={row['contract_status']} "
            f"identity={row['identity_state']} [{flag}]"
        )
    return 0 if audit["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
