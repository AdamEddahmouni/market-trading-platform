"""Operator diagnostics snapshot composition (Lane C)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.platform.operator_diagnostics import build_operator_diagnostics_snapshot
from market_platform_foundation.platform.operator_diagnostics.snapshot import (
    classify_item9_corpus_progress_truth,
    _is_windows_host_absolute,
    _operator_safe_fs_path,
    _public_runtime_resilience_section,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_SAMPLE_RESILIENCE = {
    "artifact_kind": "imp_runtime_resilience_diagnostic",
    "schema_version": "1.0.0",
    "observed_at_ns": 1,
    "evidence_class": "SOFTWARE",
    "runtime_identity": {
        "runtime_git_sha": "270ce2a6acdb975230495373613f1a65bfde8294",
        "frozen_collector_worktree_sha": "fed2d9f7",
        "frozen_collector_imp_root": "/worktrees/.imp-actual-01-phase-d",
        "runtime_matches_frozen_authority": False,
    },
    "provider_connectivity": {"state": "REACHABLE", "failure_class": "NONE"},
    "collector_process": {
        "active_collector_detected": False,
        "active_collector_matches": [
            "python tools/moomoo/opend_bar_1m_prospective_proof.py prospective --poll secret=abc123"
        ],
        "probe_status": "COMPLETED",
    },
    "item9_next_rth_preflight": {
        "disposition": "NOT_RTH",
        "blockers": [],
        "reason_codes": [],
    },
    "expected_cycle": {
        "receipt_inventory": {"availability": "AVAILABLE", "receipt_file_count": 0},
        "collector_log_gaps": None,
    },
    "readiness_vs_liveness": {"readiness": {}, "liveness": {}},
}


class OperatorDiagnosticsSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    @patch("tools.platform.control_service.build_control_status")
    @patch(
        "market_platform_foundation.platform.operator_diagnostics.snapshot.build_runtime_resilience_diagnostic",
    )
    def test_snapshot_schema_and_questions(self, mock_resilience, mock_lifecycle) -> None:
        mock_lifecycle.return_value = {
            "schema_version": "operator-lifecycle/1.1",
            "status": "HEALTHY",
            "services": [],
            "update": {"status": "UNAVAILABLE"},
        }
        mock_resilience.return_value = dict(_SAMPLE_RESILIENCE)
        payload = build_operator_diagnostics_snapshot(self.store)
        self.assertEqual(payload["schema_version"], "operator-diagnostics/1.0.0")
        self.assertFalse(payload["secrets_included"])
        questions = payload["operator_questions"]
        self.assertIn("q01_imp_running", questions)
        self.assertIn("q16_human_headline", questions)
        self.assertEqual(questions["q08_collector_active"]["process_probe_status"], "COMPLETED")
        resilience_section = payload["sections"]["runtime"]["runtime_resilience"]
        self.assertNotIn("active_collector_matches", resilience_section["collector_process"])
        self.assertEqual(resilience_section["collector_process"]["active_collector_match_count"], 1)
        summaries = resilience_section["collector_process"]["active_collector_match_summaries"]
        self.assertEqual(summaries, ["item9_prospective_poll_process"])
        serialized = json.dumps(payload).lower()
        self.assertNotIn("abc123", serialized)
        config_section = payload["sections"]["configuration"]["summary"]
        for row in config_section.get("providers", []):
            self.assertNotIn("value", row)
        frozen_root = payload["sections"]["runtime"]["item9_preflight"]["runtime"]["frozen_collector_imp_root"]
        self.assertEqual(frozen_root, ".imp-actual-01-phase-d")

    def test_item9_corpus_2_of_3_is_idle_not_degraded(self) -> None:
        section = {
            "availability": "AVAILABLE",
            "report": {
                "sample_gate_progress": {"distinct_rth_dates": "2/3"},
                "calibration_state": "NOT_CALIBRATED",
                "fitting_allowed": False,
                "calibrated": False,
            },
        }
        truth = classify_item9_corpus_progress_truth(section)
        self.assertEqual(truth, "IDLE")
        self.assertNotEqual(truth, "DEGRADED")

    def test_item9_corpus_3_of_3_is_healthy(self) -> None:
        section = {
            "availability": "AVAILABLE",
            "report": {
                "sample_gate_progress": {"distinct_rth_dates": "3/3"},
                "calibration_state": "NOT_CALIBRATED",
                "fitting_allowed": False,
                "calibrated": False,
            },
        }
        self.assertEqual(classify_item9_corpus_progress_truth(section), "HEALTHY")

    def test_snapshot_corpus_progress_truth_and_receipt_dir_redaction(self) -> None:
        host_receipt = r"C:\Users\adame\Desktop\secret-host\item9-prospective-proof-receipts"
        report = {
            "receipt_dir": host_receipt,
            "calibration_state": "NOT_CALIBRATED",
            "fitting_allowed": False,
            "calibrated": False,
            "sample_gate_progress": {"distinct_rth_dates": "2/3"},
        }
        resilience = dict(_SAMPLE_RESILIENCE)
        resilience["expected_cycle"] = {
            "receipt_dir": host_receipt,
            "receipt_inventory": {"availability": "AVAILABLE", "receipt_dir": host_receipt, "receipt_file_count": 0},
            "collector_log_gaps": None,
        }
        with (
            patch("tools.platform.control_service.build_control_status") as mock_lifecycle,
            patch(
                "market_platform_foundation.platform.operator_diagnostics.snapshot.build_runtime_resilience_diagnostic",
            ) as mock_resilience,
            patch(
                "market_platform_foundation.platform.operator_diagnostics.snapshot._item9_corpus_status_section",
            ) as mock_corpus,
        ):
            mock_lifecycle.return_value = {
                "schema_version": "operator-lifecycle/1.1",
                "status": "HEALTHY",
                "services": [],
                "update": {"status": "UNAVAILABLE"},
            }
            mock_resilience.return_value = resilience
            mock_corpus.return_value = {
                "availability": "AVAILABLE",
                "receipt_scope": "FROZEN_COLLECTOR_WORKTREE_READ_ONLY",
                "receipt_dir": "<redacted>",
                "report": {
                    **report,
                    "receipt_dir": "<redacted>",
                },
                "progress_truth": "IDLE",
                "does_not_infer_calibrated": True,
            }
            payload = build_operator_diagnostics_snapshot(self.store)
        corpus = payload["sections"]["runtime"]["item9_corpus_status"]
        self.assertEqual(corpus["progress_truth"], "IDLE")
        self.assertNotEqual(corpus["progress_truth"], "DEGRADED")
        self.assertEqual(corpus["receipt_dir"], "<redacted>")
        self.assertEqual(corpus["report"]["receipt_dir"], "<redacted>")
        serialized = json.dumps(payload)
        self.assertNotIn("secret-host", serialized)
        self.assertNotIn(host_receipt, serialized)
        cycle = payload["sections"]["runtime"]["runtime_resilience"]["expected_cycle"]
        self.assertEqual(cycle["receipt_dir"], "<redacted>")
        self.assertEqual(cycle["receipt_inventory"]["receipt_dir"], "<redacted>")

    def test_operator_safe_fs_path_redacts_host_absolute(self) -> None:
        imp_root = Path(__file__).resolve().parents[2]
        redacted = _operator_safe_fs_path(
            r"C:\Users\adame\Desktop\secret-host\item9-prospective-proof-receipts",
            imp_root=imp_root,
        )
        self.assertEqual(redacted, "<redacted>")
        frozen = _operator_safe_fs_path(
            r"C:\Users\adame\Desktop\market-trading-platform\.imp-actual-01-phase-d\projects\integrated-market-platform\artifacts\ftep-v1-002\item9-prospective-proof-receipts",
            imp_root=imp_root,
        )
        self.assertEqual(
            frozen,
            ".imp-actual-01-phase-d/projects/integrated-market-platform/artifacts/ftep-v1-002/item9-prospective-proof-receipts",
        )

    def test_windows_absolute_receipt_dir_redacted_on_posix_cwd(self) -> None:
        """CI leak: POSIX Path.resolve() of C:\\Users\\… under IMP cwd looked in-repo."""

        host_receipt = r"C:\Users\adame\Desktop\secret-host\item9-prospective-proof-receipts"
        self.assertTrue(_is_windows_host_absolute(host_receipt, host_receipt.replace("\\", "/")))
        self.assertTrue(_is_windows_host_absolute("C:/Users/adame/Desktop/secret-host", "C:/Users/adame/Desktop/secret-host"))
        self.assertTrue(_is_windows_host_absolute(r"\\filer\share\item9", "//filer/share/item9"))

        imp_root = Path(__file__).resolve().parents[2]
        previous = Path.cwd()
        try:
            os.chdir(imp_root)
            redacted = _operator_safe_fs_path(host_receipt, imp_root=imp_root)
        finally:
            os.chdir(previous)
        self.assertEqual(redacted, "<redacted>")
        self.assertNotIn("secret-host", redacted)

        resilience = dict(_SAMPLE_RESILIENCE)
        resilience["expected_cycle"] = {
            "receipt_dir": host_receipt,
            "receipt_inventory": {"availability": "AVAILABLE", "receipt_dir": host_receipt},
            "collector_log_gaps": None,
        }
        public = _public_runtime_resilience_section(resilience, imp_root=imp_root)
        cycle = public["expected_cycle"]
        self.assertEqual(cycle["receipt_dir"], "<redacted>")
        self.assertEqual(cycle["receipt_inventory"]["receipt_dir"], "<redacted>")
        self.assertNotIn("secret-host", json.dumps(public))
        if sys.platform != "win32":
            self.assertNotIn("C:", json.dumps(public))

    def test_corpus_section_sanitizes_report_receipt_dir(self) -> None:
        from market_platform_foundation.platform.operator_diagnostics.snapshot import (
            _item9_corpus_status_section,
        )
        from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (
            DEFAULT_RECEIPT_DIR,
        )

        host_receipt = r"C:\Users\adame\Desktop\secret-host\item9-receipts"
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp) / "projects" / "integrated-market-platform"
            frozen_imp = Path(tmp) / ".imp-actual-01-phase-d" / "projects" / "integrated-market-platform"
            receipt_dir = frozen_imp / DEFAULT_RECEIPT_DIR
            receipt_dir.mkdir(parents=True)
            with (
                patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight.resolve_frozen_collector_imp_root",
                    return_value=frozen_imp,
                ),
                patch(
                    "market_platform_foundation.paper.calibration.item9_calibration_protocol.build_item9_corpus_status_report",
                    return_value={
                        "receipt_dir": host_receipt,
                        "calibration_state": "NOT_CALIBRATED",
                        "fitting_allowed": False,
                        "calibrated": False,
                        "sample_gate_progress": {"distinct_rth_dates": "3/3"},
                    },
                ),
            ):
                section = _item9_corpus_status_section(imp_root)
        self.assertEqual(section["progress_truth"], "HEALTHY")
        self.assertEqual(section["receipt_dir"].replace("\\", "/").startswith(".imp-actual-01-phase-d/"), True)
        self.assertEqual(section["report"]["receipt_dir"], "<redacted>")
        self.assertNotIn("secret-host", json.dumps(section))

    def test_endpoint_registered_in_route_policy(self) -> None:
        from market_platform_foundation.platform.security.route_policy import policy_for_route

        policy = policy_for_route("GET", "/operator/diagnostics")
        self.assertEqual(policy.capability, "state.read")


if __name__ == "__main__":
    unittest.main()
