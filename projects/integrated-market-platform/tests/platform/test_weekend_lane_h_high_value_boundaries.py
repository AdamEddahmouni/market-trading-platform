"""Weekend Lane H: high-value fail-closed boundaries (software fixtures only).

Covers lifecycle-adjacent tokens, UNKNOWN/refusal, stale vs fresh, Item 9
sample-gate 2/3 vs 3/3 without claiming calibration, Live OFF, provider
UNKNOWN, missing/contradictory evidence tokens, session/auth failures,
diagnostics redaction, and persistence/restart side-effect refusals.

Does not contact collectors, mutate receipts, enable Live, or merge #222.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.operating_modes import (  # noqa: E402
    live_execution_env_enabled,
    resolve_execution_authority,
)
from market_platform_foundation.operations.runtime_resilience_diagnostic import (  # noqa: E402
    build_runtime_resilience_diagnostic,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    CALIBRATION_STATE,
    INSUFFICIENT_CALIBRATION_EVIDENCE,
    ITEM9_STATUS_NOT_CALIBRATED,
    MINIMUM_DISTINCT_RTH_DATES,
    evaluate_sample_gate,
    session_date_et,
)
from market_platform_foundation.paper.calibration.runner import (  # noqa: E402
    STATUS_LIVE_FORBIDDEN,
    classify_calibration_run,
)
from market_platform_foundation.platform.security.access_control import (  # noqa: E402
    AuthorizationErrorCode,
    AuthorizationFailure,
    authenticate_session_token,
    login_principal,
    reset_principal_registry_for_tests,
)
from market_platform_foundation.platform.security.auth_config import (  # noqa: E402
    AuthConfig,
    AuthEnforcementMode,
)
from market_platform_foundation.platform.security.redaction import (  # noqa: E402
    REDACTED,
    build_log_line,
    redact_log_line,
    redact_mapping,
)
from market_platform_foundation.platform.security.sessions import (  # noqa: E402
    SessionStore,
    get_session_store,
)
from market_platform_foundation.providers.equity_quote_selection import (  # noqa: E402
    OpenDReadiness,
)
from market_platform_foundation.providers.resilience import (  # noqa: E402
    HEALTHY,
    OPEND_REACHABLE,
    ProviderSessionState,
    classify_opend_connectivity,
    classify_provider_incident,
    note_disconnect,
    note_process_restart,
    note_reconnect,
)
from market_platform_foundation.ui_api.errors import (  # noqa: E402
    CanonicalErrorCategory,
    canonical_error_category,
)
from market_platform_foundation.ui_api.request_auth import (  # noqa: E402
    authorization_http_status,
    extract_session_token,
)
from market_platform_foundation.platform.operator_diagnostics.operator_truth import (  # noqa: E402
    build_operator_truth_section,
    item9_corpus_progress_detail,
    map_item9_corpus_progress_truth,
    next_safe_action_for_operator_row,
)

DAY_NS = 86_400 * 1_000_000_000
# Lawful RTH fixture timestamp (same geometry as Item 9 protocol tests).
SIGNAL_NS = 1_789_661_252_872_965_400
PRINCIPALS_FIXTURE = ROOT / "fixtures" / "auth" / "principals.json"


def _gate_rows(*, dates: int, per_date: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for day in range(dates):
        for index in range(per_date):
            rows.append(
                {
                    "observation_id": f"d{day}-n{index}",
                    "signal_timestamp_ns": SIGNAL_NS + day * DAY_NS + index,
                    "corpus_admissible": True,
                    "inclusion_state": "INCLUDED",
                }
            )
    return rows


class Item9SampleGateIdleVsMetTests(unittest.TestCase):
    def test_two_of_three_rth_dates_remain_insufficient_and_uncalibrated(self) -> None:
        rows = _gate_rows(dates=2, per_date=13)
        dates = {session_date_et(int(row["signal_timestamp_ns"])) for row in rows}
        self.assertEqual(len(dates), 2)
        self.assertEqual(MINIMUM_DISTINCT_RTH_DATES, 3)
        gate = evaluate_sample_gate(rows)
        self.assertEqual(gate["status"], INSUFFICIENT_CALIBRATION_EVIDENCE)
        self.assertEqual(gate["distinct_rth_dates"], 2)
        self.assertEqual(gate["minimum_distinct_rth_dates"], 3)
        self.assertEqual(f"{gate['distinct_rth_dates']}/{gate['minimum_distinct_rth_dates']}", "2/3")
        self.assertFalse(gate["calibrated"])
        self.assertFalse(gate["fitting_allowed"])
        self.assertTrue(gate["execution_claims_blocked"])
        self.assertNotEqual(gate["status"], "SAMPLE_GATE_MET")
        self.assertNotEqual(gate["status"], HEALTHY)

    def test_three_of_three_dates_can_meet_sample_gate_without_calibrating(self) -> None:
        rows = _gate_rows(dates=3, per_date=9)
        dates = {session_date_et(int(row["signal_timestamp_ns"])) for row in rows}
        self.assertEqual(len(dates), 3)
        gate = evaluate_sample_gate(rows)
        self.assertEqual(gate["status"], "SAMPLE_GATE_MET")
        self.assertEqual(f"{gate['distinct_rth_dates']}/{gate['minimum_distinct_rth_dates']}", "3/3")
        self.assertFalse(gate["calibrated"])
        self.assertFalse(gate["fitting_allowed"])
        self.assertEqual(CALIBRATION_STATE, "NOT_CALIBRATED")
        self.assertEqual(ITEM9_STATUS_NOT_CALIBRATED, "PARTIAL_NOT_CALIBRATED")


class LiveOffAndCalibrationProhibitionTests(unittest.TestCase):
    def test_live_execution_env_defaults_off_and_blocks_authority(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("IMP_LIVE_EXECUTION", None)
            self.assertFalse(live_execution_env_enabled())
            self.assertEqual(resolve_execution_authority(requested_mode="LIVE"), "BLOCKED")

    def test_live_opt_in_does_not_change_default_when_unset(self) -> None:
        with patch.dict(os.environ, {"IMP_LIVE_EXECUTION": "0"}, clear=False):
            self.assertFalse(live_execution_env_enabled())
            self.assertEqual(resolve_execution_authority(requested_mode="LIVE"), "BLOCKED")

    def test_calibration_runner_refuses_live_mode(self) -> None:
        status = classify_calibration_run(env={}, now_ns=SIGNAL_NS, requested_mode="LIVE")
        self.assertEqual(status, STATUS_LIVE_FORBIDDEN)
        self.assertEqual(canonical_error_category("LIVE_OBSERVATIONAL_DISABLED"), CanonicalErrorCategory.MODE_BLOCKED)


class ProviderUnknownStaleRestartTests(unittest.TestCase):
    def test_unknown_incident_does_not_fabricate_health_or_enable_live(self) -> None:
        incident = classify_provider_incident({})
        snapshot = incident.to_dict()
        self.assertEqual(incident.status_token, "UNKNOWN")
        self.assertEqual(snapshot["item9_mode"], "IDLE")
        self.assertEqual(snapshot["item9_sample_gate"], "2/3")
        self.assertEqual(snapshot["item9_calibration"], "NOT_CALIBRATED")
        self.assertEqual(snapshot["live_execution"], "OFF")
        self.assertFalse(incident.fallback.overlay_as_hop_l1)
        self.assertNotIn("DEGRADED", snapshot["item9_mode"])

    def test_opend_reachable_does_not_promote_item9_to_healthy_or_calibrated(self) -> None:
        incident = classify_opend_connectivity(
            OpenDReadiness(host="127.0.0.1", port=11111, loopback=True, reachable=True)
        )
        snapshot = incident.to_dict()
        self.assertEqual(incident.status_token, OPEND_REACHABLE)
        self.assertEqual(snapshot["item9_mode"], "IDLE")
        self.assertEqual(snapshot["item9_sample_gate"], "2/3")
        self.assertEqual(snapshot["item9_calibration"], "NOT_CALIBRATED")
        self.assertEqual(snapshot["live_execution"], "OFF")

    def test_non_loopback_opend_is_blocked_not_substituted(self) -> None:
        incident = classify_opend_connectivity(
            OpenDReadiness(host="8.8.8.8", port=11111, loopback=False, reachable=True)
        )
        snapshot = incident.to_dict()
        self.assertEqual(incident.status_token, "OPEND_NON_LOOPBACK_BLOCKED")
        self.assertFalse(incident.fallback.overlay_as_hop_l1)
        self.assertEqual(snapshot["live_execution"], "OFF")
        self.assertEqual(snapshot["item9_mode"], "IDLE")

    def test_restart_recovery_is_a_new_generation_not_prior_quotes(self) -> None:
        healthy = ProviderSessionState(generation=1, connected=True, status_token=HEALTHY)
        dropped = note_disconnect(healthy)
        self.assertEqual(dropped.generation, 1)
        self.assertFalse(dropped.connected)
        recovered = note_reconnect(dropped)
        self.assertEqual(recovered.generation, 2)
        restarted = note_process_restart(recovered)
        self.assertEqual(restarted.generation, 3)
        self.assertFalse(restarted.connected)
        self.assertEqual(restarted.status_token, "RESTART_RECOVERY")

    def test_classify_does_not_write_receipts_or_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            before = {path.name for path in Path(tmp).iterdir()}
            classify_provider_incident({"scenario": "timeout"})
            after = {path.name for path in Path(tmp).iterdir()}
            self.assertEqual(before, after)


class DiagnosticSanitizationAndSideEffectTests(unittest.TestCase):
    def test_redaction_strips_tokens_from_mappings_and_log_lines(self) -> None:
        payload = redact_mapping(
            {
                "api_key": "secret-live-key",
                "nested": {"Authorization": "Bearer abc.def"},
                "symbol": "AAPL",
            }
        )
        self.assertEqual(payload["api_key"], REDACTED)
        self.assertEqual(payload["nested"]["Authorization"], REDACTED)
        self.assertEqual(payload["symbol"], "AAPL")
        line = redact_log_line('opend poll token=supersecret path=C:\\Users\\op\\.local')
        self.assertNotIn("supersecret", line)
        self.assertIn(REDACTED, line)
        built = build_log_line("operator.diag", fields={"session_token": "tok-1", "host": "127.0.0.1"})
        self.assertNotIn("tok-1", built)
        self.assertIn(REDACTED, built)

    def test_runtime_diagnostic_probe_does_not_start_collectors_or_enable_live(self) -> None:
        calls: list[int] = []

        def probe() -> tuple[bool, list[str]]:
            calls.append(1)
            return False, []

        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            receipt_dir = imp_root / "receipts"
            receipt_dir.mkdir()
            before = list(receipt_dir.iterdir())
            report = build_runtime_resilience_diagnostic(
                imp_root,
                receipt_dir=receipt_dir,
                active_collector_probe=probe,
            )
            after = list(receipt_dir.iterdir())
        self.assertEqual(calls, [1])
        self.assertEqual(before, after)
        self.assertFalse(report["collector_process"]["active_collector_detected"])
        connectivity = report["provider_connectivity"]
        self.assertEqual(connectivity["live_execution"], "OFF")
        self.assertEqual(connectivity["item9_mode"], "IDLE")
        self.assertEqual(connectivity["item9_calibration"], "NOT_CALIBRATED")
        self.assertEqual(report["evidence_class"], "SOFTWARE")


class SessionAuthFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_principal_registry_for_tests()
        self._env_backup = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        reset_principal_registry_for_tests()

    def test_extract_session_token_refuses_blank_and_non_bearer(self) -> None:
        self.assertIsNone(extract_session_token({}))
        self.assertIsNone(extract_session_token({"Authorization": "Bearer "}))
        self.assertIsNone(extract_session_token({"Authorization": "Basic abc"}))
        self.assertEqual(extract_session_token({"Authorization": "Bearer tok-ok"}), "tok-ok")
        self.assertEqual(extract_session_token({"X-IMP-Session": " header-tok "}), "header-tok")

    def test_enforced_mode_missing_and_expired_sessions_fail_closed(self) -> None:
        os.environ["IMP_AUTH_ENFORCEMENT_MODE"] = "ENFORCED"
        os.environ["IMP_AUTH_PRINCIPALS_PATH"] = str(PRINCIPALS_FIXTURE)
        os.environ["IMP_AUTH_SESSION_TTL_SECONDS"] = "60"
        missing = authenticate_session_token(None)
        self.assertIsInstance(missing, AuthorizationFailure)
        self.assertEqual(missing.code, AuthorizationErrorCode.AUTH_REQUIRED)
        self.assertEqual(authorization_http_status(missing), HTTPStatus.UNAUTHORIZED)
        self.assertEqual(canonical_error_category("AUTH_REQUIRED"), CanonicalErrorCategory.AUTH_ERROR)

        bogus = authenticate_session_token("not-a-session")
        self.assertIsInstance(bogus, AuthorizationFailure)
        self.assertEqual(bogus.code, AuthorizationErrorCode.AUTH_INVALID)
        self.assertEqual(canonical_error_category("AUTH_INVALID"), CanonicalErrorCategory.AUTH_ERROR)

        login = login_principal(principal_id="canary-viewer", secret="canary-viewer-secret")
        self.assertNotIsInstance(login, AuthorizationFailure)
        session, _principal = login
        store = get_session_store()
        self.assertIsNone(store.get(session.token, now_ns=session.expires_at_ns + 1))
        gone = authenticate_session_token(session.token)
        self.assertIsInstance(gone, AuthorizationFailure)
        self.assertEqual(gone.code, AuthorizationErrorCode.AUTH_INVALID)

    def test_capability_denied_is_forbidden_not_internal(self) -> None:
        failure = AuthorizationFailure(AuthorizationErrorCode.CAPABILITY_DENIED, "nope")
        self.assertEqual(authorization_http_status(failure), HTTPStatus.FORBIDDEN)
        self.assertEqual(canonical_error_category("CAPABILITY_DENIED"), CanonicalErrorCategory.AUTH_ERROR)


class TaxonomyUnknownAndStaleTests(unittest.TestCase):
    def test_empty_reason_stays_internal_unknown_not_success(self) -> None:
        self.assertEqual(canonical_error_category(""), CanonicalErrorCategory.INTERNAL_ERROR)
        self.assertEqual(canonical_error_category("STALE_PREVIEW"), CanonicalErrorCategory.STALE_DATA)
        self.assertEqual(canonical_error_category("PARTIALLY_STALE"), CanonicalErrorCategory.STALE_DATA)

    def test_enforced_auth_config_object_still_requires_token(self) -> None:
        cfg = AuthConfig(
            enforcement_mode=AuthEnforcementMode.ENFORCED,
            principals_path=str(PRINCIPALS_FIXTURE),
            session_ttl_seconds=60,
        )
        result = authenticate_session_token("", config=cfg, store=SessionStore())
        self.assertIsInstance(result, AuthorizationFailure)
        self.assertEqual(result.code, AuthorizationErrorCode.AUTH_REQUIRED)


class OperatorTruthUnavailableDoesNotMintItem9Tests(unittest.TestCase):
    def test_unavailable_diagnostics_keep_item9_unavailable_not_two_of_three(self) -> None:
        corpus = {"availability": "UNAVAILABLE"}
        self.assertEqual(map_item9_corpus_progress_truth(corpus), "UNAVAILABLE")
        self.assertEqual(item9_corpus_progress_detail(corpus, "UNAVAILABLE"), "UNAVAILABLE")
        self.assertNotEqual(item9_corpus_progress_detail(corpus, "UNAVAILABLE"), "2/3")
        section = build_operator_truth_section(
            as_of_utc="2026-09-19T00:00:00+00:00",
            lifecycle_status="UNKNOWN",
            readiness_status=None,
            runtime_git_sha=None,
            item9_disposition="UNKNOWN",
            item9_corpus_status=corpus,
            collector_detected=False,
            collector_probe_status=None,
            live_execution_env=False,
            expected_cycle_failure="NOT_OBSERVED",
            cycle_gap_note=None,
            evidence_gaps=[],
        )
        self.assertEqual(section["by_id"]["item9-corpus"], "UNAVAILABLE")
        self.assertNotEqual(section["by_id"]["item9-corpus"], "IDLE")
        self.assertNotEqual(section["by_id"]["item9-corpus"], "DEGRADED")
        corpus_row = next(row for row in section["rows"] if row["id"] == "item9-corpus")
        self.assertNotIn("2/3", corpus_row["detail"])
        self.assertEqual(section["by_id"]["live-execution"], "BLOCKED")
        action = next_safe_action_for_operator_row("item9-corpus", "UNAVAILABLE")
        self.assertIn("do not mint 2/3", action)
        self.assertIn("enable Live", action)


if __name__ == "__main__":
    unittest.main()
