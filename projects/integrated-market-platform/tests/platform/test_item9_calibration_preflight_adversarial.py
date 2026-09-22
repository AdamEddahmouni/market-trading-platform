"""Adversarial fail-closed fixtures for Item 9 calibration preflight."""

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
    bind_preflight_toctou,
    compare_toctou_bindings,
    refuse_calibration_execution_before_corpus_read,
)
from market_platform_foundation.paper.calibration.item9_calibration_preflight import (  # noqa: E402
    run_item9_calibration_preflight,
)
from market_platform_foundation.paper.calibration.item9_readiness_snapshot import (  # noqa: E402
    build_item9_readiness_snapshot,
)
from market_platform_foundation.paper.calibration.item9_validation_readiness_contract import (  # noqa: E402
    AUTHORIZATION_ABSENT,
    CALIBRATION_EXECUTION_REFUSED,
    CALIBRATION_PREFLIGHT_BLOCKED,
    DISPOSITION_PATH_PROOF_ONLY,
    DISPOSITION_UNKNOWN_REQUIRES_REVIEW,
    REASON_TOCTOU_FINGERPRINT_MISMATCH,
)

BAR_START = 1_789_661_220_000_000_000
BAR_END = BAR_START + ONE_MINUTE_NS
SIGNAL_NS = 1_789_661_252_872_965_400


def _kline_row(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "close": 10.2,
        "high": 10.5,
        "low": 9.5,
        "open": 10.0,
        "time_key": "2023-11-14 10:30:00",
        "volume": 50_000,
    }
    body.update(overrides)
    return body


def _receipt(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "experiment_id": "adv-obs-1",
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
            "received_time_ns": BAR_END + 2,
        },
        "first_post_signal_bar": {
            "event_time_ns": BAR_START,
            "available_time_ns": BAR_END,
            "normalized_event_id": "nev-1",
            "bar_payload": _kline_row(),
        },
    }
    body.update(overrides)
    return body


