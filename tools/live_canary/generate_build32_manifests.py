#!/usr/bin/env python3
"""Generate BUILD 32 operational reliability artifact bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "operational-reliability"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    head = _git_head()

    from market_platform_foundation.intelligence.live_canary.operational_reliability import (
        DR_DRILL_SPECS,
        build_default_alert_policy,
        build_default_slo_policy,
        build_operational_reliability_qualification_report,
        run_all_dr_drills,
        run_virtual_soak_endurance,
    )
    from market_platform_foundation.intelligence.live_canary.operational_reliability.types import (
        BUILD32_KNOWN_LIMITATIONS,
    )
    from market_platform_foundation.ui_api.canary_projections import build_canary_reliability_payload

    drill_reports = run_all_dr_drills()
    qualification = build_operational_reliability_qualification_report(build32_source_ref=head)
    slo_policy = build_default_slo_policy()
    alert_policy = build_default_alert_policy()
    soak = run_virtual_soak_endurance(start_ns=1_700_000_000_000_000_000)
    reliability_snapshot = build_canary_reliability_payload()

    manifest = {
        "build": "BUILD32",
        "schema_version": "1",
        "source_head": head,
        "build31_source_ref": "844ce17edf0d100079c30c36b1cca2da3aa2870f",
        "disposition": qualification.disposition,
    }
    (ARTIFACTS / "BUILD32_QUALIFICATION_REPORT.json").write_text(
        json.dumps(
            {
                "report_id": qualification.report_id,
                "disposition": qualification.disposition,
                "dr_drill_results": qualification.dr_drill_results,
                "soak_disposition": qualification.soak_disposition,
                "limitations": list(qualification.limitations),
                "real_broker_side_effects_observed": qualification.real_broker_side_effects_observed,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD32_OBSERVABILITY_INVENTORY.json").write_text(
        json.dumps(reliability_snapshot, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD32_SLO_POLICY.json").write_text(
        json.dumps(
            {
                "slo_policy_id": slo_policy.slo_policy_id,
                "scope": slo_policy.scope,
                "measurement_window_ns": slo_policy.measurement_window_ns,
                "objectives": [o.objective_id for o in slo_policy.objectives],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD32_ALERT_POLICY.json").write_text(
        json.dumps(
            {
                "alert_policy_id": alert_policy.alert_policy_id,
                "delivery_channels": list(alert_policy.delivery_channels),
                "critical_requires_delivery": alert_policy.critical_requires_delivery,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD32_HEALTH_MATRIX.json").write_text(
        json.dumps(reliability_snapshot["health_matrix"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    drill_index = {
        drill_id: {
            "scenario": spec.scenario,
            "result": drill_reports[drill_id].result,
            "real_broker_submits": drill_reports[drill_id].real_broker_submits,
        }
        for drill_id, spec in DR_DRILL_SPECS.items()
    }
    (ARTIFACTS / "BUILD32_DRILL_INDEX.json").write_text(
        json.dumps(drill_index, indent=2, sort_keys=True), encoding="utf-8"
    )
    (ARTIFACTS / "BUILD32_SOAK_REPORT.json").write_text(
        json.dumps(
            {
                "soak_report_id": soak.soak_report_id,
                "virtual_duration_ns": soak.virtual_duration_ns,
                "actual_duration_ns": soak.actual_duration_ns,
                "disposition": soak.disposition,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD32_KNOWN_LIMITATIONS.md").write_text(
        "\n".join(f"- {item}" for item in BUILD32_KNOWN_LIMITATIONS) + "\n",
        encoding="utf-8",
    )
    (ARTIFACTS / "BUILD32_CONTROL_PLANE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    tracked = [
        "src/market_platform_foundation/intelligence/live_canary/operational_reliability/",
        "src/market_platform_foundation/ui_api/canary_projections.py",
        "docs/engineering/OPERATIONAL_RELIABILITY_SLO_DR_V1.md",
        "tests/intelligence/test_operational_reliability.py",
        "ui/src/components/live/LiveCanaryControlPlanePage.tsx",
    ]
    hashes: dict[str, str] = {}
    for rel in tracked:
        path = ROOT / rel
        if path.is_dir():
            for file in sorted(path.rglob("*")):
                if file.is_file() and file.suffix in {".py", ".tsx", ".md"}:
                    hashes[str(file.relative_to(ROOT)).replace("\\", "/")] = _sha256_file(file)
        elif path.is_file():
            hashes[rel] = _sha256_file(path)
    (ARTIFACTS / "BUILD32_FILE_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"BUILD32 artifacts written to {ARTIFACTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
