"""Generate BUILD 26 forward qualification artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.git_ref import read_git_head, read_remote_ref
from market_platform_foundation.intelligence.forward_qualification import (
    BUILD25_RC_BRANCH,
    build_forward_qualification_spec,
    forward_qualification_spec_v1_to_dict,
    provider_capability_matrix,
    run_forward_qualification,
    verify_build25_rc_integrity,
)
from market_platform_foundation.intelligence.system_acceptance import contract_inventory_hash

ARTIFACT_DIR = ROOT / "artifacts" / "forward-qualification"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    rc_head = read_remote_ref("origin", BUILD25_RC_BRANCH) or read_git_head() or ""
    head = read_git_head() or ""
    rc_integrity = verify_build25_rc_integrity(expected_head=rc_head)
    spec = build_forward_qualification_spec(
        release_candidate_ref=rc_head,
        source_head=head,
        qualification_start_ns=1_700_000_000_000_000_000,
    )
    run_result = run_forward_qualification(
        release_candidate_ref=rc_head,
        source_head=head,
    )

    provider_path = ARTIFACT_DIR / "BUILD26_PROVIDER_CAPABILITIES.json"
    spec_path = ARTIFACT_DIR / "BUILD26_QUALIFICATION_SPEC.json"
    report_path = ARTIFACT_DIR / "BUILD26_QUALIFICATION_REPORT.json"

    provider_path.write_text(json.dumps(provider_capability_matrix(), indent=2), encoding="utf-8")
    spec_path.write_text(json.dumps(forward_qualification_spec_v1_to_dict(spec), indent=2), encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "release_candidate_ref": rc_head,
                "source_head": head,
                "rc_integrity_status": rc_integrity.status,
                "disposition": run_result.disposition.value,
                "fixture_lifecycle_ok": run_result.fixture_lifecycle_ok,
                "scenario_failures": list(run_result.scenario_failures),
                "metadata": run_result.metadata,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "1",
        "build_frontier": "BUILD_26_FORWARD_SHADOW_QUALIFICATION",
        "branch": "cloud/build-26-forward-shadow-qualification",
        "release_candidate_ref": rc_head,
        "source_head": head,
        "contract_inventory_hash": contract_inventory_hash(),
        "qualification_spec_id": spec.qualification_spec_id,
        "rc_integrity_status": rc_integrity.status,
        "known_limitations_ref": "artifacts/forward-qualification/BUILD26_KNOWN_LIMITATIONS.md",
        "provider_capabilities_ref": "artifacts/forward-qualification/BUILD26_PROVIDER_CAPABILITIES.json",
        "qualification_spec_ref": "artifacts/forward-qualification/BUILD26_QUALIFICATION_SPEC.json",
        "qualification_report_ref": "artifacts/forward-qualification/BUILD26_QUALIFICATION_REPORT.json",
    }
    (ARTIFACT_DIR / "BUILD26_RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
