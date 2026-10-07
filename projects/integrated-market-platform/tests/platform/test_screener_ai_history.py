"""AI Screener results where the rows are: intake, evidence-derived reasons, and stored run history with a diff."""

from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_runs import HISTORY_SCHEMA, evidence_reasons, run_history, run_summary  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402

SCOPE = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True, "filters": [], "view": "Overview", "screen": "",
         "result_set": "set-1", "matched_count": 4630}


def evidence(instrument_id: str, *, news: int = 0, blocked: list[tuple[str, str]] = (), sufficient: bool = True) -> dict:
    return {"instrument": {"instrument_id": instrument_id, "symbol": instrument_id.split(":")[-1]},
            "current_market_evidence": [{"capability": "QUOTE", "evidence_id": f"EV:Q:{instrument_id}"}],
            "reference_evidence": [{"capability": "NEWS", "evidence_id": f"EV:N:{instrument_id}:{index}"} for index in range(news)],
            "blocked": [{"capability": capability, "reason_codes": [reason]} for capability, reason in blocked], "missing": [], "weak": [],
            "sufficient": sufficient}


def stored(run_id: str, *, selected: list[str] = (), at: str = "2026-10-07T13:58:12Z", scope: dict = SCOPE, **fields) -> dict:
    packet = [evidence("EQ:AAA"), evidence("EQ:BBB"), evidence("EQ:LABT")]
    return {"schema_version": "ai-screener-output/1.0.0", "run_id": run_id, "state": "CURRENT" if selected else "NO_GROUNDED_CANDIDATES", "reason": None,
            "scope": scope, "generated_at": at, "decision_cutoff": at, "valid_until": "2026-10-07T14:03:12Z", "provider_id": "anthropic.messages",
            "model_id": "claude-haiku-4-5", "runtime": "PAID_API", "cache": "MISS", "simulated": False, "tokens_input": 43_000, "tokens_output": 638,
            "latency_ms": 10_800, "packet_bytes": 95_600, "evidence": packet, "limitations": ["No candidate had news."],
            "candidates": [{"instrument_id": instrument_id, "rank": rank} for rank, instrument_id in enumerate(selected, 1)],
            "coverage": {"candidate_intake": len(packet), "selected": len(selected)}, **fields}


class EvidenceReasonTests(unittest.TestCase):
    def test_reasons_come_from_the_evidence_packet_with_counts_and_named_exceptions(self):
        packet = [evidence("EQ:AAA", blocked=[("TECHNICALS", "NO_OBSERVATION_TIME")]),
                  evidence("EQ:BBB", news=2, blocked=[("TECHNICALS", "NO_OBSERVATION_TIME")]),
                  evidence("EQ:LABT", blocked=[("TECHNICALS", "NO_OBSERVATION_TIME"), ("QUOTE", "AGE_EXCEEDS_POLICY")], sufficient=False)]

        reasons = evidence_reasons({"evidence": packet})

        self.assertEqual(reasons, [
            {"kind": "BLOCKED", "capability": "TECHNICALS", "reason": "NO_OBSERVATION_TIME", "count": 3, "of": 3, "symbols": ["AAA", "BBB", "LABT"]},
            {"kind": "NO_NEWS", "capability": "NEWS", "reason": None, "count": 2, "of": 3, "symbols": ["AAA", "LABT"]},
            {"kind": "BLOCKED", "capability": "QUOTE", "reason": "AGE_EXCEEDS_POLICY", "count": 1, "of": 3, "symbols": ["LABT"]},
            {"kind": "INSUFFICIENT", "capability": None, "reason": None, "count": 1, "of": 3, "symbols": ["LABT"]},
        ])

    def test_a_clean_packet_has_no_reasons_and_long_lists_are_bounded(self):
        self.assertEqual(evidence_reasons({"evidence": [evidence("EQ:AAA", news=1)]}), [])
        many = [evidence(f"EQ:S{index:02d}") for index in range(20)]
        reason = evidence_reasons({"evidence": many})[0]
        self.assertEqual((reason["kind"], reason["count"], reason["of"]), ("NO_NEWS", 20, 20))
        # A chip names at most three instruments; the count carries the rest.
        self.assertEqual(reason["symbols"], ["S00", "S01", "S02"])

    def test_the_run_summary_carries_the_intake_and_the_reasons(self):
        summary = run_summary(stored("run-1", selected=["EQ:AAA"]))

        self.assertEqual(summary["intake"], ["EQ:AAA", "EQ:BBB", "EQ:LABT"])
        self.assertEqual(summary["selected"], [{"instrument_id": "EQ:AAA", "rank": 1}])
        self.assertEqual(summary["reasons"][0]["kind"], "NO_NEWS")
        assert_no_secrets_in_payload(summary)


class RunHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = ActionDecisionRepository()

    def put(self, run: dict) -> None:
        self.repository.put("candidate_run", run["run_id"], run)

    def test_history_is_read_from_stored_runs_newest_first_with_what_changed(self):
        self.put(stored("run-1", selected=["EQ:AAA", "EQ:BBB"], at="2026-10-07T13:40:00Z"))
        self.put(stored("run-2", selected=["EQ:BBB", "EQ:LABT"], at="2026-10-07T13:50:00Z"))
        self.put(stored("run-3", at="2026-10-07T13:58:12Z"))

        history = run_history(self.repository, limit=20)

        self.assertEqual(history["schema_version"], HISTORY_SCHEMA)
        self.assertEqual([item["candidate_run_id"] for item in history["runs"]], ["run-3", "run-2", "run-1"])
        latest, middle, first = history["runs"]
        self.assertEqual((latest["previous_run_id"], latest["added"], latest["removed"]), ("run-2", [], ["EQ:BBB", "EQ:LABT"]))
        self.assertEqual((middle["previous_run_id"], middle["added"], middle["removed"]), ("run-1", ["EQ:LABT"], ["EQ:AAA"]))
        # Nothing to compare the first run with: no change is claimed.
        self.assertEqual((first["previous_run_id"], first["added"], first["removed"]), (None, None, None))
        self.assertEqual((latest["generated_at"], latest["model_id"], latest["state"], latest["selected_count"], latest["intake_count"]),
                         ("2026-10-07T13:58:12Z", "claude-haiku-4-5", "NO_GROUNDED_CANDIDATES", 0, 3))
        self.assertEqual((latest["tokens_input"], latest["tokens_output"], latest["latency_ms"], latest["cache"]), (43_000, 638, 10_800, "MISS"))
        # History rows are small: no evidence packet travels with them.
        self.assertNotIn("evidence", latest)
        assert_no_secrets_in_payload(history)

    def test_a_run_is_compared_only_with_the_previous_run_of_the_same_screener_query(self):
        other = {**SCOPE, "sort": "price"}
        self.put(stored("run-1", selected=["EQ:AAA"], at="2026-10-07T13:40:00Z"))
        self.put(stored("run-other", selected=["EQ:BBB"], at="2026-10-07T13:45:00Z", scope=other))
        # The same query after a list refresh is still the same query.
        self.put(stored("run-2", selected=["EQ:AAA", "EQ:LABT"], at="2026-10-07T13:50:00Z", scope={**SCOPE, "result_set": "set-2", "matched_count": 4631}))

        runs = {item["candidate_run_id"]: item for item in run_history(self.repository, limit=20)["runs"]}

        self.assertEqual((runs["run-2"]["previous_run_id"], runs["run-2"]["added"], runs["run-2"]["removed"]), ("run-1", ["EQ:LABT"], []))
        self.assertEqual(runs["run-other"]["previous_run_id"], None)
        self.assertEqual(runs["run-2"]["scope"]["sort"], "volume")

    def test_history_is_bounded_and_empty_history_says_so(self):
        self.assertEqual(run_history(self.repository, limit=20)["runs"], [])
        for index in range(8):
            self.put(stored(f"run-{index}", selected=["EQ:AAA"], at=f"2026-10-07T13:{index:02d}:00Z"))

        history = run_history(self.repository, limit=3)

        self.assertEqual([item["candidate_run_id"] for item in history["runs"]], ["run-7", "run-6", "run-5"])
        # The oldest listed run is still compared with its real predecessor, which is outside the page.
        self.assertEqual(history["runs"][-1]["previous_run_id"], "run-4")
        with self.assertRaisesRegex(ValueError, "INVALID_HISTORY_LIMIT"):
            run_history(self.repository, limit=0)
        with self.assertRaisesRegex(ValueError, "INVALID_HISTORY_LIMIT"):
            run_history(self.repository, limit=51)

    def test_history_reads_the_durable_store_in_insertion_order(self):
        import tempfile

        from market_platform_foundation.local_state.connection import LocalStateConnection

        with tempfile.TemporaryDirectory() as directory:
            connection = LocalStateConnection(Path(directory) / "state.sqlite")
            try:
                durable = ActionDecisionRepository(connection)
                # Written out of clock order on purpose: history follows what was stored last, not a run's own clock.
                durable.put("candidate_run", "run-b", stored("run-b", selected=["EQ:BBB"], at="2026-10-07T13:50:00Z"))
                durable.put("candidate_run", "run-a", stored("run-a", selected=["EQ:AAA"], at="2026-10-07T13:40:00Z"))
                runs = run_history(durable, limit=20)["runs"]
            finally:
                connection.close()

        self.assertEqual([item["candidate_run_id"] for item in runs], ["run-a", "run-b"])
        self.assertEqual((runs[0]["previous_run_id"], runs[0]["added"], runs[0]["removed"]), ("run-b", ["EQ:AAA"], ["EQ:BBB"]))

    def test_decisions_are_not_candidate_runs_and_history_is_a_read(self):
        self.repository.put("decision", "decision-1", {"instrument_id": "EQ:AAA", "decision_time": "2026-10-07T13:00:00Z", "position": {"account_id": "p"}})
        self.assertEqual(run_history(self.repository, limit=20)["runs"], [])
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/runs/history").capability, "state.read")


