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
        self.assertEqual(cycle["collector_log_source"]["truncated"], False)
        self.assertEqual(cycle["collector_log_gaps"]["missing_receipt_epochs"][0]["epoch"], "121031")

    def test_missing_log_keeps_gap_analysis_unobserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            report = build_runtime_resilience_diagnostic(
                imp_root,
                env={},
                active_collector_probe=lambda: (False, []),
            )
        source = report["expected_cycle"]["collector_log_source"]
        self.assertEqual(source["availability"], "NOT_OBSERVED")
        self.assertIsNone(report["expected_cycle"]["collector_log_gaps"])

    def test_empty_log_analyzes_zero_epochs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            report = build_runtime_resilience_diagnostic(
                imp_root,
                collector_log_text="",
                active_collector_probe=lambda: (False, []),
            )
        gaps = report["expected_cycle"]["collector_log_gaps"]
        self.assertEqual(gaps["started_epoch_count"], 0)
        self.assertEqual(gaps["missing_receipt_epochs"], [])

    def test_expected_cycle_copies_are_isolated(self) -> None:
        log_body = "START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031\n"
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            report = build_runtime_resilience_diagnostic(
                imp_root,
                collector_log_text=log_body,
                active_collector_probe=lambda: (False, []),
            )
            report["expected_cycle"]["collector_log_gaps"]["hung_epochs_without_end"].append("mutated")
            report["expected_cycle"]["collector_log_source"]["availability"] = "MUTATED"
            again = build_runtime_resilience_diagnostic(
                imp_root,
                collector_log_text=log_body,
                active_collector_probe=lambda: (False, []),
            )
        self.assertNotIn("mutated", again["expected_cycle"]["collector_log_gaps"]["hung_epochs_without_end"])
        self.assertEqual(again["expected_cycle"]["collector_log_source"]["availability"], "CALLER_SUPPLIED")


if __name__ == "__main__":
    unittest.main()
