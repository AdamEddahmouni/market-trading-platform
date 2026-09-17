"""Lane D: historical development fixture → features → risk simulation (development only)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.e2e_demo import (  # noqa: E402
    DEMO_EVIDENCE_CLASS,
    enrich_normalized_bar_for_replay,
    run_historical_development_e2e_demo,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
)
from market_platform_foundation.paper.calibration.dual_corpus.discovery import (  # noqa: E402
    is_historical_development_storage_path,
)

FIXTURE = ROOT / "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
SESSION_DAY = "2026-09-15"


class HistoricalDevelopmentE2eDemoTests(unittest.TestCase):
    def test_fixture_pipeline_produces_reproducible_fingerprints(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            corpus_root = Path(tmp) / "artifacts" / "historical-rth-development"
            demo_root = Path(tmp) / "artifacts" / "historical-development"
            build = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=SESSION_DAY,
                end_date=SESSION_DAY,
                artifact_root=corpus_root,
                fixture_only=True,
            )
            self.assertTrue(build.ok)
            e2e_a = run_historical_development_e2e_demo(
                repository_root=ROOT,
                build=build,
                demo_artifact_root=demo_root,
            )
            e2e_b = run_historical_development_e2e_demo(
                repository_root=ROOT,
                build=build,
                demo_artifact_root=demo_root,
            )
            self.assertTrue(e2e_a.ok)
            self.assertEqual(
                e2e_a.body["result_fingerprint"],
                e2e_b.body["result_fingerprint"],
            )
            self.assertEqual(e2e_a.body["evidence_class"], DEMO_EVIDENCE_CLASS)
            self.assertEqual(
                e2e_a.body["corpus_evidence_authority"],
                CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            )
            self.assertTrue(e2e_a.artifact_path.is_file())
            self.assertTrue(is_historical_development_storage_path(demo_root))

    def test_replay_envelope_uses_historical_ingested_time(self) -> None:
        bar = {
            "available_time": 1_000,
            "bar_payload": {"close": "1", "high": "1", "low": "1", "open": "1", "volume": 1},
            "event_time": 900,
            "event_type": "BAR_OHLCV_1M",
            "instrument_id": "canonical:EQUITY:XNAS:AAPL",
            "normalized_event_id": "evt-1",
        }
        event = enrich_normalized_bar_for_replay(bar, ingest_run_id="RUN-1")
        self.assertEqual(event["historical_ingested_time"], 1_000)
        self.assertNotIn("live_received_time", event)

    def test_demo_cli_prints_governance_and_runs(self) -> None:
        from tools.historical_data.demo_cli import main

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                [
                    "--fixture-path",
                    str(FIXTURE),
                    "--start",
                    SESSION_DAY,
                    "--end",
                    SESSION_DAY,
                ]
            )
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("AUTHORITY: HISTORICAL_DEVELOPMENT", output)
        self.assertIn("PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED", output)
        self.assertIn("CALIBRATION_STATE_CHANGED: NO", output)
        payload = json.loads(output[output.index("{") :])
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["result_fingerprint"])


if __name__ == "__main__":
    unittest.main()
