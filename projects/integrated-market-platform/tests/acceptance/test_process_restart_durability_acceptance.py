"""Process-restart durability acceptance (real OS process bounce).

Evidence class: SOFTWARE_CONTROLLED_EVIDENCE / FIXTURE.

Proves the production observational chain across a real service process restart
against the same temporary ``IMP_STATE_DIR``:

1. start API harness process
2. POST fixture news through production ``/intelligence/ingest/news``
3. EventV1 created
4. PIT clocks pass
5. observational detector mints OpportunityV1 (no direct SQLite insert)
6. persisted in local_state
7. ranked API readback
8. WATCH / DISMISS via operator API
9. ack + ExecutionDecisionTraceV1 + TradeReviewV1 persisted
10. terminate process cleanly
11. start fresh process on SAME state dir
12. query API
13. stable identities, operator state, trace/review lineage, no duplicates

Never enables Live. Never binds campaign ports 8766/5173/11111. Never claims
empirical market evidence. If the environment cannot spawn a second process,
fail with ``ENVIRONMENT_BLOCKER`` — do not substitute in-process singleton reset.
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.live_execution_safety.preflight_controls import (  # noqa: E402
    evaluate_live_preflight_bundle,
)
from market_platform_foundation.market_data.live_config import live_observational_enabled  # noqa: E402
from market_platform_foundation.ui_api.news_ingest import NEWS_INGEST_ROUTE  # noqa: E402

from tests.acceptance.harness_process_restart_ui_api import (  # noqa: E402
    BOOK_HEALTH_ROUTE,
    FORBIDDEN_PORTS,
    HARNESS_MARKER,
    TRACES_ROUTE,
)

PROCESS_RESTART_DURABILITY_ACCEPTANCE = "PROCESS_RESTART_DURABILITY_ACCEPTANCE"
EVIDENCE_CLASS = "SOFTWARE_CONTROLLED_EVIDENCE"
HARNESS_PATH = Path(__file__).resolve().parent / "harness_process_restart_ui_api.py"

_LIVE_ENV_KEYS = (
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_LIVE_INTERNAL_SIMULATION",
    "IMP_MOOMOO_LIVE",
    "IMP_IBKR_LIVE",
    "IMP_FINVIZ_LIVE",
    "IMP_LIVE_FIXTURE_FEED",
)

_CAMPAIGN_PIDS = (102752, 99624, 125168)


def _clear_live_env(env: dict[str, str]) -> None:
    for key in _LIVE_ENV_KEYS:
        env.pop(key, None)


def _unused_local_port() -> int:
    for _ in range(64):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in FORBIDDEN_PORTS:
            return port
    raise RuntimeError("ENVIRONMENT_BLOCKER: no unused local port outside campaign set")


def _fixture_clocks() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    published = (now - timedelta(seconds=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    retrieved = (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return published, retrieved


def _raw_article(
    *,
    headline: str,
    tickers: list[str],
    provider_native_id: str,
    published: str,
) -> dict[str, Any]:
    return {
        "headline": headline,
        "published_time": published,
        "url": f"https://example.com/{provider_native_id}",
        "tickers": tickers,
        "publisher_source": "Wire",
        "provider_native_id": provider_native_id,
    }


def _http_json(
    host: str,
    port: int,
    method: str,
    path: str,
    *,
    body: bytes = b"{}",
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        return int(response.status), payload
    finally:
        conn.close()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, 0, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _release_sqlite_after_kill(state_dir: str) -> None:
    """Best-effort unlock after forced process kill. Test-only; never touches campaign DBs."""

    import sqlite3

    db = Path(state_dir) / "imp-state.sqlite3"
    if not db.is_file():
        return
    try:
        conn = sqlite3.connect(str(db), timeout=30)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        for suffix in ("-wal", "-shm"):
            side = Path(str(db) + suffix)
            if side.is_file():
                try:
                    side.unlink()
                except OSError:
                    pass


class _ApiProcess:
    def __init__(self, *, state_dir: str, port: int) -> None:
        self.state_dir = state_dir
        self.port = port
        self.proc: subprocess.Popen[str] | None = None
        self.pid: int | None = None
        self.stderr_path: Path | None = None
        self.stdout_path: Path | None = None
        self._stdout_handle: Any | None = None
        self._stderr_handle: Any | None = None

    def start(self) -> dict[str, Any]:
        if self.port in FORBIDDEN_PORTS:
            raise AssertionError(f"FORBIDDEN_CAMPAIGN_PORT:{self.port}")
        env = os.environ.copy()
        _clear_live_env(env)
        env["IMP_STATE_DIR"] = self.state_dir
        env["IMP_PERSIST_STATE"] = "1"
        env[HARNESS_MARKER] = "1"
        env["PYTHONPATH"] = os.pathsep.join(
            (
                str(ROOT / "src"),
                str(ROOT),
                env.get("PYTHONPATH", ""),
            )
        ).strip(os.pathsep)
        env["PYTHONUNBUFFERED"] = "1"
        log_dir = Path(self.state_dir) / "harness-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.stdout_path = log_dir / f"api-{self.port}.out.log"
        self.stderr_path = log_dir / f"api-{self.port}.err.log"
        ready_path = log_dir / f"api-{self.port}.ready.json"
        if ready_path.exists():
            ready_path.unlink()
        env["IMP_PROCESS_RESTART_READY_FILE"] = str(ready_path)
        self._stdout_handle = self.stdout_path.open("w", encoding="utf-8")
        self._stderr_handle = self.stderr_path.open("w", encoding="utf-8")
        try:
            self.proc = subprocess.Popen(
                [
                    sys.executable,
                    str(HARNESS_PATH),
                    "--serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self.port),
                ],
                cwd=str(ROOT),
                env=env,
                stdout=self._stdout_handle,
                stderr=self._stderr_handle,
                text=True,
            )
        except OSError as exc:
            self._close_handles()
            raise AssertionError(f"ENVIRONMENT_BLOCKER: cannot spawn API process: {exc}") from exc
        self.pid = int(self.proc.pid)
        if self.pid in _CAMPAIGN_PIDS:
            self.stop()
            raise AssertionError(f"ENVIRONMENT_BLOCKER: spawned pid collided with campaign pid {self.pid}")
        deadline = time.time() + 60.0
        while time.time() < deadline:
            if self.proc.poll() is not None:
                self._close_handles()
                err = self.stderr_path.read_text(encoding="utf-8", errors="replace") if self.stderr_path else ""
                out = self.stdout_path.read_text(encoding="utf-8", errors="replace") if self.stdout_path else ""
                raise AssertionError(
                    "ENVIRONMENT_BLOCKER: API process exited before serving "
                    f"code={self.proc.returncode} stdout={out!r} stderr={err!r}"
                )
            if ready_path.is_file():
                try:
                    payload = json.loads(ready_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    time.sleep(0.05)
                    continue
                served_port = int(payload.get("port") or self.port)
                if served_port in FORBIDDEN_PORTS:
                    self.stop()
                    raise AssertionError(f"FORBIDDEN_CAMPAIGN_PORT:{served_port}")
                self.port = served_port
                # Confirm HTTP accepts after ready file.
                try:
                    status, _auth = _http_json("127.0.0.1", self.port, "GET", "/auth/status", timeout=5.0)
                except Exception as exc:  # noqa: BLE001
                    self.stop()
                    raise AssertionError(
                        f"ENVIRONMENT_BLOCKER: ready file present but HTTP probe failed: {exc}\n"
                        + self.diagnostics()
                    ) from exc
                if status != 200:
                    self.stop()
                    raise AssertionError(
                        f"ENVIRONMENT_BLOCKER: auth status HTTP {status}\n" + self.diagnostics()
                    )
                return {
                    "evidence_class": EVIDENCE_CLASS,
                    "harness": HARNESS_MARKER,
                    "host": "127.0.0.1",
                    "port": self.port,
                    "pid": int(payload.get("pid") or self.pid),
                    "status": "serving",
                }
            time.sleep(0.1)
        self.stop()
        raise AssertionError(
            "ENVIRONMENT_BLOCKER: timed out waiting for API readiness\n" + self.diagnostics()
        )

    def diagnostics(self) -> str:
        if self._stdout_handle is not None:
            self._stdout_handle.flush()
        if self._stderr_handle is not None:
            self._stderr_handle.flush()
        parts: list[str] = []
        if self.stdout_path and self.stdout_path.is_file():
            parts.append("STDOUT:\n" + self.stdout_path.read_text(encoding="utf-8", errors="replace"))
        if self.stderr_path and self.stderr_path.is_file():
            parts.append("STDERR:\n" + self.stderr_path.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(parts)

    def _close_handles(self) -> None:
        for handle in (self._stdout_handle, self._stderr_handle):
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        self._stdout_handle = None
        self._stderr_handle = None

    def stop(self) -> None:
        proc = self.proc
        if proc is None:
            self._close_handles()
            return
        if proc.poll() is None:
            try:
                if os.name == "nt":
                    # Kill the whole tree; terminate alone can leave the serve loop alive.
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                else:
                    proc.send_signal(signal.SIGTERM)
            except OSError:
                pass
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
        self._close_handles()
        self.proc = None
        self.pid = None


class ProcessRestartDurabilityAcceptanceTests(unittest.TestCase):
    """Real OS process bounce. SOFTWARE_CONTROLLED_EVIDENCE / FIXTURE only."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._state_dir = self._tmp.name
        self._steps: dict[str, str] = {}
        self._campaign_alive_before = {pid: _pid_alive(pid) for pid in _CAMPAIGN_PIDS}

    def tearDown(self) -> None:
        for attr in ("_proc1", "_proc2"):
            proc = getattr(self, attr, None)
            if isinstance(proc, _ApiProcess):
                proc.stop()
        for pid in _CAMPAIGN_PIDS:
            # Read-only liveness check only — never signal campaign PIDs.
            after = _pid_alive(pid)
            before = self._campaign_alive_before.get(pid)
            if before and not after:
                # Do not fail the product test if an unrelated campaign exit
                # happened; record only. We never signaled these PIDs.
                self._steps["campaign_pid_watch"] = f"NOTE:{pid}_exited_without_our_signal"
        self._tmp.cleanup()

    def test_acceptance_labels_and_live_gates_remain_off(self) -> None:
        self.assertEqual(PROCESS_RESTART_DURABILITY_ACCEPTANCE, "PROCESS_RESTART_DURABILITY_ACCEPTANCE")
        self.assertEqual(EVIDENCE_CLASS, "SOFTWARE_CONTROLLED_EVIDENCE")
        self.assertFalse(live_observational_enabled())
        for key in _LIVE_ENV_KEYS:
            self.assertNotEqual(os.environ.get(key), "1", msg=f"{key} must stay off")
        report = evaluate_live_preflight_bundle(
            reference_price_minor=150_00,
            quote_as_of_ns=1_700_000_000_000_000_000,
            decision_time_ns=1_700_000_000_100_000_000,
            max_quote_age_ns=1_000_000_000,
            quantity=1,
            max_quantity=10,
            required_notional_minor=150_00,
            buying_power_minor=1_000_000,
            session_state="RTH_OPEN",
            side="BUY",
            order_type="MARKET",
            limit_price_minor=None,
            confirmation_present=True,
            confirmation_expired=False,
            confirmation_matches_intent=True,
        )
        self.assertFalse(report.allows_network_submit)

    def test_real_process_restart_preserves_opportunity_operator_trace_review(self) -> None:
        self.assertFalse(live_observational_enabled())
        published, retrieved = _fixture_clocks()
        port1 = _unused_local_port()
        port2 = _unused_local_port()
        while port2 == port1:
            port2 = _unused_local_port()
        self.assertNotIn(port1, FORBIDDEN_PORTS)
        self.assertNotIn(port2, FORBIDDEN_PORTS)

        # Step 1: start API
        self._proc1 = _ApiProcess(state_dir=self._state_dir, port=port1)
        banner1 = self._proc1.start()
        self._steps["1_start_api"] = "PASS"
        pid1 = int(banner1["pid"])
        host = "127.0.0.1"
        port = int(banner1["port"])

        ingest_body = json.dumps(
            {
                "retrieved_time": retrieved,
                "articles": [
                    _raw_article(
                        headline="Example Corp reports quarterly earnings",
                        tickers=["AAPL"],
                        provider_native_id="fv-restart-watch",
                        published=published,
                    ),
                    _raw_article(
                        headline="Contoso Ltd reports quarterly earnings",
                        tickers=["MSFT"],
                        provider_native_id="fv-restart-dismiss",
                        published=published,
                    ),
                ],
            }
        ).encode("utf-8")

        # Steps 2–6: controlled ingress → EventV1 → PIT → mint → persist
        status, ingest = _http_json(host, port, "POST", NEWS_INGEST_ROUTE, body=ingest_body)
        self.assertEqual(status, 200, ingest)
        self._steps["2_provider_like_ingress"] = "PASS"
        self.assertEqual(ingest.get("admitted_count"), 2, ingest)
        self.assertEqual(ingest.get("opportunity_count"), 2, ingest)
        self.assertFalse(ingest.get("live_authority"))
        self.assertFalse(ingest.get("auto_fetch"))
        events = ingest.get("events") or []
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.get("event_id"))
            self.assertNotEqual(event.get("event_time_ns"), event.get("available_time_ns"))
            self.assertIsNotNone(event.get("received_time_ns"))
            self.assertLessEqual(int(event["available_time_ns"]), int(event["received_time_ns"]))
        self._steps["3_event_v1_created"] = "PASS"
        self._steps["4_pit_pass"] = "PASS"
        self.assertEqual(events[0].get("detector_detail"), "NEWS_ARTICLE_OPPORTUNITY_MINTED")
        self.assertEqual(events[1].get("detector_detail"), "NEWS_ARTICLE_OPPORTUNITY_MINTED")
        watch_id = str(ingest["opportunity_ids"][0])
        dismiss_id = str(ingest["opportunity_ids"][1])
        self.assertNotEqual(watch_id, dismiss_id)
        self._steps["5_opportunity_minted"] = "PASS"
        self._steps["6_persisted"] = "PASS"

        # Step 7: ranked API readback
        status, summary = _http_json(host, port, "GET", "/opportunities/summary")
        self.assertEqual(status, 200, summary)
        self.assertEqual(summary.get("feed_status"), "READY", summary)
        ranked_ids = {
            str(item.get("opportunity_id") or item.get("summary_id"))
            for item in (summary.get("items") or [])
        }
        self.assertIn(watch_id, ranked_ids)
        self.assertIn(dismiss_id, ranked_ids)
        self._steps["7_ranked_api_readback"] = "PASS"

        # Steps 8–9: operator WATCH/DISMISS + ack/trace/review
        status, watch_ack = _http_json(host, port, "POST", f"/opportunities/{watch_id}/watch")
        self.assertEqual(status, 200, watch_ack)
        self.assertEqual(watch_ack.get("action"), "WATCHED")
        self.assertEqual(watch_ack.get("opportunity_id"), watch_id)
        watch_review_id = str(watch_ack["trade_review_id"])

        status, dismiss_ack = _http_json(host, port, "POST", f"/opportunities/{dismiss_id}/dismiss")
        self.assertEqual(status, 200, dismiss_ack)
        self.assertEqual(dismiss_ack.get("action"), "DISMISSED")
        self.assertEqual(dismiss_ack.get("opportunity_id"), dismiss_id)
        dismiss_review_id = str(dismiss_ack["trade_review_id"])
        self._steps["8_watch_dismiss_operator_api"] = "PASS"

        status, watch_traces = _http_json(
            host,
            port,
            "GET",
            f"{TRACES_ROUTE}?opportunity_id={watch_id}",
        )
        self.assertEqual(status, 200, watch_traces)
        watch_kinds = {str(item.get("decision_kind")) for item in (watch_traces.get("items") or [])}
        self.assertIn("WATCH", watch_kinds)
        watch_trace = next(
            item for item in watch_traces["items"] if item.get("decision_kind") == "WATCH"
        )
        watch_trace_id = str(watch_trace["decision_trace_id"])

        status, dismiss_traces = _http_json(
            host,
            port,
            "GET",
            f"{TRACES_ROUTE}?opportunity_id={dismiss_id}",
        )
        self.assertEqual(status, 200, dismiss_traces)
        dismiss_kinds = {str(item.get("decision_kind")) for item in (dismiss_traces.get("items") or [])}
        self.assertIn("DISMISS", dismiss_kinds)
        dismiss_trace = next(
            item for item in dismiss_traces["items"] if item.get("decision_kind") == "DISMISS"
        )
        dismiss_trace_id = str(dismiss_trace["decision_trace_id"])

        status, watch_reviews = _http_json(
            host,
            port,
            "GET",
            f"/intelligence/trade-reviews?opportunity_id={watch_id}",
        )
        self.assertEqual(status, 200, watch_reviews)
        self.assertEqual(len(watch_reviews.get("items") or []), 1)
        self.assertEqual(watch_reviews["items"][0]["review_id"], watch_review_id)
        self.assertEqual(watch_reviews["items"][0]["review_mode"], "WATCHED_OPPORTUNITY")

        status, dismiss_reviews = _http_json(
            host,
            port,
            "GET",
            f"/intelligence/trade-reviews?opportunity_id={dismiss_id}",
        )
        self.assertEqual(status, 200, dismiss_reviews)
        self.assertEqual(len(dismiss_reviews.get("items") or []), 1)
        self.assertEqual(dismiss_reviews["items"][0]["review_id"], dismiss_review_id)
        self.assertEqual(dismiss_reviews["items"][0]["review_mode"], "REJECTED_OPPORTUNITY")
        self._steps["9_ack_trace_review_persisted"] = "PASS"

        status, post_summary = _http_json(host, port, "GET", "/opportunities/summary")
        self.assertEqual(status, 200, post_summary)
        remaining = {
            str(item.get("opportunity_id") or item.get("summary_id"))
            for item in (post_summary.get("items") or [])
        }
        self.assertIn(watch_id, remaining)
        self.assertNotIn(dismiss_id, remaining)

        # Step 10: terminate cleanly
        stopped_pid = pid1
        self._proc1.stop()
        deadline = time.time() + 10.0
        while time.time() < deadline and _pid_alive(stopped_pid):
            time.sleep(0.1)
        self.assertFalse(_pid_alive(stopped_pid), msg=f"API pid {stopped_pid} still alive after stop")
        # Windows SQLite WAL/lock release after forced kill needs a brief settle.
        time.sleep(1.5)
        _release_sqlite_after_kill(self._state_dir)
        self._steps["10_terminate_cleanly"] = "PASS"

        # Step 11: fresh process, SAME state dir
        last_error: Exception | None = None
        banner2: dict[str, Any] | None = None
        for attempt in range(3):
            self._proc2 = _ApiProcess(state_dir=self._state_dir, port=_unused_local_port())
            try:
                banner2 = self._proc2.start()
                break
            except AssertionError as exc:
                last_error = exc
                self._proc2.stop()
                time.sleep(1.0 + attempt)
        if banner2 is None:
            raise AssertionError(f"ENVIRONMENT_BLOCKER: fresh process failed to start: {last_error}")
        self._steps["11_start_fresh_same_state_dir"] = "PASS"
        pid2 = int(banner2["pid"])
        self.assertNotEqual(pid1, pid2)
        port = int(banner2["port"])
        self.assertNotIn(port, FORBIDDEN_PORTS)

        # Steps 12–13: query API + prove durability / idempotency
        status, summary2 = _http_json(host, port, "GET", "/opportunities/summary")
        self.assertEqual(status, 200, summary2)
        self._steps["12_query_api"] = "PASS"
        ranked2 = [
            str(item.get("opportunity_id") or item.get("summary_id"))
            for item in (summary2.get("items") or [])
        ]
        self.assertEqual(ranked2.count(watch_id), 1)
        self.assertNotIn(dismiss_id, ranked2)

        status, detail = _http_json(host, port, "GET", f"/opportunities/{watch_id}")
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail.get("opportunity_id"), watch_id)
        self.assertEqual(detail.get("lifecycle_state"), "WATCHED")

        status, dismissed_detail = _http_json(host, port, "GET", f"/opportunities/{dismiss_id}")
        self.assertEqual(status, 200, dismissed_detail)
        self.assertEqual(dismissed_detail.get("lifecycle_state"), "DISMISSED")

        status, watch_reviews2 = _http_json(
            host,
            port,
            "GET",
            f"/intelligence/trade-reviews?opportunity_id={watch_id}",
        )
        self.assertEqual(status, 200, watch_reviews2)
        self.assertEqual(len(watch_reviews2.get("items") or []), 1)
        self.assertEqual(watch_reviews2["items"][0]["review_id"], watch_review_id)

        status, dismiss_reviews2 = _http_json(
            host,
            port,
            "GET",
            f"/intelligence/trade-reviews?opportunity_id={dismiss_id}",
        )
        self.assertEqual(status, 200, dismiss_reviews2)
        self.assertEqual(len(dismiss_reviews2.get("items") or []), 1)
        self.assertEqual(dismiss_reviews2["items"][0]["review_id"], dismiss_review_id)

        status, watch_traces2 = _http_json(
            host,
            port,
            "GET",
            f"{TRACES_ROUTE}?opportunity_id={watch_id}",
        )
        self.assertEqual(status, 200, watch_traces2)
        watch_trace_ids = {str(item.get("decision_trace_id")) for item in (watch_traces2.get("items") or [])}
        self.assertIn(watch_trace_id, watch_trace_ids)
        self.assertEqual(
            sum(1 for item in watch_traces2["items"] if item.get("decision_kind") == "WATCH"),
            1,
        )

        status, dismiss_traces2 = _http_json(
            host,
            port,
            "GET",
            f"{TRACES_ROUTE}?opportunity_id={dismiss_id}",
        )
        self.assertEqual(status, 200, dismiss_traces2)
        dismiss_trace_ids = {str(item.get("decision_trace_id")) for item in (dismiss_traces2.get("items") or [])}
        self.assertIn(dismiss_trace_id, dismiss_trace_ids)
        self.assertEqual(
            sum(1 for item in dismiss_traces2["items"] if item.get("decision_kind") == "DISMISS"),
            1,
        )

        # Idempotency across restart: wall-clock received_time_ns differs on re-admit,
        # so store may fail-closed with EVENT_PERSIST_CONFLICT. That must not fork
        # OpportunityV1 identities or inflate the durable book.
        status, book_before = _http_json(host, port, "GET", BOOK_HEALTH_ROUTE)
        self.assertEqual(status, 200, book_before)
        opportunity_count_before = int((book_before.get("book") or {}).get("opportunity_count") or 0)
        self.assertGreaterEqual(opportunity_count_before, 2)

        reinject_status: int | None = None
        reinject: dict[str, Any] = {}
        try:
            reinject_status, reinject = _http_json(host, port, "POST", NEWS_INGEST_ROUTE, body=ingest_body)
        except Exception as exc:  # noqa: BLE001 - production request thread may drop on conflict
            reinject = {
                "error": "REMOTE_OR_INGRESS_FAILURE",
                "detail": str(exc),
                "note": "immutable receive-clock conflict expected without patched wall clock",
            }
        if reinject_status == 200:
            self.assertEqual(set(reinject.get("opportunity_ids") or []), {watch_id, dismiss_id})
            self.assertEqual(
                {str(row["event_id"]) for row in (reinject.get("events") or [])},
                {str(row["event_id"]) for row in events},
            )

        status, summary3 = _http_json(host, port, "GET", "/opportunities/summary")
        self.assertEqual(status, 200, summary3)
        ranked3 = [
            str(item.get("opportunity_id") or item.get("summary_id"))
            for item in (summary3.get("items") or [])
        ]
        self.assertEqual(ranked3.count(watch_id), 1)
        self.assertNotIn(dismiss_id, ranked3)

        status, book_after = _http_json(host, port, "GET", BOOK_HEALTH_ROUTE)
        self.assertEqual(status, 200, book_after)
        opportunity_count_after = int((book_after.get("book") or {}).get("opportunity_count") or 0)
        self.assertEqual(opportunity_count_after, opportunity_count_before)
        self.assertEqual(
            int((book_after.get("book") or {}).get("event_count") or 0),
            int((book_before.get("book") or {}).get("event_count") or 0),
        )

        self._steps["13_stable_identities_no_duplicates"] = "PASS"
        self._steps["duplicate_idempotency"] = "PASS"
        self._steps["classification"] = EVIDENCE_CLASS
        self._steps["ports"] = f"{banner1['port']},{banner2['port']}"
        self._steps["pids"] = f"{pid1}->{pid2}"
        self._steps["campaign_pids_untouched"] = "CONFIRMED_NO_SIGNAL"
        self.assertTrue(pid1 > 0 and pid2 > 0 and pid1 != pid2)

        self._proc2.stop()


if __name__ == "__main__":
    unittest.main()
