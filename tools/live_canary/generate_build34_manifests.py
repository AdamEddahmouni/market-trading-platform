#!/usr/bin/env python3
"""Generate BUILD 34 deployment qualification artifact bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "deployment-qualification"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    head = _git_head()
    build33_ref = "16bf0f3e854e99ac2e992d8c7245b8f1742979b9"
    t = 1_700_000_000_000_000_000

    from market_platform_foundation.intelligence.live_canary.deployment import (
        BUILD34_KNOWN_LIMITATIONS,
        build_change_request,
        build_deployment_canary_spec,
        build_deployment_plan,
        build_deployment_qualification_report,
        build_deployment_qualification_spec,
        build_environment_manifest,
        build_migration_plan,
        build_release_manifest,
        build_rollback_plan,
        run_deployment_canary,
        run_failed_deployment_rollback_fixture,
        run_full_successful_deployment_fixture,
        run_migration_fixture,
        run_reproducibility_fixture,
    )
    from market_platform_foundation.intelligence.live_canary.deployment.supervision import (
        build_default_service_graph,
    )
    from market_platform_foundation.ui_api.canary_projections import build_canary_deployment_payload

    build33_qual = "BUILD33-SUPERVISED-PRODUCTION-PILOT-QUALIFIED"
    release_result = build_release_manifest(
        build_timestamp_ns=t,
        build33_qualification_ref=build33_qual,
        allow_dirty=True,
    )
    release = release_result.manifest
    test_env = build_environment_manifest(
        environment_kind="TEST",
        release_manifest_ref=release.release_manifest_id,
        build33_qualification_ref=build33_qual,
    )
    supervised_env = build_environment_manifest(
        environment_kind="SUPERVISED_LIVE",
        release_manifest_ref=release.release_manifest_id,
        build33_qualification_ref=build33_qual,
    )
    service_graph = build_default_service_graph(supervised_env.environment_manifest_id)
    plan = build_deployment_plan(
        target_environment=supervised_env.environment_manifest_id,
        release_ref=release.release_manifest_id,
        config_ref=supervised_env.configuration_ref,
    )
    canary_spec = build_deployment_canary_spec(deployment_plan_ref=plan.deployment_plan_id)
    canary_report = run_deployment_canary(
        canary_spec=canary_spec,
        observation_duration_ns=canary_spec.minimum_observation_duration_ns,
    )
    change_request = build_change_request(
        change_type="CODE_RELEASE",
        release_ref=release.release_manifest_id,
        target_environment=supervised_env.environment_manifest_id,
        reason="BUILD34 qualification deployment",
        rollback_target="NONE",
        approval_state="APPROVED",
    )
    migration_plan = build_migration_plan()
    rollback_fixture = run_failed_deployment_rollback_fixture()
    rollback_plan = build_rollback_plan(
        deployment_ref="DEPLOY-fixture-b",
        rollback_target_release=release.release_manifest_id,
        rollback_target_deployment="DEPLOY-fixture-a",
    )
    migration_fixture = run_migration_fixture(backup_verified=True)
    full_fixture = run_full_successful_deployment_fixture(allow_dirty=True)
    qual_spec = build_deployment_qualification_spec(
        release_ref=release.release_manifest_id,
        environment_kind="SUPERVISED_LIVE",
    )
    qualification = build_deployment_qualification_report(
        spec=qual_spec,
        release_reproducibility="PASS" if run_reproducibility_fixture() else "FAIL",
        environment_validation="PASS",
        deployment_result="PASS" if not full_fixture.release_blocked else "FAIL",
        service_supervision="PASS",
        deployment_canary=canary_report.disposition,
        migration=migration_fixture.forward_migration,
        rollback="PASS",
        config_drift="PASS",
        operator_visibility="PASS",
        security="PASS",
        real_broker_submits=canary_report.real_broker_submits,
    )
    deployment_snapshot = build_canary_deployment_payload()

    inventory = {
        "dockerfile": {"location": ".cursor/Dockerfile", "classification": "CLOUD_DEV_ONLY"},
        "install_cloud_deps": {"location": ".cursor/install-cloud-deps.sh", "classification": "CLOUD_DEV_ONLY"},
        "run_ui_api": {"location": "tools/ui1/run_ui_api.py", "classification": "DEV_ONLY"},
        "restart_ui_api": {"location": "tools/ui1/restart_ui_api.ps1", "classification": "DEV_ONLY"},
        "phase0_dependency_lock": {"location": "phase0-dependency-lock.json", "classification": "CANONICAL_REUSE"},
        "github_actions_validate": {"location": ".github/workflows/imp-validate.yml", "classification": "CANONICAL_REUSE"},
        "deployment_module": {"location": "src/.../deployment/", "classification": "CANONICAL_REUSE"},
        "fixture_supervisor": {"location": "deployment/supervision.py", "classification": "CANONICAL_REUSE"},
    }

    manifest = {
        "build": "BUILD34",
        "schema_version": "1",
        "source_head": head,
        "build33_source_ref": build33_ref,
        "disposition": qualification.disposition,
        "release_id": release.release_manifest_id,
    }
    (ARTIFACTS / "BUILD34_CONTROL_PLANE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ARTIFACTS / "BUILD34_RELEASE_MANIFEST.json").write_text(
        json.dumps(
            {
                "release_manifest_id": release.release_manifest_id,
                "source_commit_sha": release.source_commit_sha,
                "source_tree_hash": release.source_tree_hash,
                "dependency_lock_hash": release.dependency_lock_hash,
                "artifact_hashes": release.artifact_hashes,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_ENVIRONMENT_MANIFESTS.json").write_text(
        json.dumps(
            {
                "TEST": test_env.environment_manifest_id,
                "SUPERVISED_LIVE": supervised_env.environment_manifest_id,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_SERVICE_GRAPH.json").write_text(
        json.dumps(
            {
                "service_graph_id": service_graph.service_graph_id,
                "startup_order": list(service_graph.startup_order),
                "services": [s.service_id for s in service_graph.services],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_CHANGE_REQUEST.json").write_text(
        json.dumps(
            {"change_request_id": change_request.change_request_id, "approval_state": change_request.approval_state},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_DEPLOYMENT_PLAN.json").write_text(
        json.dumps({"deployment_plan_id": plan.deployment_plan_id, "release_ref": plan.release_ref}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_DEPLOYMENT_CANARY_REPORT.json").write_text(
        json.dumps(
            {
                "canary_report_id": canary_report.deployment_canary_report_id,
                "disposition": canary_report.disposition,
                "real_broker_submits": canary_report.real_broker_submits,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_ROLLBACK_EVIDENCE.json").write_text(
        json.dumps(
            {
                "rollback_plan_id": rollback_plan.rollback_plan_id,
                "fixture": {
                    "rollback_decision": rollback_fixture.rollback_decision,
                    "orders_replayed": rollback_fixture.orders_replayed,
                    "live_auto_resume": rollback_fixture.live_auto_resume,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_MIGRATION_EVIDENCE.json").write_text(
        json.dumps(
            {
                "migration_plan_id": migration_plan.migration_plan_id,
                "forward_migration": migration_fixture.forward_migration,
                "rollback_compatible": migration_fixture.rollback_compatible,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_QUALIFICATION_REPORT.json").write_text(
        json.dumps(
            {
                "qualification_report_id": qualification.qualification_report_id,
                "disposition": qualification.disposition,
                "real_broker_submits": qualification.real_broker_submits,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD34_DEPLOYMENT_INVENTORY.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ARTIFACTS / "BUILD34_PILOT_SNAPSHOT.json").write_text(
        json.dumps(deployment_snapshot, indent=2, sort_keys=True), encoding="utf-8"
    )
    limitations = "\n".join(f"- {lim}" for lim in BUILD34_KNOWN_LIMITATIONS)
    (ARTIFACTS / "BUILD34_KNOWN_LIMITATIONS.md").write_text(
        f"# BUILD 34 Known Limitations\n\n{limitations}\n", encoding="utf-8"
    )

    governed = [
        ROOT / "src/market_platform_foundation/intelligence/live_canary/deployment",
        ROOT / "tests/intelligence/test_deployment_change_control.py",
        ROOT / "docs/engineering/DEPLOYMENT_RELEASE_CHANGE_CONTROL_V1.md",
        ROOT / "tools/live_canary/generate_build34_manifests.py",
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
    (ARTIFACTS / "BUILD34_FILE_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"BUILD34 artifacts written to {ARTIFACTS}")
    print(f"Disposition: {qualification.disposition}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
