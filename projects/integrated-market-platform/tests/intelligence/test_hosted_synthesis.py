"""Paid OpenAI / Gemini synthesis and the operator's engine choice.

Every HTTP call is a fake transport and every configuration a dict: no network, no key, no spend."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.inference.anthropic_synthesis import (  # noqa: E402
    BUDGET_RELATIVE, BudgetedProvider, DailyBudget,
)
from market_platform_foundation.intelligence.inference.hosted_synthesis import (  # noqa: E402
    GEMINI, OPENAI, REASONING_HEADROOM, HostedChatSynthesisProvider,
)
from market_platform_foundation.intelligence.inference.local_provider import select_synthesis_provider  # noqa: E402
from market_platform_foundation.intelligence.inference.screener_synthesis import ScreenerSynthesizer  # noqa: E402
from market_platform_foundation.intelligence.inference.synthesis_engines import (  # noqa: E402
    ENGINE_SETTINGS_RELATIVE, SynthesisSettings, engine_options,
)
from tests.intelligence.test_anthropic_synthesis_budget import Clock  # noqa: E402
from tests.intelligence.test_local_synthesis_provider import STORIES, grounded  # noqa: E402
from tools.news.auth import configured_values  # noqa: E402


class FakeChat:
    """Chat Completions stand-in: answers with schema JSON, or a scripted status / finish reason."""

    def __init__(self, *, content=None, status=200, finish_reason="stop", raise_exc=None, usage=(800, 300), refusal=None):
        self.content, self.status, self.finish_reason = content, status, finish_reason
        self.raise_exc, self.usage, self.refusal = raise_exc, usage, refusal
        self.requests = []

    def __call__(self, url, body, headers, timeout):
        request = json.loads(body.decode("utf-8"))
        self.requests.append((url, request, headers, timeout))
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.status != 200:
            return self.status, json.dumps({"error": {"message": "echo of the request"}}).encode()
        schema = request["response_format"]["json_schema"]["schema"]
        ids = schema["properties"]["observed_facts"]["items"]["properties"]["refs"]["items"]["enum"]
        content = self.content(ids) if callable(self.content) else self.content
        return 200, json.dumps({"id": "chatcmpl-1", "choices": [{"index": 0, "finish_reason": self.finish_reason,
                                "message": {"role": "assistant", "content": content, "refusal": self.refusal}}],
                                "usage": {"prompt_tokens": self.usage[0], "completion_tokens": self.usage[1]}}).encode()


def hosted(transport, *, vendor=OPENAI, model="gpt-6-luna", effort="none", budget=None, clock=None):
    clock = clock or Clock()
    provider = BudgetedProvider(HostedChatSynthesisProvider(vendor=vendor, api_key="test-key", model=model,
                                                            reasoning_effort=effort, poster=transport),
                                budget or DailyBudget(None, clock=clock))
    return provider, ScreenerSynthesizer(provider=provider, clock=clock)


def run(synth):
    return synth.synthesize(STORIES, instruments=("ACME",), as_of="t")


def answer(ids):
    return json.dumps(grounded(ids))


class HostedRequestTests(unittest.TestCase):
    def test_openai_luna_schema_typed_no_reasoning_and_temperature_zero(self):
        transport = FakeChat(content=answer)
        _, synth = hosted(transport)
        result = run(synth)
        self.assertEqual((result["state"], result["runtime"], result["provider_id"], result["model_id"]),
                         ("CURRENT", "PAID_API", "openai.chat_completions", "gpt-6-luna"))
        url, body, headers, timeout = transport.requests[0]
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual((body["model"], body["reasoning_effort"], body["temperature"], body["max_completion_tokens"]),
                         ("gpt-6-luna", "none", 0, 2048))
        schema = body["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        refs = schema["schema"]["properties"]["observed_facts"]["items"]["properties"]["refs"]["items"]
        self.assertEqual(refs["enum"], ["s1", "s2", "s3"])                      # refs limited to the packet
        self.assertEqual(timeout, 45.0)

    def test_reasoning_models_get_headroom_and_no_temperature(self):
        transport = FakeChat(content=answer)
        _, synth = hosted(transport, vendor=GEMINI, model="gemini-3.8-flash", effort="low")
        self.assertEqual(run(synth)["provider_id"], "gemini.openai_compatible")
        url, body, _, _ = transport.requests[0]
        self.assertTrue(url.startswith("https://generativelanguage.googleapis.com/v1beta/openai/"))
        self.assertNotIn("temperature", body)
        self.assertEqual((body["reasoning_effort"], body["max_completion_tokens"]), ("low", 2048 + REASONING_HEADROOM))

    def test_budget_reserves_the_reasoning_headroom(self):
        transport = FakeChat(content=answer)
        provider, synth = hosted(transport, effort="low")
        plain, _ = hosted(transport, effort="none")
        config = synth._config
        self.assertEqual(provider.worst_case_tokens("prompt", config) - plain.worst_case_tokens("prompt", config),
                         REASONING_HEADROOM)
        estimate = synth.estimate(STORIES, instruments=("ACME",), as_of="t")
        self.assertGreater(estimate["tokens"], config.max_tokens + REASONING_HEADROOM)

    def test_budget_refusal_sends_nothing(self):
        transport = FakeChat(content=answer)
        clock = Clock()
        _, synth = hosted(transport, effort="low", budget=DailyBudget(None, max_requests=9, max_tokens=3_000, clock=clock),
                          clock=clock)
        refused = run(synth)
        self.assertEqual((refused["reason"], transport.requests), ("SYNTHESIS_DAILY_TOKEN_LIMIT", []))

    def test_failures_are_stable_vendor_codes(self):
        cases = [(FakeChat(status=401), OPENAI, "OPENAI_AUTH_FAILED"),
                 (FakeChat(status=429), GEMINI, "GEMINI_HTTP_429"),
                 (FakeChat(status=404), OPENAI, "OPENAI_HTTP_404"),
                 (FakeChat(raise_exc=TimeoutError()), GEMINI, "GEMINI_TIMEOUT"),
                 (FakeChat(raise_exc=OSError("connection refused")), OPENAI, "OPENAI_UNREACHABLE"),
                 (FakeChat(content=answer, finish_reason="length"), OPENAI, "OPENAI_OUTPUT_TRUNCATED"),
                 (FakeChat(content=None, refusal="no"), OPENAI, "OPENAI_REFUSED"),
                 (FakeChat(content=""), GEMINI, "GEMINI_RESPONSE_MALFORMED")]
        for transport, vendor, reason in cases:
            with self.subTest(reason=reason):
                result = run(hosted(transport, vendor=vendor)[1])
                self.assertEqual((result["state"], result["reason"], result["synthesis"]), ("UNAVAILABLE", reason, None))
                self.assertNotIn("echo", json.dumps(result))                   # error bodies never surface

    def test_missing_key_is_not_configured_without_a_request(self):
        transport = FakeChat(content=answer)
        synth = ScreenerSynthesizer(provider=HostedChatSynthesisProvider(vendor=OPENAI, api_key="", model="gpt-6-luna",
                                                                         reasoning_effort="none", poster=transport))
        result = run(synth)
        self.assertEqual((result["state"], result["reason"], transport.requests), ("NOT_CONFIGURED", "API_KEY_MISSING", []))

    def test_output_is_still_validated(self):
        result = run(hosted(FakeChat(content=lambda ids: json.dumps(grounded(ids, summary="Investors should buy now."))))[1])
        self.assertEqual((result["state"], result["reason"]), ("INVALID_OUTPUT", "UNSUPPORTED_CERTAINTY"))


class EngineSelectionTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.cache = Path(self._directory.name)

    def tearDown(self):
        self._directory.cleanup()

    def test_options_list_every_engine_and_why_it_cannot_run(self):
        options = {item["id"]: item for item in engine_options({"OPENAI_API_KEY": "k"}.get, self.cache)}
        self.assertEqual(list(options), ["local", "anthropic", "openai", "gemini"])
        self.assertEqual((options["openai"]["state"], options["openai"]["default_model"]), ("AVAILABLE", "gpt-6-luna"))
        self.assertEqual((options["gemini"]["state"], options["gemini"]["reason"]), ("NOT_CONFIGURED", "GEMINI_API_KEY_NOT_SET"))
        self.assertEqual(options["anthropic"]["reason"], "ANTHROPIC_API_KEY_NOT_SET")
        self.assertEqual((options["local"]["models"], options["local"]["reason"]), ([], "NO_SYNTHESIS_PROVIDER_CONFIGURED"))
        self.assertNotIn("k", json.dumps(options).split('"'))                  # a key value never appears

    def test_env_model_joins_the_list_as_default(self):
        values = {"GEMINI_API_KEY": "k", "IMP_SYNTHESIS_GEMINI_MODEL": "gemini-next"}
        gemini = engine_options(values.get, self.cache)[3]
        self.assertEqual(gemini["models"][:2], ["gemini-next", "gemini-3.8-flash"])
        chosen = select_synthesis_provider(values.get, cache_dir=self.cache, engine="gemini")
        self.assertEqual((chosen.provider.model_id, chosen.provider._provider.reasoning_effort), ("gemini-next", "low"))

    def test_operator_choice_beats_environment_beats_automatic(self):
        values = {"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o", "IMP_SYNTHESIS_PROVIDER": "local"}
        settings = SynthesisSettings(values.get, self.cache)
        self.assertEqual(settings.current(), {"engine": "local", "model": None, "source": "ENVIRONMENT"})
        settings.select("openai", "gpt-6.1-sol")
        self.assertEqual(settings.current(), {"engine": "openai", "model": "gpt-6.1-sol", "source": "OPERATOR"})
        selection = settings.build()
        self.assertEqual((selection.runtime, selection.provider.model_id, selection.provider._provider.reasoning_effort),
                         ("PAID_API", "gpt-6.1-sol", "low"))
        self.assertTrue((self.cache / ENGINE_SETTINGS_RELATIVE).is_file())      # survives a restart
        self.assertEqual(SynthesisSettings(values.get, self.cache).current()["engine"], "openai")
        automatic = SynthesisSettings({"ANTHROPIC_API_KEY": "a"}.get, self.cache / "fresh")
        self.assertEqual((automatic.current()["engine"], automatic.build().provider.model_id), ("auto", "claude-sonnet-5-5"))

    def test_anthropic_model_choice_is_honoured(self):
        settings = SynthesisSettings({"ANTHROPIC_API_KEY": "a"}.get, self.cache)
        settings.select("anthropic", "claude-haiku-4-5-20251001")
        self.assertEqual(settings.build().provider.model_id, "claude-haiku-4-5-20251001")

    def test_only_catalog_engines_and_models_are_accepted(self):
        settings = SynthesisSettings({"OPENAI_API_KEY": "o"}.get, self.cache)
        for engine, model, reason in (("mystery", None, "SYNTHESIS_ENGINE_INVALID"),
                                      ("openai", "gpt-anything", "SYNTHESIS_MODEL_INVALID"),
                                      ("openai", "claude-opus-5-5", "SYNTHESIS_MODEL_INVALID"),
                                      ("openai", 5, "SYNTHESIS_MODEL_INVALID")):
            with self.subTest(engine=engine, model=model):
                with self.assertRaisesRegex(ValueError, reason):
                    settings.select(engine, model)
        self.assertFalse((self.cache / ENGINE_SETTINGS_RELATIVE).exists())

    def test_a_saved_model_dropped_from_the_catalog_falls_back_to_the_default(self):
        (self.cache / ENGINE_SETTINGS_RELATIVE).parent.mkdir(parents=True)
        (self.cache / ENGINE_SETTINGS_RELATIVE).write_text(json.dumps({"engine": "openai", "model": "gpt-retired"}))
        self.assertEqual(SynthesisSettings({"OPENAI_API_KEY": "o"}.get, self.cache).build().provider.model_id, "gpt-6-luna")

    def test_chosen_paid_engine_without_its_key_is_not_configured_never_another_vendor(self):
        settings = SynthesisSettings({"ANTHROPIC_API_KEY": "a"}.get, self.cache)
        settings.select("gemini", None)
        selection = settings.build()
        self.assertEqual((selection.provider, selection.reason), (None, "GEMINI_API_KEY_NOT_SET"))

    def test_every_paid_engine_shares_one_budget_file(self):
        values = {"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o", "GEMINI_API_KEY": "g"}
        paths = {engine: select_synthesis_provider(values.get, cache_dir=self.cache, engine=engine).provider.budget._path
                 for engine in ("anthropic", "openai", "gemini")}
        self.assertEqual(set(paths.values()), {self.cache / BUDGET_RELATIVE})

    def test_auth_configure_stores_ai_keys_without_live_flags(self):
        self.assertEqual(configured_values("", "", "", openai_key="o", gemini_key="g"),
                         {"OPENAI_API_KEY": "o", "GEMINI_API_KEY": "g"})


if __name__ == "__main__":
    unittest.main()
