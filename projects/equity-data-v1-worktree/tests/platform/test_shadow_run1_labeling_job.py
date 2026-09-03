import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore
from market_platform_foundation.shadow.labeling_job import LabelingConfig, label_due
from market_platform_foundation.shadow.predictor import FrozenPredictorConfig
from market_platform_foundation.shadow.recording import ShadowPredictionRecorder
from market_platform_foundation.shadow.runs import open_shadow_run
from market_platform_foundation.shadow.store import ShadowStore

NS = 1_000_000_000
ET = ZoneInfo("America/New_York")


def _iso(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=ET).timestamp() * NS)


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.capture_dir = root / "captures"
        self.capture_dir.mkdir()
        self.open_ns = _iso(2026, 8, 24, 9, 30)
        self.close_ns = _iso(2026, 8, 24, 16, 0)
        self.shadow = ShadowStore(root / "shadow.sqlite3")
        self.exp = ShadowExperimentStore(root / "exp.sqlite3")
        manifest, _ = open_shadow_run(
            self.shadow,
            strategy_version="shadow-run1/integrity-proof",
            prediction_version="nss-direction-v1",
            universe=("BIYA",),
            data_window_refs=({"kind": "live_observation", "capture_id": "CAP1"},),
            train_window_end_ns=self.open_ns,
            eval_window_start_ns=self.open_ns,
            eval_window_end_ns=self.close_ns + 7 * 86400 * NS,
            created_at_ns=self.open_ns - 60 * NS,
            config={},
        )
        self.manifest = manifest
        self.exp.ensure_run(manifest.run_id, "{}", manifest.manifest_hash, self.open_ns)
        self.exp.append_event(manifest.run_id, "OPEN", self.open_ns)
        self.recorder = ShadowPredictionRecorder(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=manifest,
            config=FrozenPredictorConfig(),
            session_dates=["2026-08-24"],
            capture_id="CAP1",
            clock=lambda: self.open_ns,
        )
        # Tape ENDS at the decision so the newest admitted trade is fresh
        # (stale_input_seconds=60) and the window holds >= minimum_trades.
        self.decision_s = self.open_ns // NS + 120  # 09:32 -> target 10:02
        tape = [
            {
                "admission": "ADMITTED_DISPLAY",
                "aggressor_provenance": "INFERRED",
                "aggressor_side": "BUY" if i < 12 else "SELL",
                "available_time_ns": (self.decision_s - 11 + i + 1) * NS,
                "event_time_ns": (self.decision_s - 11 + i) * NS,
                "price": 10.0,
                "provider": "moomoo",
                "quality": "PASS",
                "quantity": 10.0,
                "trade_id": f"T{i}",
            }
            for i in range(12)
        ]
        self.recorder.on_admitted(
            type("S", (), {"trades_for": lambda self_, _: tape})(),
            {"capability": "TICK", "instrument_id": "BIYA", "event_time": self.decision_s * NS},
            {},
        )
        decision = list(self.exp.iter_decisions(manifest.run_id))[0]
        self.assertEqual(decision["outcome"], "PREDICTED")
        self.prediction = self.shadow.get_prediction(decision["prediction_id"])

    def tearDown(self):
        self.shadow.close()
        self.exp.close()
        self.tmp.cleanup()

    def _write_capture(self, name, rows):
        path = self.capture_dir / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        return path

    @staticmethod
    def _tick(event_s, price, available_s=None):
        # Causality requires available_time_ns STRICTLY AFTER decision+horizon
        # (= target); default received to event+1s while keeping event_time
        # inside the tolerance window.
        received_s = available_s if available_s is not None else event_s + 1
        return {
            "capability": "TICK",
            "instrument_id": "BIYA",
            "clocks": {"received_time_ns": received_s * NS},
            "raw_payload": {"last_price": price, "quantity": 1, "event_time": event_s * NS},
            "provider": "moomoo",
            "sequence": None,
            "provider_symbol": "BIYA",
            "lifecycle": "CAPTURED",
            "quality_flags": [],
            "schema_version": "market_data.provider_envelope/1.0.0",
        }

    def test_labels_up_when_p30_rises(self):
        target_s = self.decision_s + 1800
        path = self._write_capture("cap.jsonl", [Harness._tick(target_s, 11.0)])
        summary = label_due(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=self.manifest,
            capture_paths=[path],
            now_ns=(target_s + 400) * NS,
            config=LabelingConfig(),
        )
        self.assertEqual(summary["labeled"], 1)
        label = self.shadow.get_label_for_run_prediction(
            self.manifest.run_id, self.prediction.prediction_id
        )
        self.assertIsNotNone(label)
        self.assertTrue(label.observed_positive)

    def test_zero_return_annotated_not_labeled(self):
        target_s = self.decision_s + 1800
        path = self._write_capture("cap.jsonl", [Harness._tick(target_s, 10.0)])
        summary = label_due(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=self.manifest,
            capture_paths=[path],
            now_ns=(target_s + 400) * NS,
            config=LabelingConfig(),
        )
        self.assertEqual(summary["zero_return"], 1)
        self.assertIsNone(
            self.shadow.get_label_for_run_prediction(self.manifest.run_id, self.prediction.prediction_id)
        )

    def test_no_trade_in_tolerance_is_unlabelable(self):
        far_s = self.decision_s + 1800 + 900  # beyond tolerance
        path = self._write_capture("cap.jsonl", [Harness._tick(far_s, 11.0)])
        summary = label_due(
            shadow_store=self.shadow,
            experiment_store=self.exp,
            manifest=self.manifest,
            capture_paths=[path],
            now_ns=(far_s + 60) * NS,
            config=LabelingConfig(),
        )
        self.assertEqual(summary["unlabelable"].get("NO_HORIZON_TRADE"), 1)


if __name__ == "__main__":
    unittest.main()
