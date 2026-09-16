"""Item 7 capture append auto-persist (SOFTWARE/CONTROLLED fixtures only)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.snapshot import snapshot_v1_to_dict  # noqa: E402
from market_platform_foundation.intelligence.production.corpus_persistence import (  # noqa: E402
    load_governed_intelligence_repository,
)
from market_platform_foundation.intelligence.production.emitter import emit_production_forecast  # noqa: E402
from market_platform_foundation.intelligence.production.item7_opend_capture_persist import (  # noqa: E402
    DISPOSITION_PERSISTED,
    DISPOSITION_REFUSED,
    GOVERNED_INTELLIGENCE_JSONL,
    REFUSAL_NOT_LAWFUL_SNAPSHOT_BBO,
    is_lawful_persistable_snapshot_bbo_envelope,
    persist_lawful_opend_capture_append,
)
from market_platform_foundation.intelligence.production.item7_opend_capture_writer import (  # noqa: E402
    CANONICAL_CAPTURE_FILENAME,
    DISPOSITION_APPENDED,
    append_vendor_snapshot_capture,
)
from market_platform_foundation.market_data.capture import CAPTURE_SCHEMA_VERSION  # noqa: E402
from market_platform_foundation.market_data.moomoo_snapshot_bbo import (  # noqa: E402
    BboClocks,
    SNAPSHOT_BBO_CAPABILITY,
    build_capture_envelope_from_vendor_snapshot,
)
from market_platform_foundation.strategy.path_a_production_emit import (  # noqa: E402
    persist_path_a_production_contributor,
)
from tests.intelligence.test_item7_production_readiness import (  # noqa: E402
    Item7ProductionReadinessTests,
)
from tests.intelligence.test_item7_p0_anchor import (  # noqa: E402
    _bbo_clocks,
    _snapshot_bbo_envelope,
    _trade_tick_line,
)
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
    _write_jsonl,
)
from tests.intelligence.test_path_a_production_emit import (  # noqa: E402
    PATH_A_HORIZON,
    PATH_A_TARGET,
    T,
    _emit_signals,
    _emit_snapshot,
)

def _vendor_row(**overrides: object) -> dict:
    base = {
        "code": "US.AAPL",
        "last_price": 190.1,
        "update_time": "2026-09-12 15:59:00.000",
        "bid_price": 190.0,
        "ask_price": 190.2,
        "bid_vol": 100,
        "ask_vol": 200,
        "sec_status": "NORMAL",
    }
    base.update(overrides)
    return base


class Item7OpendCapturePersistTests(unittest.TestCase):
    _env_keys = ("IMP_STATE_DIR",)

    def setUp(self) -> None:
        self._saved = {key: os.environ.get(key) for key in self._env_keys}
        self._readiness = Item7ProductionReadinessTests()
        self._readiness.setUp()
        self.contributors = self._readiness.contributors

    def tearDown(self) -> None:
        self._readiness.tearDown()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_lawful_envelope_gate_requires_bbo_valid(self) -> None:
        mapping = build_capture_envelope_from_vendor_snapshot(_vendor_row(), clocks=_bbo_clocks(), sequence=1)
        assert mapping.envelope is not None
        self.assertTrue(is_lawful_persistable_snapshot_bbo_envelope(mapping.envelope))
        invalid = {"capability": SNAPSHOT_BBO_CAPABILITY, "quality_flags": ["BBO_MISSING_ASK"]}
        self.assertFalse(is_lawful_persistable_snapshot_bbo_envelope(invalid))

    def test_auto_persist_p0_refusal_writes_event_not_ledger(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self._readiness.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="paper",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / CANONICAL_CAPTURE_FILENAME
            capture.parent.mkdir(parents=True, exist_ok=True)
            jsonl = root / GOVERNED_INTELLIGENCE_JSONL
            jsonl.write_text(
                json.dumps(
                    {"record_type": "snapshot", "payload": snapshot_v1_to_dict(_emit_snapshot())},
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            result = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_bbo_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=True,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                register_ledger=True,
            )
            self.assertEqual(result.disposition, DISPOSITION_APPENDED)
            assert result.auto_persist is not None
            self.assertEqual(result.auto_persist["disposition"], DISPOSITION_PERSISTED)
            self.assertEqual(result.auto_persist.get("ledger_registered"), 0)
            rows = [
                json.loads(line)
                for line in jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            record_types = {str(row.get("record_type")) for row in rows}
            self.assertIn("event", record_types)
            self.assertNotIn("prediction_ledger_entry", record_types)

    def test_capture_append_auto_persists_event_to_intelligence_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / CANONICAL_CAPTURE_FILENAME
            capture.parent.mkdir(parents=True, exist_ok=True)
            result = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_bbo_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=True,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                register_ledger=False,
            )
            self.assertEqual(result.disposition, DISPOSITION_APPENDED)
            self.assertIsNotNone(result.auto_persist)
            assert result.auto_persist is not None
            self.assertEqual(result.auto_persist["disposition"], DISPOSITION_PERSISTED)
            jsonl = root / GOVERNED_INTELLIGENCE_JSONL
            self.assertTrue(jsonl.is_file())
            lines = [line for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["record_type"], "event")
            loaded, report = load_governed_intelligence_repository(persistence_root=root)
            self.assertEqual(report.snapshots, 0)
            stores = getattr(loaded, "_stores", {})
            self.assertEqual(len(stores.get("events") or {}), 1)

    def test_auto_persist_skipped_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / CANONICAL_CAPTURE_FILENAME
            result = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_bbo_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            self.assertIsNone(result.auto_persist)
            self.assertFalse((root / GOVERNED_INTELLIGENCE_JSONL).exists())

    def test_invalid_bbo_never_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / CANONICAL_CAPTURE_FILENAME
            result = append_vendor_snapshot_capture(
                _vendor_row(bid_price=None, ask_price=None),
                clocks=_bbo_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=True,
            )
            self.assertEqual(result.disposition, "REFUSED")
            self.assertIsNone(result.auto_persist)

    def test_full_path_registers_ledger_when_trade_and_contributor_present(self) -> None:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self._readiness.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=T,
        )
        assert emitted.forecast is not None
        persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="paper",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / CANONICAL_CAPTURE_FILENAME
            capture.parent.mkdir(parents=True, exist_ok=True)
            _write_jsonl(
                capture,
                [
                    _snapshot_bbo_envelope(sequence=1),
                    _trade_tick_line(),
                ],
            )
            jsonl = root / GOVERNED_INTELLIGENCE_JSONL
            jsonl.write_text(
                json.dumps(
                    {"record_type": "snapshot", "payload": snapshot_v1_to_dict(_emit_snapshot())},
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            persist = persist_lawful_opend_capture_append(
                _snapshot_bbo_envelope(sequence=1),
                capture_path=capture,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                persistence_root=root,
            )
            self.assertEqual(persist.disposition, DISPOSITION_PERSISTED)
            self.assertGreaterEqual(persist.events_persisted, 1)
            rows = [
                json.loads(line)
                for line in jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            record_types = {str(row.get("record_type")) for row in rows}
            self.assertIn("event", record_types)
            self.assertIn("prediction_ledger_entry", record_types)
            blob = json.dumps(persist.to_dict())
            self.assertNotIn("ITEM7_COMPLETE", blob)
            self.assertNotIn("GOVERNED_ROW_CAPTURED", blob)

    def test_persist_refuses_non_lawful_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refused = persist_lawful_opend_capture_append(
                {"capability": SNAPSHOT_BBO_CAPABILITY, "quality_flags": []},
                persistence_root=root,
            )
            self.assertEqual(refused.disposition, DISPOSITION_REFUSED)
            self.assertEqual(refused.refusal_reason, REFUSAL_NOT_LAWFUL_SNAPSHOT_BBO)


if __name__ == "__main__":
    unittest.main()
