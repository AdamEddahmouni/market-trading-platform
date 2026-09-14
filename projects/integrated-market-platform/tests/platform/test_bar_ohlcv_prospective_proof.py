"""Item 9 BAR_OHLCV_1M prospective proof operator tests (offline, no RTH hammering)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_experiment import (  # noqa: E402
    CLASSIFICATION_CONTRACT_MISMATCH,
    CLASSIFICATION_RUNNABLE,
    run_bounded_bar_ohlcv_experiment,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    NOT_PROSPECTIVE_EVIDENCE,
    PROOF_MODE_PROSPECTIVE,
    PROOF_MODE_RETROSPECTIVE,
    READINESS_RTH_REQUIRED,
    READINESS_TOOL_READY,
    REASON_NO_POST_SIGNAL_BAR,
    REASON_POLL_REQUIRED,
    REASON_PROSPECTIVE_EXPLICIT_SIGNAL,
    REASON_PROSPECTIVE_RETROSPECTIVE_SIGNAL,
    REASON_PROSPECTIVE_WRONG_SOURCE,
    build_evidence_receipt,
    hash_raw_kline_rows,
    item9_prospective_readiness,
    load_latest_completed_bars_for_display,
    poll_prospective_proof,
    prospective_run_without_poll_outcome,
    run_prospective_proof,
    run_transport_proof,
    validate_prospective_signal_request,
    validate_prospective_signal_vs_bar,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import (  # noqa: E402
    ONE_MINUTE_NS,
    first_admissible_post_signal_bar,
    load_moomoo_opend_kline_bars,
    normalize_moomoo_kline_row,
    pit_visible_bars,
)

COLLECTION_ROOT = ROOT.parent


def _kline_row(time_key: str = "2023-11-14 10:30:00") -> dict[str, object]:
    return {
        "close": 10.2,
        "high": 10.5,
        "low": 9.5,
        "open": 10.0,
        "time_key": time_key,
        "volume": 50_000,
    }


class BarOhlcvProspectiveProofTests(unittest.TestCase):
    def test_readiness_reports_tool_ready_and_rth_gate(self) -> None:
        closed = item9_prospective_readiness(now_ns=1_700_000_000_000_000_000)
        self.assertEqual(closed["readiness"], READINESS_TOOL_READY)
        self.assertEqual(closed["empirical_status"], READINESS_RTH_REQUIRED)
        self.assertFalse(closed["calibrated"])

    def test_without_poll_off_hours_reports_rth_required(self) -> None:
        outcome = prospective_run_without_poll_outcome(
            now_ns=1_700_000_000_000_000_000,
            signal_time_ns=100,
            signal_established_at_ns=100,
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], READINESS_RTH_REQUIRED)
        self.assertFalse(outcome["readiness"]["rth_active"])

    @mock.patch(
        "market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof.is_within_us_equity_rth",
        return_value=True,
    )
    def test_without_poll_during_rth_reports_poll_required(self, _rth: mock.Mock) -> None:
        outcome = prospective_run_without_poll_outcome(
            now_ns=1,
            signal_time_ns=100,
            signal_established_at_ns=100,
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], REASON_POLL_REQUIRED)
        self.assertNotEqual(outcome["reason_code"], READINESS_RTH_REQUIRED)
        self.assertTrue(outcome["readiness"]["rth_active"])

    def test_prospective_refuses_explicit_signal_time(self) -> None:
        gate = validate_prospective_signal_request(
            proof_mode=PROOF_MODE_PROSPECTIVE,
            signal_time_ns=123,
            signal_established_at_ns=100,
            source="moomoo-opend",
        )
        self.assertFalse(gate.ok)
        self.assertEqual(gate.reason_code, REASON_PROSPECTIVE_EXPLICIT_SIGNAL)

    def test_prospective_refuses_wrong_source(self) -> None:
        gate = validate_prospective_signal_request(
            proof_mode=PROOF_MODE_PROSPECTIVE,
            signal_time_ns=None,
            signal_established_at_ns=100,
            source="admitted-fixture",
        )
        self.assertFalse(gate.ok)
        self.assertEqual(gate.reason_code, REASON_PROSPECTIVE_WRONG_SOURCE)

    def test_prospective_refuses_retrospective_signal_vs_bar(self) -> None:
        gate = validate_prospective_signal_vs_bar(
            signal_time_ns=200,
            signal_established_at_ns=200,
            bar_available_time_ns=200,
        )
        self.assertFalse(gate.ok)
        self.assertEqual(gate.reason_code, REASON_PROSPECTIVE_RETROSPECTIVE_SIGNAL)

    def test_transport_receipt_labels_not_prospective(self) -> None:
        rows = (_kline_row(time_key="2023-11-14 10:29:00"), _kline_row())
        first = normalize_moomoo_kline_row(
            rows[0],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        second = normalize_moomoo_kline_row(
            rows[1],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first is not None and second is not None
        signal = int(first["available_time"]) - 1
        payload = run_transport_proof(
            signal_time_ns=signal,
            observation_time_ns=int(second["available_time"]),
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
            env={},
            kline_rows=rows,
            runtime_git_sha="test-sha",
        )
        receipt = payload["receipt"]
        self.assertEqual(receipt["proof_mode"], PROOF_MODE_RETROSPECTIVE)
        self.assertTrue(receipt["not_prospective_evidence"])
        self.assertEqual(receipt["evidence_class"], NOT_PROSPECTIVE_EVIDENCE)

    def test_prospective_happy_path_with_injected_rows(self) -> None:
        rows = (_kline_row(time_key="2023-11-14 10:29:00"), _kline_row())
        first = normalize_moomoo_kline_row(
            rows[0],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        second = normalize_moomoo_kline_row(
            rows[1],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first is not None and second is not None
        signal_established = int(first["event_time"])
        signal = signal_established
        observation = int(second["available_time"])
        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=signal,
            signal_established_at_ns=signal_established,
            observation_time_ns=observation,
            kline_rows=rows,
            runtime_git_sha="test-sha",
        )
        self.assertTrue(outcome["ok"])
        receipt = outcome["receipt"]
        assert receipt is not None
        self.assertEqual(receipt["proof_mode"], PROOF_MODE_PROSPECTIVE)
        self.assertFalse(receipt["not_prospective_evidence"])
        self.assertFalse(receipt["calibrated"])
        self.assertFalse(receipt["orders_placed"])

    def test_prospective_receipt_uses_operator_experiment_id(self) -> None:
        rows = (_kline_row(time_key="2023-11-14 10:29:00"), _kline_row())
        first = normalize_moomoo_kline_row(
            rows[0],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        second = normalize_moomoo_kline_row(
            rows[1],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first is not None and second is not None
        operator_id = "item9-rth-20260915-aapl"
        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=int(first["event_time"]),
            signal_established_at_ns=int(first["event_time"]),
            observation_time_ns=int(second["available_time"]),
            kline_rows=rows,
            experiment_id=operator_id,
        )
        self.assertTrue(outcome["ok"])
        receipt = outcome["receipt"]
        assert receipt is not None
        self.assertEqual(receipt["experiment_id"], operator_id)

    def test_no_post_signal_bar(self) -> None:
        row = _kline_row()
        bar = normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=9_999_999_999_999_999_999)
        assert bar is not None
        bar_end = int(bar["available_time"])
        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=bar_end,
            signal_established_at_ns=bar_end - 1,
            observation_time_ns=bar_end,
            kline_rows=(row,),
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], REASON_NO_POST_SIGNAL_BAR)

    def test_same_time_bar_not_admissible(self) -> None:
        bars = [{"available_time": 500, "instrument_id": "AAPL"}]
        self.assertIsNone(first_admissible_post_signal_bar(bars, signal_time_ns=500))

    def test_future_incomplete_bar_hidden(self) -> None:
        row = _kline_row()
        probe = normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=9_999_999_999_999_999_999)
        assert probe is not None
        mid = int(probe["event_time"]) + (ONE_MINUTE_NS // 2)
        self.assertIsNone(normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=mid))

    def test_stale_observation_hides_bar(self) -> None:
        row = _kline_row()
        probe = normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=9_999_999_999_999_999_999)
        assert probe is not None
        bar_end = int(probe["available_time"])
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=bar_end - 1,
            fetched_at_ns=bar_end,
            kline_rows=(row,),
        )
        self.assertFalse(loaded.ok)

    def test_malformed_bar_rejected(self) -> None:
        self.assertIsNone(
            normalize_moomoo_kline_row(
                _kline_row(time_key="bad"),
                instrument_id="AAPL",
                fetched_at_ns=9_999_999_999_999_999_999,
            ),
        )

    def test_out_of_order_rows_still_select_first_lawful_bar(self) -> None:
        rows = (_kline_row(time_key="2023-11-14 10:31:00"), _kline_row(time_key="2023-11-14 10:30:00"))
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=9_999_999_999_999_999_999,
            fetched_at_ns=9_999_999_999_999_999_999,
            kline_rows=rows,
        )
        self.assertTrue(loaded.ok)
        visible = pit_visible_bars(loaded.bars, observation_time_ns=9_999_999_999_999_999_999, instrument_id="AAPL")
        self.assertEqual(len(visible), 2)
        first_bar = normalize_moomoo_kline_row(
            _kline_row(time_key="2023-11-14 10:30:00"),
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first_bar is not None
        hit = first_admissible_post_signal_bar(visible, signal_time_ns=int(first_bar["available_time"]) - 1)
        assert hit is not None
        self.assertEqual(int(hit["available_time"]), int(first_bar["available_time"]))

    def test_wrong_instrument_filtered(self) -> None:
        row = _kline_row()
        bar = normalize_moomoo_kline_row(
            row,
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert bar is not None
        visible = pit_visible_bars(
            (bar,),
            observation_time_ns=9_999_999_999_999_999_999,
            instrument_id="MSFT",
        )
        self.assertEqual(len(visible), 0)

    def test_duplicate_available_times_keep_first_lawful_post_signal(self) -> None:
        row = _kline_row()
        bar = normalize_moomoo_kline_row(
            row,
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert bar is not None
        duplicate = dict(bar)
        bars = pit_visible_bars(
            (bar, duplicate),
            observation_time_ns=9_999_999_999_999_999_999,
            instrument_id="AAPL",
        )
        hit = first_admissible_post_signal_bar(bars, signal_time_ns=int(bar["available_time"]) - 1)
        assert hit is not None
        self.assertEqual(int(hit["available_time"]), int(bar["available_time"]))

    @mock.patch(
        "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_reachable",
        return_value=False,
    )
    def test_provider_unavailable_without_rows(self, _reachable: mock.Mock) -> None:
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=1_700_000_000_000_000_000,
        )
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, "OPEND_UNAVAILABLE")

    def test_poll_refuses_off_hours_without_loader_calls(self) -> None:
        loader = mock.Mock()
        outcome = poll_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=1,
            signal_established_at_ns=1,
            max_wait_s=1.0,
            poll_interval_s=0.01,
            sleep_fn=lambda _s: None,
            now_fn=lambda: 1_700_000_000_000_000_000,
            loader=loader,
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], READINESS_RTH_REQUIRED)
        loader.assert_not_called()

    def test_transport_experiment_classifies_runnable(self) -> None:
        rows = (_kline_row(time_key="2023-11-14 10:29:00"), _kline_row())
        first = normalize_moomoo_kline_row(
            rows[0],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        second = normalize_moomoo_kline_row(
            rows[1],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first is not None and second is not None
        payload = run_transport_proof(
            signal_time_ns=int(first["available_time"]) - 1,
            observation_time_ns=int(second["available_time"]),
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
            env={},
            kline_rows=rows,
        )
        self.assertEqual(payload["result"]["classification"], CLASSIFICATION_RUNNABLE)

    def test_contract_mismatch_when_no_strict_post_signal(self) -> None:
        row = _kline_row()
        bar = normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=9_999_999_999_999_999_999)
        assert bar is not None
        bar_end = int(bar["available_time"])
        payload = run_transport_proof(
            signal_time_ns=bar_end,
            observation_time_ns=bar_end,
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
            env={},
            kline_rows=(row,),
        )
        self.assertEqual(payload["result"]["classification"], CLASSIFICATION_CONTRACT_MISMATCH)

    def test_raw_hash_stable(self) -> None:
        rows = (_kline_row(),)
        self.assertEqual(hash_raw_kline_rows(rows), hash_raw_kline_rows(rows))

    def test_display_builds_rows_from_injected_klines(self) -> None:
        row = _kline_row()
        loaded, display = load_latest_completed_bars_for_display(
            instrument_id="AAPL",
            observation_time_ns=9_999_999_999_999_999_999,
            kline_rows=(row,),
        )
        self.assertTrue(loaded.ok)
        self.assertEqual(len(display), 1)
        self.assertEqual(display[0].instrument_id, "AAPL")

    def test_receipt_includes_contract_version(self) -> None:
        row = _kline_row()
        bar = normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=9_999_999_999_999_999_999)
        assert bar is not None
        result = run_bounded_bar_ohlcv_experiment(
            signal_time_ns=int(bar["available_time"]) - 1,
            observation_time_ns=int(bar["available_time"]),
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
            kline_rows=(row,),
        )
        receipt = build_evidence_receipt(
            experiment_id="test-exp",
            proof_mode=PROOF_MODE_PROSPECTIVE,
            experiment=result,
            runtime_git_sha="sha",
            raw_provenance_hash="abc",
            signal_established_at_ns=1,
        )
        self.assertIn("receipt_contract_version", receipt)
        self.assertEqual(receipt["runtime_git_sha"], "sha")


if __name__ == "__main__":
    unittest.main()
