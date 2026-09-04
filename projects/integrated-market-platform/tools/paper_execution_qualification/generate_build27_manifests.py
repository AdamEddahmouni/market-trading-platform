"""Generate BUILD 27 paper execution qualification artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.git_ref import read_git_head, read_remote_ref
from market_platform_foundation.intelligence.forward_qualification import BUILD25_RC_BRANCH
from market_platform_foundation.intelligence.paper_execution_qualification import (
    BUILD26_BRANCH,
    build_initial_paper_portfolio_state,
    build_paper_execution_qualification_spec,
    paper_execution_qualification_spec_v1_to_dict,
    run_paper_execution_qualification,
    verify_build26_integrity,
)
from market_platform_foundation.intelligence.system_acceptance import contract_inventory_hash

ARTIFACT_DIR = ROOT / "artifacts" / "paper-execution-qualification"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    build26_head = read_remote_ref("origin", BUILD26_BRANCH) or read_git_head() or ""
    build25_head = read_remote_ref("origin", BUILD25_RC_BRANCH) or read_git_head() or ""
    head = read_git_head() or ""
    build26_integrity = verify_build26_integrity(expected_head=build26_head)
    portfolio = build_initial_paper_portfolio_state()
    spec = build_paper_execution_qualification_spec(
        source_build26_ref=build26_head,
        source_release_candidate_ref=build25_head,
        source_head=head,
        qualification_start_ns=1_700_000_000_000_000_000,
        initial_portfolio=portfolio,
    )
    run_result = run_paper_execution_qualification(
        source_build26_ref=build26_head,
        source_release_candidate_ref=build25_head,
        source_head=head,
    )

    spec_path = ARTIFACT_DIR / "BUILD27_QUALIFICATION_SPEC.json"
    report_path = ARTIFACT_DIR / "BUILD27_QUALIFICATION_REPORT.json"
    spec_path.write_text(json.dumps(paper_execution_qualification_spec_v1_to_dict(spec), indent=2), encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_build26_ref": build26_head,
                "source_release_candidate_ref": build25_head,
                "source_head": head,
                "build26_integrity_status": build26_integrity.status,
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
        "build_frontier": "BUILD_27_FORWARD_PAPER_EXECUTION",
        "branch": "cloud/build-27-forward-paper-execution",
        "source_build26_ref": build26_head,
        "source_release_candidate_ref": build25_head,
        "source_head": head,
        "contract_inventory_hash": contract_inventory_hash(),
        "qualification_spec_id": spec.qualification_spec_id,
        "initial_portfolio_state_id": portfolio.state_id,
        "build26_integrity_status": build26_integrity.status,
        "known_limitations_ref": "artifacts/paper-execution-qualification/BUILD27_KNOWN_LIMITATIONS.md",
        "qualification_spec_ref": "artifacts/paper-execution-qualification/BUILD27_QUALIFICATION_SPEC.json",
        "qualification_report_ref": "artifacts/paper-execution-qualification/BUILD27_QUALIFICATION_REPORT.json",
    }
    (ARTIFACT_DIR / "BUILD27_RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    evidence = {
        "schema_version": "1",
        "qualification_spec_id": spec.qualification_spec_id,
        "source_build26_ref": build26_head,
        "source_release_candidate_ref": build25_head,
        "initial_portfolio_state_id": portfolio.state_id,
        "fill_policy_ref": spec.fill_policy_ref,
        "execution_policy_ref": spec.execution_policy_ref,
        "opportunity_policy_ref": spec.opportunity_policy_ref,
    }
    (ARTIFACT_DIR / "BUILD27_EXECUTION_EVIDENCE_MANIFEST.json").write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
