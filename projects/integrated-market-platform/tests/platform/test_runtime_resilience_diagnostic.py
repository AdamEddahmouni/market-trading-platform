"""Runtime resilience diagnostic snapshot (Lane B backend contract)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.operations.runtime_resilience_diagnostic import (  # noqa: E402
    build_runtime_resilience_diagnostic,
)


class RuntimeResilienceDiagnosticTests(unittest.TestCase):
    def test_build_diagnostic_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            report = build_runtime_resilience_diagnostic(
                imp_root,
                active_collector_probe=lambda: (False, []),
            )
        self.assertEqual(report["artifact_kind"], "imp_runtime_resilience_diagnostic")
        self.assertIn("provider_connectivity", report)
        self.assertIn("runtime_identity", report)
        self.assertIn("expected_cycle", report)
        self.assertIn("readiness_vs_liveness", report)
        self.assertFalse(report["collector_process"]["active_collector_detected"])


if __name__ == "__main__":
    unittest.main()
