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
from market_platform_foundation.platform.artifact_path_resolver import (  # noqa: E402
    ITEM9_COLLECTOR_LOG_ENV,
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

    def test_collector_log_wires_gap_analysis(self) -> None:
        log_body = """
09/18/2026 12:10:31 START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031
09/18/2026 13:54:11 END item9-prospective-20260918-epoch-fed2d9f7-aapl-121031 exit=1
""".strip()
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            log_path = imp_root / "collector.log"
            log_path.write_text(log_body + "\n", encoding="utf-8")
            report = build_runtime_resilience_diagnostic(
                imp_root,
                env={ITEM9_COLLECTOR_LOG_ENV: str(log_path)},
                active_collector_probe=lambda: (False, []),
            )
        cycle = report["expected_cycle"]
        self.assertIsInstance(cycle["collector_log_gaps"], dict)
        self.assertEqual(cycle["collector_log_gaps"]["started_epoch_count"], 1)
        self.assertEqual(cycle["collector_log_source"]["availability"], "AVAILABLE")


if __name__ == "__main__":
    unittest.main()
