"""Dual-corpus contamination and authority machine-safety tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    persist_receipt,
)
from market_platform_foundation.paper.calibration.dual_corpus.admission import (  # noqa: E402
    ITEM9_ADMISSION_REFUSED,
    REFUSAL_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
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
        hist = Path("artifacts/historical-rth-development/receipts")
        self.assertTrue(is_historical_development_storage_path(hist))
        with self.assertRaises(ValueError) as ctx:
            iter_item9_prospective_receipt_paths(hist)
        self.assertEqual(str(ctx.exception), ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT)
        filtered = filter_item9_prospective_scan_roots((hist, Path("artifacts/ftep-v1-002/item9-prospective-proof-receipts")))
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
