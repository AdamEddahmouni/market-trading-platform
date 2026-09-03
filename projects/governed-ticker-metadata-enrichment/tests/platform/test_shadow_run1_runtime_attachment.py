import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime

# Mirrors the admitted US_EQUITY_TICKS record from
# tests/fixtures/market_data/moomoo/captured-aapl.jsonl (admission drops
# unknown providers, so the fixture reuses an already-admitted shape).
ADMITTED_TICK = {
    "available_time_ns": 1200,
    "capability": "US_EQUITY_TICKS",
    "clocks": {
        "available_time_ns": 1200,
        "event_time_ns": 1150,
        "ingested_time_ns": 1300,
        "provider_time_ns": 1150,
        "received_time_ns": 1200,
    },
    "instrument_id": "AAPL",
    "lifecycle": "CAPTURED",
    "provider": "moomoo",
    "provider_symbol": "US.AAPL",
    "quality_flags": [],
    "raw_payload": {
        "code": "US.AAPL",
        "price": 190.12,
        "sequence": 11,
        "ticker_direction": "BUY",
        "time": "2026-08-19 16:01:02",
        "turnover": 1901.2,
        "type": "NORMAL",
        "volume": 10,
    },
    "schema_version": "market_data.provider_envelope/1.0.0",
    "sequence": 11,
}


class AttachmentTests(unittest.TestCase):
    def test_recorder_defaults_to_none_and_admission_survives_without_it(self):
        rt = LiveObservationalRuntime()
        self.assertIsNone(getattr(rt, "shadow_recorder", None))
        result = rt.ingest_record(ADMITTED_TICK, wall_now_ns=250)
        self.assertIsInstance(result, dict)
        health = rt.health_payload()
        self.assertFalse(health.get("shadow", {}).get("shadow_recording_enabled", False))

    def test_attach_default_recorder_returns_none_when_no_open_run(self):
        from market_platform_foundation.shadow.recording import attach_default_recorder

        rt = LiveObservationalRuntime()
        with tempfile.TemporaryDirectory() as tmp:
            # Point the resolver at an empty store directory via monkeypatched path.
            import market_platform_foundation.shadow.recording as rec

            original = rec.default_experiment_store_path
            rec.default_experiment_store_path = lambda: Path(tmp) / "exp.sqlite3"
            try:
                with mock.patch.dict(os.environ, {"IMP_SHADOW_RECORDING": "1"}):
                    self.assertIsNone(attach_default_recorder(rt))
            finally:
                rec.default_experiment_store_path = original
        self.assertIsNone(rt.shadow_recorder)


if __name__ == "__main__":
    unittest.main()
