"""Engine picker safety: the machine-wide engine choice is locked while a loop runs, and each engine says whether the packet fits."""

from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.local_provider import MANIFEST_RELATIVE  # noqa: E402
from market_platform_foundation.intelligence.inference.synthesis_engines import engine_options  # noqa: E402
from market_platform_foundation.local_state.external_cache import write_json_atomic  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.ui_api import screener_news  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService, engine_fit  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler, with_engine_lock  # noqa: E402
from tests.intelligence.test_reevaluation import Harness  # noqa: E402
from tests.platform.test_screener_s18 import NOW, CandidateProvider, News, Reader, row  # noqa: E402

SCOPE = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True, "filters": [], "result_set": "set-1"}


class EngineContextTests(unittest.TestCase):
    def test_a_managed_local_model_states_its_context_window_and_hosted_engines_claim_none(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            for name in ("llama-server.exe", "model.gguf"):
                (cache / name).write_bytes(b"x")
            write_json_atomic(cache / MANIFEST_RELATIVE, {"runtime_path": str(cache / "llama-server.exe"), "model_path": str(cache / "model.gguf"),
                                                          "model_id": "small-4b", "context": 8192})

            options = {item["id"]: item for item in engine_options({"ANTHROPIC_API_KEY": "k"}.get, cache)}

            self.assertEqual((options["local"]["state"], options["local"]["context_window"]), ("AVAILABLE", 8192))
            assert_no_secrets_in_payload({"ai": {"engines": list(options.values())}})
            # IMP records no context window for hosted models, so it states none instead of guessing one.
            self.assertIsNone(options["anthropic"]["context_window"])
            # An operator-run local endpoint is not described by the manifest.
            external = {"IMP_LOCAL_LLM_BASE_URL": "http://127.0.0.1:9999", "IMP_LOCAL_LLM_MODEL": "mine"}
            local = next(item for item in engine_options(external.get, cache) if item["id"] == "local")
            self.assertEqual((local["state"], local["context_window"]), ("AVAILABLE", None))


class PacketFitTests(unittest.TestCase):
    ENGINES = [{"id": "local", "runtime": "LOCAL_MODEL", "state": "AVAILABLE", "context_window": 8192},
               {"id": "anthropic", "runtime": "PAID_API", "state": "AVAILABLE", "context_window": None},
               {"id": "gemini", "runtime": "PAID_API", "state": "NOT_CONFIGURED", "context_window": None}]

    def test_an_engine_whose_context_is_smaller_than_the_packet_is_marked_unfit(self):
        fit = {item["engine"]: item for item in engine_fit(self.ENGINES, input_tokens=34_740, output_tokens=2_600)}

        self.assertEqual(fit["local"], {"engine": "local", "fits": False, "packet_size": 37_340, "context_window": 8192})
        # No recorded limit: neither "fits" nor "does not fit" is claimed.
        self.assertEqual(fit["anthropic"], {"engine": "anthropic", "fits": None, "packet_size": 37_340, "context_window": None})
        self.assertEqual(fit["gemini"]["fits"], None)

    def test_a_small_packet_fits_and_an_unknown_packet_size_claims_nothing(self):
        self.assertTrue(engine_fit(self.ENGINES, input_tokens=4_000, output_tokens=2_600)[0]["fits"])
        unknown = engine_fit(self.ENGINES, input_tokens=None, output_tokens=2_600)[0]
        self.assertEqual((unknown["fits"], unknown["packet_size"]), (None, None))

    def test_the_preview_reports_fit_for_every_listed_engine(self):
        provider = CandidateProvider()
        news = News(provider)
        status = news.ai_status()
        news.ai_status = lambda: {**status, "engines": self.ENGINES}
        service = ScreenerAiService(reader=Reader([row("EQ:A")]), news=news, clock=lambda: NOW)

        preview = service.preview(SCOPE)

        self.assertEqual([item["engine"] for item in preview["engine_fit"]], ["local", "anthropic", "gemini"])
        assert_no_secrets_in_payload(preview)
        required = preview["estimate"]["input_tokens"] + 2_600
        self.assertEqual(preview["engine_fit"][0], {"engine": "local", "fits": required <= 8192, "packet_size": required, "context_window": 8192})
        self.assertEqual(provider.calls, 0)


class EngineLockTests(unittest.TestCase):
    def test_the_choice_is_free_until_a_loop_holds_its_lease_and_free_again_after_stop(self):
        harness = Harness()
        self.assertEqual(harness.service.engine_lock(), {"locked": False, "reason": None})
        harness.configure()
        self.assertFalse(harness.service.engine_lock()["locked"])

        harness.service.start(wait=lambda seconds: True, threaded=False)
        self.assertEqual(harness.service.engine_lock(), {"locked": True, "reason": "REEVALUATION_LOOP_RUNNING"})

        harness.service.stop()
        self.assertFalse(harness.service.engine_lock()["locked"])

    def test_a_lease_held_by_another_process_also_locks_and_an_expired_lease_does_not(self):
        first = Harness()
        first.configure()
        first.service.start(wait=lambda seconds: True, threaded=False)
        from market_platform_foundation.ui_api.screener_reevaluation import ReevaluationService

        other = ReevaluationService(first.store, repository=first.repo, actions=first.actions, ai=first.ai, clock=first.clock, owner_id="other-process")
        self.assertTrue(other.engine_lock()["locked"])

        first.clock.value += 24 * 3600
        self.assertFalse(other.engine_lock()["locked"])


class EngineLockInResponsesTests(unittest.TestCase):
    def test_a_response_that_offers_the_picker_states_the_lock_and_others_are_untouched(self):
        lock = {"locked": True, "reason": "REEVALUATION_LOOP_RUNNING"}
        reads: list[int] = []
        read = lambda: reads.append(1) or lock  # noqa: E731

        offered = with_engine_lock({"ai": {"state": "AVAILABLE", "engines": [{"id": "local"}]}, "rows": []}, read)
        self.assertEqual(offered["ai"]["engine_lock"], lock)
        self.assertEqual(offered["rows"], [])

        plain = {"ai": {"state": "AVAILABLE"}, "rows": []}
        self.assertIs(with_engine_lock(plain, read), plain)
        self.assertIs(with_engine_lock({"rows": []}, read)["rows"].__class__, list)
        # The lease is read only for responses that carry the picker.
        self.assertEqual(len(reads), 1)


class EngineRouteLockTests(unittest.TestCase):
    """Frontend gating is not security: the route itself refuses a switch while the loop runs."""

    def setUp(self) -> None:
        self.selected: list[tuple[str, str | None]] = []
        self.lock = {"locked": False, "reason": None}
        store = SimpleNamespace(_reevaluation_service=SimpleNamespace(engine_lock=lambda: dict(self.lock)))
        select = lambda engine, model=None: self.selected.append((engine, model)) or {"state": "AVAILABLE", "reason": None, "provider_id": "p", "model_id": model, "runtime": "PAID_API"}  # noqa: E731
        for patcher in (patch.object(UiApiHandler, "store", store, create=True), patch.object(UiApiHandler, "_authorize_request", return_value=True),
                        patch.object(screener_news, "select_synthesis_engine", select)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def post(self, body: dict) -> tuple[int, dict]:
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=30)
        connection.request("POST", "/screener/news/synthesis/engine", body=json.dumps(body), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, payload

    def test_a_switch_is_refused_while_locked_and_nothing_is_saved(self):
        self.lock = {"locked": True, "reason": "REEVALUATION_LOOP_RUNNING"}

        status, payload = self.post({"engine": "local", "model": None})

        self.assertEqual((status, payload["reason_code"]), (409, "SYNTHESIS_ENGINE_LOCKED"))
        self.assertIn("REEVALUATION_LOOP_RUNNING", payload["error"])
        self.assertEqual(self.selected, [])

    def test_a_switch_goes_through_when_no_loop_runs_and_reports_the_lock_state(self):
        status, payload = self.post({"engine": "anthropic", "model": "claude-haiku-4-5-20251001"})

        self.assertEqual(status, 200)
        self.assertEqual(self.selected, [("anthropic", "claude-haiku-4-5-20251001")])
        self.assertEqual(payload["engine_lock"], {"locked": False, "reason": None})

    def test_an_unreadable_loop_state_fails_closed(self):
        UiApiHandler.store._reevaluation_service.engine_lock = lambda: (_ for _ in ()).throw(RuntimeError("db unavailable"))

        status, payload = self.post({"engine": "local", "model": None})

        self.assertEqual((status, payload["reason_code"]), (409, "SYNTHESIS_ENGINE_LOCKED"))
        self.assertIn("REEVALUATION_STATE_UNKNOWN", payload["error"])
        self.assertEqual(self.selected, [])


if __name__ == "__main__":
    unittest.main()
