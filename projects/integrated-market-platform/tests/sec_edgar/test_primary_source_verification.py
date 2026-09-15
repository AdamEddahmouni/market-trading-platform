"""SEC EDGAR primary-source verification (fixture-only)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.research.public_record_primary_source import (  # noqa: E402
    PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY,
    PublicRecordDomain,
    verify_market_trackers_row,
)
from market_platform_foundation.sec_edgar.primary_verification import (  # noqa: E402
    verify_sec_insider_row_against_submissions,
)
from market_platform_foundation.sec_edgar.submission_lookup import (  # noqa: E402
    edgar_primary_mapping_for_accession,
    find_accession_index,
)

_FIXTURES = ROOT / "tests" / "fixtures"
_MT = _FIXTURES / "market_trackers" / "sec_insider"
_SEC = _FIXTURES / "sec_edgar"
_OBSERVED = "2026-09-14T12:00:00Z"


class SecPrimarySourceVerificationTests(unittest.TestCase):
    def test_acceptance_label_constant(self) -> None:
        self.assertEqual(
            PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY,
            "PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY",
        )

    def test_submission_lookup_finds_form4_accession(self) -> None:
        submissions = json.loads((_SEC / "submissions_nvda_slice.json").read_text(encoding="utf-8"))
        index = find_accession_index(submissions, "0001045810-25-000011")
        self.assertIsNotNone(index)
        mapping = edgar_primary_mapping_for_accession(
            submissions,
            "0001045810-25-000011",
            observed_time=_OBSERVED,
        )
        self.assertEqual(mapping["filing_date"], "2025-01-16")
        self.assertIn("acceptance_datetime", mapping)

    def test_verify_insider_row_without_market_trackers_payload(self) -> None:
        row = json.loads((_MT / "form4_open_market_purchase.json").read_text(encoding="utf-8"))
        submissions = (_SEC / "submissions_nvda_slice.json").read_bytes()
        result = verify_sec_insider_row_against_submissions(
            row,
            submissions_payload=submissions,
            observed_time=_OBSERVED,
        )
        self.assertEqual(result.status, "VERIFIED_PRIMARY_SUBMISSIONS")
        self.assertEqual(result.evidence_class, "SOFTWARE/FIXTURE/REPLAY")
        self.assertIn("EDGAR_SUBMISSIONS_MATCHED", result.reconcile_hints)
        self.assertTrue(result.provenance.primary_url.startswith("https://www.sec.gov/"))
        self.assertEqual(result.provenance.document_identifier, "0001045810-25-000011")

    def test_pipeline_emits_artifact_with_provenance(self) -> None:
        row = json.loads((_MT / "form4_open_market_purchase.json").read_text(encoding="utf-8"))
        envelope = verify_market_trackers_row(
            PublicRecordDomain.SEC_INSIDER,
            row,
            observed_time=_OBSERVED,
            submissions_payload=(_SEC / "submissions_nvda_slice.json").read_bytes(),
        )
        artifact = envelope["artifact"]
        self.assertEqual(
            artifact["artifact_type"],
            "PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_ARTIFACT",
        )
        self.assertEqual(artifact["realtime_congressional_feed_claim"], "NOT_CLAIMED")
        self.assertIn("content_sha256", artifact)
        prov = artifact["verification"]["provenance"]
        self.assertIn("parser_version", prov)
        self.assertIn("submissions_hash_sha256", prov)

    def test_missing_accession_in_submissions_fails_closed(self) -> None:
        row = json.loads((_MT / "form4_open_market_purchase.json").read_text(encoding="utf-8"))
        row = dict(row)
        row["accessionNumber"] = "0001045810-25-999999"
        with self.assertRaises(ValueError):
            verify_sec_insider_row_against_submissions(
                row,
                submissions_payload=(_SEC / "submissions_nvda_slice.json").read_bytes(),
                observed_time=_OBSERVED,
            )


if __name__ == "__main__":
    unittest.main()
