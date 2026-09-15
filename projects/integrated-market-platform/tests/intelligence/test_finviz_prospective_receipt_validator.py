"""Finviz prospective catalyst watch receipt validator."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.finviz_prospective_receipt_validator import (  # noqa: E402
    REASON_EMPIRICAL_LOCK_PRESENT,
    REASON_FIXTURE_PROVENANCE,
    REASON_FIXTURE_SMOKE_NOT_PROSPECTIVE,
    REASON_INGRESS_OUTCOME_FAILED,
    REASON_CAMPAIGN_SLUG_UNSUPPORTED,
    REASON_MANIFEST_FINGERPRINT_MISMATCH,
    REASON_PROVIDER_MISSING,
    REASON_PUBLISHED_AFTER_RETRIEVAL,
    REASON_PUBLISHED_TIME_FUTURE,
    REASON_RUNTIME_SHA_MISSING,
    REASON_SIDECAR_ARTIFACT_HASH_MISMATCH,
    REASON_SIDECAR_EVIDENCE_CLASS_UPGRADE,
    REASON_ZERO_QUALIFYING_ROWS,
    VERDICT_INVALID,
    VERDICT_VALID,
    VERDICT_VALID_WITH_LIMITATIONS,
    validate_finviz_prospective_receipt,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (  # noqa: E402
    FTEP_V1_002_EXPECTED_FINGERPRINT,
)

_SESSIONS = ["fts-6DB7771FD9B3A991", "fts-D93189A042A1BEF2"]


def _live_summary() -> dict:
    return {
        "summary_id": "att-live-aapl",
        "instrument_id": "AAPL",
        "headline": "Apple reports earnings beat",
        "metadata": {
            "provider_id": "FINVIZ_ELITE",
            "source_id": "finviz_elite",
            "published_time": "2026-09-14T16:55:00Z",
            "retrieved_time": "2026-09-14T17:00:00.000000Z",
            "attention_data_kind": "LIVE_PROSPECTIVE",
        },
    }


def _prospective_base(**overrides: object) -> dict:
    payload: dict = {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_catalyst_watch_report",
        "campaign_slug": "FTEP-V1-002",
        "dry_run": True,
        "test_mode": "SIGNAL_ONLY",
        "watch_mode": "PROSPECTIVE_FINVIZ_INGRESS",
        "disposition": "PASS",
        "blockers": [],
        "campaign_status": {
            "us_equity_rth_open": True,
            "governed_session_count": 2,
            "empirical_lock_count": 0,
            "manifest_fingerprint": FTEP_V1_002_EXPECTED_FINGERPRINT,
        },
        "governed_session_ids": list(_SESSIONS),
        "attention_source": "live:finviz_elite_prospective",
        "attention_data_kind": "LIVE_PROSPECTIVE",
        "ingress_outcome": "LIVE_INGRESS_SUCCESS",
        "prospective_ingress": {
            "attempted": True,
            "ready": True,
            "reason": None,
            "source_label": "live:finviz_elite_prospective",
            "row_count": 1,
            "durable_lock": False,
            "test_mode": "SIGNAL_ONLY",
        },
        "summary_count": 1,
        "summaries": [_live_summary()],
        "secrets_included": False,
        "runtime_git_sha": "e0c7a9232daa49d21d07074f1764dfb683b2ec37",
    }
    payload.update(overrides)
    return payload


class FinvizProspectiveReceiptValidatorTests(unittest.TestCase):
    def test_valid_live_prospective(self) -> None:
        result = validate_finviz_prospective_receipt(_prospective_base())
        self.assertEqual(result["verdict"], VERDICT_VALID)
        self.assertTrue(result["prospective_observation_valid"])
        self.assertIsNone(result["program_gate_decision"])

    def test_valid_zero_rows_not_failed(self) -> None:
        report = _prospective_base(
            ingress_outcome="LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS",
            summary_count=0,
            summaries=[],
            prospective_ingress={
                "attempted": True,
                "ready": True,
                "reason": None,
                "source_label": "live:finviz_elite_prospective",
                "row_count": 0,
                "durable_lock": False,
                "test_mode": "SIGNAL_ONLY",
            },
        )
        result = validate_finviz_prospective_receipt(report)
        self.assertNotEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_ZERO_QUALIFYING_ROWS, result["reason_codes"])
        self.assertNotIn(REASON_INGRESS_OUTCOME_FAILED, result["reason_codes"])
        self.assertEqual(result["verdict"], VERDICT_VALID_WITH_LIMITATIONS)

    def test_fixture_mislabeled_prospective(self) -> None:
        report = _prospective_base(
            watch_mode="FIXTURE_SMOKE",
            attention_data_kind="LIVE_PROSPECTIVE",
            attention_source="artifacts/forward-test-campaigns/FTEP-V1-002/opportunity-attention-fixture.json",
            ingress_outcome=None,
        )
        result = validate_finviz_prospective_receipt(report)
        self.assertEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_FIXTURE_SMOKE_NOT_PROSPECTIVE, result["reason_codes"])
        self.assertIn(REASON_FIXTURE_PROVENANCE, result["reason_codes"])
        self.assertFalse(result["prospective_observation_valid"])

    def test_future_published_timestamp(self) -> None:
        summary = _live_summary()
        summary["metadata"]["published_time"] = "2099-01-01T12:00:00Z"
        report = _prospective_base(summaries=[summary])
        result = validate_finviz_prospective_receipt(report)
        self.assertEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_PUBLISHED_TIME_FUTURE, result["reason_codes"])

    def test_published_after_retrieval(self) -> None:
        summary = _live_summary()
        summary["metadata"]["published_time"] = "2026-09-14T18:00:00Z"
        summary["metadata"]["retrieved_time"] = "2026-09-14T17:00:00Z"
        report = _prospective_base(summaries=[summary])
        result = validate_finviz_prospective_receipt(report)
        self.assertEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_PUBLISHED_AFTER_RETRIEVAL, result["reason_codes"])

    def test_missing_provider(self) -> None:
        summary = _live_summary()
        summary["metadata"].pop("provider_id")
        report = _prospective_base(summaries=[summary])
        result = validate_finviz_prospective_receipt(report)
        self.assertEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_PROVIDER_MISSING, result["reason_codes"])

    def test_lock_present(self) -> None:
        report = _prospective_base(
            campaign_status={
                "us_equity_rth_open": True,
                "governed_session_count": 2,
                "empirical_lock_count": 1,
                "manifest_fingerprint": FTEP_V1_002_EXPECTED_FINGERPRINT,
            }
        )
        result = validate_finviz_prospective_receipt(report)
        self.assertEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_EMPIRICAL_LOCK_PRESENT, result["reason_codes"])

    def test_wrong_campaign(self) -> None:
        report = _prospective_base(campaign_slug="FTEP-V1-001")
        result = validate_finviz_prospective_receipt(report)
        self.assertEqual(result["verdict"], VERDICT_INVALID)
        self.assertIn(REASON_CAMPAIGN_SLUG_UNSUPPORTED, result["reason_codes"])

    def test_sidecar_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            report = _prospective_base(runtime_git_sha=None)
            path.write_text(json.dumps(report), encoding="utf-8")
            context = {
                "schema_version": "1.0.0",
                "artifact_sha256": "0" * 64,
                "runtime_git_sha": "abc123",
                "evidence_class": "LIVE_PROSPECTIVE",
            }
            result = validate_finviz_prospective_receipt(
                report,
                artifact_path=path,
                context=context,
            )
            self.assertIn(REASON_SIDECAR_ARTIFACT_HASH_MISMATCH, result["reason_codes"])
            self.assertEqual(result["verdict"], VERDICT_INVALID)

    def test_sidecar_cannot_upgrade_fixture_evidence(self) -> None:
        report = _prospective_base(
            watch_mode="FIXTURE_SMOKE",
            attention_data_kind="FIXTURE",
            attention_source="sample",
            ingress_outcome=None,
            runtime_git_sha=None,
        )
        context = {
            "runtime_git_sha": "abc123",
            "evidence_class": "LIVE_PROSPECTIVE",
        }
        result = validate_finviz_prospective_receipt(report, context=context)
        self.assertIn(REASON_SIDECAR_EVIDENCE_CLASS_UPGRADE, result["reason_codes"])

    def test_sidecar_supplies_runtime_sha(self) -> None:
        report = _prospective_base(runtime_git_sha=None)
        context = {"runtime_git_sha": "e0c7a9232daa49d21d07074f1764dfb683b2ec37"}
        result = validate_finviz_prospective_receipt(report, context=context)
        self.assertNotIn(REASON_RUNTIME_SHA_MISSING, result["reason_codes"])
        self.assertEqual(result["verdict"], VERDICT_VALID)

    def test_sidecar_hash_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            report = _prospective_base(runtime_git_sha=None)
            raw = json.dumps(report)
            path.write_text(raw, encoding="utf-8")
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
            context = {
                "artifact_sha256": digest,
                "runtime_git_sha": "e0c7a9232daa49d21d07074f1764dfb683b2ec37",
                "evidence_class": "LIVE_PROSPECTIVE",
            }
            result = validate_finviz_prospective_receipt(
                report,
                artifact_path=path,
                context=context,
            )
            self.assertEqual(result["verdict"], VERDICT_VALID)
            self.assertTrue(result["sidecar_applied"])


if __name__ == "__main__":
    unittest.main()
