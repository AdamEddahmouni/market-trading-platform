#!/usr/bin/env python3
"""Generate BUILD 35 full-system acceptance artifact bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "full-system-acceptance"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    head = _git_head()
    t = 1_700_000_000_000_000_000

    from market_platform_foundation.intelligence.live_canary.release_governance import (
        BUILD35_KNOWN_LIMITATIONS,
        assemble_release_candidate_fixture,
        build_canonical_authority_map,
        build_change_impact_policy,
        run_full_lifecycle_fixture,
        run_revocation_exercise,
        run_rollback_exercises,
    )
    from market_platform_foundation.intelligence.live_canary.release_governance.registry import (
        ProductionReleaseRegistry,
    )

    (
        release,
        gov_policy,
        evidence,
        candidate,
        eligibility,
        acceptance_spec,
        acceptance_report,
        approval,
        env_promo_policy,
        change_window_policy,
    ) = assemble_release_candidate_fixture(allow_dirty=True, assembled_at_ns=t)

    registry = ProductionReleaseRegistry()
    registry.register_candidate(candidate)
    registry.register_approval(approval, event_time_ns=t)

    authority_map = build_canonical_authority_map()
    change_impact = build_change_impact_policy()
    rollback_exercises = run_rollback_exercises()
    revocation = run_revocation_exercise()
    lifecycle = run_full_lifecycle_fixture()

    # Write artifacts
    (ARTIFACTS / "BUILD35_RELEASE_GOVERNANCE_POLICY.json").write_text(
        json.dumps(
            {
                "release_governance_policy_id": gov_policy.release_governance_policy_id,
                "required_build_evidence": list(gov_policy.required_build_evidence),
                "forbidden_authority_expansions": list(gov_policy.forbidden_authority_expansions),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_RELEASE_EVIDENCE_BUNDLE.json").write_text(
        json.dumps(
            {
                "release_evidence_bundle_id": evidence.release_evidence_bundle_id,
                "release_manifest_ref": evidence.release_manifest_ref,
                "source_hashes": evidence.source_hashes,
                "artifact_hashes": evidence.artifact_hashes,
                "build25": evidence.build25_acceptance_ref,
                "build34": evidence.build34_deployment_qualification_ref,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_PRODUCTION_RELEASE_CANDIDATE.json").write_text(
        json.dumps(
            {
                "production_release_candidate_id": candidate.production_release_candidate_id,
                "exact_source_sha": candidate.exact_source_sha,
                "release_manifest_ref": candidate.release_manifest_ref,
                "candidate_status": candidate.candidate_status,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_ELIGIBILITY_ASSESSMENT.json").write_text(
        json.dumps(
            {
                "eligibility_assessment_id": eligibility.eligibility_assessment_id,
                "disposition": eligibility.disposition,
                "blocking_reasons": list(eligibility.blocking_reasons),
                "limitations": list(eligibility.limitations),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_ENVIRONMENT_PROMOTION_POLICY.json").write_text(
        json.dumps(
            {
                "environment_promotion_policy_id": env_promo_policy.environment_promotion_policy_id,
                "environment_graph": [list(e) for e in env_promo_policy.environment_graph],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_CHANGE_IMPACT_POLICY.json").write_text(
        json.dumps(
            {"change_impact_policy_id": change_impact.change_impact_policy_id},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_CHANGE_WINDOW_POLICY.json").write_text(
        json.dumps(
            {
                "change_window_policy_id": change_window_policy.change_window_policy_id,
                "active_order_behavior": change_window_policy.active_order_behavior,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_AUTHORITY_MAP.json").write_text(
        json.dumps(
            {
                "authority_map_id": authority_map.authority_map_id,
                "entries": [
                    {"decision": e.decision_artifact, "authority": e.canonical_authority}
                    for e in authority_map.entries
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_RELEASE_HISTORY.json").write_text(
        json.dumps(
            {
                "event_count": registry.event_count(),
                "events": [
                    {"event_id": e.event_id, "event_type": e.event_type}
                    for e in registry.events
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_FULL_ACCEPTANCE_SPEC.json").write_text(
        json.dumps(
            {
                "acceptance_spec_id": acceptance_spec.acceptance_spec_id,
                "required_build_range": list(acceptance_spec.required_build_range),
                "domain_count": len(acceptance_spec.required_domains),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    matrix = [
        {
            "domain": dr.domain,
            "result": dr.result,
            "blocking": dr.blocking,
            "limitations": list(dr.limitations),
        }
        for dr in acceptance_report.domain_results
    ]
    (ARTIFACTS / "BUILD35_FULL_ACCEPTANCE_MATRIX.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ARTIFACTS / "BUILD35_FULL_ACCEPTANCE_REPORT.json").write_text(
        json.dumps(
            {
                "full_system_acceptance_report_id": acceptance_report.full_system_acceptance_report_id,
                "final_disposition": acceptance_report.final_disposition,
                "blocking_requirement_count": len(acceptance_report.blocking_requirements),
                "nonblocking_limitation_count": len(acceptance_report.nonblocking_limitations),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_ROLLBACK_EXERCISE_EVIDENCE.json").write_text(
        json.dumps(
            [{"exercise_id": r.exercise_id, "scenario": r.scenario, "result": r.result} for r in rollback_exercises],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD35_REVOCATION_EXERCISE.json").write_text(
        json.dumps(
            {
                "scenario": revocation.scenario,
                "approval_state_after": revocation.approval_state_after,
                "deployment_blocked": revocation.deployment_blocked,
                "result": revocation.result,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    limitations = "\n".join(f"- {lim}" for lim in BUILD35_KNOWN_LIMITATIONS)
    (ARTIFACTS / "BUILD35_KNOWN_LIMITATIONS.md").write_text(
        f"# BUILD 35 Known Limitations\n\n{limitations}\n", encoding="utf-8"
    )

    manifest = {
        "build": "BUILD35",
        "schema_version": "1",
        "source_head": head,
        "build34_source_ref": "1cbfb415c398b37056030c6037b91744f7a33b90",
        "disposition": acceptance_report.final_disposition,
        "release_approval_status": approval.approval_status,
        "release_id": release.release_manifest_id,
        "lifecycle_result": lifecycle.result,
    }
    (ARTIFACTS / "BUILD35_CONTROL_PLANE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    governed = [
        ROOT / "src/market_platform_foundation/intelligence/live_canary/release_governance",
        ROOT / "tests/intelligence/test_release_governance.py",
        ROOT / "docs/engineering/PRODUCTION_RELEASE_GOVERNANCE_V1.md",
        ROOT / "tools/live_canary/generate_build35_manifests.py",
        ARTIFACTS,
    ]
    hashes = {}
    for base in governed:
        if base.is_file():
            rel = str(base.relative_to(ROOT)).replace("\\", "/")
            hashes[rel] = _sha256_file(base)
        elif base.is_dir():
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    rel = str(path.relative_to(ROOT)).replace("\\", "/")
                    hashes[rel] = _sha256_file(path)
    (ARTIFACTS / "BUILD35_FILE_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"BUILD35 artifacts written to {ARTIFACTS}")
    print(f"Disposition: {acceptance_report.final_disposition}")
    print(f"Approval: {approval.approval_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
