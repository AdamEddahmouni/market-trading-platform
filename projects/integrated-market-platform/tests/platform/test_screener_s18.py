"""OCT1-04 AI Screener scope, evidence, and explicit-run boundaries."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import MAX_INTAKE, ScreenerAiService  # noqa: E402

NOW = 1790953200.0  # 2026-10-02T15:00:00Z
NOW_ISO = "2026-10-02T15:00:00Z"


def row(instrument_id: str = "EQ:A") -> dict:
    return {
        "instrument": {"instrument_id": instrument_id, "symbol": instrument_id.split(":")[-1],
                       "universe": "US_EQUITIES", "asset_class": "EQUITY"},
        "symbol": instrument_id.split(":")[-1],
        "fields": {
            "price": {"value": 123.0, "source": "IMP_TEST", "state": "LIVE", "as_of": NOW_ISO},
            "change_pct": {"value": 1.2, "source": "IMP_TEST", "state": "LIVE", "as_of": NOW_ISO},
            "rsi_14": {"value": 52.0, "source": "IMP_TEST", "state": "LIVE", "as_of": NOW_ISO},
        },
    }


class CandidateProvider:
    provider_id = "inference.test"
    model_id = "candidate-reduction.v1"
    runtime = "FIXTURE"

    def __init__(self) -> None:
        self.calls = 0
        self.last_prompt = ""

    def infer(self, packet, *, rendered_prompt, config):
        self.calls += 1
        self.last_prompt = rendered_prompt
        candidate = packet.candidates[0]
        refs = [item["evidence_id"] for item in candidate["current_market_evidence"]]
        return ProviderInferenceResponse(json.dumps({
            "schema_version": "ai-screener-output/1.0.0",
            "candidates": [{
                "instrument_id": candidate["instrument"]["instrument_id"], "rank": 1,
                "rationale": "Candidate for review based on admitted observations.",
                "supporting_refs": refs, "conflicting_refs": [],
                "weak_refs": [item["evidence_id"] for item in candidate["current_market_evidence"]
                              if item["weak_reasons"]],
                "missing_capabilities": [item["capability"] for item in candidate["missing"]],
                "uncertainties": ["Coverage is limited."],
            }],
            "limitations": ["Candidate reduction only."],
        }), self.provider_id, self.model_id, tokens_input=100, tokens_output=50, latency_ms=1, simulated=True)


class Reader:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[dict] = []

    def read(self, **kwargs):
        self.calls.append(kwargs)
        return {"rows": self.rows, "result_count": 100, "result_set_id": "set-1",
                "universe_as_of": NOW_ISO, "screener_as_of": NOW_ISO}


class News:
    def __init__(self, provider: CandidateProvider) -> None:
        self.provider = provider

    def synthesis_provider(self):
        return self.provider

    def ai_status(self):
        return {"state": "AVAILABLE", "reason": None, "provider_id": self.provider.provider_id,
                "model_id": self.provider.model_id, "runtime": self.provider.runtime,
                "engine": "fixture", "engine_model": self.provider.model_id, "engines": []}


class AiScreenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = Reader([row(f"EQ:{chr(65 + index)}") for index in range(MAX_INTAKE + 4)])
        self.provider = CandidateProvider()
        self.service = ScreenerAiService(reader=self.reader, news=News(self.provider), clock=lambda: NOW)
        self.scope = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True,
                      "filters": [{"id": "r1", "field": "rsi_14", "operator": "gt", "value": 50}],
                      "result_set": "set-1"}

    def test_preview_is_bounded_and_never_calls_provider(self):
        preview = self.service.preview(self.scope)

        self.assertEqual(preview["intake_count"], MAX_INTAKE)
        self.assertEqual(preview["matched_count"], 100)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(self.reader.calls[-1]["limit"], MAX_INTAKE)
        self.assertEqual(self.reader.calls[-1]["filters"], self.scope["filters"])
        self.assertEqual(preview["scope"]["filters"], self.scope["filters"])

    def test_preview_and_result_pass_the_actual_response_leak_gate(self):
        assert_no_secrets_in_payload(self.service.preview(self.scope))
        assert_no_secrets_in_payload(self.service.run(self.scope))

    def test_run_is_explicit_and_reuses_news_provider(self):
        result = self.service.run(self.scope)

        self.assertEqual(result["schema_version"], "screener-ai-screener/1.0.0")
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(result["state"], "CURRENT")
        self.assertEqual(result["result_set"], "set-1")
        self.assertEqual(result["candidates"][0]["instrument_id"], "EQ:A")
        self.assertIn("BEGIN IMP EVIDENCE DATA", self.provider.last_prompt)

    def test_provider_is_not_authorized_to_add_unknown_refs_or_instructions(self):
        result = self.service.run(self.scope)
        self.assertIn("No BUY, SELL, ENTER, EXIT", self.provider.last_prompt)
        self.assertIn("no instruction authority", self.provider.last_prompt)
        self.assertIn(result["candidates"][0]["supporting_refs"][0],
                      {item["evidence_id"] for item in result["evidence"][0]["current_market_evidence"]})

    def test_invalid_scope_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID_AI_SCREENER_SCOPE"):
            self.service.preview({**self.scope, "filters": [None] * 65})
        with self.assertRaisesRegex(ValueError, "INVALID_AI_SCREENER_SCOPE"):
            self.service.preview({**self.scope, "search": "x" * 121})

    def test_mixed_field_clocks_never_admit_stale_values(self):
        mixed = row()
        mixed["fields"]["rsi_14"] = {"value": 987654321, "source": "IMP_TEST", "state": "STALE", "as_of": "2026-10-02T14:00:00Z"}
        self.reader.rows = [mixed]
        result = self.service.run(self.scope)
        self.assertNotIn("987654321", self.provider.last_prompt)
        self.assertTrue(any(item["capability"] == "TECHNICALS" for item in result["evidence"][0]["blocked"]))

    def test_reference_source_state_is_not_promoted(self):
        mixed = row()
        mixed["fields"]["auction_yield"] = {"value": 987654321, "source": "IMP_TEST", "state": "STALE", "as_of": "2026-10-01"}
        self.reader.rows = [mixed]
        result = self.service.run(self.scope)
        self.assertNotIn("987654321", self.provider.last_prompt)
        self.assertTrue(any(item["capability"] == "RATES" for item in result["evidence"][0]["blocked"]))


class RoutePolicyTests(unittest.TestCase):
    def test_ai_screener_is_registered_for_every_supported_universe(self):
        from market_platform_foundation.ui_api.screener_universes import UNIVERSES
        for spec in UNIVERSES.values():
            with self.subTest(universe=spec.id):
                self.assertIn("ai_screener", spec.panels)

    def test_preview_is_read_and_run_is_explicit_write(self):
        self.assertEqual(policy_for_route("GET", "/screener/ai-screener/preview").capability, "state.read")
        self.assertEqual(policy_for_route("POST", "/screener/ai-screener").capability, "state.write")


if __name__ == "__main__":
    unittest.main()