class RunHistoryRouteTests(unittest.TestCase):
    """The history as the browser receives it: through the real handler and its response guard."""

    def setUp(self) -> None:
        self.repository = ActionDecisionRepository()
        for index in range(3):
            run = stored(f"run-{index}", selected=["EQ:AAA"] if index else [], at=f"2026-10-07T13:{index:02d}:00Z")
            self.repository.put("candidate_run", run["run_id"], run)
        store = SimpleNamespace(paper_ledger=SimpleNamespace(paper_account_id="PAPER-1"))
        for patcher in (patch.object(UiApiHandler, "store", store, create=True), patch.object(UiApiHandler, "_authorize_request", return_value=True),
                        patch("market_platform_foundation.local_state.action_decisions.action_repository", lambda: self.repository)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path: str) -> tuple[int, dict]:
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=30)
        connection.request("GET", path)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, payload

    def test_history_is_served_bounded_and_passes_the_response_guard(self):
        status, payload = self.get("/screener/ai-screener/runs/history?limit=2")

        self.assertEqual((status, payload["schema_version"]), (200, HISTORY_SCHEMA))
        self.assertEqual([item["candidate_run_id"] for item in payload["runs"]], ["run-2", "run-1"])
        self.assertEqual((payload["runs"][0]["tokens_input"], payload["runs"][0]["added"], payload["runs"][0]["removed"]), (43_000, [], []))
        self.assertEqual(payload["runs"][1]["added"], ["EQ:AAA"])

    def test_an_out_of_range_or_malformed_limit_is_refused(self):
        for limit in ("0", "51", "many"):
            with self.subTest(limit=limit):
                status, payload = self.get(f"/screener/ai-screener/runs/history?limit={limit}")
                self.assertEqual((status, payload["reason_code"], payload["error"]), (400, "SCREENER_AI_INVALID", "INVALID_HISTORY_LIMIT"))


if __name__ == "__main__":
    unittest.main()
