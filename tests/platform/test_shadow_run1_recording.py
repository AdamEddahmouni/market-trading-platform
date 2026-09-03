import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore
from market_platform_foundation.shadow.predictor import FrozenPredictorConfig
from market_platform_foundation.shadow.recording import ShadowPredictionRecorder
from market_platform_foundation.shadow.runs import open_shadow_run
from market_platform_foundation.shadow.session import build_session_list
from market_platform_foundation.shadow.store import ShadowStore

NS = 1_000_000_000
OPEN_NS = 1787718600 * NS  # 2026-08-24 09:30 ET is 13:30 UTC; exact value not asserted


def _trade(i, event_s, side="BUY", qty=10.0, price=10.0):
    return {
        "admission": "ADMITTED_DISPLAY",
        "aggressor_provenance": "INFERRED",
        "aggressor_side": side,
        "available_time_ns": (event_s + 1) * NS,
        "event_time_ns": event_s * NS,
        "price": price,
        "provider": "moomoo",
        "quality": "PASS",
        "quantity": qty,
        "trade_id": f"T{i}-{event_s}",
    }


class FakeState:
    def __init__(self, tape):
        self._tape = tape

    def trades_for(self, instrument_id):
        return list(self._tape)


class RecorderHarness(unittest.TestCase):
    """Shared fixture: stores + OPEN run + recorder on session date."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.shadow = ShadowStore(root / "shadow.sqlite3")
        self.exp = ShadowExperimentStore(root / "exp.sqlite3")
        self.dates = build_session_list("2026-08-24", 8, frozenset(), frozenset())
        from datetime import datetime
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        open_ns = int(datetime(2026, 8, 24, 9, 30, tzinfo=et).timestamp() * NS)
        close_ns = int(datetime(2026, 8, 24, 16, 0, tzinfo=et).timestamp() * NS)
        self.open_ns = open_ns
        manifest, _ = open_shadow_run(
            self.shadow,
            strategy_version="shadow-run1/integrity-proof",
            prediction_version="nss-direction-v1",
            universe=("BIYA",),
            data_window_refs=({"kind": "live_observation", "capture_id": "CAP1"},),
            train_window_end_ns=open_ns,
            eval_window_start_ns=open_ns,
            eval_window_end_ns=close_ns + 7 * 86400 * NS,
            created_at_ns=open_ns - 60 * NS,
            config={"constants": {"window_seconds": 300}},
        )
        self.manifest = manifest
        self.exp.ensure_run(manifest.run_id, '{"contract": true}', manifest.manifest_hash, open_ns - 60 * NS)
        self.exp.append_event(manifest.run_id, "OPEN", open_ns - 30 * NS)
        self.recorder = ShadowPredictionRecorder(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=manifest,
            config=FrozenPredictorConfig(),
            session_dates=self.dates,
            capture_id="CAP1",
            clock=lambda: open_ns,
        )

    def tearDown(self):
        self.shadow.close()
        self.exp.close()
        self.tmp.cleanup()


class RecordingTests(RecorderHarness):
    def test_first_qualifying_trade_of_bucket_writes_prediction(self):
        # Session opens 09:30; decision at 09:32 with an all-buy window.
        base = self.open_ns // NS
        decision_s = base + 120
        state = FakeState([_trade(i, decision_s - 11 + i) for i in range(12)])
        envelope = {"capability": "TICK", "instrument_id": "BIYA", "event_time": decision_s * NS}
        self.recorder.on_admitted(state, envelope, {})
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "PREDICTED")
        pred = self.shadow.get_prediction(rows[0]["prediction_id"])
        self.assertIsNotNone(pred)
        self.assertAlmostEqual(pred.predicted_probability, 0.9)
        self.assertEqual(pred.instrument_id, "BIYA")
        stats = self.recorder.stats()
        self.assertEqual(stats.predictions_written, 1)

    def test_second_trade_in_same_bucket_is_silent_counter(self):
        base = self.open_ns // NS
        state = FakeState([_trade(i, base + 120 - 19 + i) for i in range(20)])
        for offset in (121, 125):  # same 60s bucket
            self.recorder.on_admitted(
                state,
                {"capability": "TICK", "instrument_id": "BIYA", "event_time": (base + offset) * NS},
                {},
            )
        self.assertEqual(len(list(self.exp.iter_decisions(self.manifest.run_id))), 1)
        self.assertEqual(self.recorder.stats().duplicate_bucket_observations, 1)

    def test_flat_band_writes_model_abstention_row(self):
        base = self.open_ns // NS
        decision_s = base + 120
        tape = [
            _trade(i, decision_s - 13 + i, side="BUY" if i % 2 == 0 else "SELL")
            for i in range(14)
        ]
        self.recorder.on_admitted(
            FakeState(tape),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": decision_s * NS},
            {},
        )
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "ABSTAINED_MODEL")
        self.assertEqual(rows[0]["detail"]["reason"], "FLAT_BAND")
        self.assertEqual(rows[0]["detail"]["decision_time_ns"], decision_s * NS)
        self.assertIsNone(rows[0]["prediction_id"])
        self.assertEqual(self.recorder.stats().model_abstentions, 1)

    def test_late_session_opportunity_is_outside_session_window(self):
        # 15:40 ET: target 16:10 + 5m tolerance crosses 16:00 close.
        base = self.open_ns // NS
        late_s = base + (6 * 60 + 10) * 60 + 30  # ~15:40:30
        tape = [_trade(i, late_s - 11 + i) for i in range(12)]
        self.recorder.on_admitted(
            FakeState(tape),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": late_s * NS},
            {},
        )
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(rows[0]["outcome"], "OUTSIDE_SESSION_WINDOW")

    def test_non_universe_or_non_tick_records_are_ignored(self):
        base = self.open_ns // NS
        self.recorder.on_admitted(
            FakeState([]),
            {"capability": "QUOTE", "instrument_id": "BIYA", "event_time": (base + 120) * NS},
            {},
        )
        self.recorder.on_admitted(
            FakeState([]),
            {"capability": "TICK", "instrument_id": "OTHER", "event_time": (base + 120) * NS},
            {},
        )
        self.assertEqual(list(self.exp.iter_decisions(self.manifest.run_id)), [])

    def test_recorder_failure_never_raises_and_is_logged(self):
        class BrokenState:
            def trades_for(self, instrument_id):
                raise RuntimeError("boom")

        base = self.open_ns // NS
        self.recorder.on_admitted(
            BrokenState(),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": (base + 120) * NS},
            {},
        )
        stats = self.recorder.stats()
        self.assertGreaterEqual(stats.errors_total, 1)
        self.assertEqual(stats.consecutive_errors, 1)
        errors = self.exp.recorder_errors(self.manifest.run_id)
        self.assertEqual(errors[-1]["error_code"], "RECORDER_EXCEPTION")

    def test_live_admission_envelope_uses_event_type_for_ticks(self):
        base = self.open_ns // NS
        decision_s = base + 120
        state = FakeState([_trade(i, decision_s - 11 + i) for i in range(12)])
        envelope = {
            "event_type": "US_EQUITY_TICKS",
            "instrument_id": "BIYA",
            "event_time": decision_s * NS,
        }
        self.recorder.on_admitted(state, envelope, {})
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "PREDICTED")

    def test_stale_input_abstention_records_decision_time_provenance(self):
        base = self.open_ns // NS
        decision_s = base + 120
        self.recorder.on_admitted(
            FakeState([]),
            {
                "capability": "TICK",
                "instrument_id": "BIYA",
                "event_time": decision_s * NS,
                "available_time": (decision_s + 1) * NS,
            },
            {},
        )
        rows = list(self.exp.iter_decisions(self.manifest.run_id))
        self.assertEqual(len(rows), 1)
        detail = rows[0]["detail"]
        self.assertEqual(detail["reason"], "STALE_INPUT")
        self.assertEqual(detail["decision_time_ns"], decision_s * NS)
        self.assertEqual(detail["available_time_ns"], (decision_s + 1) * NS)

    def test_health_exposes_required_fields(self):
        health = self.recorder.health()
        for key in (
            "shadow_recording_enabled", "shadow_run_id", "shadow_run_state",
            "shadow_last_success_ns", "shadow_last_error_code", "shadow_error_count",
            "shadow_consecutive_errors", "shadow_predictions_written",
            "shadow_abstentions_written", "shadow_duplicate_bucket_observations",
        ):
            self.assertIn(key, health)


if __name__ == "__main__":
    unittest.main()
