"""High-value operator lifecycle / diagnostics boundary tests (Weekend Wave B Lane H).

Exercises truth tokens, evidence gaps, cycle freshness, governance refusal, and
worker diagnostic sanitization without manufacturing market evidence.
"""

from __future__ import annotations

import json
import unittest

from market_platform_foundation.platform.operator_diagnostics.operator_truth import (
    OPERATOR_TRUTH_CLASSES,
    map_evidence_gaps_truth,
    map_item9_disposition_truth,
    map_lifecycle_truth,
    map_live_execution_truth,
    map_readiness_truth,
)
from market_platform_foundation.platform.operator_diagnostics.snapshot import (
    _FORBIDDEN_OPERATOR_ACTIONS,
    _cycle_recovery_view,
    _evidence_gaps,
    _freshness_view,
    _governance_block,
    _provider_rollups,
    _sanitize_collector_match_lines,
    classify_item9_corpus_progress_truth,
)
from tools.validation_worker import sanitize_diagnostic


class OperatorTruthBoundaryTests(unittest.TestCase):
    def test_lifecycle_unknown_maps_to_unknown_not_healthy(self) -> None:
        self.assertEqual(map_lifecycle_truth("UNKNOWN"), "UNKNOWN")
        self.assertEqual(map_lifecycle_truth(None), "UNKNOWN")
        self.assertNotEqual(map_lifecycle_truth("UNKNOWN"), "HEALTHY")

    def test_item9_disposition_refusal_tokens(self) -> None:
        self.assertEqual(map_item9_disposition_truth("WRONG_RUNTIME"), "BLOCKED")
        self.assertEqual(map_item9_disposition_truth("OUTPUT_PATH_INVALID"), "BLOCKED")
        self.assertEqual(map_item9_disposition_truth("PROVIDER_UNAVAILABLE"), "UNAVAILABLE")
        self.assertEqual(map_item9_disposition_truth("ACTIVE_COLLECTOR_EXISTS"), "DEGRADED")
        self.assertEqual(map_item9_disposition_truth("NOT_RTH"), "IDLE")
        self.assertEqual(map_item9_disposition_truth("READY_TO_COLLECT"), "HEALTHY")
        self.assertEqual(map_item9_disposition_truth("MYSTERY_DISPOSITION"), "UNKNOWN")

    def test_readiness_unknown_is_not_healthy(self) -> None:
        self.assertEqual(map_readiness_truth("BLOCKED"), "UNKNOWN")
        self.assertEqual(map_readiness_truth("READY"), "HEALTHY")
        self.assertEqual(map_readiness_truth("ACTION_REQUIRED"), "DEGRADED")

    def test_live_off_is_blocked_not_healthy(self) -> None:
        self.assertEqual(map_live_execution_truth(False), "BLOCKED")
        self.assertEqual(map_live_execution_truth(True), "DEGRADED")

    def test_evidence_gaps_truth_degraded_only_when_gaps_present(self) -> None:
        self.assertEqual(map_evidence_gaps_truth([]), "NOT_OBSERVED")
        self.assertEqual(
            map_evidence_gaps_truth([{"domain": "opportunity_feed", "gap_class": "UNREADY"}]),
            "DEGRADED",
        )

    def test_all_truth_classes_are_canonical_strings(self) -> None:
        for token in (
            map_lifecycle_truth("PARTIAL"),
            map_item9_disposition_truth("NOT_RTH"),
            map_live_execution_truth(False),
            map_evidence_gaps_truth([{"domain": "x"}]),
        ):
            self.assertIn(token, OPERATOR_TRUTH_CLASSES)


class Item9CorpusProgressBoundaryTests(unittest.TestCase):
    def test_malformed_gate_fraction_is_unknown(self) -> None:
        section = {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": "not-a-fraction"},
        }
        self.assertEqual(classify_item9_corpus_progress_truth(section), "UNKNOWN")

    def test_over_admitted_fraction_is_unknown(self) -> None:
        section = {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": "4/3"},
        }
        self.assertEqual(classify_item9_corpus_progress_truth(section), "UNKNOWN")

    def test_unavailable_corpus_availability(self) -> None:
        self.assertEqual(
            classify_item9_corpus_progress_truth({"availability": "UNAVAILABLE"}),
            "UNAVAILABLE",
        )


