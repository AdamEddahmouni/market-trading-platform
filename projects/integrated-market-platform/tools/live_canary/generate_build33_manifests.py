#!/usr/bin/env python3
"""Generate BUILD 33 supervised production pilot artifact bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "supervised-production-pilot"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    head = _git_head()

    from market_platform_foundation.intelligence.live_canary.supervised_production_pilot import (
        BUILD33_KNOWN_LIMITATIONS,
        build_broker_redundancy_assessment,
        build_default_pilot_policy,
        build_default_pilot_qualification_spec,
        build_default_provider_redundancy_policy,
        build_pilot_run,
        build_sustained_pilot_qualification_report,
        run_all_runbook_exercises,
        run_maintenance_fixture,
        run_multi_provider_pilot_fixture,
        run_operational_incident_fixture,
    )
    from market_platform_foundation.ui_api.canary_projections import build_canary_pilot_payload

    build32_ref = "ce49004c1388afc4895dd6d595ccb1b063757441"
    t = 1_700_000_000_000_000_000
    pilot_policy = build_default_pilot_policy(source_build32_ref=build32_ref, pilot_start_ns=t)
    redundancy = build_default_provider_redundancy_policy()
    pilot_run = build_pilot_run(build33_source_ref=head, build32_ref=build32_ref, start_ns=t)
    qual_spec = build_default_pilot_qualification_spec(pilot_policy_ref=pilot_policy.pilot_policy_id)
    duration_ns = 90 * 60 * 1_000_000_000
    qualification = build_sustained_pilot_qualification_report(
        qualification_spec=qual_spec,
        pilot_run_ref=pilot_run.pilot_run_id,
        build33_source_ref=head,
        actual_observation_duration_ns=duration_ns,
    )
    runbook_reports = run_all_runbook_exercises()
    failover_fixture = run_multi_provider_pilot_fixture()
    incident_fixture = run_operational_incident_fixture()
    maintenance_fixture = run_maintenance_fixture()
    broker_assessment = build_broker_redundancy_assessment()
    pilot_snapshot = build_canary_pilot_payload()

    manifest = {
        "build": "BUILD33",
        "schema_version": "1",
        "source_head": head,
        "build32_source_ref": build32_ref,
        "disposition": qualification.disposition,
    }
    (ARTIFACTS / "BUILD33_CONTROL_PLANE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ARTIFACTS / "BUILD33_PILOT_POLICY.json").write_text(
        json.dumps(
            {
                "pilot_policy_id": pilot_policy.pilot_policy_id,
                "pilot_start_ns": pilot_policy.pilot_start_ns,
                "pilot_end_ns": pilot_policy.pilot_end_ns,
                "allowed_data_providers": list(pilot_policy.allowed_data_providers),
                "max_pilot_sessions": pilot_policy.max_pilot_sessions,
                "human_session_authorization_required": pilot_policy.human_session_authorization_required,
                "human_order_confirmation_required": pilot_policy.human_order_confirmation_required,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PROVIDER_REDUNDANCY_POLICY.json").write_text(
        json.dumps(
            {
                "provider_redundancy_policy_id": redundancy.provider_redundancy_policy_id,
                "primary_provider": redundancy.primary_provider,
                "fallback_providers": list(redundancy.fallback_providers),
                "minimum_failure_duration_ns": redundancy.minimum_failure_duration_ns,
                "minimum_recovery_duration_ns": redundancy.minimum_recovery_duration_ns,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PROVIDER_CAPABILITY_MATRIX.json").write_text(
        json.dumps(
            {
                "providers": {
                    "polygon": {"capabilities": ["QUOTES", "TRADES"], "live_availability": "fixture"},
                    "finviz": {"capabilities": ["QUOTES"], "live_availability": "fixture"},
                }
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PILOT_RUN_MANIFEST.json").write_text(
        json.dumps(
            {"pilot_run_id": pilot_run.pilot_run_id, "start_ns": pilot_run.start_ns},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PILOT_CHECKPOINT_INDEX.json").write_text(
        json.dumps(
            {"checkpoints": [c.checkpoint_id for c in failover_fixture.checkpoints]},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PROVIDER_FAILOVER_EVIDENCE.json").write_text(
        json.dumps(
            {
                "provider_switches": failover_fixture.provider_switches,
                "switch_back_count": failover_fixture.switch_back_count,
                "degraded_intervals": failover_fixture.degraded_intervals,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_RUNBOOK_INDEX.json").write_text(
        json.dumps(
            {k: v.result for k, v in runbook_reports.items()},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_RUNBOOK_EXERCISE_REPORTS.json").write_text(
        json.dumps(
            {k: v.exercise_report_id for k, v in runbook_reports.items()},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PILOT_REPORT.json").write_text(
        json.dumps(
            {
                "report_id": qualification.report_id,
                "disposition": qualification.disposition,
                "actual_observation_duration_ns": qualification.actual_observation_duration_ns,
                "limitations": list(qualification.limitations),
                "real_broker_side_effects_observed": qualification.real_broker_side_effects_observed,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_PILOT_SNAPSHOT.json").write_text(
        json.dumps(pilot_snapshot, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_OPERATIONAL_INCIDENT_EVIDENCE.json").write_text(
        json.dumps(incident_fixture, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_MAINTENANCE_EVIDENCE.json").write_text(
        json.dumps(maintenance_fixture, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD33_BROKER_REDUNDANCY_ASSESSMENT.json").write_text(
        json.dumps(
            {
                "assessment_id": broker_assessment.assessment_id,
                "auto_failover_authorization": broker_assessment.auto_failover_authorization,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    limitations_md = "# BUILD 33 Known Limitations\n\n" + "\n".join(
        f"- {item}" for item in BUILD33_KNOWN_LIMITATIONS
    )
    (ARTIFACTS / "BUILD33_KNOWN_LIMITATIONS.md").write_text(limitations_md, encoding="utf-8")

    tracked_dirs = [
        ROOT / "src" / "market_platform_foundation" / "intelligence" / "live_canary" / "supervised_production_pilot",
        ROOT / "tests" / "intelligence",
        ROOT / "docs" / "engineering",
    ]
    hashes: dict[str, str] = {}
    for d in tracked_dirs:
        if not d.exists():
            continue
        for path in sorted(d.rglob("*")):
            if path.suffix in {".py", ".md", ".tsx"} and path.is_file():
                rel = str(path.relative_to(ROOT)).replace("\\", "/")
                hashes[rel] = _sha256_file(path)
    for path in sorted(ARTIFACTS.glob("BUILD33_*")):
        if path.is_file():
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            hashes[rel] = _sha256_file(path)
    (ARTIFACTS / "BUILD33_FILE_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"BUILD33 artifacts written to {ARTIFACTS}")
    print(f"Disposition: {qualification.disposition}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
