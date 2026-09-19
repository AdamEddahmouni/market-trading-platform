"""Item 9 corpus-status CLI (read-only; fixtures only)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    EMPTY_RAW_KLINE_HASH,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    CALIBRATION_STATE,
    INSUFFICIENT_CALIBRATION_EVIDENCE,
    ITEM9_CORPUS_STATUS_ARTIFACT_KIND,
    build_item9_corpus_status_report,
    validate_item9_governed_receipt_dir,
)
from tests.platform.test_item9_calibration_protocol import (  # noqa: E402
    _prospective_receipt,
)


class Item9CorpusStatusCliTests(unittest.TestCase):
    def test_corpus_status_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_item9_corpus_status_report(Path(tmp))
        self.assertEqual(report["artifact_kind"], ITEM9_CORPUS_STATUS_ARTIFACT_KIND)
        self.assertEqual(report["calibration_state"], CALIBRATION_STATE)
        self.assertFalse(report["calibrated"])
        self.assertFalse(report["empirical_active"])
        self.assertFalse(report["fitting_allowed"])
        self.assertEqual(report["counts"]["corpus_admissible"], 0)
        self.assertEqual(report["sample_gate"]["status"], INSUFFICIENT_CALIBRATION_EVIDENCE)
        self.assertEqual(report["sample_gate_progress"]["admissible"], "0/20")

    def test_corpus_status_counts_admissible_and_path_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "good.json").write_text(json.dumps(_prospective_receipt()), encoding="utf-8")
            (directory / "proof.json").write_text(
                json.dumps(
                    _prospective_receipt(
                        experiment_id="item9-fixture-obs-2",
                        raw_provenance_hash=EMPTY_RAW_KLINE_HASH,
                    )
                ),
                encoding="utf-8",
            )
            report = build_item9_corpus_status_report(directory)
        self.assertEqual(report["counts"]["corpus_admissible"], 1)
        self.assertEqual(report["counts"]["path_proof_only"], 1)
        self.assertEqual(len(report["session_dates_rth"]), 1)

    def test_cli_corpus_status_command(self) -> None:
        from item9_corpus_status import main  # type: ignore[import-not-found]

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "a.json").write_text(json.dumps(_prospective_receipt()), encoding="utf-8")
            buf = StringIO()
            with patch("sys.stdout", buf):
                code = main(["corpus-status", "--receipt-dir", str(directory)])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["counts"]["corpus_admissible"], 1)

    def test_cli_classify_invalid_receipt(self) -> None:
        from item9_corpus_status import main  # type: ignore[import-not-found]

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_bytes(b"\xff\xfe")
            code = main(["classify", "--receipt", str(bad)])
        self.assertEqual(code, 2)

    def test_validate_flags_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "bad.json").write_bytes(b"\xff\xfe")
            report = validate_item9_governed_receipt_dir(directory)
        self.assertEqual(report["verdict"], "INVALID")
        self.assertTrue(report["blockers"])


if __name__ == "__main__":
    unittest.main()
