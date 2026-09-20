"""High-value operator lifecycle / diagnostics boundary tests (Weekend Wave B Lane H).

Exercises truth tokens, evidence gaps, cycle freshness, governance refusal, and
worker diagnostic sanitization without manufacturing market evidence.
"""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from market_platform_foundation.execution.simulator import SIMULATOR_VERSION
from market_platform_foundation.intelligence.paper_forward_bridge.repository import ForwardTestRepositoryError
from market_platform_foundation.intelligence.paper_forward_bridge.types import (
    EvaluationState,
    ForwardTestDecision,
    ForwardTestEvidenceClass,
    ForwardTestMode,
    ForwardTestRunKind,
    ForwardTestState,
)
from market_platform_foundation.operating_modes import (
    live_execution_env_enabled,
    resolve_execution_authority,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (
    INSUFFICIENT_CALIBRATION_EVIDENCE,
    evaluate_sample_gate,
)
from market_platform_foundation.paper.calibration.persistence import persist_run_status
from market_platform_foundation.paper.calibration.runner import (
    STATUS_LIVE_FORBIDDEN,
    classify_calibration_run,
    run_calibration_campaign,
)
from market_platform_foundation.platform.operator_diagnostics.operator_truth import (
    OPERATOR_TRUTH_CLASSES,
    build_operator_truth_section,
    map_collector_truth,
    map_cycle_failure_truth,
    map_evidence_gaps_truth,
    map_item9_corpus_progress_truth,
    map_item9_disposition_truth,
    map_lifecycle_truth,
    map_live_execution_truth,
    map_readiness_truth,
    parse_item9_sample_gate_fraction,
    item9_corpus_progress_detail,
    next_safe_action_for_operator_row,
)
from market_platform_foundation.platform.operator_diagnostics.snapshot import (
    _FORBIDDEN_OPERATOR_ACTIONS,
    _READ_ONLY_OPERATOR_ACTIONS,
    _classify_session_evidence,
    _config_summary,
    _cycle_recovery_view,
    _evidence_gaps,
    _freshness_view,
    _governance_block,
    _operator_questions,
    _provider_rollups,
    _sanitize_collector_match_lines,
    _sanitize_mapping_paths,
    classify_item9_corpus_progress_truth,
)
from tools.validation_worker import sanitize_diagnostic

_CALIBRATION_DECISION_NS = 1_789_661_252_872_965_400


def _paper_calibration_decision() -> ForwardTestDecision:
    return ForwardTestDecision(
        forward_test_id="ftd-lane-h-boundary",
        session_id="fts-lane-h",
        account_id="paper-lane-h",
        mode="PAPER",
        run_kind=ForwardTestRunKind.FORWARD_TEST,
        test_mode=ForwardTestMode.EXECUTION,
        symbol="AAPL",
        decision_time_ns=_CALIBRATION_DECISION_NS,
        source_time_ns=_CALIBRATION_DECISION_NS - 1,
        state=ForwardTestState.LOCKED,
        direction="BUY",
        quantity=1,
        confidence=None,
        strategy_id="calibration",
        strategy_version="1",
        research_artifact_ref=None,
        evaluation_horizon_ns=3_600_000_000_000,
        decision_payload={"asset_class": "EQUITY"},
        provenance_snapshot={"simulator_version": SIMULATOR_VERSION},
        locked_at_ns=_CALIBRATION_DECISION_NS,
        evaluation_state=EvaluationState.PENDING,
        evidence_class=ForwardTestEvidenceClass.SOFTWARE_FIXTURE_ONLY,
        observations=(),
    )


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
        self.assertEqual(map_readiness_truth(None), "UNKNOWN")
        self.assertEqual(map_readiness_truth(""), "UNKNOWN")
        self.assertEqual(map_readiness_truth("READY"), "HEALTHY")
        self.assertEqual(map_readiness_truth("ACTION_REQUIRED"), "DEGRADED")
        self.assertNotEqual(map_readiness_truth("BLOCKED"), "HEALTHY")

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


class AdditionalTruthRefusalTests(unittest.TestCase):
    def test_partial_lifecycle_is_degraded_garbage_is_unknown(self) -> None:
        self.assertEqual(map_lifecycle_truth("PARTIAL"), "DEGRADED")
        self.assertEqual(map_lifecycle_truth("STOPPED"), "BLOCKED")
        self.assertEqual(map_lifecycle_truth("not-a-status"), "UNKNOWN")
        self.assertNotEqual(map_lifecycle_truth("not-a-status"), "HEALTHY")

    def test_collector_truth_does_not_invent_health_when_absent(self) -> None:
        self.assertEqual(map_collector_truth(detected=True, item9_disposition="NOT_RTH"), "HEALTHY")
        self.assertEqual(map_collector_truth(detected=False, item9_disposition="NOT_RTH"), "IDLE")
        self.assertEqual(map_collector_truth(detected=False, item9_disposition="READY_TO_COLLECT"), "NOT_OBSERVED")
        self.assertEqual(map_collector_truth(detected=False, item9_disposition=None), "NOT_OBSERVED")

    def test_cycle_failure_unknown_token_is_not_observed_or_healthy(self) -> None:
        self.assertEqual(map_cycle_failure_truth("OBSERVED"), "DEGRADED")
        self.assertEqual(map_cycle_failure_truth("NOT_OBSERVED"), "NOT_OBSERVED")
        self.assertEqual(map_cycle_failure_truth("MAYBE"), "UNKNOWN")
        self.assertEqual(map_cycle_failure_truth(None), "NOT_OBSERVED")
        self.assertNotEqual(map_cycle_failure_truth("MAYBE"), "HEALTHY")

    def test_zero_denominator_fraction_is_unknown_not_healthy(self) -> None:
        self.assertIsNone(parse_item9_sample_gate_fraction("2/0"))
        self.assertEqual(
            map_item9_corpus_progress_truth(
                {"availability": "AVAILABLE", "sample_gate_progress": {"distinct_rth_dates": "2/0"}}
            ),
            "UNKNOWN",
        )
        self.assertEqual(
            classify_item9_corpus_progress_truth(
                {"availability": "AVAILABLE", "sample_gate_progress": {"distinct_rth_dates": "1/0"}}
            ),
            "UNKNOWN",
        )

    def test_missing_corpus_availability_is_not_observed(self) -> None:
        self.assertEqual(map_item9_corpus_progress_truth({}), "NOT_OBSERVED")
        self.assertEqual(classify_item9_corpus_progress_truth({}), "NOT_OBSERVED")
        self.assertEqual(
            classify_item9_corpus_progress_truth(
                {"availability": "AVAILABLE", "sample_gate_progress": {"distinct_rth_dates": "UNKNOWN"}}
            ),
            "NOT_OBSERVED",
        )

    def test_truth_section_refuses_missing_sha_and_keeps_live_off_blocked(self) -> None:
        section = build_operator_truth_section(
            as_of_utc="2026-09-19T00:00:00+00:00",
            lifecycle_status="UNKNOWN",
            readiness_status=None,
            runtime_git_sha=None,
            item9_disposition="MYSTERY",
            item9_corpus_status={"availability": "AVAILABLE", "sample_gate_progress": {"distinct_rth_dates": "3/3"}},
            collector_detected=False,
            collector_probe_status=None,
            live_execution_env=False,
            expected_cycle_failure="WEIRD",
            cycle_gap_note=None,
            evidence_gaps=None,
        )
        self.assertEqual(section["by_id"]["imp-lifecycle"], "UNKNOWN")
        self.assertEqual(section["by_id"]["operator-readiness"], "UNKNOWN")
        self.assertEqual(section["by_id"]["runtime-sha"], "UNAVAILABLE")
        self.assertEqual(section["by_id"]["item9-preflight"], "UNKNOWN")
        self.assertEqual(section["by_id"]["item9-corpus"], "HEALTHY")
        self.assertEqual(section["by_id"]["collector"], "NOT_OBSERVED")
        self.assertEqual(section["by_id"]["live-execution"], "BLOCKED")
        self.assertEqual(section["by_id"]["expected-cycle"], "UNKNOWN")
        self.assertEqual(section["by_id"]["evidence-gaps"], "NOT_OBSERVED")
        self.assertNotEqual(section["by_id"]["item9-corpus"], "DEGRADED")
        corpus_row = next(row for row in section["rows"] if row["id"] == "item9-corpus")
        self.assertEqual(corpus_row["detail"], "3/3")
        self.assertIn("NOT CALIBRATED", corpus_row["next_safe_action"])
        self.assertIn("Do not enable Live", corpus_row["next_safe_action"])


class Item9UnavailableDetailHonestyTests(unittest.TestCase):
    def test_unavailable_corpus_is_not_collapsed_to_not_observed_or_two_of_three(self) -> None:
        corpus = {"availability": "UNAVAILABLE"}
        self.assertEqual(map_item9_corpus_progress_truth(corpus), "UNAVAILABLE")
        self.assertEqual(item9_corpus_progress_detail(corpus, "UNAVAILABLE"), "UNAVAILABLE")
        self.assertEqual(next_safe_action_for_operator_row("item9-corpus", "UNAVAILABLE"), (
            "Retry GET /operator/diagnostics. Keep Item 9 as UNAVAILABLE; "
            "do not mint 2/3, calibrate, or enable Live."
        ))


class StaleFreshRecoveryBoundaryTests(unittest.TestCase):
    def test_fresh_but_truncated_log_keeps_recovery_unknown(self) -> None:
        resilience = {
            "expected_cycle": {
                "collector_log_source": {
                    "availability": "AVAILABLE",
                    "freshness": "FRESH",
                    "truncated": True,
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
        self.assertEqual(cycle["collector_log_freshness"], "FRESH")
        self.assertEqual(cycle["collector_log_truncated"], True)
        self.assertEqual(cycle["recovery_observed"], "UNKNOWN")
        self.assertEqual(cycle["expected_cycle_failure"], "NOT_OBSERVED")

    def test_hung_epochs_are_observed_failure_not_recovery(self) -> None:
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
                    "hung_epochs_without_end": ["121031"],
                    "ended_epoch_count": 1,
                },
            }
        }
        cycle = _cycle_recovery_view({"disposition": "NOT_RTH"}, {"services": []}, resilience=resilience)
        self.assertEqual(cycle["expected_cycle_failure"], "OBSERVED")
        self.assertEqual(cycle["hung_epochs_without_end"], ["121031"])
        self.assertEqual(cycle["recovery_observed"], "NOT_OBSERVED")
        self.assertEqual(cycle["collector_log_freshness"], "FRESH")

    def test_missing_receipt_dir_is_observed_cycle_failure(self) -> None:
        resilience = {
            "expected_cycle": {
                "receipt_inventory": {"reason_code": "RECEIPT_DIR_MISSING"},
            }
        }
        cycle = _cycle_recovery_view({"disposition": "NOT_RTH"}, {"services": []}, resilience=resilience)
        self.assertEqual(cycle["expected_cycle_failure"], "OBSERVED")
        self.assertEqual(cycle["collector_log_freshness"], "NOT_OBSERVED")
        self.assertEqual(cycle["recovery_observed"], "NOT_OBSERVED")

    def test_freshness_defaults_and_live_metrics_only_when_available(self) -> None:
        hidden = _freshness_view(
            [{"provider": "ibkr_observational"}],
            {"available": False, "provider_summary": {"event_lag_ms_p50": 9}},
            {},
        )
        self.assertEqual(hidden["provider_rows"][0]["freshness"], "NOT_OBSERVED")
        self.assertEqual(hidden["live_feed_metrics"], "UNAVAILABLE")
        self.assertEqual(hidden["opportunity_feed_status"], "NOT_OBSERVED")

        shown = _freshness_view(
            [{"provider": "ibkr_observational", "freshness": "FRESH"}],
            {"available": True, "provider_summary": {"event_lag_ms_p50": 9}},
            {"feed_status": "READY"},
        )
        self.assertEqual(shown["provider_rows"][0]["freshness"], "FRESH")
        self.assertEqual(shown["live_feed_metrics"]["event_lag_ms_p50"], 9)
        self.assertEqual(shown["opportunity_feed_status"], "READY")


class LiveOffAndCalibrationForbiddenTests(unittest.TestCase):
    def test_only_literal_one_enables_live_env(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMP_LIVE_EXECUTION", None)
            self.assertFalse(live_execution_env_enabled())
        with patch.dict(os.environ, {"IMP_LIVE_EXECUTION": "true"}, clear=False):
            self.assertFalse(live_execution_env_enabled())
        with patch.dict(os.environ, {"IMP_LIVE_EXECUTION": "YES"}, clear=False):
            self.assertFalse(live_execution_env_enabled())
        with patch.dict(os.environ, {"IMP_LIVE_EXECUTION": "1"}, clear=False):
            self.assertTrue(live_execution_env_enabled())

    def test_live_env_on_is_degraded_and_still_cannot_enable_live_or_fit(self) -> None:
        with patch.dict(os.environ, {"IMP_LIVE_EXECUTION": "1"}, clear=False):
            block = _governance_block(
                lifecycle_status="HEALTHY",
                readiness_status="READY",
                item9_disposition="READY_TO_COLLECT",
                state_warnings=[],
                interventions=[],
            )
            self.assertTrue(block["live_execution_env"])
            self.assertIn("enable_live_execution", block["forbidden"])
            self.assertIn("auto_fit_item9_calibration", block["forbidden"])
            self.assertIn("merge_pr222", block["forbidden"])
            self.assertIn("mutate_prospective_receipt_or_corpus", block["forbidden"])
            self.assertEqual(map_live_execution_truth(True), "DEGRADED")
            self.assertNotEqual(map_live_execution_truth(True), "HEALTHY")

    def test_sample_gate_complete_does_not_authorize_calibration(self) -> None:
        section = {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": "3/3"},
            "calibration_state": "NOT_CALIBRATED",
            "fitting_allowed": False,
            "does_not_infer_calibrated": True,
        }
        self.assertEqual(classify_item9_corpus_progress_truth(section), "HEALTHY")
        self.assertNotEqual(classify_item9_corpus_progress_truth(section), "CALIBRATED")
        self.assertFalse(section["fitting_allowed"])
        self.assertTrue(section["does_not_infer_calibrated"])
        self.assertIn("auto_fit_item9_calibration", _FORBIDDEN_OPERATOR_ACTIONS)

    def test_calibration_runner_refuses_live_even_when_env_flag_is_set(self) -> None:
        status = classify_calibration_run(
            env={"IMP_LIVE_EXECUTION": "1"},
            now_ns=1_789_661_252_872_965_400,
            requested_mode="LIVE",
        )
        self.assertEqual(status, STATUS_LIVE_FORBIDDEN)

    def test_unknown_lifecycle_is_not_claimed_running(self) -> None:
        questions = _operator_questions(
            lifecycle={"status": "UNKNOWN"},
            runtime_sha="",
            item9={"disposition": "UNKNOWN"},
            readiness={"status": "UNKNOWN", "providers": []},
            config_summary={},
            state_path={},
            session={},
            freshness={},
            cycle={},
            evidence_gaps=[],
            governance={"allowed_read_only": [], "forbidden": list(_FORBIDDEN_OPERATOR_ACTIONS)},
        )
        self.assertFalse(questions["q01_imp_running"]["answer"])
        self.assertEqual(questions["q01_imp_running"]["detail"], "UNKNOWN")
        self.assertEqual(questions["q14_forbidden_actions"]["answer"], list(_FORBIDDEN_OPERATOR_ACTIONS))


class ContradictoryEvidenceBoundaryTests(unittest.TestCase):
    def test_ready_feed_does_not_inherit_stale_unready_reason(self) -> None:
        gaps = _evidence_gaps(
            {"feed_status": "READY", "unready_reason": "LIVE_AS_OF_UNAVAILABLE"},
            {"disposition": "READY_TO_COLLECT", "blockers": []},
        )
        self.assertEqual(gaps, [])

    def test_empty_feed_is_not_expected_not_unavailable(self) -> None:
        gaps = _evidence_gaps({"feed_status": "EMPTY"}, {"disposition": "NOT_RTH", "blockers": []})
        self.assertEqual(gaps[0]["gap_class"], "NOT_EXPECTED")
        self.assertEqual(gaps[0]["domain"], "opportunity_feed")
        self.assertNotEqual(gaps[0]["gap_class"], "UNAVAILABLE")

    def test_unknown_feed_does_not_fabricate_an_opportunity_gap(self) -> None:
        gaps = _evidence_gaps({"feed_status": "UNKNOWN"}, {"disposition": "NOT_RTH", "blockers": []})
        self.assertEqual(gaps, [])

    def test_unready_feed_and_wrong_runtime_keep_both_gap_domains(self) -> None:
        gaps = _evidence_gaps(
            {"feed_status": "UNREADY", "unready_reason": "QUALITY_SUMMARY_NOT_HEALTHY"},
            {"disposition": "WRONG_RUNTIME", "blockers": []},
        )
        by_domain = {row["domain"]: row["gap_class"] for row in gaps}
        self.assertEqual(by_domain["opportunity_feed"], "UNREADY")
        self.assertEqual(by_domain["runtime_authority"], "UNAVAILABLE")
        self.assertNotIn("item9_receipt_path", by_domain)

    def test_live_observational_does_not_upgrade_evidence_class(self) -> None:
        class _Store:
            mode = "LIVE"
            data_mode = "LIVE"
            execution_mode = "NONE"

        with patch(
            "market_platform_foundation.platform.operator_diagnostics.snapshot.projections.build_as_of_context",
            return_value={"mode": "LIVE", "data_mode": "LIVE", "execution_mode": "NONE"},
        ):
            session = _classify_session_evidence(
                _Store(),  # type: ignore[arg-type]
                {"disposition": "NOT_RTH", "active_collector": {"detected": False}},
            )
        self.assertEqual(session["primary_evidence_session_class"], "idle")
        self.assertIn("live_observational_surface", session["tags"])
        self.assertNotEqual(session["primary_evidence_session_class"], "empirical")
        self.assertNotIn("live_execution", session["primary_evidence_session_class"])

    def test_replay_plus_collector_keeps_empirical_and_tags_replay(self) -> None:
        class _Store:
            mode = "REPLAY"
            data_mode = "FIXTURE_REPLAY"
            execution_mode = "NONE"

        with patch(
            "market_platform_foundation.platform.operator_diagnostics.snapshot.projections.build_as_of_context",
            return_value={"mode": "REPLAY", "data_mode": "FIXTURE_REPLAY", "execution_mode": "NONE"},
        ):
            session = _classify_session_evidence(
                _Store(),  # type: ignore[arg-type]
                {"disposition": "READY_TO_COLLECT", "active_collector": {"detected": True}},
            )
        self.assertEqual(session["primary_evidence_session_class"], "empirical")
        self.assertIn("replay_data_mode_also_active", session["tags"])
        self.assertNotEqual(session["primary_evidence_session_class"], "replay")


class DiagnosticsSanitizationBoundaryTests(unittest.TestCase):
    def test_collector_summaries_cap_at_three_and_drop_cmdlines(self) -> None:
        lines = [
            "python tools/other_a.py password=one --path C:\\Users\\op\\.local\\a",
            "python tools/other_b.py token=two",
            "python tools/other_c.py secret=three",
            "python tools/other_d.py api_key=four",
        ]
        summaries = _sanitize_collector_match_lines(lines)
        self.assertEqual(len(summaries), 3)
        self.assertEqual(summaries, ["collector_process_match"] * 3)
        serialized = json.dumps(summaries)
        self.assertNotIn("password=", serialized)
        self.assertNotIn("one", serialized)
        self.assertNotIn("four", serialized)
        self.assertNotIn(".local", serialized)

    def test_config_summary_omits_provider_field_values(self) -> None:
        summary = _config_summary(
            {
                "schema_version": "operator-config/1.0",
                "providers": [
                    {
                        "provider": "moomoo",
                        "label": "Moomoo",
                        "fields": [
                            {"name": "api_key", "configured": True, "value": "not-a-real-key"},
                        ],
                    }
                ],
            }
        )
        serialized = json.dumps(summary)
        self.assertNotIn("not-a-real-key", serialized)
        self.assertEqual(summary["providers"][0]["fields_configured"], 1)
        self.assertNotIn("value", summary["providers"][0])


class Item9CorpusClassifierParityTests(unittest.TestCase):
    def _section(self, *, fraction: str) -> dict[str, object]:
        return {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": fraction},
            "report": {"sample_gate_progress": {"distinct_rth_dates": fraction}},
        }

    def test_map_and_classify_agree_on_two_of_three_idle(self) -> None:
        section = self._section(fraction="2/3")
        self.assertEqual(map_item9_corpus_progress_truth(section), "IDLE")
        self.assertEqual(classify_item9_corpus_progress_truth(section), "IDLE")
        self.assertNotEqual(classify_item9_corpus_progress_truth(section), "HEALTHY")

    def test_map_and_classify_agree_on_three_of_three_healthy_not_calibrated(self) -> None:
        section = self._section(fraction="3/3")
        self.assertEqual(map_item9_corpus_progress_truth(section), "HEALTHY")
        self.assertEqual(classify_item9_corpus_progress_truth(section), "HEALTHY")
        self.assertNotEqual(classify_item9_corpus_progress_truth(section), "CALIBRATED")

    def test_over_admitted_fraction_is_unknown_in_both_classifiers(self) -> None:
        section = self._section(fraction="4/3")
        self.assertEqual(map_item9_corpus_progress_truth(section), "UNKNOWN")
        self.assertEqual(classify_item9_corpus_progress_truth(section), "UNKNOWN")


class Item9CalibrationRunForbiddenContractTests(unittest.TestCase):
    def test_sample_gate_blocked_and_governance_forbids_auto_fit(self) -> None:
        gate = evaluate_sample_gate(
            [
                {
                    "observation_id": "a",
                    "signal_timestamp_ns": _CALIBRATION_DECISION_NS,
                    "corpus_admissible": True,
                    "inclusion_state": "INCLUDED",
                },
                {
                    "observation_id": "b",
                    "signal_timestamp_ns": _CALIBRATION_DECISION_NS + 86_400_000_000_000,
                    "corpus_admissible": True,
                    "inclusion_state": "INCLUDED",
                },
            ]
        )
        self.assertEqual(gate["status"], INSUFFICIENT_CALIBRATION_EVIDENCE)
        self.assertEqual(f"{gate['distinct_rth_dates']}/{gate['minimum_distinct_rth_dates']}", "2/3")
        self.assertFalse(gate["fitting_allowed"])
        self.assertTrue(gate["execution_claims_blocked"])
        self.assertIn("auto_fit_item9_calibration", _FORBIDDEN_OPERATOR_ACTIONS)
        self.assertIn("run_item9_corpus_status_read_only", _READ_ONLY_OPERATOR_ACTIONS)

    def test_governance_read_only_never_includes_forbidden_actions(self) -> None:
        block = _governance_block(
            lifecycle_status="HEALTHY",
            readiness_status="READY",
            item9_disposition="READY_TO_COLLECT",
            state_warnings=[],
            interventions=[],
        )
        allowed = set(block["allowed_read_only"])
        forbidden = set(block["forbidden"])
        self.assertFalse(allowed & forbidden)
        self.assertIn("run_item9_corpus_status_read_only", allowed)
        self.assertNotIn("auto_fit_item9_calibration", allowed)
        self.assertIn("enable_live_execution", forbidden)

    def test_worktree_state_mismatch_surfaces_in_governance_headline(self) -> None:
        block = _governance_block(
            lifecycle_status="HEALTHY",
            readiness_status="READY",
            item9_disposition="NOT_RTH",
            state_warnings=["WORKTREE_STATE_MISMATCH"],
            interventions=[],
        )
        self.assertIn("linked worktree", block["headline"])
        self.assertIn("canonical state dir", block["headline"])


class LiveAuthorityVsOperatorGovernanceTests(unittest.TestCase):
    def test_live_env_opt_in_authorizes_mode_but_operator_still_blocks(self) -> None:
        with patch.dict(os.environ, {"IMP_LIVE_EXECUTION": "1"}, clear=False):
            self.assertTrue(live_execution_env_enabled())
            self.assertEqual(resolve_execution_authority(requested_mode="LIVE"), "AUTHORIZED")
            self.assertEqual(map_live_execution_truth(True), "DEGRADED")
            block = _governance_block(
                lifecycle_status="HEALTHY",
                readiness_status="READY",
                item9_disposition="READY_TO_COLLECT",
                state_warnings=[],
                interventions=[],
            )
            self.assertTrue(block["live_execution_env"])
            self.assertIn("enable_live_execution", block["forbidden"])
            self.assertIn("auto_fit_item9_calibration", block["forbidden"])


class CalibrationPersistenceBoundaryTests(unittest.TestCase):
    def test_persist_run_status_refuses_live_forward_test_mode(self) -> None:
        repository = MagicMock()
        decision = _paper_calibration_decision()
        live_decision = replace(decision, mode="LIVE")
        with self.assertRaises(ForwardTestRepositoryError):
            persist_run_status(
                repository,
                decision=live_decision,
                status="WAITING_FOR_MARKET",
                detail={"orders_placed": False},
            )
        repository.put_decision.assert_not_called()

    def test_live_forbidden_campaign_persists_not_observable_status_label(self) -> None:
        repository = MagicMock()
        stored = _paper_calibration_decision()

        def _put(decision: ForwardTestDecision) -> None:
            nonlocal stored
            stored = decision

        def _get(_forward_test_id: str) -> ForwardTestDecision:
            return stored

        repository.put_decision.side_effect = _put
        repository.get_decision.side_effect = _get

        result = run_calibration_campaign(
            env={"IMP_LIVE_EXECUTION": "1"},
            now_ns=_CALIBRATION_DECISION_NS,
            requested_mode="LIVE",
            decision=stored,
            repository=repository,
        )
        self.assertEqual(result.status, STATUS_LIVE_FORBIDDEN)
        self.assertFalse(result.calibrated)
        self.assertEqual(len(stored.observations), 1)
        payload = stored.observations[0].payload
        self.assertEqual(payload["kind"], "CALIBRATION_RUN_STATUS")
        self.assertEqual(payload["observation_label"], "NOT_OBSERVABLE")
        self.assertFalse(payload["calibrated"])


class DiagnosticsPathSanitizationBoundaryTests(unittest.TestCase):
    def test_sanitize_mapping_paths_redacts_unc_and_windows_receipt_and_log(self) -> None:
        imp_root = Path(__file__).resolve().parents[2]
        host_receipt = r"\\filer\corp\item9-prospective-proof-receipts"
        host_log = r"C:\Users\operator\secret\item9-prospective-collector.log"
        cleaned = _sanitize_mapping_paths(
            {
                "receipt_dir": host_receipt,
                "collector_log_source": {"log_path": host_log, "availability": "AVAILABLE"},
                "receipt_inventory": {"receipt_dir": host_receipt},
            },
            imp_root=imp_root,
        )
        serialized = json.dumps(cleaned)
        self.assertEqual(cleaned["receipt_dir"], "<redacted>")
        self.assertEqual(cleaned["receipt_inventory"]["receipt_dir"], "<redacted>")
        self.assertEqual(cleaned["collector_log_source"]["log_path"], "<redacted>")
        self.assertNotIn("secret", serialized)
        self.assertNotIn("filer", serialized.lower())


class ValidationWorkerSanitizationTests(unittest.TestCase):
    def test_sanitize_diagnostic_redacts_credential_patterns(self) -> None:
        raw = "failed: api_key=not-a-real-key and Authorization: Bearer deadbeef"
        cleaned = sanitize_diagnostic(raw)
        self.assertNotIn("not-a-real-key", cleaned)
        self.assertNotIn("deadbeef", cleaned)
        self.assertIn("<redacted>", cleaned)

    def test_sanitize_diagnostic_redacts_password_and_keeps_non_secret_status(self) -> None:
        cleaned = sanitize_diagnostic("password=hunter2 status=FAILED")
        self.assertNotIn("hunter2", cleaned)
        self.assertIn("status=FAILED", cleaned)
        self.assertIn("<redacted>", cleaned)


if __name__ == "__main__":
    unittest.main()
