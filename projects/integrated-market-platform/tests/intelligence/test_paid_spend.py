"""Hard dollar caps for paid AI: pinned prices, the dollar ledger, the paid-off-by-default gate, the assistant rule.

Every HTTP call is a fake transport: no network, no key, no spend."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.inference.anthropic_synthesis import (  # noqa: E402
    AnthropicSynthesisProvider, BudgetedProvider, DailyBudget,
)
from market_platform_foundation.intelligence.inference.local_provider import select_synthesis_provider  # noqa: E402
from market_platform_foundation.intelligence.inference.paid_prices import (  # noqa: E402
    PRICES, cost_micro, price_for, price_schedule,
)
from market_platform_foundation.intelligence.inference.paid_spend import (  # noqa: E402
    LEDGER_RELATIVE, DollarLedger, caps_micro, paid_gate, parse_cap,
)
from market_platform_foundation.intelligence.inference.screener_synthesis import ScreenerSynthesizer  # noqa: E402
from market_platform_foundation.intelligence.inference.synthesis_engines import ENGINE_SPECS  # noqa: E402
from market_platform_foundation.intelligence.inference.token_cost import estimated_cost  # noqa: E402
from tests.intelligence.test_anthropic_synthesis_budget import DAY, Clock, FakeClaude, run  # noqa: E402
from tests.intelligence.test_local_synthesis_provider import grounded  # noqa: E402

CAPS = {"IMP_PAID_AI_DAILY_USD": "1", "IMP_PAID_AI_MONTHLY_USD": "5"}


def capped(transport, ledger, *, budget=None, clock=None, model=None):
    clock = clock or Clock()
    provider = BudgetedProvider(AnthropicSynthesisProvider(api_key="test-key", model=model, poster=transport),
                                budget or DailyBudget(None, clock=clock), ledger)
    return provider, ScreenerSynthesizer(provider=provider, clock=clock)


class PriceTests(unittest.TestCase):
    def test_every_paid_catalog_model_has_a_pinned_price(self):
        for engine in ("anthropic", "openai", "gemini"):
            for model, _ in ENGINE_SPECS[engine].models:
                with self.subTest(model=model):
                    self.assertIsNotNone(price_for(model, date(2026, 10, 24)))
        self.assertTrue(all(row.source.startswith("https://") for row in PRICES))

    def test_cost_rounds_up_and_uses_the_long_prompt_tier(self):
        day = date(2026, 10, 24)
        self.assertEqual(cost_micro("claude-haiku-5-5", 1_000, 100, day), 150)           # $0.10 + $0.50 per MTok
        self.assertEqual(cost_micro("claude-haiku-5-5", 100_001, 0, day), 50_001)        # whole call at $0.50
        self.assertEqual(cost_micro("claude-sonnet-5-5", 1, 1, day), 12)
        self.assertEqual(cost_micro("gpt-6.1-sol", 272_001, 0, day), 1_088_004)          # long tier $4
        self.assertIsNone(cost_micro("claude-unknown", 1, 1, day))

    def test_a_dated_price_change_applies_from_its_day(self):
        self.assertEqual(cost_micro("gemini-3.8-flash", 1_000_000, 0, date(2026, 12, 31)), 750_000)
        self.assertEqual(cost_micro("gemini-3.8-flash", 1_000_000, 0, date(2027, 1, 1)), 1_500_000)

    def test_preview_schedule_matches_the_pinned_price(self):
        schedule = price_schedule("claude-haiku-5-5", date(2026, 10, 24))
        cost = estimated_cost(schedule, model_id="claude-haiku-5-5", input_tokens=1_000_000, output_tokens=0,
                              now="2026-10-24T12:00:00Z")
        self.assertEqual(cost["estimated_dollars"], 0.1)


class CapSettingTests(unittest.TestCase):
    def test_caps_parse_strictly_and_default_to_zero(self):
        self.assertEqual(caps_micro({}.get), (0, 0))
        self.assertEqual(caps_micro({"IMP_PAID_AI_DAILY_USD": "1.25", "IMP_PAID_AI_MONTHLY_USD": "20"}.get),
                         (1_250_000, 20_000_000))
        for bad in ("-1", "1e3", "nan", "inf", "1.234", "99999.99", "$5", "five"):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_cap(bad))
                self.assertEqual(caps_micro({"IMP_PAID_AI_DAILY_USD": bad, "IMP_PAID_AI_MONTHLY_USD": "5"}.get)[0], 0)

    def test_gate_needs_both_caps_and_a_price(self):
        self.assertEqual(paid_gate({}.get, "claude-haiku-5-5"), "PAID_AI_CAP_NOT_SET")
        self.assertEqual(paid_gate({"IMP_PAID_AI_DAILY_USD": "1"}.get, "claude-haiku-5-5"), "PAID_AI_CAP_NOT_SET")
        self.assertEqual(paid_gate(CAPS.get, "claude-unknown"), "PAID_MODEL_PRICE_UNKNOWN")
        self.assertIsNone(paid_gate(CAPS.get, "claude-haiku-5-5"))


class LedgerTests(unittest.TestCase):
    def test_reserve_then_settle_charges_reported_usage(self):
        ledger = DollarLedger(None, daily_micro=1_000_000, monthly_micro=5_000_000, clock=Clock())
        amount, reason = ledger.reserve("claude-sonnet-5-5", 10_000, 4_000)
        self.assertEqual((amount, reason), (60_000, None))                # $0.02 in + $0.04 out
        self.assertEqual(ledger.status()["reserved_usd"], 0.06)
        self.assertEqual(ledger.settle(amount, "claude-sonnet-5-5", 1_000, 100), 3_000)
        status = ledger.status()
        self.assertEqual((status["spent_today_usd"], status["spent_month_usd"], status["reserved_usd"]), (0.003, 0.003, 0))

    def test_unknown_usage_keeps_the_worst_case(self):
        ledger = DollarLedger(None, daily_micro=1_000_000, monthly_micro=5_000_000, clock=Clock())
        amount, _ = ledger.reserve("claude-sonnet-5-5", 10_000, 4_000)
        ledger.settle(amount, "claude-sonnet-5-5", None, None)
        self.assertEqual(ledger.status()["spent_today_usd"], 0.06)

    def test_daily_and_monthly_caps_refuse_before_the_call(self):
        clock = Clock()
        ledger = DollarLedger(None, daily_micro=100_000, monthly_micro=150_000, clock=clock)
        amount, _ = ledger.reserve("claude-sonnet-5-5", 0, 9_000)          # $0.09
        ledger.settle(amount, "claude-sonnet-5-5", 0, 9_000)
        self.assertEqual(ledger.reserve("claude-sonnet-5-5", 0, 2_000), (0, "PAID_AI_DAILY_DOLLAR_CAP"))
        clock.now += 86_400                                                  # a new UTC day, same month
        amount, _ = ledger.reserve("claude-sonnet-5-5", 0, 5_000)
        ledger.settle(amount, "claude-sonnet-5-5", 0, 5_000)
        self.assertEqual(ledger.reserve("claude-sonnet-5-5", 0, 2_000), (0, "PAID_AI_MONTHLY_DOLLAR_CAP"))

    def test_zero_caps_and_unknown_prices_refuse(self):
        self.assertEqual(DollarLedger(None, daily_micro=0, monthly_micro=5, clock=Clock()).reserve("claude-haiku-5-5", 1, 1),
                         (0, "PAID_AI_CAP_NOT_SET"))
        self.assertEqual(DollarLedger(None, daily_micro=5, monthly_micro=5, clock=Clock()).reserve("mystery", 1, 1),
                         (0, "PAID_MODEL_PRICE_UNKNOWN"))

    def test_state_survives_a_restart_and_unreadable_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / LEDGER_RELATIVE
            clock = Clock()
            ledger = DollarLedger(path, daily_micro=1_000_000, monthly_micro=5_000_000, clock=clock)
            amount, _ = ledger.reserve("claude-haiku-5-5", 1_000, 1_000)
            ledger.settle(amount, "claude-haiku-5-5", 1_000, 1_000)
            restarted = DollarLedger(path, daily_micro=1_000_000, monthly_micro=5_000_000, clock=clock)
            self.assertEqual(restarted.status()["spent_today_usd"], 0.0006)
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(restarted.reserve("claude-haiku-5-5", 1, 1), (0, "PAID_AI_LEDGER_UNREADABLE"))
            self.assertEqual(restarted.status()["state"], "UNREADABLE")
            path.write_text(json.dumps({"day": "2026-09-21", "month": "2026-09", "day_micro": -5, "month_micro": 0,
                                        "day_reserved": 0, "month_reserved": 0}), encoding="utf-8")
            self.assertEqual(restarted.reserve("claude-haiku-5-5", 1, 1), (0, "PAID_AI_LEDGER_UNREADABLE"))

    def test_concurrent_reservations_never_cross_the_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / LEDGER_RELATIVE
            results = []

            def reserve():
                ledger = DollarLedger(path, daily_micro=100_000, monthly_micro=100_000, clock=Clock())
                results.append(ledger.reserve("claude-sonnet-5-5", 0, 3_000)[1])   # $0.03 each

            threads = [threading.Thread(target=reserve) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count(None), 3)
            self.assertEqual(results.count("PAID_AI_DAILY_DOLLAR_CAP"), 5)


class ProviderTests(unittest.TestCase):
    def test_a_call_over_the_dollar_cap_is_never_sent(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids))
        clock = Clock()
        ledger = DollarLedger(None, daily_micro=1_000, monthly_micro=1_000, clock=clock)   # $0.001
        _, synth = capped(transport, ledger, clock=clock)
        refused = run(synth)
        self.assertEqual((refused["reason"], transport.requests), ("PAID_AI_DAILY_DOLLAR_CAP", []))

    def test_a_sent_call_is_charged_its_reported_usage(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids), usage=(900, 400))
        clock = Clock()
        ledger = DollarLedger(None, daily_micro=1_000_000, monthly_micro=5_000_000, clock=clock)
        _, synth = capped(transport, ledger, clock=clock, model="claude-sonnet-5-5")
        self.assertEqual(run(synth)["state"], "CURRENT")
        status = ledger.status()
        self.assertEqual((status["spent_today_usd"], status["reserved_usd"]), (0.0058, 0))   # 900 x $2 + 400 x $10

    def test_a_token_refusal_returns_the_dollar_reservation(self):
        transport = FakeClaude(tool_input=lambda ids: grounded(ids))
        clock = Clock()
        ledger = DollarLedger(None, daily_micro=1_000_000, monthly_micro=5_000_000, clock=clock)
        _, synth = capped(transport, ledger, clock=clock,
                          budget=DailyBudget(None, max_requests=99, max_tokens=2_000, clock=clock))
        self.assertEqual(run(synth)["reason"], "SYNTHESIS_DAILY_TOKEN_LIMIT")
        self.assertEqual((ledger.status()["reserved_usd"], ledger.status()["spent_today_usd"]), (0, 0))

    def test_a_timeout_keeps_the_worst_case_charged(self):
        clock = Clock()
        ledger = DollarLedger(None, daily_micro=1_000_000, monthly_micro=5_000_000, clock=clock)
        _, synth = capped(FakeClaude(raise_exc=TimeoutError()), ledger, clock=clock)
        run(synth)
        self.assertGreater(ledger.status()["spent_today_usd"], 0)

    def test_paid_engines_need_caps_before_any_provider_is_built(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            keys = {"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o", "GEMINI_API_KEY": "g"}
            for engine in ("anthropic", "openai", "gemini"):
                with self.subTest(engine=engine):
                    refused = select_synthesis_provider(keys.get, cache_dir=cache, engine=engine)
                    self.assertEqual((refused.provider, refused.reason), (None, "PAID_AI_CAP_NOT_SET"))
                    env_chosen = select_synthesis_provider({**keys, "IMP_SYNTHESIS_PROVIDER": engine}.get, cache_dir=cache)
                    self.assertEqual(env_chosen.reason, "PAID_AI_CAP_NOT_SET")
                    allowed = select_synthesis_provider({**keys, **CAPS}.get, cache_dir=cache, engine=engine)
                    self.assertEqual(allowed.runtime, "PAID_API")
                    self.assertEqual(allowed.provider.ledger.daily_micro, 1_000_000)
            # Automatic, with every key and caps set, never selects a paid engine.
            self.assertNotEqual(select_synthesis_provider({**keys, **CAPS}.get, cache_dir=cache).runtime, "PAID_API")


class AssistantTests(unittest.TestCase):
    def _assistant(self, values, cache):
        from market_platform_foundation.assistant.inference_factory import MachineEngineInference

        return MachineEngineInference(values.get, cache)

    def test_the_assistant_is_paid_only_when_claude_is_the_engine_with_caps(self):
        from market_platform_foundation.intelligence.inference.synthesis_engines import SynthesisSettings

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            keys = {"ANTHROPIC_API_KEY": "a"}
            self.assertEqual(self._assistant(keys, cache).provider_id, "grounded.evidence")       # automatic
            SynthesisSettings({**keys, **CAPS}.get, cache).select("anthropic", "claude-haiku-5-5")
            self.assertEqual(self._assistant(keys, cache).provider_id, "grounded.evidence")       # caps removed
            paid = self._assistant({**keys, **CAPS}, cache)
            self.assertEqual((paid.provider_id, paid.model_id), ("anthropic.messages", "claude-haiku-5-5"))

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "IMP_ASSISTANT_PROVIDER": "anthropic"}, clear=False)
    def test_a_key_in_the_environment_alone_does_not_make_the_assistant_paid(self):
        from market_platform_foundation.assistant.inference_factory import resolve_assistant_inference

        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"IMP_CACHE_DIR": directory}):
            self.assertEqual(resolve_assistant_inference().provider_id, "grounded.evidence")

    @patch("market_platform_foundation.assistant.anthropic_inference.urlopen")
    def test_assistant_calls_are_charged_and_refused_past_the_cap(self, mock_urlopen):
        import io

        from market_platform_foundation.assistant.anthropic_inference import AnthropicInference

        payload = {"content": [{"type": "text", "text": "Cannot determine from available evidence."}],
                   "usage": {"input_tokens": 1_000, "output_tokens": 100}}
        mock_urlopen.return_value.__enter__.side_effect = lambda: io.BytesIO(json.dumps(payload).encode("utf-8"))
        ledger = DollarLedger(None, daily_micro=1_000_000, monthly_micro=5_000_000, clock=Clock(DAY))
        inference = AnthropicInference(api_key="k", model="claude-sonnet-5-5", ledger=ledger)
        context = {"resolve_explain": lambda _ref: {}, "explain_refs": ["explain:quality:system"]}
        outcome = inference.infer("Why?", evidence_context=context)
        self.assertEqual(outcome.provider_id, "anthropic.messages")
        self.assertEqual(ledger.status()["spent_today_usd"], 0.003)                          # 1000 x $2 + 100 x $10
        broke = AnthropicInference(api_key="k", model="claude-sonnet-5-5",
                                   ledger=DollarLedger(None, daily_micro=1, monthly_micro=1, clock=Clock(DAY)))
        mock_urlopen.reset_mock()
        self.assertNotEqual(broke.infer("Why?", evidence_context=context).provider_id, "anthropic.messages")
        mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
