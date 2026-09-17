"""Item 9 calibration protocol machinery (fixtures only; not empirical calibration)."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.policy import (  # noqa: E402
    DIRECTION_UP_DOWN_5M_POLICY,
)
from market_platform_foundation.intelligence.production.identity import (  # noqa: E402
    PATH_A_HORIZON_NS,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    EMPTY_RAW_KLINE_HASH,
    hash_raw_kline_rows,
    run_prospective_proof,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import (  # noqa: E402
    BAR_CAPABILITY,
    ONE_MINUTE_NS,
    load_moomoo_opend_kline_bars,
    normalize_moomoo_kline_row,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    CALIBRATION_STATE,
    EXCL_EMPTY_RAW_HASH,
    EXCL_PATH_A_BAR_LABEL,
    INCLUSION_PATH_PROOF_ONLY,
    INSUFFICIENT_CALIBRATION_EVIDENCE,
    PROTOCOL_VERSION,
    SPLIT_EVALUATION,
    audit_receipt_directory,
    bar_may_compose_path_a_label,
    build_dataset_row,
    chronological_split,
    classify_item9_receipt,
    evaluate_sample_gate,
    feature_cutoff_ns,
    overlapping_signal_bar_is_feature_eligible,
    path_a_target_time_ns,
    path_a_terminal_window,
    protocol_freeze_record,
    reject_incomplete_bar,
)

ET = ZoneInfo("America/New_York")
COLLECTION_ROOT = ROOT.parent
# Lawful RTH timestamps matching the Sep 17 overlapping-bar geometry (fixture copy, not the receipt).
BAR_START = 1_789_661_220_000_000_000
BAR_END = BAR_START + ONE_MINUTE_NS
SIGNAL_NS = 1_789_661_252_872_965_400


def _kline_row(time_key: str = "2023-11-14 10:30:00") -> dict[str, object]:
    return {
        "close": 10.2,
        "high": 10.5,
        "low": 9.5,
        "open": 10.0,
        "time_key": time_key,
        "volume": 50_000,
    }


def _prospective_receipt(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "experiment_id": "item9-fixture-obs-1",
        "proof_mode": "PROSPECTIVE_BAR_OHLCV_1M",
        "not_prospective_evidence": False,
        "evidence_class": "PROSPECTIVE_BAR_OHLCV_1M",
        "instrument_id": "AAPL",
        "signal_time_ns": SIGNAL_NS,
        "signal_established_at_ns": SIGNAL_NS,
        "observation_time_ns": BAR_END + 1,
        "bar_id": "bar-1",
        "bar_start_ns": BAR_START,
        "bar_available_time_ns": BAR_END,
        "bar_source_id": "MOOMOO_OPEND_HISTORY_KLINE_1M",
        "provider_id": "moomoo.opend",
        "raw_provenance_hash": hash_raw_kline_rows((_kline_row(),)),
        "calibrated": False,
        "empirical_active": False,
        "item9_status": "PARTIAL_NOT_CALIBRATED",
        "runtime_git_sha": "test-sha",
        "receipt_contract_version": "item9.bar-ohlcv-prospective-proof/1.1.0",
        "sim_order_state": "FILLED",
        "bar_provenance": {
            "evidence_class": "PROSPECTIVE_OPEND_KLINE",
            "provider_id": "moomoo.opend",
            "fetched_at_ns": BAR_END + 1,
            "timing_basis": "available_time_at_bar_end",
        },
        "first_post_signal_bar": {
            "event_time_ns": BAR_START,
            "available_time_ns": BAR_END,
            "normalized_event_id": "bar-1",
            "bar_payload": {"close": "10.2", "high": "10.5", "low": "9.5", "open": "10.0"},
        },
    }
    body.update(overrides)
    return body


class Item9CalibrationProtocolTests(unittest.TestCase):
    def test_protocol_is_not_calibrated(self) -> None:
        freeze = protocol_freeze_record()
        self.assertEqual(freeze["calibration_state"], CALIBRATION_STATE)
        self.assertEqual(freeze["search_complexity_max"], 0)
        self.assertFalse(freeze["path_a_bars_approved_label_source"])
        self.assertEqual(PROTOCOL_VERSION, "item9.calibration-protocol/1.0.0")

    def test_signal_overlapping_bar_is_feature_eligible_not_path_a_label(self) -> None:
        self.assertTrue(
            overlapping_signal_bar_is_feature_eligible(
                signal_time_ns=SIGNAL_NS,
                bar_start_ns=BAR_START,
                bar_available_ns=BAR_END,
            )
        )
        self.assertGreater(BAR_END, SIGNAL_NS)
        self.assertLess(BAR_START, SIGNAL_NS)
        self.assertFalse(bar_may_compose_path_a_label())
        self.assertNotIn(BAR_CAPABILITY, DIRECTION_UP_DOWN_5M_POLICY.observation_kinds)
        self.assertEqual(DIRECTION_UP_DOWN_5M_POLICY.observation_kinds, ("TRADE",))

    def test_label_horizon_is_path_a_five_minutes(self) -> None:
        target = path_a_target_time_ns(SIGNAL_NS)
        start, end = path_a_terminal_window(SIGNAL_NS)
        self.assertEqual(target, SIGNAL_NS + PATH_A_HORIZON_NS)
        self.assertEqual(start, target)
        self.assertEqual(end - start, DIRECTION_UP_DOWN_5M_POLICY.target_window_tolerance_ns)
        self.assertEqual(feature_cutoff_ns(signal_time_ns=SIGNAL_NS, first_bar_available_ns=BAR_END), BAR_END)
        self.assertLess(BAR_END, target)

    def test_incomplete_bar_rejected(self) -> None:
        self.assertTrue(reject_incomplete_bar(bar_end_ns=BAR_END, fetched_at_ns=BAR_END - 1))
        self.assertFalse(reject_incomplete_bar(bar_end_ns=BAR_END, fetched_at_ns=BAR_END))

    def test_empty_raw_hash_is_path_proof_only(self) -> None:
        receipt = _prospective_receipt(raw_provenance_hash=EMPTY_RAW_KLINE_HASH)
        classified = classify_item9_receipt(receipt)
        self.assertEqual(classified.inclusion_state, INCLUSION_PATH_PROOF_ONLY)
        self.assertEqual(classified.exclusion_reason, EXCL_EMPTY_RAW_HASH)
        self.assertFalse(classified.corpus_admissible)
        self.assertFalse(classified.labelable_path_a_now)
        self.assertEqual(classified.path_a_label_state, EXCL_PATH_A_BAR_LABEL)
        row = build_dataset_row(receipt, classification=classified)
        self.assertIsNone(row["path_a_label_value"])
        self.assertFalse(row["calibrated"])
        self.assertFalse(row["simulator_fill_is_market_truth"])

    def test_hashed_prospective_receipt_still_missing_path_a_trade_label(self) -> None:
        classified = classify_item9_receipt(_prospective_receipt())
        self.assertTrue(classified.corpus_admissible)
        self.assertFalse(classified.labelable_path_a_now)
        self.assertEqual(classified.path_a_label_state, EXCL_PATH_A_BAR_LABEL)

    def test_retrospective_and_fixture_excluded(self) -> None:
        retro = classify_item9_receipt(
            _prospective_receipt(
                proof_mode="RETROSPECTIVE_TRANSPORT_PROOF",
                evidence_class="NOT_PROSPECTIVE_EVIDENCE",
                not_prospective_evidence=True,
            )
        )
        self.assertEqual(retro.exclusion_reason, "NOT_PROSPECTIVE_EVIDENCE")
        fixture = classify_item9_receipt(
            _prospective_receipt(
                evidence_class="ADMITTED_HISTORICAL_FIXTURE",
                bar_provenance={"evidence_class": "ADMITTED_HISTORICAL_FIXTURE"},
            )
        )
        self.assertEqual(fixture.evidence_class, "ADMITTED_HISTORICAL_FIXTURE")

    def test_gaps_and_missing_terminal_do_not_invent_bar_labels(self) -> None:
        row = build_dataset_row(_prospective_receipt())
        self.assertEqual(row["path_a_label_evidence_ids"], [])
        self.assertIsNone(row["path_a_label_value"])

    def test_future_information_rejected_when_bar_not_after_signal(self) -> None:
        classified = classify_item9_receipt(
            _prospective_receipt(bar_available_time_ns=SIGNAL_NS, signal_time_ns=SIGNAL_NS)
        )
        self.assertEqual(classified.inclusion_state, "INVALID")
        self.assertEqual(classified.exclusion_reason, "FEATURE_USES_FUTURE_INFORMATION")

    def test_extended_hours_excluded(self) -> None:
        pre_rth = int(datetime(2026, 9, 17, 8, 0, tzinfo=ET).timestamp() * 1_000_000_000)
        classified = classify_item9_receipt(
            _prospective_receipt(
                signal_time_ns=pre_rth,
                signal_established_at_ns=pre_rth,
                bar_start_ns=pre_rth - 30_000_000_000,
                bar_available_time_ns=pre_rth + 30_000_000_000,
                observation_time_ns=pre_rth + 30_000_000_001,
                bar_provenance={
                    "evidence_class": "PROSPECTIVE_OPEND_KLINE",
                    "fetched_at_ns": pre_rth + 30_000_000_001,
                    "timing_basis": "available_time_at_bar_end",
                },
            )
        )
        self.assertEqual(classified.exclusion_reason, "EXTENDED_HOURS_OR_NON_RTH")

    def test_duplicate_and_non_utf8_scan(self) -> None:
        with self._temp_receipts() as directory:
            good = _prospective_receipt()
            (directory / "a.json").write_text(json.dumps(good), encoding="utf-8")
            (directory / "b.json").write_text(json.dumps(good), encoding="utf-8")
            (directory / "bad.json").write_bytes(b"\xff\xfe not utf-8")
            audit = audit_receipt_directory(directory)
        self.assertEqual(audit["calibration_state"], CALIBRATION_STATE)
        self.assertGreaterEqual(audit["counts"].get("duplicate", 0), 1)
        self.assertGreaterEqual(audit["counts"].get("invalid", 0), 1)
        self.assertFalse(audit["path_a_bars_are_approved_label_source"])

    def test_does_not_scan_dot_local(self) -> None:
        with self._temp_receipts() as directory:
            local = directory / ".local"
            local.mkdir()
            (local / "agent.jsonl").write_bytes(b"\xff")
            audit = audit_receipt_directory(directory)
        self.assertEqual(audit["observations"], [])

    def test_chronological_split_not_shuffled(self) -> None:
        rows = [
            {"observation_id": "c", "signal_timestamp_ns": 30, "corpus_admissible": True},
            {"observation_id": "a", "signal_timestamp_ns": 10, "corpus_admissible": True},
            {"observation_id": "b", "signal_timestamp_ns": 20, "corpus_admissible": True},
            {"observation_id": "d", "signal_timestamp_ns": 40, "corpus_admissible": True},
            {"observation_id": "e", "signal_timestamp_ns": 50, "corpus_admissible": True},
        ]
        split = chronological_split(rows)
        chained = list(split["DEVELOPMENT"]) + list(split["CALIBRATION_SELECTION"]) + list(split[SPLIT_EVALUATION])
        self.assertEqual(chained, ["a", "b", "c", "d", "e"])

    def test_insufficient_sample_gate(self) -> None:
        rows = [
            {
                "observation_id": "only",
                "signal_timestamp_ns": SIGNAL_NS,
                "corpus_admissible": True,
                "inclusion_state": "INCLUDED",
            }
        ]
        gate = evaluate_sample_gate(rows)
        self.assertEqual(gate["status"], INSUFFICIENT_CALIBRATION_EVIDENCE)
        self.assertFalse(gate["fitting_allowed"])
        self.assertFalse(gate["calibrated"])
        self.assertTrue(gate["execution_claims_blocked"])

    def test_opend_load_retains_raw_rows_for_hash(self) -> None:
        rows = (_kline_row(),)
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=9_999_999_999_999_999_999,
            fetched_at_ns=9_999_999_999_999_999_999,
            kline_rows=rows,
        )
        self.assertTrue(loaded.ok)
        self.assertEqual(len(loaded.raw_rows), 1)

    def test_live_hash_uses_injected_raw_rows(self) -> None:
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
        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=int(first["event_time"]),
            signal_established_at_ns=int(first["event_time"]),
            observation_time_ns=int(second["available_time"]),
            kline_rows=rows,
            runtime_git_sha="test-sha",
        )
        self.assertTrue(outcome["ok"])
        self.assertNotEqual(outcome["receipt"]["raw_provenance_hash"], EMPTY_RAW_KLINE_HASH)
        self.assertEqual(outcome["receipt"]["raw_provenance_hash"], hash_raw_kline_rows(rows))
        self.assertFalse(outcome["receipt"]["calibrated"])

    def _temp_receipts(self):
        import tempfile

        class _Ctx:
            def __enter__(self_inner):
                self_inner.ctx = tempfile.TemporaryDirectory()
                return Path(self_inner.ctx.name)

            def __exit__(self_inner, *args: object) -> None:
                self_inner.ctx.cleanup()

        return _Ctx()


if __name__ == "__main__":
    unittest.main()
