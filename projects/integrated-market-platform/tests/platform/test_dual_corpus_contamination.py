"""Dual-corpus contamination and authority machine-safety tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    hash_raw_kline_rows,
    persist_receipt,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import ONE_MINUTE_NS  # noqa: E402
from market_platform_foundation.paper.calibration.dual_corpus.admission import (  # noqa: E402
    ITEM9_ADMISSION_REFUSED,
    REFUSAL_AUTHORITY_CONTRADICTS_PROSPECTIVE_RECEIPT,
    REFUSAL_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    audit_receipt_directory,
    build_item9_corpus_status_report,
    classify_item9_receipt,
    governed_receipt_paths,
)
from market_platform_foundation.paper.calibration.dual_corpus.consumption import (  # noqa: E402
    CONSUMPTION_REFUSED_PROTECTED_CORPUS,
    ProtectedCorpusConsumptionError,
    assert_corpus_consumable_for_selection_or_training,
)
from market_platform_foundation.paper.calibration.dual_corpus.discovery import (  # noqa: E402
    ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT,
    filter_item9_prospective_scan_roots,
    is_historical_development_storage_path,
    iter_item9_prospective_receipt_paths,
)
from market_platform_foundation.paper.calibration.dual_corpus.evidence_authority import (  # noqa: E402
    AUTHORITY_UPGRADE_FORBIDDEN,
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
    resolve_effective_corpus_evidence_authority,
)
from market_platform_foundation.paper.calibration.dual_corpus.historical_manifest import (  # noqa: E402
    build_historical_development_dataset_manifest,
)
from market_platform_foundation.paper.calibration.dual_corpus.historical_provenance import (  # noqa: E402
    build_historical_development_provenance,
)
from market_platform_foundation.paper.calibration.dual_corpus.normalization import (  # noqa: E402
    normalize_historical_development_bars,
)


_BAR_START = 1_789_661_220_000_000_000
_BAR_END = _BAR_START + ONE_MINUTE_NS
_SIGNAL_NS = 1_789_661_252_872_965_400


def _kline_row(time_key: str = "2023-11-14 10:30:00") -> dict[str, object]:
    return {
        "close": 10.2,
        "high": 10.5,
        "low": 9.5,
        "open": 10.0,
        "time_key": time_key,
        "volume": 50_000,
    }


def _prospective_item9_receipt(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "experiment_id": "item9-dual-corpus-fixture-1",
        "proof_mode": "PROSPECTIVE_BAR_OHLCV_1M",
        "not_prospective_evidence": False,
        "evidence_class": "PROSPECTIVE_BAR_OHLCV_1M",
        "instrument_id": "AAPL",
        "signal_time_ns": _SIGNAL_NS,
        "signal_established_at_ns": _SIGNAL_NS,
        "observation_time_ns": _BAR_END + 1,
        "bar_id": "bar-1",
        "bar_start_ns": _BAR_START,
        "bar_available_time_ns": _BAR_END,
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
            "fetched_at_ns": _BAR_END + 1,
            "timing_basis": "available_time_at_bar_end",
        },
        "first_post_signal_bar": {
            "event_time_ns": _BAR_START,
            "available_time_ns": _BAR_END,
            "normalized_event_id": "bar-1",
            "bar_payload": {"close": "10.2", "high": "10.5", "low": "9.5", "open": "10.0"},
        },
    }
    body.update(overrides)
    return body


def _sample_provenance(**overrides: object) -> dict[str, object]:
    base = build_historical_development_provenance(
        provider_id="moomoo.opend",
        capability_id="BAR_OHLCV_1M",
        instrument_id="canonical:EQUITY:XNAS:AAPL",
        request_params={"ktype": "K_1M"},
        requested_interval_start_ns=1,
        requested_interval_end_ns=2,
        returned_interval_start_ns=1,
        returned_interval_end_ns=2,
        timezone_policy="America/New_York",
        session_policy="US_EQUITY_RTH",
        bar_resolution="1_MINUTE",
        raw_timestamp_semantics="bar_start_local",
        availability_semantics="bar_end_available",
        retrieval_timestamp_ns=3,
        provider_response_identity="fixture-response-1",
        raw_payload_ref="fixtures/hist/raw.json",
        raw_payload_sha256="ABC",
        dataset_id="HIST-DEV-AAPL-001",
        dataset_version="0.1.0",
        code_sha="deadbeef",
        transformation_lineage=("raw", "normalize_moomoo_kline_row"),
        inclusion_reason="fixture",
        exclusion_reason=None,
    )
    base.update(overrides)
    return base


class DualCorpusContaminationTests(unittest.TestCase):
    def test_historical_development_refused_for_item9_prospective_corpus(self) -> None:
        outcome = evaluate_item9_prospective_corpus_admission(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        )
        self.assertEqual(outcome["disposition"], ITEM9_ADMISSION_REFUSED)
        self.assertEqual(outcome["reason_code"], REFUSAL_HISTORICAL_DEVELOPMENT)

    def test_historical_directories_never_scanned_for_item9_receipts(self) -> None:
        hist = ROOT / "artifacts/historical-rth-development/receipts"
        self.assertTrue(is_historical_development_storage_path(hist))
        with self.assertRaises(ValueError) as ctx:
            iter_item9_prospective_receipt_paths(hist)
        self.assertEqual(str(ctx.exception), ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT)
        filtered = filter_item9_prospective_scan_roots(
            (hist, ROOT / "artifacts/ftep-v1-002/item9-prospective-proof-receipts")
        )
        self.assertEqual(len(filtered), 1)

    def test_manifest_cannot_upgrade_historical_authority(self) -> None:
        resolved = resolve_effective_corpus_evidence_authority(
            provenance_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            manifest_authority=CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
        )
        self.assertFalse(resolved["ok"])
        self.assertEqual(resolved["reason_code"], AUTHORITY_UPGRADE_FORBIDDEN)
        self.assertEqual(
            resolved["effective_authority"],
            CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        )

    def test_provenance_attached_through_normalization(self) -> None:
        provenance = _sample_provenance()
        row = {"time_key": "2023-11-14 10:30:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
        fetched_at_ns = 1_700_000_000_000_000_000
        first = normalize_historical_development_bars((row,), provenance=provenance, fetched_at_ns=fetched_at_ns)
        second = normalize_historical_development_bars((row,), provenance=provenance, fetched_at_ns=fetched_at_ns)
        self.assertTrue(first["ok"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        bar = first["bars"][0]
        ref = bar["historical_provenance_ref"]
        self.assertEqual(ref["corpus_evidence_authority"], CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT)
        self.assertEqual(ref["dataset_id"], "HIST-DEV-AAPL-001")

    def test_untouched_forward_cannot_be_consumed_for_training(self) -> None:
        with self.assertRaises(ProtectedCorpusConsumptionError) as ctx:
            assert_corpus_consumable_for_selection_or_training(
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
                purpose="selection",
            )
        self.assertIn(CONSUMPTION_REFUSED_PROTECTED_CORPUS, str(ctx.exception))

    def test_persist_receipt_refuses_historical_development_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "historical-development-corpus" / "receipts"
            bad.mkdir(parents=True)
            with self.assertRaises(ValueError) as ctx:
                persist_receipt({"experiment_id": "x"}, out_dir=bad)
            self.assertEqual(str(ctx.exception), ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT)

    def test_persist_receipt_stamps_prospective_feature_authority_for_mode_b(self) -> None:
        receipt = _prospective_item9_receipt()
        self.assertNotIn("corpus_evidence_authority", receipt)
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "item9-prospective-proof-receipts"
            path = persist_receipt(receipt, out_dir=good)
            persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted["corpus_evidence_authority"],
            CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
        )
        classified = classify_item9_receipt(persisted)
        self.assertTrue(classified.corpus_admissible)

    def test_persist_receipt_does_not_upgrade_stamped_historical_authority(self) -> None:
        receipt = _prospective_item9_receipt(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        )
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "item9-prospective-proof-receipts"
            path = persist_receipt(receipt, out_dir=good)
            persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted["corpus_evidence_authority"],
            CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        )
        classified = classify_item9_receipt(persisted)
        self.assertFalse(classified.corpus_admissible)
        self.assertEqual(classified.exclusion_reason, REFUSAL_HISTORICAL_DEVELOPMENT)
        admission = evaluate_item9_prospective_corpus_admission(payload=persisted)
        self.assertEqual(admission["disposition"], ITEM9_ADMISSION_REFUSED)
        self.assertEqual(admission["reason_code"], REFUSAL_HISTORICAL_DEVELOPMENT)

    def test_admission_refuses_empty_authority_without_prospective_receipt_shape(self) -> None:
        outcome = evaluate_item9_prospective_corpus_admission(payload={"experiment_id": "x"})
        self.assertEqual(outcome["disposition"], ITEM9_ADMISSION_REFUSED)

    def test_classify_excludes_historical_corpus_authority_on_prospective_receipt(self) -> None:
        receipt = _prospective_item9_receipt(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        )
        classified = classify_item9_receipt(receipt)
        self.assertFalse(classified.corpus_admissible)
        self.assertEqual(classified.exclusion_reason, REFUSAL_HISTORICAL_DEVELOPMENT)

    def test_classify_excludes_mislabeled_prospective_with_untouched_authority(self) -> None:
        receipt = _prospective_item9_receipt(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
        )
        classified = classify_item9_receipt(receipt)
        self.assertFalse(classified.corpus_admissible)
        self.assertEqual(classified.exclusion_reason, REFUSAL_AUTHORITY_CONTRADICTS_PROSPECTIVE_RECEIPT)

    def test_governed_receipt_paths_empty_on_historical_development_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "historical-rth-development" / "receipts"
            hist.mkdir(parents=True)
            (hist / "leak.json").write_text(json.dumps(_prospective_item9_receipt()), encoding="utf-8")
            self.assertEqual(governed_receipt_paths(hist), ())

    def test_audit_refuses_historical_development_scan_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "historical-development-corpus" / "receipts"
            hist.mkdir(parents=True)
            (hist / "leak.json").write_text(json.dumps(_prospective_item9_receipt()), encoding="utf-8")
            audit = audit_receipt_directory(hist)
        self.assertEqual(audit.get("discovery_refusal"), ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT)
        self.assertEqual(audit["observations"], [])
        self.assertEqual(audit["counts"].get("corpus_admissible", 0), 0)

    def test_corpus_status_report_empty_on_historical_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "historical-development" / "receipts"
            hist.mkdir(parents=True)
            (hist / "leak.json").write_text(json.dumps(_prospective_item9_receipt()), encoding="utf-8")
            report = build_item9_corpus_status_report(hist)
        self.assertEqual(report["counts"]["corpus_admissible"], 0)
        self.assertEqual(report["item9_status"], "PARTIAL_NOT_CALIBRATED")

    def test_classify_accepts_explicit_prospective_feature_authority(self) -> None:
        receipt = _prospective_item9_receipt(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
        )
        classified = classify_item9_receipt(receipt)
        self.assertTrue(classified.corpus_admissible)

    def test_historical_manifest_declares_authority_explicitly(self) -> None:
        provenance = _sample_provenance()
        manifest = build_historical_development_dataset_manifest(
            dataset_id="HIST-DEV-AAPL-001",
            dataset_version="0.1.0",
            providers=("moomoo.opend",),
            universe=("canonical:EQUITY:XNAS:AAPL",),
            interval={"start_ns": 1, "end_ns": 2},
            session_policy="US_EQUITY_RTH",
            bar_resolution="1_MINUTE",
            source_artifacts=({"ref": "fixtures/hist/raw.json", "sha256": "ABC"},),
            normalized_artifact_ref="normalized/bars.jsonl",
            row_count=1,
            duplicate_row_count=0,
            excluded_row_count=0,
            missing_intervals=(),
            lineage={"historical_provenance": provenance},
            code_sha="deadbeef",
            created_at_ns=4,
        )
        self.assertEqual(
            manifest["corpus_evidence_authority"],
            CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        )


if __name__ == "__main__":
    unittest.main()
