"""Generate BUILD 28 live execution safety artifacts."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.git_ref import read_git_head, read_remote_ref
from market_platform_foundation.intelligence.live_execution_safety import (
    BUILD25_RC_BRANCH,
    BUILD26_BRANCH,
    BUILD27_BRANCH,
    BUILD28_KNOWN_LIMITATIONS,
    BROKER_INVENTORY,
    build_live_execution_safety_spec,
    certify_all_brokers,
    live_execution_safety_spec_v1_to_dict,
    run_live_execution_safety_certification,
    verify_build27_integrity,
)
from market_platform_foundation.intelligence.system_acceptance import contract_inventory_hash

ARTIFACT_DIR = ROOT / "artifacts" / "live-execution-safety"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    build27_head = read_remote_ref("origin", BUILD27_BRANCH) or read_git_head() or ""
    build26_head = read_remote_ref("origin", BUILD26_BRANCH) or read_git_head() or ""
    build25_head = read_remote_ref("origin", BUILD25_RC_BRANCH) or read_git_head() or ""
    head = read_git_head() or ""

    build27_integrity = verify_build27_integrity(expected_head=build27_head)
    spec = build_live_execution_safety_spec(
        source_build27_ref=build27_head,
        source_build26_ref=build26_head,
        source_release_candidate_ref=build25_head,
        source_head=head,
    )
    run_result = run_live_execution_safety_certification(
        source_build27_ref=build27_head,
        source_build26_ref=build26_head,
        source_release_candidate_ref=build25_head,
        source_head=head,
    )
    certifications = certify_all_brokers()

    capabilities_path = ARTIFACT_DIR / "BUILD28_BROKER_CAPABILITIES.json"
    gate_spec_path = ARTIFACT_DIR / "BUILD28_EXECUTION_GATE_SPEC.json"
    certs_path = ARTIFACT_DIR / "BUILD28_BROKER_CERTIFICATIONS.json"
    dry_run_path = ARTIFACT_DIR / "BUILD28_DRY_RUN_EVIDENCE.json"
    safety_report_path = ARTIFACT_DIR / "BUILD28_LIVE_EXECUTION_SAFETY_REPORT.json"
    limitations_path = ARTIFACT_DIR / "BUILD28_KNOWN_LIMITATIONS.md"

    capabilities_path.write_text(
        json.dumps(
            [
                {
                    "broker": e.broker,
                    "adapter_module": e.adapter_module,
                    "market_data": e.market_data,
                    "paper": e.paper,
                    "live_capable_code": e.live_capable_code,
                    "preview_what_if": e.preview_what_if,
                    "cancel": e.cancel,
                    "replace": e.replace,
                    "current_status": e.current_status.value,
                    "default_environment": e.default_environment.value,
                    "notes": e.notes,
                }
                for e in BROKER_INVENTORY
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    gate_spec_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "policy_ref": "BUILD28_LIVE_EXECUTION_GATE_V1",
                "production_kill_switch": "ACTIVE_BLOCK",
                "production_live_submit": "FORBIDDEN",
                "required_gates": [
                    "runtime_activation_allows_live",
                    "live_authorization_enabled",
                    "broker_capability_certified",
                    "opportunity_valid",
                    "trade_proposal_valid",
                    "risk_decision_approved",
                    "order_intent_unexpired",
                    "broker_health_healthy",
                    "reconciliation_healthy",
                    "kill_switch_inactive",
                    "idempotency_key_unused",
                ],
                "build28_law": "PRELIVE_SAFETY_CERTIFICATION_ONLY",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    certs_path.write_text(
        json.dumps(
            [
                {
                    "certification_id": c.certification_id,
                    "broker": c.broker,
                    "adapter_version": c.adapter_version,
                    "disposition": c.disposition.value,
                    "certification_mode": c.certification_mode.value,
                    "account_environment": c.account_environment.value,
                    "tested_capabilities": list(c.tested_capabilities),
                    "untested_capabilities": list(c.untested_capabilities),
                    "limitations": list(c.limitations),
                }
                for c in certifications
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    dry_run_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "real_submit_count": run_result.real_submit_count,
                "real_cancel_count": run_result.real_cancel_count,
                "real_replace_count": run_result.real_replace_count,
                "scenario_failures": list(run_result.scenario_failures),
                "certification_mode": "ZERO_SUBMIT",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    safety_report_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_build27_ref": build27_head,
                "source_build26_ref": build26_head,
                "source_release_candidate_ref": build25_head,
                "source_head": head,
                "build27_integrity_status": build27_integrity.status,
                "build27_disposition": build27_integrity.disposition,
                "disposition": run_result.disposition.value,
                "live_authorization": "NOT_AUTHORIZED",
                "real_submit_count": run_result.real_submit_count,
                "metadata": run_result.metadata,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    limitations_path.write_text(
        "# BUILD 28 Known Limitations\n\n"
        + "\n".join(f"- {item}" for item in BUILD28_KNOWN_LIMITATIONS)
        + "\n\n"
        + "> BUILD 28 certifies the pre-live safety boundary only. "
        + "Live trading remains unauthorized.\n",
        encoding="utf-8",
    )

    spec_path = ARTIFACT_DIR / "BUILD28_SAFETY_SPEC.json"
    spec_path.write_text(json.dumps(live_execution_safety_spec_v1_to_dict(spec), indent=2), encoding="utf-8")

    manifest = {
        "schema_version": "1",
        "build_frontier": "BUILD_28_LIVE_EXECUTION_SAFETY_GATE",
        "branch": "cloud/build-28-live-execution-safety-gate",
        "source_build27_ref": build27_head,
        "source_build26_ref": build26_head,
        "source_release_candidate_ref": build25_head,
        "source_head": head,
        "contract_inventory_hash": contract_inventory_hash(),
        "safety_spec_id": spec.spec_id,
        "disposition": run_result.disposition.value,
        "live_authorization": "NOT_AUTHORIZED",
        "real_submit_count": 0,
    }
    (ARTIFACT_DIR / "BUILD28_RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    artifact_files = sorted(ARTIFACT_DIR.glob("BUILD28_*"))
    hashes = {p.name: _file_hash(p) for p in artifact_files}
    (ARTIFACT_DIR / "BUILD28_FILE_HASHES.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    print(f"BUILD28 disposition: {run_result.disposition.value}")
    print(f"Artifacts written to {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
