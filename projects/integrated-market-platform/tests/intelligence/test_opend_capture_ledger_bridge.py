"""OpenD prospective capture JSONL → BUILD 15 ledger bridge (Item 7)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (  # noqa: E402
    derive_capture_ledger_candidate_id,
    materialize_opend_capture_jsonl,
    scan_capture_funnel,
)
from market_platform_foundation.intelligence.outcomes.service import OutcomeSettlementService  # noqa: E402
from market_platform_foundation.intelligence.outcomes.types import SettlementStatus  # noqa: E402
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.market_data.capture import CAPTURE_SCHEMA_VERSION  # noqa: E402
from tests.intelligence.outcome_fixtures import baseline_control_forecast, seed_anchor_trade  # noqa: E402
from tests.intelligence.test_baseline_fixtures import T as DECISION_T  # noqa: E402

FIVE_SEC = 5 * 1_000_000_000
SESSION_START = DECISION_T - FIVE_SEC
AS_OF = DECISION_T + FIVE_SEC


def _quote_line(
    *,
    sequence: int = 1,
    event_time_ns: int = DECISION_T,
    available_time_ns: int = DECISION_T + 1_000_000,
    received_time_ns: int = DECISION_T + FIVE_SEC,
    capability: str = "US_EQUITY_L1",
) -> dict:
    return {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "provider": "moomoo.opend.observational",
        "capability": capability,
        "provider_symbol": "US.NVDA",
        "instrument_id": "NVDA",
        "lifecycle": "CAPTURED",
        "sequence": sequence,
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns,
            "available_time_ns": available_time_ns,
            "received_time_ns": received_time_ns,
            "ingested_time_ns": received_time_ns,
        },
        "quality_flags": [],
        "raw_payload": {
            "bid_price": 190.0,
            "ask_price": 190.2,
            "bid_vol": 100,
            "ask_vol": 200,
            "code": "US.NVDA",
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


class OpendCaptureLedgerBridgeTests(unittest.TestCase):
    def test_lawful_quote_persists_event_and_grid_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertEqual(result.events_persisted, 1)
            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.ledger_registered, 0)
            self.assertEqual(result.funnel.grid_points, 1)
            self.assertEqual(result.funnel.tape_eligible, 1)

    def test_depth_envelope_is_raw_not_tape_eligible_grid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line(capability="US_EQUITY_DEPTH", sequence=2)])
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertEqual(result.funnel.raw_envelopes, 1)
            self.assertEqual(result.funnel.tape_eligible, 0)
            self.assertEqual(result.funnel.grid_points, 0)

    def test_malformed_json_line_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            path.write_text("{not json}\n" + json.dumps(_quote_line()) + "\n", encoding="utf-8")
            funnel = scan_capture_funnel(path, as_of_ns=AS_OF, session_start_ns=SESSION_START)
            self.assertEqual(funnel.refused, 1)
            self.assertEqual(funnel.raw_envelopes, 1)

    def test_temporally_impossible_event_after_available_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(
                path,
                [_quote_line(event_time_ns=DECISION_T + FIVE_SEC, available_time_ns=DECISION_T)],
            )
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertIn("TEMPORALLY_IMPOSSIBLE_EVENT_AFTER_AVAILABLE", result.refusal_reasons)
            self.assertEqual(result.events_persisted, 0)

    def test_non_pit_available_after_as_of_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            future = AS_OF + FIVE_SEC
            _write_jsonl(path, [_quote_line(available_time_ns=future, received_time_ns=future)])
            result = materialize_opend_capture_jsonl(
                path,
                InMemoryIntelligenceRepository(),
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertIn("NON_PIT_AVAILABLE_AFTER_AS_OF", result.refusal_reasons)

    def test_replay_is_idempotent_for_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            first = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            second = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertEqual(first.events_persisted, 1)
            self.assertEqual(second.events_persisted, 0)
            self.assertEqual(second.events_idempotent, 1)

    def test_pre_session_backfill_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line(event_time_ns=SESSION_START - 1)])
            result = materialize_opend_capture_jsonl(
                path,
                InMemoryIntelligenceRepository(),
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertIn("PROSPECTIVE_BACKFILL_BEFORE_SESSION_START", result.refusal_reasons)

    def test_bound_forecast_registers_pending_ledger_without_settlement(self) -> None:
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
            bound = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                forecast_bindings={candidate_id: forecast.forecast_id},
            )
            self.assertEqual(bound.ledger_registered, 1)
            entries = repo.get_prediction_ledger_entries_by_forecast(forecast.forecast_id)
            self.assertEqual(len(entries), 1)
            settlement = OutcomeSettlementService(repo)
            status = settlement.inspect_settlement(entries[0], now_ns=AS_OF)
            self.assertIn(status, {SettlementStatus.NOT_DUE, SettlementStatus.DUE})
            self.assertEqual(repo.get_outcomes_by_forecast(forecast.forecast_id), ())

    def test_same_sequence_different_payload_refused_as_persist_conflict(self) -> None:
        """Cross-file sequence reuse must not overwrite an existing event (fail closed)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path_a = base / "capture_a.jsonl"
            path_b = base / "capture_b.jsonl"
            _write_jsonl(path_a, [_quote_line(sequence=0)])
            conflicting = _quote_line(sequence=0)
            conflicting = {
                **conflicting,
                "raw_payload": {
                    "bid_price": 191.0,
                    "ask_price": 191.2,
                    "bid_vol": 100,
                    "ask_vol": 200,
                    "code": "US.NVDA",
                },
            }
            _write_jsonl(path_b, [conflicting])
            repo = InMemoryIntelligenceRepository()
            first = materialize_opend_capture_jsonl(
                path_a,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            second = materialize_opend_capture_jsonl(
                path_b,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
            )
            self.assertEqual(first.events_persisted, 1)
            self.assertEqual(second.events_persisted, 0)
            self.assertIn("EVENT_PERSIST_CONFLICT", second.refusal_reasons)
            self.assertEqual(second.refusal_reasons["EVENT_PERSIST_CONFLICT"], 1)
            stored = repo.get_event(first.candidates[0].event_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.payload.get("bid"), 190.0)

    def test_candidate_id_is_deterministic(self) -> None:
        candidate_id = derive_capture_ledger_candidate_id(
            capture_path="/tmp/capture.jsonl",
            line_index=3,
            event_id="EVT-1",
            decision_time_ns=DECISION_T,
        )
        again = derive_capture_ledger_candidate_id(
            capture_path="/tmp/capture.jsonl",
            line_index=3,
            event_id="EVT-1",
            decision_time_ns=DECISION_T,
        )
        self.assertEqual(candidate_id, again)
        self.assertTrue(candidate_id.startswith("OCLC-"))


if __name__ == "__main__":
    unittest.main()
