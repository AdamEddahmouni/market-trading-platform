"""Anthropic inference adapter tests."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.assistant.anthropic_inference import (
    AnthropicInference,
    extract_citation_refs,
)
from market_platform_foundation.assistant.context_assembler import build_evidence_context
from market_platform_foundation.assistant.inference_factory import resolve_assistant_inference
from market_platform_foundation.ui_api.store import ReplayStore


class AnthropicInferenceTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_extract_citation_refs_filters_allowed(self) -> None:
        allowed = {"explain:quality:system", "explain:disclosure:BIYA"}
        refs = extract_citation_refs(
            "Quality is degraded per [explain:quality:system] and disclosure [explain:disclosure:BIYA].",
            allowed,
        )
        self.assertEqual(
            refs,
            ("explain:quality:system", "explain:disclosure:BIYA"),
        )

    def test_missing_api_key_abstains(self) -> None:
        inference = AnthropicInference(api_key="")
        outcome = inference.infer("Why is BIYA here?", evidence_context={"resolve_explain": lambda _ref: {}})
        self.assertTrue(outcome.abstained)
        self.assertEqual(outcome.abstention_reason, "API_KEY_MISSING")

    @patch("market_platform_foundation.assistant.anthropic_inference.urlopen")
    def test_successful_anthropic_response(self, mock_urlopen) -> None:
        payload = {
            "content": [{"type": "text", "text": "BIYA is on the admitted fixture [explain:disclosure:BIYA]."}],
            "usage": {"input_tokens": 120, "output_tokens": 40},
        }
        mock_response = io.BytesIO(json.dumps(payload).encode("utf-8"))
        mock_urlopen.return_value.__enter__.return_value = mock_response

        evidence_context = build_evidence_context(self.store)
        inference = AnthropicInference(api_key="test-key", model="claude-test")
        outcome = inference.infer("Why is BIYA here?", evidence_context=evidence_context)
        self.assertFalse(outcome.abstained)
        self.assertIn("explain:disclosure:BIYA", [row.get("ref") for row in outcome.citations])
        self.assertEqual(outcome.provider_id, "anthropic.messages")

    @patch("market_platform_foundation.assistant.anthropic_inference.urlopen")
    def test_provider_failure_falls_back_to_grounded(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = ConnectionError("network down")
        evidence_context = build_evidence_context(self.store)
        inference = AnthropicInference(api_key="test-key", model="claude-test")
        outcome = inference.infer("Why is BIYA here?", evidence_context=evidence_context)
        self.assertFalse(outcome.abstained)
        self.assertEqual(outcome.provider_id, "grounded.evidence")

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "IMP_ASSISTANT_PROVIDER": "anthropic"}, clear=False)
    def test_factory_selects_anthropic_when_configured(self) -> None:
        inference = resolve_assistant_inference()
        self.assertEqual(getattr(inference, "provider_id", ""), "anthropic.messages")


if __name__ == "__main__":
    unittest.main()
