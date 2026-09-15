"""FTEP prospective Finviz catalyst ingress (offline mocks only)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.finviz.credential_manager import reset_finviz_credential_manager
from market_platform_foundation.finviz.redaction import FinvizHTTPError
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (
    collect_ftep_catalyst_watch,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    CLASS_GATES_INACTIVE,
    CLASS_HTTP_429,
    CLASS_PROVIDER_FAILURE,
    CLASS_SECRET_DIR_MISSING,
    CLASS_SUCCESS,
    CLASS_SUCCESS_EMPTY,
    CLASS_TOKEN_ABSENT,
    ProspectiveCatalystIngressResult,
    classify_finviz_fetch_exception,
    collect_finviz_prospective_attention_rows,
    prospective_catalyst_ingress_enabled,
    resolve_finviz_ingress_secret_dir,
)
from market_platform_foundation.local_state.paths import REPO_ROOT
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.providers.adapters.finviz_elite_context import FINVIZ_TOKEN_NAMES

_STORE_FIXTURE_TOKEN = "fixture-secure-store-token"


def _gates_env(**extra: str) -> dict[str, str]:
    env = {
        "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1",
        "IMP_FINVIZ_LIVE": "1",
    }
    for name in FINVIZ_TOKEN_NAMES:
        env[name] = ""
    env.update(extra)
    return env


class _StubFinvizClient:
    def __init__(
        self,
        *,
        received_at: str = "2026-09-14T17:00:00.000000Z",
        items: list[dict[str, object]] | None = None,
        error: str | None = None,
        success: bool = True,
        exc: BaseException | None = None,
    ) -> None:
        self._received_at = received_at
        self._items = items if items is not None else []
        self._error = error
        self._success = success
        self._exc = exc
        self.fetch_calls = 0

    def fetch_news(self, *, force: bool = False) -> dict[str, object]:
        del force
        self.fetch_calls += 1
        if self._exc is not None:
            raise self._exc
        return {
            "success": self._success,
            "error": self._error,
            "items": self._items,
            "received_at": self._received_at,
            "available_time_ns": 1_700_000_000_000_000_000,
        }


def _http_429() -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://elite.finviz.com/news_export.ashx",
        429,
        "Too Many Requests",
        Message(),
        None,
    )


def _watch_payload_for_ingress(ingress: ProspectiveCatalystIngressResult) -> dict[str, object]:
    status = {
        "us_equity_rth_open": True,
        "governed_session_count": 2,
        "empirical_lock_count": 0,
    }
    with (
        patch(
            "market_platform_foundation.intelligence.paper_forward_bridge."
            "ftep_catalyst_watch.collect_ftep_campaign_status",
            return_value=status,
        ),
        patch(
            "market_platform_foundation.intelligence.paper_forward_bridge."
            "ftep_catalyst_watch.load_governed_session_ids_from_evidence",
            return_value=(["fts-A", "fts-B"], "evidence.jsonl"),
        ),
        patch(
            "market_platform_foundation.intelligence.paper_forward_bridge."
            "ftep_prospective_catalyst_ingress.collect_finviz_prospective_attention_rows",
            return_value=ingress,
        ),
    ):
        return collect_ftep_catalyst_watch(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
        )


class FtepProspectiveCatalystIngressTests(unittest.TestCase):
    def test_injected_env_does_not_use_credential_store_for_gate(self) -> None:
        env = _gates_env()
        with patch(
            "market_platform_foundation.finviz.credential_manager.read_secure_token",
            return_value=_STORE_FIXTURE_TOKEN,
        ):
            reset_finviz_credential_manager()
            self.assertFalse(prospective_catalyst_ingress_enabled(env))
            reset_finviz_credential_manager()

    def test_gates_inactive_without_env(self) -> None:
        env = {
            "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "0",
            "IMP_FINVIZ_LIVE": "1",
            "FINVIZ_API_KEY": "test-token",
        }
        self.assertFalse(prospective_catalyst_ingress_enabled(env))
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            env=env,
        )
        self.assertTrue(result.attempted)
        self.assertFalse(result.ready)
        self.assertEqual(result.reason, "INGRESS_GATES_INACTIVE")
        self.assertEqual(result.classification, CLASS_GATES_INACTIVE)
        self.assertFalse(result.retry_attempted)

    def test_token_absent_when_gates_on_and_no_secret(self) -> None:
        env = _gates_env()
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            env=env,
        )
        self.assertTrue(result.attempted)
        self.assertFalse(result.ready)
        self.assertEqual(result.reason, "FINVIZ_TOKEN_ABSENT")
        self.assertEqual(result.classification, CLASS_TOKEN_ABSENT)
        report = result.to_report_dict()
        encoded = json.dumps(report)
        self.assertNotIn(_STORE_FIXTURE_TOKEN, encoded)

    def test_secret_dir_missing_when_configured_path_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-private"
            env = _gates_env(IMP_FINVIZ_SECRET_DIR=str(missing))
            result = collect_finviz_prospective_attention_rows(
                REPO_ROOT,
                "FTEP-V1-002",
                live_ingress=True,
                env=env,
            )
        self.assertEqual(result.classification, CLASS_SECRET_DIR_MISSING)
        self.assertEqual(result.reason, "FINVIZ_SECRET_DIR_MISSING")
        self.assertFalse(result.secret_dir_present)
        self.assertEqual(result.secret_dir_source, "CONFIGURED_SECRET_DIR")

    def test_prefers_configured_primary_private_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "primary-private"
            secret.mkdir()
            (secret / "finviz-token.txt").write_text("primary-token\n", encoding="utf-8")
            env = _gates_env(IMP_FINVIZ_SECRET_DIR=str(secret))
            client = _StubFinvizClient(items=[])
            result = collect_finviz_prospective_attention_rows(
                REPO_ROOT,
                "FTEP-V1-002",
                live_ingress=True,
                news_client=client,
                env=env,
            )
        self.assertEqual(result.classification, CLASS_SUCCESS_EMPTY)
        self.assertEqual(result.token_source, "SECRET_DIR")
        self.assertTrue(result.secret_dir_present)
        self.assertEqual(client.fetch_calls, 1)
        self.assertNotIn("primary-token", json.dumps(result.to_report_dict()))

    def test_prefers_primary_private_over_empty_worktree_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "wt" / "projects" / "integrated-market-platform"
            primary = tmp_path / "main" / "projects" / "integrated-market-platform"
            worktree.mkdir(parents=True)
            (worktree / ".private").mkdir()
            primary.mkdir(parents=True)
            (primary / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            secret = primary / ".private"
            secret.mkdir()
            (secret / "finviz-token.txt").write_text("primary-token\n", encoding="utf-8")
            isolated = _gates_env()
            isolated["IMP_FINVIZ_SECRET_DIR"] = ""
            client = _StubFinvizClient(items=[])
            with patch.dict(os.environ, isolated, clear=False), patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_catalyst_watch.operator_primary_imp_root_for_evidence",
                return_value=primary,
            ):
                reset_finviz_credential_manager()
                result = collect_finviz_prospective_attention_rows(
                    worktree,
                    "FTEP-V1-002",
                    live_ingress=True,
                    news_client=client,
                    env=None,
                    primary_root=primary,
                )
                reset_finviz_credential_manager()
        self.assertEqual(result.classification, CLASS_SUCCESS_EMPTY)
        self.assertEqual(result.secret_dir_source, "PRIMARY_PRIVATE")
        self.assertEqual(result.token_source, "SECRET_DIR")
        self.assertTrue(str(result.secret_dir_path or "").replace("\\", "/").endswith("main/projects/integrated-market-platform/.private"))

    def test_http_429_from_raised_httperror_does_not_retry(self) -> None:
        client = _StubFinvizClient(exc=_http_429())
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            news_client=client,
            env=_gates_env(FINVIZ_API_KEY="test-token"),
        )
        self.assertEqual(result.classification, CLASS_HTTP_429)
        self.assertEqual(result.reason, "FINVIZ_HTTP_429")
        self.assertEqual(result.fetch_error, "HTTP_429")
        self.assertFalse(result.retry_attempted)
        self.assertEqual(result.retry_count, 0)
        self.assertEqual(client.fetch_calls, 1)

    def test_http_429_from_wrapped_finviz_error_classifies_explicitly(self) -> None:
        inner = _http_429()
        wrapped = FinvizHTTPError("network_error: HTTPError")
        wrapped.__cause__ = inner
        classification, detail = classify_finviz_fetch_exception(wrapped)
        self.assertEqual(classification, CLASS_HTTP_429)
        self.assertEqual(detail, "HTTP_429")

    def test_provider_failure_from_fetch_dict(self) -> None:
        client = _StubFinvizClient(success=False, error="HTTP_503")
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            news_client=client,
            env=_gates_env(FINVIZ_API_KEY="test-token"),
        )
        self.assertEqual(result.classification, CLASS_PROVIDER_FAILURE)
        self.assertEqual(result.reason, "FINVIZ_FETCH_FAILED")
        self.assertEqual(result.fetch_error, "HTTP_503")
        self.assertEqual(client.fetch_calls, 1)
        self.assertFalse(result.retry_attempted)

    def test_successful_empty_qualifying_rows(self) -> None:
        client = _StubFinvizClient(items=[])
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            news_client=client,
            env=_gates_env(FINVIZ_API_KEY="test-token"),
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.classification, CLASS_SUCCESS_EMPTY)
        self.assertEqual(result.rows, ())
        self.assertFalse(result.retry_attempted)

    def test_mock_finviz_maps_prospective_rows_with_timestamps(self) -> None:
        received = "2026-09-14T17:00:00.000000Z"
        as_of_ns = (epoch_ns_from_iso(received) or 0) + 1_000_000_000
        client = _StubFinvizClient(
            received_at=received,
            items=[
                {
                    "headline": "Apple reports quarterly earnings beat",
                    "published_time": "2026-09-14T16:55:00Z",
                    "url": "https://example.com/aapl-earnings",
                    "tickers": ["AAPL"],
                    "provider": "FINVIZ_ELITE",
                    "publisher_source": "Reuters",
                }
            ],
        )
        env = _gates_env(FINVIZ_API_KEY="test-token")
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            news_client=client,
            as_of_ns=as_of_ns,
            env=env,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.classification, CLASS_SUCCESS)
        self.assertEqual(result.source_label, "live:finviz_elite_prospective")
        self.assertGreaterEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertEqual(row.get("symbol"), "AAPL")
        self.assertEqual(row.get("attention_data_kind"), "LIVE_PROSPECTIVE")
        self.assertEqual(row.get("published_time"), "2026-09-14T16:55:00Z")
        self.assertTrue(str(row.get("retrieved_time", "")).startswith("2026-09-14T17:00:00"))
        catalyst_ids = row.get("catalyst_ids") or ()
        self.assertIn("earnings", catalyst_ids)

    def test_live_ingress_fail_closed_under_fixture_smoke(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"
        payload = collect_ftep_catalyst_watch(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            fixture_only=True,
        )
        self.assertEqual(payload["watch_mode"], "FIXTURE_SMOKE")
        self.assertEqual(payload["disposition"], "BLOCKED")
        self.assertIn("LIVE_INGRESS_UNAVAILABLE", payload["blockers"])
        self.assertEqual(payload["summary_count"], 0)
        self.assertEqual(payload["attention_data_kind"], "UNAVAILABLE")
        self.assertIsNone(payload["prospective_ingress"])

    def test_live_ingress_zero_qualifying_rows_passes_without_legacy_blocker(self) -> None:
        empty_ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=True,
            reason=None,
            source_label="live:finviz_elite_prospective",
            rows=(),
            stats={"accepted_pipeline_events": 0},
            classification=CLASS_SUCCESS_EMPTY,
        )
        payload = _watch_payload_for_ingress(empty_ingress)
        self.assertEqual(payload["disposition"], "PASS")
        self.assertEqual(payload["watch_mode"], "PROSPECTIVE_FINVIZ_INGRESS")
        self.assertEqual(
            payload["ingress_outcome"],
            "LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS",
        )
        self.assertEqual(payload["ingress_classification"], CLASS_SUCCESS_EMPTY)
        self.assertEqual(payload["summary_count"], 0)
        self.assertEqual(payload["attention_data_kind"], "LIVE_PROSPECTIVE")
        self.assertNotIn("PROSPECTIVE_CATALYST_INGRESS_ZERO_ROWS", payload["blockers"])

    def test_watch_live_ingress_blocked_when_gates_inactive(self) -> None:
        ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=False,
            reason="INGRESS_GATES_INACTIVE",
            source_label="",
            rows=(),
            stats={},
            classification=CLASS_GATES_INACTIVE,
        )
        payload = _watch_payload_for_ingress(ingress)
        self.assertEqual(payload["watch_mode"], "PROSPECTIVE_FINVIZ_INGRESS")
        self.assertIn("PROSPECTIVE_CATALYST_INGRESS_GATES_INACTIVE", payload["blockers"])
        self.assertEqual(payload["ingress_outcome"], "LIVE_INGRESS_GATES_INACTIVE")
        self.assertEqual(payload["ingress_classification"], CLASS_GATES_INACTIVE)
        self.assertEqual(payload["attention_data_kind"], "UNAVAILABLE")
        self.assertEqual(payload["summary_count"], 0)
        self.assertIsNotNone(payload["prospective_ingress"])

    def test_watch_maps_http_429_classification(self) -> None:
        ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=False,
            reason="FINVIZ_HTTP_429",
            source_label="",
            rows=(),
            stats={},
            classification=CLASS_HTTP_429,
            fetch_error="HTTP_429",
        )
        payload = _watch_payload_for_ingress(ingress)
        self.assertEqual(payload["watch_mode"], "PROSPECTIVE_FINVIZ_INGRESS")
        self.assertEqual(payload["ingress_outcome"], "LIVE_INGRESS_RATE_LIMITED")
        self.assertEqual(payload["ingress_classification"], CLASS_HTTP_429)
        self.assertIn("FINVIZ_PROSPECTIVE_RATE_LIMITED", payload["blockers"])
        self.assertEqual(payload["disposition"], "BLOCKED")
        self.assertFalse(payload["prospective_ingress"]["retry_attempted"])

    def test_watch_maps_token_absent_classification(self) -> None:
        ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=False,
            reason="FINVIZ_TOKEN_ABSENT",
            source_label="",
            rows=(),
            stats={},
            classification=CLASS_TOKEN_ABSENT,
        )
        payload = _watch_payload_for_ingress(ingress)
        self.assertEqual(payload["watch_mode"], "PROSPECTIVE_FINVIZ_INGRESS")
        self.assertEqual(payload["ingress_outcome"], "LIVE_INGRESS_TOKEN_ABSENT")
        self.assertIn("FINVIZ_PROSPECTIVE_TOKEN_ABSENT", payload["blockers"])

    def test_watch_maps_provider_failure_classification(self) -> None:
        ingress = ProspectiveCatalystIngressResult(
            attempted=True,
            ready=False,
            reason="FINVIZ_FETCH_FAILED",
            source_label="",
            rows=(),
            stats={},
            classification=CLASS_PROVIDER_FAILURE,
            fetch_error="HTTP_503",
        )
        payload = _watch_payload_for_ingress(ingress)
        self.assertEqual(payload["watch_mode"], "PROSPECTIVE_FINVIZ_INGRESS")
        self.assertEqual(payload["ingress_outcome"], "LIVE_INGRESS_FAILED")
        self.assertIn("FINVIZ_PROSPECTIVE_FETCH_FAILED", payload["blockers"])

    def test_cli_emits_utf8_json_when_collect_raises_429(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ftep_watch_catalysts_cli",
            Path(__file__).resolve().parents[2] / "tools" / "ftep_watch_catalysts.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)

        buf = io.BytesIO()

        class _Stdout:
            def __init__(self) -> None:
                self.buffer = buf

            def write(self, text: str) -> int:
                encoded = text.encode("utf-8")
                self.buffer.write(encoded)
                return len(text)

            def flush(self) -> None:
                return None

        with (
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_catalyst_watch.collect_ftep_catalyst_watch",
                side_effect=_http_429(),
            ),
            patch("sys.stdout", _Stdout()),
        ):
            code = cli.main(["FTEP-V1-002", "--live-ingress", "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(buf.getvalue().decode("utf-8"))
        self.assertEqual(payload["watch_mode"], "PROSPECTIVE_FINVIZ_INGRESS")
        self.assertEqual(payload["ingress_classification"], CLASS_HTTP_429)
        self.assertEqual(payload["ingress_outcome"], "LIVE_INGRESS_RATE_LIMITED")
        self.assertFalse(payload["prospective_ingress"]["retry_attempted"])

        classified = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            news_client=_StubFinvizClient(exc=_http_429()),
            env=_gates_env(FINVIZ_API_KEY="test-token"),
        )
        receipt = io.BytesIO()

        class _BufStdout:
            def __init__(self) -> None:
                self.buffer = receipt

            def write(self, text: str) -> int:
                self.buffer.write(text.encode("utf-8"))
                return len(text)

            def flush(self) -> None:
                return None

        cli.emit_utf8_json(classified.to_report_dict(), stream=_BufStdout())
        decoded = json.loads(receipt.getvalue().decode("utf-8"))
        self.assertEqual(decoded["classification"], CLASS_HTTP_429)

    def test_resolve_secret_dir_does_not_search_leftover_nested_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "configured-missing"
            resolved = resolve_finviz_ingress_secret_dir(
                REPO_ROOT,
                env=_gates_env(IMP_FINVIZ_SECRET_DIR=str(missing)),
            )
        self.assertFalse(resolved.present)
        self.assertEqual(resolved.source, "CONFIGURED_SECRET_DIR")


if __name__ == "__main__":
    unittest.main()