def _write(directory: Path, receipts: list[dict[str, object]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for i, receipt in enumerate(receipts):
        name = str(receipt.get("experiment_id") or f"anon-{i}") + f"-{i}.json"
        (directory / name).write_text(json.dumps(receipt), encoding="utf-8")


class Item9CalibrationPreflightAdversarialTests(unittest.TestCase):
    def test_duplicate_receipt_experiment_id_accounted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            r = _receipt(experiment_id="dup-id")
            _write(receipt_dir, [r, dict(r)])
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            dups = [
                d
                for d in snapshot["dispositions"]
                if d.get("inclusion_state") == "DUPLICATE"
            ]
            self.assertTrue(dups)

    def test_bad_raw_hash_path_proof_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(
                receipt_dir,
                [_receipt(experiment_id="empty-hash", raw_provenance_hash=EMPTY_RAW_KLINE_HASH)],
            )
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "empty-hash")
            self.assertEqual(row["disposition"], DISPOSITION_PATH_PROOF_ONLY)
            self.assertFalse(row["corpus_admissible"])

    def test_feature_lookahead_blocks_or_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(
                receipt_dir,
                [
                    _receipt(
                        experiment_id="lookahead",
                        bar_available_time_ns=SIGNAL_NS - 1,
                        first_post_signal_bar={
                            "event_time_ns": BAR_START,
                            "available_time_ns": SIGNAL_NS - 1,
                            "normalized_event_id": "nev-x",
                            "bar_payload": _kline_row(),
                        },
                    )
                ],
            )
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "lookahead")
            self.assertFalse(row["corpus_admissible"])

    def test_future_available_after_received(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(
                receipt_dir,
                [
                    _receipt(
                        experiment_id="ts-order",
                        bar_provenance={
                            "evidence_class": "PROSPECTIVE_OPEND_KLINE",
                            "provider_id": "moomoo.opend",
                            "fetched_at_ns": BAR_END + 1,
                            "timing_basis": "available_time_at_bar_end",
                            "received_time_ns": BAR_START,
                        },
                    )
                ],
            )
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "ts-order")
            codes = {f["code"] for f in row["forensic_flags"]}
            self.assertIn("AVAILABLE_AFTER_RECEIVED", codes)

    def test_zero_price_or_volume_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(
                receipt_dir,
                [
                    _receipt(
                        experiment_id="zero-vol",
                        first_post_signal_bar={
                            "event_time_ns": BAR_START,
                            "available_time_ns": BAR_END,
                            "normalized_event_id": "nev-z",
                            "bar_payload": _kline_row(volume=0, high=0),
                        },
                    )
                ],
            )
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "zero-vol")
            codes = {f["code"] for f in row["forensic_flags"]}
            self.assertIn("ZERO_PRICE_OR_VOLUME", codes)

    def test_missing_instrument_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(receipt_dir, [_receipt(experiment_id="no-inst", instrument_id="")])
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "no-inst")
            codes = {f["code"] for f in row["forensic_flags"]}
            self.assertIn("MISSING_INSTRUMENT", codes)

    def test_path_proof_in_consumption_blocks_preflight(self) -> None:
        """If a PATH_PROOF_ONLY row were wrongly marked admissible, preflight blocks."""

        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "evaluation_fingerprint": "ghi",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 1,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "bad-ppo",
                    "disposition": DISPOSITION_PATH_PROOF_ONLY,
                    "reason": "EMPTY",
                    "rule": "RULE.FORENSIC.EMPTY_RAW_HASH_PATH_PROOF",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True, "intervals": []},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("PATH_PROOF_ONLY_IN_CONSUMPTION_SET", report["blockers"])

    def test_eval_row_in_calibration_set_blocks(self) -> None:
        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["leak"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["leak", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": False,
                "holdout_leak_ids": ["leak"],
            },
            "dispositions": [
                {
                    "observation_id": "ok",
                    "disposition": "ADMISSIBLE",
                    "reason": None,
                    "rule": "RULE.ADMISSION.PROSPECTIVE_CORPUS",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertTrue(
            any("HOLDOUT" in b or "TRAIN_EVAL" in b for b in report["blockers"])
            or "HOLDOUT_IN_DEVELOPMENT_OR_SELECTION" in report["blockers"]
        )

    def test_critical_unknown_blocks(self) -> None:
        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "unk",
                    "disposition": DISPOSITION_UNKNOWN_REQUIRES_REVIEW,
                    "reason": "CRITICAL",
                    "rule": "RULE.FORENSIC.POINT_IN_TIME",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": ["unk"],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("CRITICAL_UNKNOWN_REQUIRES_REVIEW", report["blockers"])

    def test_missing_rth_date_floor_blocks(self) -> None:
        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 1,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "ok",
                    "disposition": "ADMISSIBLE",
                    "reason": None,
                    "rule": "RULE.ADMISSION.PROSPECTIVE_CORPUS",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("RTH_DATES_UNMET", report["blockers"])

    def test_missing_authorization_refuses_execute(self) -> None:
        result = refuse_calibration_execution_before_corpus_read(
            authorization_path=None,
            receipt_dir=Path("/nonexistent/receipts"),
            imp_root=ROOT,
        )
        self.assertEqual(result["verdict"], CALIBRATION_EXECUTION_REFUSED)
        self.assertFalse(result["corpus_read_attempted"])
        self.assertFalse(result["receipt_dir_opened"])

    def test_fingerprint_change_after_preflight_detected_via_mismatch(self) -> None:
        """Corpus/protocol hash change is a blocker when fingerprints vanish."""

        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "corpus_fingerprint": None,
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "ok",
                    "disposition": "ADMISSIBLE",
                    "reason": None,
                    "rule": "RULE.ADMISSION.PROSPECTIVE_CORPUS",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("INTEGRITY_FAILURE", report["blockers"])

    def test_missing_provenance_blocks(self) -> None:
        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 2,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "ok",
                    "disposition": "ADMISSIBLE",
                    "reason": None,
                    "rule": "RULE.ADMISSION.PROSPECTIVE_CORPUS",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("INTEGRITY_FAILURE", report["blockers"])

    def test_non_rth_flagged(self) -> None:
        overnight_ns = 1_789_620_000_000_000_000  # outside US cash RTH
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(
                receipt_dir,
                [_receipt(experiment_id="non-rth", signal_time_ns=overnight_ns)],
            )
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "non-rth")
            self.assertFalse(row["corpus_admissible"])
            codes = {f["code"] for f in row["forensic_flags"]}
            self.assertIn("NON_RTH", codes)

    def test_stale_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            _write(
                receipt_dir,
                [_receipt(experiment_id="stale-row", freshness_status="STALE")],
            )
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "stale-row")
            codes = {f["code"] for f in row["forensic_flags"]}
            self.assertIn("STALE", codes)

    def test_incomplete_outcome_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            body = _receipt(experiment_id="incomplete")
            body["first_post_signal_bar"] = {
                "event_time_ns": BAR_START,
                "available_time_ns": BAR_END,
                "normalized_event_id": "nev-inc",
            }
            _write(receipt_dir, [body])
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            row = next(d for d in snapshot["dispositions"] if d["observation_id"] == "incomplete")
            codes = {f["code"] for f in row["forensic_flags"]}
            self.assertIn("INCOMPLETE_OUTCOME", codes)

    def test_mode_b_unknown_strategy_is_not_applicable_not_block(self) -> None:
        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": "phase7.bar-conservative/1.1.0",
            "cost_model_version": "NOT_OBSERVED",
            "settlement_model_version": "NOT_OBSERVED",
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "ok",
                    "disposition": "ADMISSIBLE",
                    "reason": None,
                    "rule": "RULE.ADMISSION.PROSPECTIVE_CORPUS",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                    "mode_b_strategy_fields": "NOT_APPLICABLE",
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
            "mode_b_field_applicability": {"strategy_id": "NOT_APPLICABLE"},
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertNotIn("CRITICAL_UNKNOWN_REQUIRES_REVIEW", report["blockers"])

    def test_retry_duplicate_file_hash_accounted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            receipt_dir.mkdir(parents=True, exist_ok=True)
            text = json.dumps(_receipt(experiment_id="retry-same"))
            (receipt_dir / "retry-same-0.json").write_text(text, encoding="utf-8")
            (receipt_dir / "retry-same-1.json").write_text(text, encoding="utf-8")
            snapshot = build_item9_readiness_snapshot(receipt_dir, imp_root=ROOT)
            self.assertGreaterEqual(int(snapshot["counts"].get("duplicate_file_hash_groups") or 0), 1)

    def test_toctou_fingerprint_change_refuses_execute(self) -> None:
        bound = bind_preflight_toctou(
            {
                "corpus_fingerprint": "aaa",
                "evaluation_fingerprint": "bbb",
                "protocol_fingerprint": "ccc",
            }
        )
        current = dict(bound)
        current["corpus_fingerprint"] = "mutated"
        cmp = compare_toctou_bindings(bound, current)
        self.assertFalse(cmp["ok"])
        self.assertIn("corpus_fingerprint", cmp["mismatched"])
        result = refuse_calibration_execution_before_corpus_read(
            authorization_path=None,
            bound_toctou=bound,
            current_toctou=current,
        )
        self.assertEqual(result["verdict"], CALIBRATION_EXECUTION_REFUSED)
        self.assertFalse(result["corpus_read_attempted"])
        self.assertEqual(cmp["reason"], REASON_TOCTOU_FINGERPRINT_MISMATCH)

    def test_missing_simulator_version_blocks(self) -> None:
        snapshot = {
            "snapshot_status": "COMPUTED",
            "receipt_dir_status": "PRESENT",
            "protocol_version": "item9.calibration-protocol/1.0.0",
            "dataset_schema_version": "item9.calibration-dataset/1.0.0",
            "simulator_version": None,
            "corpus_fingerprint": "abc",
            "protocol_fingerprint": "def",
            "authorization_state": AUTHORIZATION_ABSENT,
            "session_dates_rth": ["2026-09-17", "2026-09-18", "2026-09-21"],
            "counts": {
                "corpus_admissible": 25,
                "evaluation_rows": 5,
                "path_proof_only": 0,
                "duplicate": 0,
                "unknown_provenance": 0,
            },
            "sample_gate": {
                "included_count": 25,
                "distinct_rth_dates": 3,
                "evaluation_count": 5,
            },
            "evaluation_boundary": {
                "DEVELOPMENT": ["a"],
                "CALIBRATION_SELECTION": ["b"],
                "UNTOUCHED_EVALUATION": ["c", "d", "e", "f", "g"],
                "split_fractions": [0.6, 0.2, 0.2],
                "shuffle": False,
                "untouched_evaluation_sealed": True,
                "holdout_leak_ids": [],
            },
            "dispositions": [
                {
                    "observation_id": "ok",
                    "disposition": "ADMISSIBLE",
                    "reason": None,
                    "rule": "RULE.ADMISSION.PROSPECTIVE_CORPUS",
                    "corpus_admissible": True,
                    "forensic_flags": [],
                }
            ],
            "critical_unknown_observation_ids": [],
            "gap_register": {"loaded": True},
            "schema_id": "item9.validation-readiness-snapshot/1.0.0",
        }
        report = run_item9_calibration_preflight(snapshot=snapshot)
        self.assertEqual(report["preflight_verdict"], CALIBRATION_PREFLIGHT_BLOCKED)
        self.assertIn("INTEGRITY_FAILURE", report["blockers"])


if __name__ == "__main__":
    unittest.main()
