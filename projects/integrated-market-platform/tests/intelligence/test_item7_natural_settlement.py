"""Item 7 natural settlement / maturity (SOFTWARE/CONTROLLED fixtures only)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import OutcomeResolutionStatus  # noqa: E402
from market_platform_foundation.intelligence.contracts.snapshot import snapshot_v1_to_dict  # noqa: E402
from market_platform_foundation.intelligence.outcomes.types import (  # noqa: E402
    SettlementResult,
    UnlabelableReason,
)
from market_platform_foundation.intelligence.production.identity import PATH_A_HORIZON_NS  # noqa: E402
from market_platform_foundation.intelligence.production.item7_natural_settlement import (  # noqa: E402
    exercise_item7_natural_settlement,
)
from market_platform_foundation.intelligence.production.item7_opend_capture_persist import (  # noqa: E402
    DISPOSITION_PERSISTED,
    GOVERNED_INTELLIGENCE_JSONL,
    persist_lawful_opend_capture_append,
)
from market_platform_foundation.intelligence.production.emitter import emit_production_forecast  # noqa: E402
from market_platform_foundation.strategy.path_a_production_emit import (  # noqa: E402
    persist_path_a_production_contributor,
)
from tests.intelligence.test_item7_p0_anchor import (  # noqa: E402
    _snapshot_bbo_envelope,
    _trade_tick_line,
)
from tests.intelligence.test_item7_production_readiness import (  # noqa: E402
    Item7ProductionReadinessTests,
)
from tests.intelligence.test_opend_capture_ledger_bridge import _write_jsonl  # noqa: E402
from tests.intelligence.test_path_a_production_emit import (  # noqa: E402
    PATH_A_HORIZON,
    PATH_A_TARGET,
    T,
    _emit_signals,
    _emit_snapshot,
)

FIVE_SEC = 5 * 1_000_000_000
ONE_MIN = 60 * 1_000_000_000
SESSION_START = T - FIVE_SEC
EARLY_AS_OF = T + FIVE_SEC
MATURITY_AS_OF = T + PATH_A_HORIZON_NS + ONE_MIN


def _terminal_trade_line(*, price: float = 191.0) -> dict:
    target_time = T + PATH_A_HORIZON_NS
    received = target_time + FIVE_SEC
    return _trade_tick_line(
        sequence=12,
        clocks={
            "event_time_ns": target_time,
            "provider_time_ns": target_time,
            "available_time_ns": target_time,
            "received_time_ns": received,
            "ingested_time_ns": received,
        },
        raw_payload={
            "code": "US.AAPL",
            "price": price,
            "sequence": 12,
            "ticker_direction": "BUY",
            "time": "2026-09-12 16:04:00.000",
            "turnover": price * 10,
            "type": "NORMAL",
            "volume": 10,
        },
    )


class Item7NaturalSettlementTests(unittest.TestCase):
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

    def _seed_contributor(self) -> None:
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

    def test_before_maturity_reports_not_due_without_outcome(self) -> None:
        self._seed_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / "opend_capture.jsonl"
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
            result = persist_lawful_opend_capture_append(
                _snapshot_bbo_envelope(sequence=1),
                capture_path=capture,
                as_of_ns=EARLY_AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                persistence_root=root,
            )
            self.assertEqual(result.disposition, DISPOSITION_PERSISTED)
            assert result.natural_settlement is not None
            self.assertEqual(result.natural_settlement["not_due"], 1)
            self.assertEqual(result.natural_settlement["settled"], 0)
            record_types = {
                str(json.loads(line).get("record_type"))
                for line in jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
            self.assertNotIn("outcome", record_types)

    def test_at_maturity_without_terminal_trade_is_unlabelable(self) -> None:
        self._seed_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / "opend_capture.jsonl"
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
            result = persist_lawful_opend_capture_append(
                _snapshot_bbo_envelope(sequence=1),
                capture_path=capture,
                as_of_ns=MATURITY_AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                persistence_root=root,
            )
            assert result.natural_settlement is not None
            self.assertEqual(result.natural_settlement["settled"], 0)
            self.assertEqual(result.natural_settlement["due_unlabelable"], 1)
            reasons = result.natural_settlement["refusal_reasons"]
            self.assertIn(UnlabelableReason.NO_TARGET_OBSERVATION.value, reasons)

    def test_terminal_trade_at_maturity_settles_naturally(self) -> None:
        self._seed_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / "opend_capture.jsonl"
            capture.parent.mkdir(parents=True, exist_ok=True)
            _write_jsonl(
                capture,
                [
                    _snapshot_bbo_envelope(sequence=1),
                    _trade_tick_line(),
                    _terminal_trade_line(price=191.5),
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
            result = persist_lawful_opend_capture_append(
                _snapshot_bbo_envelope(sequence=1),
                capture_path=capture,
                as_of_ns=MATURITY_AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                persistence_root=root,
            )
            assert result.natural_settlement is not None
            self.assertEqual(result.natural_settlement["settled"], 1)
            self.assertEqual(result.natural_settlement["outcomes_appended"], 1)
            rows = [
                json.loads(line)
                for line in jsonl.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            outcomes = [row for row in rows if row.get("record_type") == "outcome"]
            self.assertEqual(len(outcomes), 1)
            payload = outcomes[0]["payload"]
            self.assertEqual(payload["resolution_status"], OutcomeResolutionStatus.SETTLED.value)
            blob = json.dumps(result.to_dict())
            self.assertNotIn("EMPIRICAL", blob)
            self.assertNotIn("CALIBRATED", blob)

    def test_late_terminal_append_settles_pending_ledger(self) -> None:
        self._seed_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["IMP_STATE_DIR"] = str(root)
            capture = root / "captures" / "opend_capture.jsonl"
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
            first = persist_lawful_opend_capture_append(
                _snapshot_bbo_envelope(sequence=1),
                capture_path=capture,
                as_of_ns=EARLY_AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                persistence_root=root,
            )
            assert first.natural_settlement is not None
            self.assertEqual(first.natural_settlement["not_due"], 1)

            with capture.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    json.dumps(_terminal_trade_line(price=192.0), sort_keys=True, separators=(",", ":"))
                    + "\n"
                )
            second = persist_lawful_opend_capture_append(
                _snapshot_bbo_envelope(sequence=2),
                capture_path=capture,
                as_of_ns=MATURITY_AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                persistence_root=root,
            )
            assert second.natural_settlement is not None
            self.assertEqual(second.natural_settlement["settled"], 1)
            self.assertEqual(second.natural_settlement["outcomes_appended"], 1)

    def test_exercise_helper_never_settles_before_cutoff(self) -> None:
        from market_platform_foundation.intelligence.persistence import (  # noqa: E402
            InMemoryIntelligenceRepository,
        )
        from market_platform_foundation.intelligence.outcomes import PredictionLedgerService  # noqa: E402
        from tests.intelligence.outcome_fixtures import (  # noqa: E402
            baseline_control_forecast,
            cutoff_for,
            seed_terminal_trade,
            target_time_for,
        )

        repo = InMemoryIntelligenceRepository()
        forecast = baseline_control_forecast(repo)
        entry = PredictionLedgerService(repo).register_forecast(forecast, now_ns=T)
        assert not isinstance(entry, SettlementResult)
        target = target_time_for(forecast)
        seed_terminal_trade(repo, price=110.0, event_time_ns=target)
        summary = exercise_item7_natural_settlement(
            repo,
            now_ns=cutoff_for(forecast) - 1,
        )
        self.assertEqual(summary.not_due, 1)
        self.assertEqual(summary.settled, 0)
        self.assertEqual(repo.get_outcomes_by_forecast(forecast.forecast_id), ())


if __name__ == "__main__":
    unittest.main()
