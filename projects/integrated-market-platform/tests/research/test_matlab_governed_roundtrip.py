"""Governed Research Export v1 ↔ MATLAB round-trip contract tests (fixture-backed)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_platform_foundation.research.export_v1 import (  # noqa: E402
    PROFILE_MARKET_TECHNICAL,
    build_research_export_v1,
    write_research_export_v1_package,
)
from market_platform_foundation.research.export_v1_matlab_result import (  # noqa: E402
    CONTRACT_READY,
    MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY,
    MATLAB_RESEARCH_EVIDENCE_ARTIFACT_TYPE,
    project_matlab_research_evidence_artifact,
    validate_matlab_research_result_v1,
    verify_matlab_result_export_lineage,
)
from market_platform_foundation.research.export_v1_matlab_roundtrip import (  # noqa: E402
    execute_governed_roundtrip,
)
from tools.research.matlab_governed_roundtrip import (  # noqa: E402
    execute_governed_roundtrip_with_matlab,
)
from tools.research.matlab_runtime import (  # noqa: E402
    probe_matlab_runtime,
    run_matlab_parity_smoke,
)

_GOLDEN_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "research"
    / "matlab_golden_result_v1.json"
)


class MatlabGovernedRoundtripTests(unittest.TestCase):
    def test_golden_fixture_lineage_and_evidence_projection(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        golden = json.loads(_GOLDEN_FIXTURE.read_text(encoding="utf-8"))
        validate_matlab_research_result_v1(golden)
        verify_matlab_result_export_lineage(golden, package)
        evidence = project_matlab_research_evidence_artifact(golden)
        self.assertEqual(evidence["artifact_type"], MATLAB_RESEARCH_EVIDENCE_ARTIFACT_TYPE)
        self.assertEqual(
            evidence["dataset"]["manifest_hash"],
            package.manifest["manifest_hash"],
        )

    def test_python_reference_roundtrip_contract_ready(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_governed_roundtrip(
                package,
                work_dir=Path(tmp),
            )
        self.assertTrue(report.lineage_verified)
        self.assertEqual(report.readiness, CONTRACT_READY)
        self.assertEqual(report.analysis_source, "python_reference")

    def test_matlab_smoke_when_runtime_available(self) -> None:
        probe = probe_matlab_runtime()
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            package_dir = work / "pkg"
            write_research_export_v1_package(package_dir, package)
            if probe["status"] != "AVAILABLE":
                self.skipTest("MATLAB runtime not available on host")
            smoke = run_matlab_parity_smoke(package_dir, work / "out")
            self.assertEqual(smoke["status"], "PASS")
            verify_matlab_result_export_lineage(smoke["result"], package)
            report = execute_governed_roundtrip_with_matlab(
                package,
                work_dir=work / "full",
                prefer_matlab=True,
            )
            self.assertEqual(report.readiness, MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY)
            self.assertEqual(report.analysis_source, "matlab_smoke")


if __name__ == "__main__":
    unittest.main()
