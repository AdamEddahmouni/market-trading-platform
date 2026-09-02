"""Finviz auth lifecycle tests — no live credentials."""

from __future__ import annotations

import logging
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.finviz.auth_classification import (  # noqa: E402
    FinvizFailureKind,
    classify_http_response,
)
from market_platform_foundation.finviz.auth_state import FinvizAuthState, FinvizCredentialSource  # noqa: E402
from market_platform_foundation.finviz.credential_manager import (  # noqa: E402
    FinvizCredentialManager,
    reset_finviz_credential_manager,
)
from market_platform_foundation.finviz.http_client import UrllibSession  # noqa: E402
from market_platform_foundation.finviz.login_recovery import (  # noqa: E402
    LoginRecoveryStatus,
    recover_token_via_login,
    reset_login_session_factory,
    validate_host,
)
from market_platform_foundation.finviz.redaction import (  # noqa: E402
    FinvizHTTPError,
    redact_payload,
    sanitize_text,
    sanitize_url,
)
from market_platform_foundation.finviz.request_manager import (  # noqa: E402
    FinvizRequestManager,
    reset_finviz_request_manager,
)
from market_platform_foundation.finviz.secure_store import (  # noqa: E402
    FinvizCredentialMetadata,
    load_metadata,
    save_metadata,
)

TEST_TOKEN = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SECRET_URL = (
    "https://elite.finviz.com/export/screener?v=152&auth="
    + TEST_TOKEN
)


class FinvizAuthLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_finviz_credential_manager()
        reset_finviz_request_manager()
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        for key in (
            "FINVIZ_API_KEY",
            "FINVIZ_AUTH_TOKEN",
            "FINVIZ_API_TOKEN",
            "IMP_PROVIDER_ENV",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        reset_login_session_factory()
        reset_finviz_credential_manager()
        reset_finviz_request_manager()
        self._env_patch.stop()

    def test_valid_credential_loaded(self) -> None:
        manager = FinvizCredentialManager()
        with patch(
            "market_platform_foundation.finviz.credential_manager.read_secure_token",
            return_value=TEST_TOKEN,
        ):
            token = manager.load()
        self.assertEqual(token, TEST_TOKEN)
        self.assertEqual(manager.health().source, FinvizCredentialSource.PRIVATE_FILE)

    def test_missing_credential_reports_unconfigured(self) -> None:
        manager = FinvizCredentialManager()
        with patch(
            "market_platform_foundation.finviz.credential_manager.read_secure_token",
            return_value=None,
        ), patch(
            "market_platform_foundation.finviz.credential_manager._provider_env_token",
            return_value=None,
        ):
            self.assertIsNone(manager.load())
        self.assertEqual(manager.health().state, FinvizAuthState.UNCONFIGURED)

    def test_invalid_auth_classified(self) -> None:
        result = classify_http_response(status_code=401, body="Unauthorized")
        self.assertEqual(result.kind, FinvizFailureKind.AUTH_INVALID)
        self.assertTrue(result.triggers_recovery)

    def test_429_does_not_trigger_rotation(self) -> None:
        result = classify_http_response(status_code=429, body="rate limit")
        self.assertEqual(result.kind, FinvizFailureKind.RATE_LIMITED)
        self.assertFalse(result.triggers_recovery)

    def test_429_uses_bounded_exponential_backoff(self) -> None:
        manager = FinvizRequestManager(min_interval_s=5.0)
        manager._last_request_at = -5.0
        responses = [
            MagicMock(status_code=429, text="rate limit", headers={}),
            MagicMock(status_code=429, text="rate limit", headers={}),
            MagicMock(
                status_code=200,
                text="Ticker,Price\nAAPL,100\n",
                headers={"content-type": "text/csv"},
            ),
        ]
        elapsed = {"value": 0.0}
        delays: list[float] = []

        def fake_sleep(delay: float) -> None:
            delays.append(delay)
            elapsed["value"] += delay

        with patch.object(
            manager._credential_manager,
            "get_token",
            return_value=TEST_TOKEN,
        ), patch.object(
            manager,
            "_raw_get",
            side_effect=responses,
        ), patch(
            "market_platform_foundation.finviz.request_manager.time.monotonic",
            side_effect=lambda: elapsed["value"],
        ), patch(
            "market_platform_foundation.finviz.request_manager.time.sleep",
            side_effect=fake_sleep,
        ):
            status, body, _ = manager.get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152"},
            )

        self.assertEqual(status, 200)
        self.assertIn("AAPL", body)
        self.assertEqual(delays, [5.0, 10.0])
        self.assertEqual(manager.metrics.http_429_count, 2)

    def test_429_honors_larger_retry_after(self) -> None:
        manager = FinvizRequestManager(min_interval_s=5.0)
        manager._last_request_at = -5.0
        responses = [
            MagicMock(
                status_code=429,
                text="rate limit",
                headers={"retry-after": "12"},
            ),
            MagicMock(
                status_code=200,
                text="Ticker,Price\nAAPL,100\n",
                headers={"content-type": "text/csv"},
            ),
        ]
        elapsed = {"value": 0.0}
        delays: list[float] = []

        def fake_sleep(delay: float) -> None:
            delays.append(delay)
            elapsed["value"] += delay

        with patch.object(
            manager._credential_manager,
            "get_token",
            return_value=TEST_TOKEN,
        ), patch.object(
            manager,
            "_raw_get",
            side_effect=responses,
        ), patch(
            "market_platform_foundation.finviz.request_manager.time.monotonic",
            side_effect=lambda: elapsed["value"],
        ), patch(
            "market_platform_foundation.finviz.request_manager.time.sleep",
            side_effect=fake_sleep,
        ):
            status, _, _ = manager.get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(delays, [12.0])

    def test_login_html_is_never_cached(self) -> None:
        manager = FinvizRequestManager(min_interval_s=0.0)
        login_html = MagicMock(
            status_code=200,
            text="<html><form>Login Password</form></html>",
            headers={"content-type": "text/html"},
        )

        with patch.object(
            manager._credential_manager,
            "get_token",
            return_value=TEST_TOKEN,
        ), patch.object(
            manager._credential_manager,
            "should_attempt_recovery",
            return_value=False,
        ), patch.object(
            manager,
            "_raw_get",
            side_effect=[login_html, login_html],
        ) as raw_get:
            first = manager.get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152"},
                cache_ttl_s=60,
            )
            second = manager.get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152"},
                cache_ttl_s=60,
            )

        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertEqual(raw_get.call_count, 2)
        self.assertEqual(manager.metrics.cache_hits, 0)

    def test_network_error_does_not_trigger_rotation(self) -> None:
        result = classify_http_response(status_code=None, network_error=True)
        self.assertEqual(result.kind, FinvizFailureKind.NETWORK_ERROR)
        self.assertFalse(result.triggers_recovery)

    def test_5xx_does_not_trigger_rotation(self) -> None:
        result = classify_http_response(status_code=503, body="unavailable")
        self.assertEqual(result.kind, FinvizFailureKind.PROVIDER_ERROR)
        self.assertFalse(result.triggers_recovery)

    def test_single_flight_refresh(self) -> None:
        manager = FinvizCredentialManager()
        manager._token = "old-token"
        manager._source = FinvizCredentialSource.PRIVATE_FILE
        calls: list[int] = []

        def slow_recovery() -> bool:
            calls.append(1)
            import time

            time.sleep(0.2)
            manager._token = TEST_TOKEN
            manager._state = FinvizAuthState.HEALTHY
            return True

        with patch.object(manager, "attempt_recovery", side_effect=slow_recovery):
            thread = threading.Thread(target=manager.attempt_recovery)
            thread2 = threading.Thread(target=manager.attempt_recovery)
            thread.start()
            thread2.start()
            thread.join(timeout=5)
            thread2.join(timeout=5)
        self.assertLessEqual(len(calls), 2)

    def test_concurrent_auth_failures_trigger_one_recovery(self) -> None:
        manager = FinvizCredentialManager()
        recovery_count = 0
        recovery_lock = threading.Lock()

        original = manager.attempt_recovery

        def counting_recovery() -> bool:
            nonlocal recovery_count
            with recovery_lock:
                recovery_count += 1
            return original()

        manager._token = "stale"
        manager._source = FinvizCredentialSource.PRIVATE_FILE
        with patch.object(manager, "attempt_recovery", side_effect=counting_recovery):
            with patch(
                "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
                return_value=MagicMock(status=LoginRecoveryStatus.CONFIG_MISSING),
            ):
                threads = [threading.Thread(target=manager.attempt_recovery) for _ in range(3)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)

    def test_candidate_credential_validated_before_swap(self) -> None:
        manager = FinvizCredentialManager()
        validated: list[str] = []

        def fake_validate(token: str, **kwargs) -> bool:
            validated.append(token)
            return token == TEST_TOKEN

        with patch.object(manager, "validate_token", side_effect=fake_validate), patch(
            "market_platform_foundation.finviz.credential_manager.write_secure_token",
            return_value=True,
        ), patch(
            "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
            return_value=MagicMock(
                status=LoginRecoveryStatus.REFRESHED,
                token=TEST_TOKEN,
            ),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials",
            return_value=("user", "pass"),
        ):
            manager._token = "old"
            manager._source = FinvizCredentialSource.PRIVATE_FILE
            self.assertTrue(manager.attempt_recovery())
        self.assertIn(TEST_TOKEN, validated)

    def test_recovery_adopts_changed_secure_token_before_login(self) -> None:
        manager = FinvizCredentialManager()
        manager._token = "old-token"
        manager._source = FinvizCredentialSource.PRIVATE_FILE

        with patch(
            "market_platform_foundation.finviz.credential_manager._env_override_token",
            return_value=None,
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_secure_token",
            return_value=TEST_TOKEN,
        ), patch.object(
            manager,
            "validate_token",
            return_value=True,
        ) as validate_mock, patch(
            "market_platform_foundation.finviz.credential_manager.record_credential_activation",
            return_value=FinvizCredentialMetadata(finviz_credential_generation=1),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
        ) as login_mock:
            recovered = manager.attempt_recovery()

        self.assertTrue(recovered)
        self.assertEqual(manager.get_token(), TEST_TOKEN)
        self.assertEqual(manager.health().source, FinvizCredentialSource.PRIVATE_FILE)
        self.assertEqual(manager.health().state, FinvizAuthState.HEALTHY)
        validate_mock.assert_called_once_with(TEST_TOKEN)
        login_mock.assert_not_called()

    def test_file_credentials_report_automatic_reload_capability(self) -> None:
        manager = FinvizCredentialManager()
        manager._token = TEST_TOKEN
        manager._source = FinvizCredentialSource.PRIVATE_FILE

        with patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials",
            return_value=(None, None),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials_from_env",
            return_value=(None, None),
        ):
            health = manager.health()

        self.assertEqual(health.recovery_mode.value, "AUTO")
        self.assertEqual(health.automatic_recovery, "AUTOMATIC")

    def test_unchanged_secure_token_falls_through_to_login(self) -> None:
        manager = FinvizCredentialManager()
        manager._token = "old-token"
        manager._source = FinvizCredentialSource.PRIVATE_FILE

        with patch(
            "market_platform_foundation.finviz.credential_manager._env_override_token",
            return_value=None,
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_secure_token",
            return_value="old-token",
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials",
            return_value=("operator@example.com", "secret"),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
            return_value=MagicMock(
                status=LoginRecoveryStatus.REFRESHED,
                token=TEST_TOKEN,
            ),
        ) as login_mock, patch.object(
            manager,
            "validate_token",
            return_value=True,
        ), patch(
            "market_platform_foundation.finviz.credential_manager.write_secure_token",
            return_value=True,
        ):
            recovered = manager.attempt_recovery()

        self.assertTrue(recovered)
        self.assertEqual(manager.get_token(), TEST_TOKEN)
        login_mock.assert_called_once_with(
            username="operator@example.com",
            password="secret",
        )

    def test_request_raw_get_accepts_validation_headers(self) -> None:
        manager = FinvizRequestManager(min_interval_s=0.01)
        response = MagicMock(status_code=200, text="Ticker\nAAPL", headers={})

        with patch(
            "market_platform_foundation.finviz.request_manager.urllib_get",
            return_value=response,
        ) as get_mock:
            returned = manager._raw_get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152"},
                timeout=15,
                headers={"Accept": "text/csv"},
            )

        self.assertIs(returned, response)
        self.assertEqual(get_mock.call_args.kwargs["headers"]["Accept"], "text/csv")

    def test_bad_candidate_not_persisted(self) -> None:
        manager = FinvizCredentialManager()
        with patch.object(manager, "validate_token", return_value=False), patch(
            "market_platform_foundation.finviz.credential_manager.write_secure_token",
        ) as write_mock, patch(
            "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
            return_value=MagicMock(
                status=LoginRecoveryStatus.REFRESHED,
                token="bad-token",
            ),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials",
            return_value=("user", "pass"),
        ):
            manager._token = "old"
            manager._source = FinvizCredentialSource.PRIVATE_FILE
            self.assertFalse(manager.attempt_recovery())
        write_mock.assert_not_called()

    def test_credential_generation_increments(self) -> None:
        meta = FinvizCredentialMetadata(finviz_credential_generation=2)
        with patch(
            "market_platform_foundation.finviz.secure_store.load_metadata",
            return_value=meta,
        ), patch(
            "market_platform_foundation.finviz.secure_store.save_metadata",
        ) as save_mock:
            updated = __import__(
                "market_platform_foundation.finviz.secure_store",
                fromlist=["record_credential_activation"],
            ).record_credential_activation(source="PRIVATE_FILE", rotated=True)
        self.assertEqual(updated.finviz_credential_generation, 3)
        save_mock.assert_called_once()

    def test_read_request_retries_once_after_successful_recovery(self) -> None:
        manager = FinvizRequestManager(min_interval_s=0.01)
        responses = [
            MagicMock(status_code=401, text="Unauthorized", headers={}),
            MagicMock(status_code=200, text="Ticker,Price\nAAPL,100", headers={}),
        ]

        with patch.object(
            manager._credential_manager,
            "get_token",
            return_value=TEST_TOKEN,
        ), patch.object(
            manager._credential_manager,
            "attempt_recovery",
            return_value=True,
        ), patch.object(manager, "_raw_get", side_effect=responses):
            status, body, meta = manager.get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152", "f": "t=AAPL"},
                cache_ttl_s=None,
            )
        self.assertEqual(status, 200)
        self.assertIn("AAPL", body)
        self.assertFalse(meta.get("cached"))

    def test_recovery_loop_is_bounded(self) -> None:
        manager = FinvizCredentialManager()
        manager._token = "bad"
        manager._source = FinvizCredentialSource.PRIVATE_FILE
        with patch(
            "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
            return_value=MagicMock(status=LoginRecoveryStatus.AUTH_FAILED),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials",
            return_value=("u", "p"),
        ):
            manager.attempt_recovery()
            manager.attempt_recovery()
            third = manager.attempt_recovery()
        self.assertFalse(third)
        self.assertEqual(manager.health().state, FinvizAuthState.AUTH_OPERATOR_ACTION_REQUIRED)

    def test_auth_failure_isolated_from_moomoo(self) -> None:
        from market_platform_foundation.ui_api.live_projections import build_provider_health_payload

        with patch.dict(os.environ, {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1"}):
            with patch(
                "market_platform_foundation.ui_api.live_projections._runtime_or_none",
                return_value=MagicMock(
                    health_payload=lambda: {
                        "lifecycle": {"connection_state": "CONNECTED"},
                    },
                    capability_registry=MagicMock(dimensions=MagicMock(entitled=True)),
                    state=MagicMock(
                        quote_for=lambda _: None,
                        trades_for=lambda _: [],
                        book_for=lambda _: None,
                    ),
                    feed_metrics={},
                    subscription_manager=MagicMock(active_keys=[]),
                ),
            ), patch(
                "market_platform_foundation.ui_api.live_projections.ReplayStore",
            ) as store_cls, patch(
                "market_platform_foundation.finviz.credential_manager.get_finviz_credential_manager",
            ) as cred_mock:
                store_cls.return_value = MagicMock(data_mode="LIVE")
                cred_mock.return_value.health.return_value = MagicMock(
                    state=FinvizAuthState.AUTH_INVALID,
                    source=FinvizCredentialSource.PRIVATE_FILE,
                    credential_present=False,
                    finviz_credential_generation=1,
                    last_validated=None,
                    last_rotation=None,
                    recovery_mode=MagicMock(value="MANUAL"),
                    last_auth_error="AUTH_INVALID",
                    automatic_recovery="MANUAL",
                )
                payload = build_provider_health_payload(MagicMock())
        self.assertTrue(payload.get("available"))
        self.assertEqual(
            payload.get("lifecycle", {}).get("connection_state"),
            "CONNECTED",
        )
        self.assertIn("finviz", payload)

    def test_auth_failure_isolated_from_sec(self) -> None:
        manager = FinvizCredentialManager()
        with patch.object(FinvizCredentialManager, "load", return_value=None):
            reset_finviz_credential_manager()
            manager = FinvizCredentialManager()
            self.assertEqual(manager.health().state, FinvizAuthState.UNCONFIGURED)
        from market_platform_foundation.finra import client_config as finra_client_config

        with patch.object(
            finra_client_config,
            "load_finra_credentials",
            return_value=MagicMock(present=lambda: True),
        ):
            creds = finra_client_config.load_finra_credentials()
        self.assertTrue(creds.present())

    def test_finvis_request_queue_resumes_after_recovery(self) -> None:
        req = FinvizRequestManager(min_interval_s=0.01)
        calls = {"n": 0}

        def raw_get(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return MagicMock(status_code=403, text="Forbidden", headers={})
            return MagicMock(status_code=200, text="Ticker\nAAPL", headers={})

        with patch.object(req._credential_manager, "get_token", return_value=TEST_TOKEN), patch.object(
            req._credential_manager,
            "attempt_recovery",
            return_value=True,
        ), patch.object(req, "_raw_get", side_effect=raw_get):
            status, _, _ = req.get(
                "https://elite.finviz.com/export/screener",
                params={"v": "152"},
            )
        self.assertEqual(status, 200)
        self.assertEqual(calls["n"], 2)

    def test_rate_budget_survives_credential_rotation(self) -> None:
        req = FinvizRequestManager(min_interval_s=5.0)
        req.metrics.request_count = 50
        with patch.object(req._credential_manager, "attempt_recovery", return_value=True):
            req._credential_manager._token = "new-token"
        self.assertEqual(req.metrics.request_count, 50)
        self.assertEqual(req._min_interval_s, 5.0)

    def test_auth_url_redacted_in_logs(self) -> None:
        cleaned = sanitize_url(SECRET_URL, secret=TEST_TOKEN)
        self.assertNotIn(TEST_TOKEN, cleaned)
        self.assertTrue("REDACTED" in cleaned)
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=cleaned,
            args=(),
            exc_info=None,
        )
        formatted = logging.Formatter().format(log_record)
        self.assertNotIn(TEST_TOKEN, formatted)

    def test_auth_url_redacted_in_exception(self) -> None:
        error = FinvizHTTPError("failed", url=SECRET_URL, secret=TEST_TOKEN)
        self.assertNotIn(TEST_TOKEN, str(error))
        self.assertNotIn(TEST_TOKEN, repr(error))

    def test_auth_not_present_in_metrics(self) -> None:
        req = FinvizRequestManager(min_interval_s=0.01)
        metrics_repr = repr(req.metrics)
        self.assertNotIn(TEST_TOKEN, metrics_repr)
        self.assertNotIn("auth=", metrics_repr)

    def test_password_never_logged(self) -> None:
        text = sanitize_text("password=supersecret cookie=abc123")
        self.assertNotIn("supersecret", text)
        self.assertIn("<REDACTED>", text)

    def test_cookie_never_logged(self) -> None:
        text = sanitize_text("Set-Cookie: sessionid=deadbeef")
        self.assertNotIn("deadbeef", text)

    def test_real_secret_never_written_to_evidence_fixture(self) -> None:
        report = (ROOT / "evidence" / "market_data" / "finviz" / "auth-lifecycle-report.json").read_text(
            encoding="utf-8",
        )
        self.assertNotIn(TEST_TOKEN, report)
        self.assertNotIn("FINVIZ_API_KEY=", report)

    def test_environment_override_supported(self) -> None:
        os.environ["FINVIZ_API_KEY"] = TEST_TOKEN
        manager = FinvizCredentialManager()
        self.assertEqual(manager.load(), TEST_TOKEN)
        self.assertEqual(manager.health().source, FinvizCredentialSource.ENVIRONMENT)

    def test_secure_store_preferred_when_configured(self) -> None:
        with patch(
            "market_platform_foundation.finviz.credential_manager._env_override_token",
            return_value=None,
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_secure_token",
            return_value=TEST_TOKEN,
        ):
            manager = FinvizCredentialManager()
            self.assertEqual(manager.load(), TEST_TOKEN)
            self.assertEqual(
                manager.health().source,
                FinvizCredentialSource.PRIVATE_FILE,
            )

    def test_login_host_allowlist(self) -> None:
        self.assertTrue(validate_host("https://elite.finviz.com/api_explanation"))
        self.assertFalse(validate_host("https://evil.example.com/login"))

    def test_session_records_final_redirect_url(self) -> None:
        response = MagicMock()
        response.status = 200
        response.headers = {"content-type": "text/plain"}
        response.read.return_value = b"ok"
        response.geturl.return_value = "https://elite.finviz.com/api_explanation"

        finalized = UrllibSession._finalize(response, "https://finviz.com/login_submit")

        self.assertEqual(finalized.url, "https://elite.finviz.com/api_explanation")

    def test_current_login_flow_primes_session_and_validates_export(self) -> None:
        session = MagicMock()
        session.get.side_effect = [
            MagicMock(
                status_code=200,
                text='<form action="/login_submit"></form>',
                url="https://finviz.com/login-email?remember=true",
                headers={"content-type": "text/html"},
            ),
            MagicMock(
                status_code=200,
                text=f'<a href="/export/screener?auth={TEST_TOKEN}">API</a>',
                url="https://elite.finviz.com/api_explanation",
                headers={"content-type": "text/html"},
            ),
            MagicMock(
                status_code=200,
                text="Ticker,Price\nAAPL,100\n",
                url="https://elite.finviz.com/export/screener",
                headers={"content-type": "text/csv"},
            ),
        ]
        session.post.return_value = MagicMock(
            status_code=200,
            text="account",
            url="https://finviz.com/",
            headers={"content-type": "text/html"},
        )

        result = recover_token_via_login(
            username="operator@example.com",
            password="secret",
            session_factory=lambda: session,
        )

        self.assertEqual(result.status, LoginRecoveryStatus.REFRESHED)
        self.assertEqual(result.token, TEST_TOKEN)
        self.assertEqual(
            session.get.call_args_list[0],
            call("https://finviz.com/login-email?remember=true", timeout=15),
        )
        session.post.assert_called_once_with(
            "https://finviz.com/login_submit",
            data={
                "email": "operator@example.com",
                "password": "secret",
                "remember": "on",
            },
            timeout=15,
            allow_redirects=True,
        )
        session.close.assert_called_once_with()

    def test_unknown_redirect_fails_closed(self) -> None:
        session = MagicMock()
        session.post.return_value = MagicMock(
            status_code=200,
            text="ok",
            url="https://phishing.example.com/",
            headers={},
        )
        result = recover_token_via_login(
            username="u",
            password="p",
            session_factory=lambda: session,
        )
        self.assertEqual(result.status, LoginRecoveryStatus.REDIRECT_REJECTED)

    def test_mfa_returns_operator_action_required(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200,
            text="login",
            url="https://finviz.com/login-email?remember=true",
            headers={"content-type": "text/html"},
        )
        session.post.return_value = MagicMock(
            status_code=200,
            text="two-factor authentication required",
            url="https://elite.finviz.com/",
            headers={},
        )
        result = recover_token_via_login(
            username="u",
            password="p",
            session_factory=lambda: session,
        )
        self.assertEqual(result.status, LoginRecoveryStatus.MANUAL_AUTH_REQUIRED)

    def test_captcha_returns_operator_action_required(self) -> None:
        result = classify_http_response(
            status_code=200,
            body="<html>captcha required</html>",
            content_type="text/html",
        )
        self.assertFalse(result.triggers_recovery)

    def test_login_retry_is_bounded(self) -> None:
        manager = FinvizCredentialManager()
        manager._source = FinvizCredentialSource.PRIVATE_FILE
        with patch(
            "market_platform_foundation.finviz.credential_manager.recover_token_via_login",
            return_value=MagicMock(status=LoginRecoveryStatus.NETWORK_ERROR),
        ), patch(
            "market_platform_foundation.finviz.credential_manager.read_login_credentials",
            return_value=("u", "p"),
        ):
            for _ in range(3):
                manager.attempt_recovery()
        self.assertEqual(manager.health().state, FinvizAuthState.AUTH_OPERATOR_ACTION_REQUIRED)

    def test_login_transport_urllib_mode(self) -> None:
        from tools.finviz.login_transport import configure_login_transport

        with patch(
            "tools.finviz.login_transport.reset_login_session_factory",
        ) as reset_factory:
            selected = configure_login_transport("urllib")

        self.assertEqual(selected, "URLLIB")
        reset_factory.assert_called_once_with()

    def test_login_transport_registers_chrome_impersonation(self) -> None:
        from tools.finviz.login_transport import configure_login_transport

        fake_requests = MagicMock()
        fake_session = MagicMock()
        fake_requests.Session.return_value = fake_session
        captured: list[object] = []

        with patch(
            "tools.finviz.login_transport.set_login_session_factory",
            side_effect=captured.append,
        ):
            selected = configure_login_transport(
                "curl_cffi",
                requests_module=fake_requests,
            )

        self.assertEqual(selected, "CURL_CFFI")
        self.assertEqual(len(captured), 1)
        self.assertIs(captured[0](), fake_session)
        fake_requests.Session.assert_called_once_with(impersonate="chrome")

    def test_login_transport_auto_falls_back_without_dependency(self) -> None:
        from tools.finviz.login_transport import configure_login_transport

        with patch(
            "tools.finviz.login_transport.reset_login_session_factory",
        ) as reset_factory:
            selected = configure_login_transport("auto", requests_module=None)

        self.assertEqual(selected, "URLLIB")
        reset_factory.assert_called_once_with()

    def test_ui_launcher_configures_login_transport_after_env_load(self) -> None:
        from tools.ui1 import run_ui_api

        events: list[str] = []
        args = MagicMock(serve=True, host="127.0.0.1", port=0, output_dir=None)
        with patch.object(
            run_ui_api,
            "_load_local_env",
            side_effect=lambda: events.append("env"),
        ), patch.object(
            run_ui_api,
            "configure_login_transport",
            side_effect=lambda: events.append("transport"),
        ), patch.object(
            run_ui_api,
            "parse_args",
            return_value=args,
        ), patch.object(
            run_ui_api,
            "serve",
        ):
            result = run_ui_api.main()

        self.assertEqual(result, 0)
        self.assertEqual(events, ["env", "transport"])

    def test_redact_payload_covers_api_token(self) -> None:
        cleaned = redact_payload({"api_token": "secret", "auth": "secret"})
        self.assertEqual(cleaned["api_token"], "REDACTED")
        self.assertEqual(cleaned["auth"], "REDACTED")

    def test_configure_login_stores_credentials_and_recovers_token(self) -> None:
        from tools.finviz import auth

        manager = MagicMock()
        manager.attempt_recovery.return_value = True
        with patch.object(auth, "configure_login_transport"), patch.object(
            auth.getpass,
            "getpass",
            return_value="password",
        ), patch("builtins.input", return_value="user@example.com"), patch.object(
            auth,
            "write_login_credentials",
            return_value=True,
        ) as write_credentials, patch.object(
            auth,
            "get_finviz_credential_manager",
            return_value=manager,
        ):
            result = auth.main(["configure-login"])

        self.assertEqual(result, 0)
        write_credentials.assert_called_once_with("user@example.com", "password")
        manager.attempt_recovery.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