class DiagnosticsCompositionBoundaryTests(unittest.TestCase):
    def test_evidence_gaps_distinguish_unready_unavailable_and_authority(self) -> None:
        unready = _evidence_gaps(
            {"feed_status": "UNREADY", "unready_reason": "QUALITY_SUMMARY_NOT_HEALTHY"},
            {"disposition": "NOT_RTH", "blockers": []},
        )
        self.assertEqual(unready[0]["gap_class"], "UNREADY")

        unavailable = _evidence_gaps(
            {"feed_status": "UNREADY", "unready_reason": "LIVE_AS_OF_UNAVAILABLE"},
            {"disposition": "NOT_RTH", "blockers": []},
        )
        self.assertEqual(unavailable[0]["gap_class"], "UNAVAILABLE")

        contradictory = _evidence_gaps(
            {"feed_status": "READY"},
            {
                "disposition": "WRONG_RUNTIME",
                "blockers": ["OUTPUT_PATH_INVALID"],
            },
        )
        domains = {row["domain"] for row in contradictory}
        self.assertIn("runtime_authority", domains)
        self.assertIn("item9_receipt_path", domains)

    def test_cycle_recovery_stale_truncated_is_unknown_recovery(self) -> None:
        resilience = {
            "expected_cycle": {
                "collector_log_source": {
                    "availability": "AVAILABLE",
                    "freshness": "STALE",
                    "truncated": True,
                },
                "collector_log_gaps": {
                    "analysis_completeness": "PARTIAL_TAIL",
                    "missing_receipt_epochs": [{"epoch": "121031"}],
                    "hung_epochs_without_end": [],
                    "ended_epoch_count": 1,
                },
            }
        }
        cycle = _cycle_recovery_view({"disposition": "NOT_RTH"}, {"services": []}, resilience=resilience)
        self.assertEqual(cycle["expected_cycle_failure"], "OBSERVED")
        self.assertEqual(cycle["collector_log_freshness"], "STALE")
        self.assertEqual(cycle["recovery_observed"], "UNKNOWN")

    def test_cycle_recovery_clean_end_observes_recovery(self) -> None:
        resilience = {
            "expected_cycle": {
                "collector_log_source": {
                    "availability": "AVAILABLE",
                    "freshness": "FRESH",
                    "truncated": False,
                },
                "collector_log_gaps": {
                    "analysis_completeness": "FULL",
                    "missing_receipt_epochs": [],
                    "hung_epochs_without_end": [],
                    "ended_epoch_count": 2,
                },
            }
        }
        cycle = _cycle_recovery_view({"disposition": "READY_TO_COLLECT"}, {"services": []}, resilience=resilience)
        self.assertEqual(cycle["expected_cycle_failure"], "NOT_OBSERVED")
        self.assertEqual(cycle["collector_log_freshness"], "FRESH")
        self.assertEqual(cycle["recovery_observed"], "OBSERVED")

    def test_freshness_view_hides_live_metrics_when_unavailable(self) -> None:
        view = _freshness_view(
            [{"provider": "moomoo_observational", "freshness": "STALE"}],
            {"available": False, "provider_summary": {"event_lag_ms_p50": 12}},
            {"feed_status": "UNREADY", "unready_reason": "LIVE_AS_OF_UNAVAILABLE"},
        )
        self.assertEqual(view["provider_rows"][0]["freshness"], "STALE")
        self.assertEqual(view["live_feed_metrics"], "UNAVAILABLE")
        self.assertEqual(view["opportunity_feed_status"], "UNREADY")

    def test_provider_rollups_count_degraded_transport(self) -> None:
        rollup = _provider_rollups(
            [
                {"gate_state": "ENABLED", "transport_state": "CONNECTED"},
                {"gate_state": "ENABLED", "transport_state": "UNAVAILABLE"},
                {"gate_state": "DISABLED", "transport_state": "CONNECTED"},
            ]
        )
        self.assertEqual(rollup["healthy"], 1)
        self.assertEqual(rollup["degraded"], 1)
        self.assertEqual(rollup["blocked_or_disabled"], 1)

    def test_governance_forbids_calibration_fit_and_live_enable(self) -> None:
        block = _governance_block(
            lifecycle_status="HEALTHY",
            readiness_status="READY",
            item9_disposition="NOT_RTH",
            state_warnings=[],
            interventions=[],
        )
        self.assertIn("auto_fit_item9_calibration", block["forbidden"])
        self.assertIn("enable_live_execution", block["forbidden"])
        self.assertFalse(block["live_execution_env"])
        self.assertEqual(set(_FORBIDDEN_OPERATOR_ACTIONS), set(block["forbidden"]))

    def test_collector_match_sanitization_strips_secrets(self) -> None:
        lines = [
            "python tools/moomoo/opend_bar_1m_prospective_proof.py prospective --poll api_key=supersecret",
            "python other_collector.py token=abc123",
        ]
        summaries = _sanitize_collector_match_lines(lines)
        serialized = json.dumps(summaries)
        self.assertNotIn("supersecret", serialized)
        self.assertNotIn("abc123", serialized)
        self.assertIn("item9_prospective_poll_process", summaries)


class ValidationWorkerSanitizationTests(unittest.TestCase):
    def test_sanitize_diagnostic_redacts_credential_patterns(self) -> None:
        raw = "failed: api_key=not-a-real-key and Authorization: Bearer deadbeef"
        cleaned = sanitize_diagnostic(raw)
        self.assertNotIn("not-a-real-key", cleaned)
        self.assertNotIn("deadbeef", cleaned)
        self.assertIn("<redacted>", cleaned)


if __name__ == "__main__":
    unittest.main()
