"""Zero-cost local AI synthesis: provider selection, loopback-only transport, grounding, failure states,
and the on-demand llama-server lifecycle. Every HTTP call and process is a fake: no network, no model."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.local_provider import (  # noqa: E402
    MANIFEST_RELATIVE, SERVER_ALIAS, LocalChatInferenceProvider, LocalLlamaServer, LocalModelManifest,
    is_loopback_url, select_synthesis_provider,
)
from market_platform_foundation.intelligence.inference.screener_synthesis import (  # noqa: E402
    MAX_STORIES, ScreenerSynthesizer, SynthesisStory, output_json_schema,
)
from market_platform_foundation.local_state.external_cache import write_json_atomic  # noqa: E402


def story(index, headline, summary="", when="2026-09-29T14:00:00Z", publishers=("Wire",)):
    return SynthesisStory(story_id=f"s{index}", headline=headline, summary=summary, published_time=when, retrieved_time=when,
                          source_type="NEWS", source_count=len(publishers), publishers=publishers, categories=())


STORIES = [story(1, "Acme beats revenue estimates", "Revenue rose 8%."),
           story(2, "Acme cuts full-year margin outlook", "Margin now seen at 14%."),
           story(3, "Acme shares fall despite the beat", "Shares were down 3%.", when="2026-09-27T14:00:00Z")]


def grounded(ids, **overrides):
    payload = {"summary": "Acme beat revenue estimates but cut its margin outlook; shares fell.",
               "observed_facts": [{"text": "Revenue beat estimates.", "refs": [ids[0]]},
                                  {"text": "Margin outlook was cut.", "refs": [ids[1]]}],
               "derived_context": [{"text": "The outlook cut may weigh on the reaction to the beat.", "refs": ids[:2]}],
               "uncertainties": ["Only one outlet per story."],
               "conflicting_evidence": [{"text": "A revenue beat alongside a lower margin outlook.", "refs": ids[:2]}],
               "potential_market_relevance": [{"text": "Guidance changes can matter to the shares.", "refs": [ids[1]]}]}
    payload.update(overrides)
    return payload


class FakeTransport:
    def __init__(self, content=None, *, status=200, raise_exc=None):
        self.content, self.status, self.raise_exc, self.bodies = content, status, raise_exc, []

    def __call__(self, url, body, timeout):
        request = json.loads(body.decode("utf-8"))
        self.bodies.append((url, request, timeout))
        if self.raise_exc is not None:
            raise self.raise_exc
        schema_ids = request["response_format"]["json_schema"]["schema"]["properties"]["observed_facts"]["items"][
            "properties"]["refs"]["items"]["enum"]
        content = self.content(schema_ids) if callable(self.content) else self.content
        return self.status, json.dumps({"id": "r1", "choices": [{"message": {"content": content}}],
                                        "usage": {"prompt_tokens": 10, "completion_tokens": 20}}).encode("utf-8")


def local(transport, base_url="http://127.0.0.1:18089"):
    provider = LocalChatInferenceProvider(base_url=base_url, model_id="Qwen/Qwen3-4B-GGUF:Q4_K_M", poster=transport)
    return provider, ScreenerSynthesizer(provider=provider, clock=lambda: 1_790_000_000.0)


class SelectionTests(unittest.TestCase):
    def test_priority_and_zero_cost_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            values = {}
            none = select_synthesis_provider(values.get, cache_dir=cache)
            self.assertEqual((none.provider, none.reason, none.runtime), (None, "NO_SYNTHESIS_PROVIDER_CONFIGURED", None))
            values.update(IMP_LOCAL_LLM_BASE_URL="http://127.0.0.1:11434", IMP_LOCAL_LLM_MODEL="qwen3:4b")
            chosen = select_synthesis_provider(values.get, cache_dir=cache)
            self.assertEqual((chosen.runtime, chosen.provider.model_id), ("LOCAL_MODEL", "qwen3:4b"))
            values["ANTHROPIC_API_KEY"] = "k"
            paid = select_synthesis_provider(values.get, cache_dir=cache, anthropic_factory=lambda: "anthropic")
            self.assertEqual((paid.provider, paid.runtime), ("anthropic", "PAID_API"))
            values["IMP_SYNTHESIS_PROVIDER"] = "local"            # the owner can force the zero-cost path
            self.assertEqual(select_synthesis_provider(values.get, cache_dir=cache).runtime, "LOCAL_MODEL")

    def test_remote_endpoint_is_refused(self):
        values = {"IMP_LOCAL_LLM_BASE_URL": "https://api.example.test/v1", "IMP_LOCAL_LLM_MODEL": "m"}
        with tempfile.TemporaryDirectory() as directory:
            selection = select_synthesis_provider(values.get, cache_dir=Path(directory))
        self.assertEqual((selection.provider, selection.reason), (None, "LOCAL_ENDPOINT_NOT_LOOPBACK"))
        self.assertTrue(is_loopback_url("http://localhost:1234"))
        self.assertFalse(is_loopback_url("http://10.0.0.5:1234"))

    def test_manifest_with_missing_files_is_not_configured(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            write_json_atomic(cache / MANIFEST_RELATIVE, {"runtime_path": str(cache / "nope.exe"),
                                                          "model_path": str(cache / "nope.gguf"), "model_id": "m"})
            selection = select_synthesis_provider({}.get, cache_dir=cache)
        self.assertEqual((selection.provider, selection.reason), (None, "LOCAL_RUNTIME_NOT_FOUND"))


class GroundingTests(unittest.TestCase):
    def test_grounded_summary_with_conflict_and_refs(self):
        transport = FakeTransport(lambda ids: json.dumps(grounded(ids)))
        _, synth = local(transport)
        result = synth.synthesize(STORIES, instruments=("ACME",), as_of="2026-09-29T15:00:00Z")
        self.assertEqual((result["state"], result["runtime"]), ("CURRENT", "LOCAL_MODEL"))
        refs = {ref for key in ("observed_facts", "conflicting_evidence") for item in result["synthesis"][key] for ref in item["refs"]}
        self.assertLessEqual(refs, {"s1", "s2", "s3"})
        self.assertTrue(result["synthesis"]["conflicting_evidence"])
        url, request, _ = transport.bodies[0]
        self.assertEqual(url, "http://127.0.0.1:18089/v1/chat/completions")
        self.assertEqual(request["temperature"], 0)
        prompt = request["messages"][1]["content"]
        self.assertIn("2026-09-27T14:00:00Z", prompt)            # an older story keeps its own timestamp
        self.assertIn("Acme shares fall despite the beat", prompt)
        again = synth.synthesize(STORIES, instruments=("ACME",), as_of="2026-09-29T15:00:00Z")
        self.assertEqual((again["cache"], len(transport.bodies)), ("HIT", 1))

    def test_schema_limits_refs_to_packet_ids(self):
        schema = output_json_schema(["s1", "s2"])
        self.assertEqual(schema["properties"]["observed_facts"]["items"]["properties"]["refs"]["items"]["enum"], ["s1", "s2"])
        self.assertEqual(schema["properties"]["observed_facts"]["minItems"], 1)
        self.assertEqual(schema["properties"]["uncertainties"]["items"], {"type": "string"})

    def test_hallucinated_ref_and_unsupported_conclusion_are_rejected(self):
        _, synth = local(FakeTransport(lambda ids: json.dumps(grounded(ids, observed_facts=[{"text": "x", "refs": ["s99"]}]))))
        self.assertEqual(synth.synthesize(STORIES, instruments=("ACME",), as_of="t")["reason"], "INVALID_OBSERVED_FACTS")
        _, synth = local(FakeTransport(lambda ids: json.dumps(grounded(ids, summary="Acme will rally after the beat."))))
        self.assertEqual(synth.synthesize(STORIES, instruments=("ACME",), as_of="t")["reason"], "UNSUPPORTED_CERTAINTY")

    def test_malformed_output_and_thinking_tags(self):
        _, synth = local(FakeTransport("{not json"))
        result = synth.synthesize(STORIES, instruments=("ACME",), as_of="t")
        self.assertEqual((result["state"], result["reason"], result["synthesis"]), ("INVALID_OUTPUT", "MALFORMED_JSON", None))
        _, synth = local(FakeTransport(lambda ids: "<think>reasoning</think>" + json.dumps(grounded(ids))))
        self.assertEqual(synth.synthesize(STORIES, instruments=("ACME",), as_of="t")["state"], "CURRENT")

    def test_model_unavailable_timeout_and_http_errors_are_states(self):
        cases = [(FakeTransport(raise_exc=URLError(ConnectionRefusedError())), "LOCAL_MODEL_UNAVAILABLE"),
                 (FakeTransport(raise_exc=TimeoutError()), "LOCAL_MODEL_TIMEOUT"),
                 (FakeTransport(raise_exc=URLError("timed out")), "LOCAL_MODEL_TIMEOUT"),
                 (FakeTransport("{}", status=500), "LOCAL_MODEL_HTTP_500")]
        for transport, reason in cases:
            _, synth = local(transport)
            result = synth.synthesize(STORIES, instruments=("ACME",), as_of="t")
            self.assertEqual((result["state"], result["reason"], result["synthesis"]), ("UNAVAILABLE", reason, None), reason)

    def test_no_stories_and_packet_bound(self):
        transport = FakeTransport(lambda ids: json.dumps(grounded(ids)))
        _, synth = local(transport)
        empty = synth.synthesize([], instruments=("ACME",), as_of="t")
        self.assertEqual((empty["state"], empty["reason"], len(transport.bodies)), ("INSUFFICIENT_EVIDENCE", "NO_STORIES_IN_WINDOW", 0))
        many = [story(index, f"Peer {index} reports") for index in range(1, 21)]
        result = synth.synthesize(many, instruments=("ACME",), as_of="t")
        self.assertEqual(len(result["story_ids"]), MAX_STORIES)   # names only what the model was given

    def test_remote_base_url_never_called(self):
        transport = FakeTransport("{}")
        _, synth = local(transport, base_url="https://api.example.test")
        result = synth.synthesize(STORIES, instruments=("ACME",), as_of="t")
        self.assertEqual((result["state"], result["reason"], transport.bodies), ("UNAVAILABLE", "LOCAL_ENDPOINT_NOT_LOOPBACK", []))

    def test_local_provider_gets_a_longer_budget(self):
        provider, synth = local(FakeTransport("{}"))
        self.assertGreaterEqual(synth._config.timeout_seconds, 120)
        self.assertEqual(ScreenerSynthesizer(provider=None)._config.timeout_seconds, 45.0)


class FakeProcess:
    def __init__(self, exits=False):
        self.exits, self.terminated = exits, False

    def poll(self):
        return 1 if self.exits or self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


class ServerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / "llama-server.exe").write_bytes(b"x")
        (root / "model.gguf").write_bytes(b"x")
        self.manifest = LocalModelManifest(root / "llama-server.exe", root / "model.gguf", "m", "rev", "b1")
        self.clock = [0.0]

    def tearDown(self):
        self.directory.cleanup()

    def server(self, getter, spawn):
        return LocalLlamaServer(self.manifest, getter=getter, spawn=spawn, clock=lambda: self.clock[0],
                                sleep=lambda s: self.clock.__setitem__(0, self.clock[0] + s), startup_timeout_s=5)

    def test_starts_once_on_loopback_and_reuses(self):
        spawned, up = [], {"on": False}

        def spawn(args, **kwargs):
            spawned.append(args)
            up["on"] = True
            return FakeProcess()

        def getter(url, timeout):
            if not up["on"]:
                raise URLError("refused")
            if url.endswith("/v1/models"):
                return 200, json.dumps({"data": [{"id": SERVER_ALIAS}]}).encode()
            return 200, b"{}"
        server = self.server(getter, spawn)
        self.assertIsNone(server.ensure_running())
        self.assertIsNone(server.ensure_running())
        self.assertEqual(len(spawned), 1)
        args = spawned[0]
        self.assertEqual(args[args.index("--host") + 1], "127.0.0.1")
        self.assertIn("--no-webui", args)
        server.stop()
        self.assertFalse(server.running())

    def test_foreign_port_owner_missing_files_and_exit_are_states(self):
        foreign = self.server(lambda url, timeout: (200, json.dumps({"data": [{"id": "other"}]}).encode()),
                              lambda *a, **k: self.fail("must not spawn over a foreign server"))
        self.assertEqual(foreign.ensure_running(), "LOCAL_MODEL_PORT_IN_USE")

        def refused(url, timeout):
            raise URLError("refused")
        exited = self.server(refused, lambda *a, **k: FakeProcess(exits=True))
        self.assertEqual(exited.ensure_running(), "LOCAL_RUNTIME_EXITED")
        slow = self.server(refused, lambda *a, **k: FakeProcess())
        self.assertEqual(slow.ensure_running(), "LOCAL_RUNTIME_START_TIMEOUT")
        self.manifest.model_path.unlink()
        self.assertEqual(self.server(refused, lambda *a, **k: FakeProcess()).ensure_running(), "LOCAL_MODEL_FILE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
