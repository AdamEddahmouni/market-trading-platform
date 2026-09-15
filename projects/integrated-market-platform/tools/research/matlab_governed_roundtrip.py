#!/usr/bin/env python3
"""Run governed Research Export v1 ↔ MATLAB round-trip (offline fixtures only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from market_platform_foundation.research.export_v1 import (  # noqa: E402
    PROFILE_EVENT_MACRO,
    PROFILE_MARKET_TECHNICAL,
    ResearchExportV1Package,
    build_research_export_v1,
    load_research_export_v1_package,
    write_research_export_v1_package,
)
from market_platform_foundation.research.export_v1_matlab_roundtrip import (  # noqa: E402
    GovernedMatlabRoundtripReport,
    execute_governed_roundtrip,
)
from tools.research.matlab_runtime import (  # noqa: E402
    probe_matlab_runtime,
    run_matlab_parity_smoke,
)


def execute_governed_roundtrip_with_matlab(
    package: ResearchExportV1Package,
    *,
    work_dir: Path,
    prefer_matlab: bool = True,
) -> GovernedMatlabRoundtripReport:
    """Probe/run MATLAB smoke when requested, then delegate lineage finalize to foundation."""
    matlab_smoke_result: dict[str, Any] | None = None
    matlab_runtime_available = False
    package_dir = work_dir / "export_package"
    write_research_export_v1_package(package_dir, package)

    if prefer_matlab:
        probe = probe_matlab_runtime()
        matlab_runtime_available = probe["status"] == "AVAILABLE"
        if matlab_runtime_available:
            smoke = run_matlab_parity_smoke(package_dir, work_dir / "matlab_out")
            if smoke.get("status") == "PASS":
                matlab_smoke_result = smoke["result"]

    return execute_governed_roundtrip(
        package,
        work_dir=work_dir,
        matlab_smoke_result=matlab_smoke_result,
        matlab_runtime_available=matlab_runtime_available,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Governed MATLAB research round-trip")
    parser.add_argument(
        "--profile",
        choices=(PROFILE_MARKET_TECHNICAL, PROFILE_EVENT_MACRO),
        default=PROFILE_MARKET_TECHNICAL,
    )
    parser.add_argument("--package-dir", type=Path, help="Existing Research Export v1 directory")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--no-matlab", action="store_true", help="Force Python reference path")
    args = parser.parse_args()

    if args.package_dir:
        package = load_research_export_v1_package(args.package_dir)
    else:
        package = build_research_export_v1(profile=args.profile)

    report = execute_governed_roundtrip_with_matlab(
        package,
        work_dir=args.work_dir,
        prefer_matlab=not args.no_matlab,
    )
    probe = probe_matlab_runtime()
    payload = {"probe": probe, "report": report.to_dict()}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
