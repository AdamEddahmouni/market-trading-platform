"""Item 7 — SNAPSHOT_BBO capture + lawful TRADE P0 anchor → BUILD 15 ledger (controlled)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ForecastV1,
    IntelligenceScope,
    SnapshotV1,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.production.emitter import emit_production_forecast  # noqa: E402
from market_platform_foundation.intelligence.production.item7_p0_anchor import (  # noqa: E402
    REFUSAL_FORECAST_SNAPSHOT_MISSING,
    REFUSAL_P0_TRADE_MISSING,
    REFUSAL_TARGET_INSTRUMENT_NOT_IN_SCOPE,
    materialize_item7_lawful_capture_ledger,
    p0_anchor_refusal_reasons,
    preflight_p0_anchor_for_forecast,
)
from market_platform_foundation.market_data.capture import CAPTURE_SCHEMA_VERSION  # noqa: E402
from market_platform_foundation.market_data.moomoo_snapshot_bbo import (  # noqa: E402
    BboClocks,
    build_capture_envelope_from_vendor_snapshot,
)
from market_platform_foundation.strategy.path_a_production_emit import (  # noqa: E402
    persist_path_a_production_contributor,
)
from tests.intelligence.test_item7_production_readiness import (  # noqa: E402
    Item7ProductionReadinessTests,
)
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
    _quote_line,
    _write_jsonl,
)
from tests.intelligence.test_path_a_production_emit import (  # noqa: E402
    EMIT_SNAPSHOT_ID,
    PATH_A_HORIZON,
    PATH_A_TARGET,
    QUALITY,
    T,
    _emit_signals,
    _emit_snapshot,
)
from tests.intelligence.test_baseline_fixtures import T as DECISION_T  # noqa: E402

FIVE_SEC = 5 * 1_000_000_000


def _vendor_row() -> dict:
    return {
        "code": "US.AAPL",
        "last_price": 190.1,
        "update_time": "2026-09-12 15:59:00.000",
        "bid_price": 190.0,
        "ask_price": 190.2,
        "bid_vol": 100,
        "ask_vol": 200,
        "sec_status": "NORMAL",
    }


def _bbo_clocks() -> BboClocks:
    received = DECISION_T + FIVE_SEC
    return BboClocks(
        request_time_ns=DECISION_T,
        provider_time_ns=DECISION_T,
        receive_time_ns=received,
        available_time_ns=received,
    )


def _snapshot_bbo_envelope(**overrides: object) -> dict:
    mapping = build_capture_envelope_from_vendor_snapshot(
        _vendor_row(),
        clocks=_bbo_clocks(),
        sequence=int(overrides.pop("sequence", 1)),
    )
    assert mapping.envelope is not None
    envelope = dict(mapping.envelope)
    envelope["instrument_id"] = "AAPL"
    envelope["provider_symbol"] = "US.AAPL"
    envelope.update(overrides)
    return envelope


def _trade_tick_line(**overrides: object) -> dict:
    received = DECISION_T + FIVE_SEC
    available = DECISION_T
    row = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "provider": "moomoo.opend.observational",
        "capability": "US_EQUITY_TICKS",
        "provider_symbol": "US.AAPL",
        "instrument_id": "AAPL",
        "lifecycle": "CAPTURED",
        "sequence": 11,
        "clocks": {
            "event_time_ns": DECISION_T,
            "provider_time_ns": DECISION_T,
            "available_time_ns": available,
            "received_time_ns": received,
            "ingested_time_ns": received,
        },
        "quality_flags": [],
        "raw_payload": {
            "code": "US.AAPL",
            "price": 190.1,
            "sequence": 11,
            "ticker_direction": "BUY",
            "time": "2026-09-12 15:59:00.000",
            "turnover": 1901.0,
            "type": "NORMAL",
            "volume": 10,
        },
    }
    row.update(overrides)
    return row


def _aapl_quote_line(**kwargs: object) -> dict:
    row = _quote_line(**kwargs)
    row["instrument_id"] = "AAPL"
    row["provider_symbol"] = "US.AAPL"
    return row


class Item7P0AnchorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._readiness = Item7ProductionReadinessTests()
        self._readiness.setUp()
        self.contributors = self._readiness.contributors
        self.model = self._readiness.model

    def tearDown(self) -> None:
        self._readiness.tearDown()

    def _persist_lawful_contributor(self) -> ForecastV1:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
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
        return emitted.forecast

    def _seed_snapshot_only(self, repo: InMemoryIntelligenceRepository) -> None:
        repo.put_snapshot(_emit_snapshot())

    def test_snapshot_bbo_plus_trade_tick_registers_ledger(self) -> None:
        forecast = self._persist_lawful_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(
                path,
                [
                    _snapshot_bbo_envelope(sequence=1),
                    _trade_tick_line(),
                ],
            )
            repo = InMemoryIntelligenceRepository()
            self._seed_snapshot_only(repo)
            result = materialize_item7_lawful_capture_ledger(
                (path,),
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                use_production_ingress=False,
            )
            self.assertEqual(result.ledger_registered, 1)
            self.assertEqual(result.candidates[0].forecast_id, str(forecast.forecast_id))
            self.assertIsNotNone(result.candidates[0].ledger_entry_id)
            self.assertNotIn(REFUSAL_P0_TRADE_MISSING, result.refusal_reasons)

    def test_snapshot_bbo_without_trade_refuses_p0(self) -> None:
        self._persist_lawful_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_snapshot_bbo_envelope()])
            repo = InMemoryIntelligenceRepository()
            self._seed_snapshot_only(repo)
            result = materialize_item7_lawful_capture_ledger(
                (path,),
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                use_production_ingress=False,
            )
            self.assertEqual(result.ledger_registered, 0)
            self.assertIn(REFUSAL_P0_TRADE_MISSING, result.refusal_reasons)

    def test_preflight_missing_snapshot_refuses(self) -> None:
        forecast = self._persist_lawful_contributor()
        repo = InMemoryIntelligenceRepository()
        repo.put_forecast(forecast)
        stored = repo.get_forecast(str(forecast.forecast_id))
        assert stored is not None
        preflight = preflight_p0_anchor_for_forecast(stored, repo)
        self.assertEqual(preflight.refusal_reasons, (REFUSAL_FORECAST_SNAPSHOT_MISSING,))

    def test_target_instrument_not_in_scope_refuses(self) -> None:
        forecast = self._persist_lawful_contributor()
        repo = InMemoryIntelligenceRepository()
        repo.put_forecast(forecast)
        repo.put_snapshot(
            SnapshotV1(
                snapshot_id=EMIT_SNAPSHOT_ID,
                schema_version="1",
                decision_time_ns=T,
                scope=IntelligenceScope(instrument_ids=("NVDA",)),
                quality=QUALITY,
            )
        )
        stored = repo.get_forecast(str(forecast.forecast_id))
        assert stored is not None
        reasons = p0_anchor_refusal_reasons(stored, repo)
        self.assertIn(REFUSAL_TARGET_INSTRUMENT_NOT_IN_SCOPE, reasons)

    def test_lawful_quote_capture_still_refuses_without_trade(self) -> None:
        self._persist_lawful_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_aapl_quote_line()])
            repo = InMemoryIntelligenceRepository()
            self._seed_snapshot_only(repo)
            result = materialize_item7_lawful_capture_ledger(
                (path,),
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                use_production_ingress=False,
            )
            self.assertEqual(result.ledger_registered, 0)
            self.assertIn(REFUSAL_P0_TRADE_MISSING, result.refusal_reasons)


if __name__ == "__main__":
    unittest.main()
