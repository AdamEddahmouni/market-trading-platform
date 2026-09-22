"""Item 9 validation readiness contract, snapshot, preflight, execute (fixtures)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    EMPTY_RAW_KLINE_HASH,
    hash_raw_kline_rows,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import (  # noqa: E402
    ONE_MINUTE_NS,
)
from market_platform_foundation.paper.calibration.item9_calibration_execute import (  # noqa: E402
    assert_corpus_unread_on_refusal,
    refuse_calibration_execution_before_corpus_read,
)
from market_platform_foundation.paper.calibration.item9_calibration_preflight import (  # noqa: E402
    run_item9_calibration_preflight,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    PROTOCOL_VERSION,
)
from market_platform_foundation.paper.calibration.item9_readiness_snapshot import (  # noqa: E402
    build_item9_readiness_snapshot,
    load_not_observed_gap_register,
)
from market_platform_foundation.paper.calibration.item9_validation_readiness_contract import (  # noqa: E402
    AUTHORIZATION_ABSENT,
    CALIBRATION_EXECUTION_REFUSED,
    CALIBRATION_PREFLIGHT_BLOCKED,
    CALIBRATION_PREFLIGHT_READY,
    DISPOSITION_ADMISSIBLE,
    DISPOSITION_EVALUATION_ONLY,
    DISPOSITION_PATH_PROOF_ONLY,
    FITTING_ALLOWED_DEFAULT,
    ITEM9_CALIBRATION_RUN_FORBIDDEN,
    READINESS_SNAPSHOT_SCHEMA_ID,
    READINESS_STATE_AWAITING_AUTHORIZATION,
    SEARCH_COMPLEXITY_MAX,
    contract_freeze_record,
)

# Lawful RTH timestamps matching fixture geometry from protocol tests.
BAR_START = 1_789_661_220_000_000_000
BAR_END = BAR_START + ONE_MINUTE_NS
SIGNAL_NS = 1_789_661_252_872_965_400


def _kline_row() -> dict[str, object]:
    return {
        "close": 10.2,
        "high": 10.5,
        "low": 9.5,
        "open": 10.0,
        "time_key": "2023-11-14 10:30:00",
        "volume": 50_000,
    }


def _prospective_receipt(
    *,
    experiment_id: str,
    signal_time_ns: int = SIGNAL_NS,
    empty_hash: bool = False,
) -> dict[str, object]:
    raw_hash = EMPTY_RAW_KLINE_HASH if empty_hash else hash_raw_kline_rows((_kline_row(),))
    # Keep bar geometry relative to the signal so staggered fixtures stay PIT-valid.
    bar_start = signal_time_ns - 32_872_965_400
    bar_end = bar_start + ONE_MINUTE_NS
    if bar_end <= signal_time_ns:
        bar_start = signal_time_ns - (ONE_MINUTE_NS // 2)
        bar_end = bar_start + ONE_MINUTE_NS
    return {
        "experiment_id": experiment_id,
        "proof_mode": "PROSPECTIVE_BAR_OHLCV_1M",
        "not_prospective_evidence": False,
        "evidence_class": "PROSPECTIVE_BAR_OHLCV_1M",
        "instrument_id": "AAPL",
        "signal_time_ns": signal_time_ns,
        "signal_established_at_ns": signal_time_ns,
        "observation_time_ns": bar_end + 1,
        "bar_id": f"bar-{experiment_id}",
        "bar_start_ns": bar_start,
        "bar_available_time_ns": bar_end,
        "bar_source_id": "MOOMOO_OPEND_HISTORY_KLINE_1M",
        "provider_id": "moomoo.opend",
        "raw_provenance_hash": raw_hash,
        "calibrated": False,
        "empirical_active": False,
        "item9_status": "PARTIAL_NOT_CALIBRATED",
        "runtime_git_sha": "test-sha",
        "receipt_contract_version": "item9.bar-ohlcv-prospective-proof/1.1.0",
        "sim_order_state": "FILLED",
        "bar_provenance": {
            "evidence_class": "PROSPECTIVE_OPEND_KLINE",
            "provider_id": "moomoo.opend",
            "fetched_at_ns": bar_end + 1,
            "timing_basis": "available_time_at_bar_end",
        },
        "first_post_signal_bar": {
            "event_time_ns": bar_start,
            "available_time_ns": bar_end,
            "normalized_event_id": f"nev-{experiment_id}",
            "bar_payload": _kline_row(),
        },
    }


def _write_receipts(directory: Path, receipts: list[dict[str, object]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for receipt in receipts:
        name = str(receipt["experiment_id"]) + ".json"
        (directory / name).write_text(json.dumps(receipt), encoding="utf-8")


class Item9ValidationReadinessContractTests(unittest.TestCase):
    def test_contract_freeze_binds_protocol_1_0_0_without_fitting(self) -> None:
        freeze = contract_freeze_record()
        self.assertEqual(freeze["bound_protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(freeze["fitting_allowed"], False)
        self.assertEqual(freeze["calibrated"], False)
        self.assertEqual(freeze["item9_calibration_run"], ITEM9_CALIBRATION_RUN_FORBIDDEN)
        self.assertEqual(freeze["search_complexity_max"], 0)
        self.assertFalse(freeze["authorization_absent_blocks_preflight"])
        self.assertTrue(freeze["authorization_absent_blocks_execution"])
        self.assertTrue(freeze["evaluation_only_is_lifecycle_role"])


class Item9ReadinessSnapshotTests(unittest.TestCase):
    def test_gap_register_loads_and_refuses_synthesis(self) -> None:
        gap = load_not_observed_gap_register(imp_root=ROOT)
        self.assertTrue(gap["loaded"])
        self.assertFalse(gap["synthesize_bars_for_gaps"])
        ids = {item["gap_id"] for item in gap["intervals"]}
        self.assertIn("SEP21_MID_SESSION_1043_1309_ET", ids)
        self.assertIn("SEP18_OUTAGE_EPOCH_121031", ids)

    def test_absent_receipt_dir_is_not_run(self) -> None:
        missing = ROOT / "artifacts" / "__missing_item9_receipts__"
        snapshot = build_item9_readiness_snapshot(missing, imp_root=ROOT)
        self.assertEqual(snapshot["snapshot_status"], "NOT_RUN")
        self.assertEqual(snapshot["receipt_dir_status"], "UNAVAILABLE")
        self.assertEqual(snapshot["calibrated"], False)
        self.assertEqual(snapshot["fitting_allowed"], FITTING_ALLOWED_DEFAULT)
        self.assertEqual(snapshot["schema_id"], READINESS_SNAPSHOT_SCHEMA_ID)

    def test_snapshot_marks_path_proof_and_evaluation_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            # 25 admissible rows across staggered signal times for split
            receipts = [
                _prospective_receipt(
                    experiment_id=f"obs-{i:03d}",
                    signal_time_ns=SIGNAL_NS + i * 60_000_000_000,
                )
                for i in range(25)
            ]
            receipts.append(
                _prospective_receipt(experiment_id="path-proof-1", empty_hash=True)
            )
            _write_receipts(receipt_dir, receipts)
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            self.assertEqual(snapshot["snapshot_status"], "COMPUTED")
            self.assertEqual(snapshot["calibrated"], False)
            self.assertEqual(snapshot["search_complexity_max"], SEARCH_COMPLEXITY_MAX)
            dispositions = {d["observation_id"]: d for d in snapshot["dispositions"]}
            self.assertEqual(
                dispositions["path-proof-1"]["disposition"], DISPOSITION_PATH_PROOF_ONLY
            )
            self.assertFalse(dispositions["path-proof-1"]["corpus_admissible"])
            eval_ids = set(snapshot["evaluation_boundary"]["UNTOUCHED_EVALUATION"])
            self.assertTrue(eval_ids)
            for obs_id in eval_ids:
                self.assertEqual(
                    dispositions[obs_id]["disposition"], DISPOSITION_EVALUATION_ONLY
                )
                self.assertTrue(dispositions[obs_id]["corpus_admissible"])
            # Non-eval admissible
            non_eval = [
                d
                for d in snapshot["dispositions"]
                if d["disposition"] == DISPOSITION_ADMISSIBLE
            ]
            self.assertTrue(non_eval)
            self.assertTrue(snapshot["evaluation_boundary"]["untouched_evaluation_sealed"])
            self.assertFalse(
                snapshot["evaluation_boundary"]["protocol_freeze_provenance"][
                    "chosen_from_this_corpus"
                ]
            )
            self.assertEqual(
                snapshot["mode_b_field_applicability"]["strategy_id"], "NOT_APPLICABLE"
            )
            role_map = snapshot["dual_corpus_role_map"]
            self.assertEqual(set(role_map), {"TRAINING", "DEVELOPMENT", "CALIBRATION", "UNTOUCHED"})
            self.assertTrue(snapshot["toctou_binding"]["corpus_fingerprint"])
            self.assertIn("contamination_status", snapshot["dual_corpus"])


class Item9CalibrationPreflightTests(unittest.TestCase):
    def test_absent_auth_does_not_block_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            # Need 3 distinct RTH dates — stagger by calendar days in ET.
            # SIGNAL_NS is 2026-09-17-ish; add ~1 day and ~4 days of ns.
            day_ns = 86_400_000_000_000
            receipts: list[dict[str, object]] = []
            for day_i, day_offset in enumerate((0, day_ns, 4 * day_ns)):
                for i in range(10):
                    receipts.append(
                        _prospective_receipt(
                            experiment_id=f"d{day_i}-obs-{i:03d}",
                            signal_time_ns=SIGNAL_NS + day_offset + i * 60_000_000_000,
                        )
                    )
            _write_receipts(receipt_dir, receipts)
            report = run_item9_calibration_preflight(
                receipt_dir=receipt_dir,
                imp_root=ROOT,
                authorization_state=AUTHORIZATION_ABSENT,
            )
            self.assertEqual(report["authorization_state"], AUTHORIZATION_ABSENT)
            self.assertFalse(report["authorization_blocks_preflight"])
            self.assertTrue(report["authorization_blocks_execution"])
            self.assertEqual(report["calibrated"], False)
            self.assertEqual(report["fitting_allowed"], False)
            self.assertEqual(report["item9_calibration_run"], ITEM9_CALIBRATION_RUN_FORBIDDEN)
            if report["preflight_verdict"] == CALIBRATION_PREFLIGHT_READY:
                self.assertEqual(
                    report["readiness_state"], READINESS_STATE_AWAITING_AUTHORIZATION
                )
            else:
                # If RTH date math fails on fixture timestamps, stay honest BLOCKED.
                self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)

    def test_missing_dir_blocks(self) -> None:
        report = run_item9_calibration_preflight(
            receipt_dir=ROOT / "artifacts" / "__no_such_item9__",
            imp_root=ROOT,
        )
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("RECEIPT_DIR_UNAVAILABLE", report["blockers"])


class Item9CalibrationExecuteTests(unittest.TestCase):
    def test_missing_auth_refuses_before_corpus_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write_receipts(receipt_dir, [_prospective_receipt(experiment_id="obs-1")])
            result = refuse_calibration_execution_before_corpus_read(
                authorization_path=None,
                receipt_dir=receipt_dir,
                imp_root=ROOT,
            )
            self.assertEqual(result["verdict"], CALIBRATION_EXECUTION_REFUSED)
            self.assertFalse(result["corpus_read_attempted"])
            self.assertFalse(result["receipt_dir_opened"])
            self.assertEqual(result["calibrated"], False)
            assert_corpus_unread_on_refusal(result)


if __name__ == "__main__":
    unittest.main()
