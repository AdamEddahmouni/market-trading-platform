"""Item 7 Lane D production forecast progression diagnostics."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (  # noqa: E402
    materialize_opend_capture_jsonl,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.production.progression import (  # noqa: E402
    ITEM7_STAGE_ORDER,
    ITEM7_STATUS_PARTIAL,
    build_item7_progression_report,
)
from tests.intelligence.outcome_fixtures import baseline_control_forecast  # noqa: E402
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
    _quote_line,
    _write_jsonl,
)

class Item7ProductionForecastProgressionTests(unittest.TestCase):
    def test_lawful_quote_fails_at_production_forecast_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            report = build_item7_progression_report(
                repository=repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                capture_path=path,
            )
            self.assertEqual(report.item7_status, ITEM7_STATUS_PARTIAL)
            self.assertTrue(report.stage_vector.raw)
            self.assertTrue(report.stage_vector.normalized)
            self.assertTrue(report.stage_vector.tape_eligible)
            self.assertTrue(report.stage_vector.grid)
            self.assertFalse(report.stage_vector.production_forecast_available)
            self.assertEqual(report.first_failing_stage, "production_forecast_available")
            payload = report.to_dict()
            self.assertEqual(set(payload["stage_vector"].keys()), set(ITEM7_STAGE_ORDER))
            self.assertEqual(payload["item7_status"], ITEM7_STATUS_PARTIAL)

    def test_bound_control_forecast_reaches_ledger_not_production_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            forecast = baseline_control_forecast(repo, anchor_price=190.1)
            partial = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            candidate_id = partial.candidates[0].candidate_id
            report = build_item7_progression_report(
                repository=repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                capture_path=path,
                forecast_bindings={candidate_id: forecast.forecast_id},
                materialize_capture=True,
            )
            self.assertFalse(report.stage_vector.production_forecast_available)
            self.assertEqual(report.first_failing_stage, "production_forecast_available")
            self.assertTrue(report.stage_vector.forecast_bound)
            self.assertTrue(report.stage_vector.ledger)
            self.assertGreaterEqual(report.counts.pending, 1)

    def test_depth_envelope_fails_at_tape_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            row = _quote_line(capability="US_EQUITY_DEPTH", sequence=2)
            _write_jsonl(path, [row])
            repo = InMemoryIntelligenceRepository()
            report = build_item7_progression_report(
                repository=repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                capture_path=path,
            )
            self.assertTrue(report.stage_vector.raw)
            self.assertTrue(report.stage_vector.normalized)
            self.assertFalse(report.stage_vector.tape_eligible)
            self.assertEqual(report.first_failing_stage, "tape_eligible")

    def test_readable_summary_never_claims_item7_complete(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = build_item7_progression_report(
            repository=repo,
            as_of_ns=AS_OF,
            session_start_ns=SESSION_START,
        )
        self.assertEqual(report.item7_status, ITEM7_STATUS_PARTIAL)
        self.assertNotIn("ITEM7_COMPLETE", report.readable_summary().upper())


if __name__ == "__main__":
    unittest.main()
