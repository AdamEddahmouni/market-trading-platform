"""Paid Claude synthesis: request shape, key source, daily budget, and no-rebill behaviour.

Every HTTP call is a fake transport: no network, no key, no spend."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.inference.anthropic_models import THINKING_HEADROOM  # noqa: E402
from market_platform_foundation.intelligence.inference.anthropic_synthesis import (  # noqa: E402
    BUDGET_RELATIVE, DEFAULT_MODEL, TOOL_NAME, AnthropicSynthesisProvider, BudgetedProvider, DailyBudget,
    build_paid_provider,
)
from market_platform_foundation.intelligence.inference.local_provider import select_synthesis_provider  # noqa: E402
from market_platform_foundation.intelligence.inference.screener_synthesis import (  # noqa: E402
    CACHE_TTL_S, FAILURE_TTL_S, ScreenerSynthesizer,
)
from tests.intelligence.test_local_synthesis_provider import STORIES, grounded  # noqa: E402
from tools.news.auth import configured_values  # noqa: E402

DAY = 1_790_000_000.0          # 2026-09-21 UTC


class Clock:
    def __init__(self, now=DAY):
        self.now = now

    def __call__(self):
        return self.now


class FakeClaude:
    """Messages API stand-in: returns the forced tool call, or a scripted status / stop reason."""

    def __init__(self, *, tool_input=None, status=200, stop_reason="tool_use", error_type=None, raise_exc=None,
                 gate=None, usage=(900, 400)):
        self.tool_input, self.status, self.stop_reason = tool_input, status, stop_reason
        self.error_type, self.raise_exc, self.gate, self.usage = error_type, raise_exc, gate, usage
        self.requests = []

    def __call__(self, url, body, headers, timeout):
        request = json.loads(body.decode("utf-8"))
        self.requests.append((url, request, headers, timeout))
        if self.gate is not None:
            self.gate.wait(5)
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.status != 200:
            return self.status, json.dumps({"type": "error", "error": {"type": self.error_type or "api_error",
                                                                       "message": "detail"}}).encode()
        ids = request["tools"][0]["input_schema"]["properties"]["observed_facts"]["items"]["properties"]["refs"]["items"]["enum"]
        tool_input = self.tool_input(ids) if callable(self.tool_input) else self.tool_input
        return 200, json.dumps({"id": "msg_1", "stop_reason": self.stop_reason,
                                "content": [{"type": "tool_use", "id": "t1", "name": TOOL_NAME, "input": tool_input}],
                                "usage": {"input_tokens": self.usage[0], "output_tokens": self.usage[1]}}).encode()


def paid(transport, *, budget=None, clock=None):
    clock = clock or Clock()
    provider = BudgetedProvider(AnthropicSynthesisProvider(api_key="test-key", poster=transport),
                                budget or DailyBudget(None, clock=clock))
    return provider, ScreenerSynthesizer(provider=provider, clock=clock)


def run(synth):
    return synth.synthesize(STORIES, instruments=("ACME",), as_of="t")


class RequestShapeTests(unittest.TestCase):
    def test_candidate_reduction_enables_strict_instrument_specific_tool_schema(self):
        from tests.intelligence.test_ai_screener import candidate, output, NOW
        from market_platform_foundation.intelligence.inference.candidate_reduction import CandidateReducer
        calls = []
        c = candidate()
        def poster(url, body, headers, timeout):
            request = json.loads(body)
            calls.append(request)
            return 200, json.dumps({'content': [{'type': 'tool_use', 'name': TOOL_NAME, 'input': output(c)}],
                                    'usage': {'input_tokens': 100, 'output_tokens': 50}}).encode()
        provider = AnthropicSynthesisProvider(api_key='controlled', model='claude-haiku-4-5-20251001', poster=poster)
        result = CandidateReducer(provider=provider, clock=lambda: 1790953200.0).reduce({}, [c], NOW)
        self.assertEqual(result['state'], 'CURRENT')
        tool = calls[0]['tools'][0]
        self.assertTrue(tool['strict'])
        choice = tool['input_schema']['properties']['candidates']['items']
        self.assertEqual(choice['properties']['candidate_key']['enum'], [0])
        self.assertEqual(choice['properties']['supporting_refs']['items']['type'], 'integer')
        def check(schema):
            if isinstance(schema, dict):
                self.assertFalse({'minimum', 'maximum', 'maxItems', 'uniqueItems', 'maxLength'} & schema.keys())
                self.assertLessEqual(schema.get('minItems', 0), 1)
                self.assertNotIn('anyOf', schema)
                if 'const' in schema:
                    self.assertNotIsInstance(schema['const'], (list, dict))
                for value in schema.values(): check(value)
            elif isinstance(schema, list):
                for value in schema: check(value)
        check(tool['input_schema'])

    def test_schema_tool_current_model_and_bounded_output(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids))
        _, synth = paid(transport)
        result = run(synth)
        self.assertEqual((result["state"], result["runtime"], result["model_id"]), ("CURRENT", "PAID_API", DEFAULT_MODEL))
        url, body, headers, timeout = transport.requests[0]
        self.assertEqual(DEFAULT_MODEL, "claude-sonnet-5-5")
        # The default model rejects an explicit temperature and a forced tool call, and reasons before it answers.
        self.assertNotIn("temperature", body)
        self.assertEqual((body["max_tokens"], timeout), (2048 + THINKING_HEADROOM, 45.0))
        self.assertEqual(body["tool_choice"], {"type": "auto", "disable_parallel_tool_use": True})
        refs = body["tools"][0]["input_schema"]["properties"]["observed_facts"]["items"]["properties"]["refs"]["items"]
        self.assertEqual(refs["enum"], ["s1", "s2", "s3"])                     # refs limited to the packet
        self.assertEqual((headers["x-api-key"], headers["anthropic-version"]), ("test-key", "2023-06-01"))
        self.assertTrue(url.startswith("https://api.anthropic.com/"))

    def test_key_and_model_come_from_the_same_configuration_source(self):
        with tempfile.TemporaryDirectory() as directory:
            values = {"ANTHROPIC_API_KEY": "from-private-file", "IMP_SYNTHESIS_ANTHROPIC_MODEL": "claude-haiku-4-5-20251001",
                      "IMP_SYNTHESIS_DAILY_REQUESTS": "5", "IMP_SYNTHESIS_DAILY_TOKENS": "50000"}
            chosen = select_synthesis_provider(values.get, cache_dir=Path(directory))
            self.assertEqual((chosen.runtime, chosen.provider.model_id), ("PAID_API", "claude-haiku-4-5-20251001"))
            self.assertEqual(chosen.provider._provider._api_key, "from-private-file")   # not only os.environ
            status = chosen.provider.budget_status()
            self.assertEqual((status["max_requests"], status["max_tokens"]), (5, 50000))
            forced_local = select_synthesis_provider({**values, "IMP_SYNTHESIS_PROVIDER": "local"}.get, cache_dir=Path(directory))
            self.assertNotEqual(forced_local.runtime, "PAID_API")                # operator can switch paid off

    def test_auth_configure_stores_the_key_without_a_live_flag(self):
        self.assertEqual(configured_values("", "", "sk-test"), {"ANTHROPIC_API_KEY": "sk-test"})
        self.assertEqual(configured_values("n", "", ""), {"NEWSAPI_API_KEY": "n", "IMP_NEWSAPI_LIVE": "1"})


class BudgetTests(unittest.TestCase):
    def test_request_limit_refuses_before_any_network_call(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids))
        clock = Clock()
        budget = DailyBudget(None, max_requests=1, max_tokens=1_000_000, clock=clock)
        _, synth = paid(transport, budget=budget, clock=clock)
        self.assertEqual(run(synth)["state"], "CURRENT")
        other = ScreenerSynthesizer(provider=BudgetedProvider(AnthropicSynthesisProvider(api_key="k", poster=transport), budget),
                                    clock=clock)
        refused = other.synthesize(STORIES[:2], instruments=("ACME",), as_of="t")
        self.assertEqual((refused["state"], refused["reason"], len(transport.requests)),
                         ("UNAVAILABLE", "SYNTHESIS_DAILY_REQUEST_LIMIT", 1))

    def test_token_limit_reserves_the_worst_case(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids))
        clock = Clock()
        _, synth = paid(transport, budget=DailyBudget(None, max_requests=99, max_tokens=2_000, clock=clock), clock=clock)
        refused = run(synth)
        self.assertEqual((refused["reason"], transport.requests), ("SYNTHESIS_DAILY_TOKEN_LIMIT", []))

    def test_usage_is_settled_persisted_and_resets_on_a_new_day(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / BUDGET_RELATIVE
            clock = Clock()
            _, synth = paid(FakeClaude(tool_input=lambda ids: grounded(ids), usage=(900, 400)),
                            budget=DailyBudget(path, clock=clock), clock=clock)
            run(synth)
            restarted = DailyBudget(path, clock=clock)                       # a restart keeps today's count
            self.assertEqual({key: restarted.status()[key] for key in ("requests", "tokens")}, {"requests": 1, "tokens": 1300})
            clock.now += 86_400
            self.assertEqual(restarted.status()["requests"], 0)

    def test_billing_outcomes_per_failure(self):
        cases = [(FakeClaude(status=401, error_type="authentication_error"), "ANTHROPIC_AUTH_FAILED", 0),
                 (FakeClaude(status=400, error_type="invalid_request_error"), "ANTHROPIC_INVALID_REQUEST_ERROR", 0),
                 (FakeClaude(status=529, error_type="overloaded_error"), "ANTHROPIC_OVERLOADED_ERROR", 0),
                 (FakeClaude(raise_exc=TimeoutError()), "ANTHROPIC_TIMEOUT", None),        # unknown: worst case charged
                 (FakeClaude(tool_input={"summary": "x"}, stop_reason="max_tokens", usage=(900, 2048)),
                  "ANTHROPIC_OUTPUT_TRUNCATED", 2948)]
        for transport, reason, tokens in cases:
            clock = Clock()
            budget = DailyBudget(None, clock=clock)
            _, synth = paid(transport, budget=budget, clock=clock)
            result = run(synth)
            self.assertEqual((result["state"], result["reason"]), ("UNAVAILABLE", reason), reason)
            used = budget.status()["tokens"]
            if tokens is None:
                self.assertGreater(used, 2048, reason)
            else:
                self.assertEqual(used, tokens, reason)
            self.assertEqual(budget.status()["requests"], 1, reason)


class NoRebillTests(unittest.TestCase):
    def test_rejected_output_is_not_bought_twice(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids, summary="Acme will rally after the beat."))
        clock = Clock()
        _, synth = paid(transport, clock=clock)
        self.assertEqual(run(synth)["reason"], "UNSUPPORTED_CERTAINTY")
        again = run(synth)
        self.assertEqual((again["reason"], again["cache"], len(transport.requests)), ("UNSUPPORTED_CERTAINTY", "HIT", 1))
        clock.now += CACHE_TTL_S + 1
        run(synth)
        self.assertEqual(len(transport.requests), 2)

    def test_transient_failure_is_held_briefly_and_budget_refusal_is_not(self):
        transport = FakeClaude(status=529, error_type="overloaded_error")
        clock = Clock()
        _, synth = paid(transport, clock=clock)
        run(synth)
        run(synth)
        self.assertEqual(len(transport.requests), 1)
        clock.now += FAILURE_TTL_S + 1
        run(synth)
        self.assertEqual(len(transport.requests), 2)
        budget = DailyBudget(None, max_requests=0, clock=clock)
        _, capped = paid(FakeClaude(tool_input=lambda ids: grounded(ids)), budget=budget, clock=clock)
        self.assertEqual(run(capped)["cache"], "MISS")
        budget.max_requests = 5                                           # raising the limit takes effect at once
        self.assertEqual(run(capped)["state"], "CURRENT")

    def test_concurrent_identical_requests_make_one_call(self):
        gate = threading.Event()
        transport = FakeClaude(tool_input=lambda ids: grounded(ids), gate=gate)
        _, synth = paid(transport)
        results = []
        threads = [threading.Thread(target=lambda: results.append(run(synth))) for _ in range(3)]
        for thread in threads:
            thread.start()
        for _ in range(200):
            if transport.requests:
                break
            threading.Event().wait(0.01)
        threading.Event().wait(0.05)
        gate.set()
        for thread in threads:
            thread.join(5)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(sorted(result["cache"] for result in results), ["HIT", "HIT", "MISS"])
        self.assertEqual({result["state"] for result in results}, {"CURRENT"})


class PreviewTests(unittest.TestCase):
    def test_estimate_is_the_reservation_the_call_makes(self):
        claude = FakeClaude(tool_input=lambda ids: grounded(ids))
        reserved = []
        clock = Clock()
        budget = DailyBudget(None, clock=clock)

        def transport(*args):
            reserved.append(budget.status()["tokens"])
            return claude(*args)
        _, synth = paid(transport, budget=budget, clock=clock)
        estimate = synth.estimate(STORIES, instruments=("ACME",), as_of="t")
        self.assertEqual((estimate["story_count"], estimate["cached"]), (len(STORIES), False))
        run(synth)
        self.assertEqual(reserved, [estimate["tokens"]])
        # The same input is now cached: a click would cost nothing, and the estimate never called the model.
        again = synth.estimate(STORIES, instruments=("ACME",), as_of="t")
        self.assertEqual((again["cached"], len(claude.requests)), (True, 1))

    def test_result_names_the_headlines_the_model_was_given(self):
        _, synth = paid(FakeClaude(tool_input=lambda ids: grounded(ids)))
        result = run(synth)
        self.assertEqual([item["story_id"] for item in result["stories"]], result["story_ids"])
        self.assertEqual([item["headline"] for item in result["stories"]], [story.headline for story in STORIES])

    def test_no_estimate_without_a_provider_or_stories(self):
        self.assertIsNone(ScreenerSynthesizer(provider=None).estimate(STORIES, instruments=("ACME",), as_of="t"))
        _, synth = paid(FakeClaude())
        self.assertIsNone(synth.estimate([], instruments=("ACME",), as_of="t"))


class PaidStatusTests(unittest.TestCase):
    def test_build_paid_provider_budget_file_lives_in_the_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = build_paid_provider({"ANTHROPIC_API_KEY": "k"}.get, cache_dir=Path(directory))
            self.assertEqual((provider.model_id, provider.runtime), (DEFAULT_MODEL, "PAID_API"))
            self.assertEqual(provider.budget._path, Path(directory) / BUDGET_RELATIVE)


if __name__ == "__main__":
    unittest.main()
