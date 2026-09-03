"""Grounded assistant inference tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.assistant.audit_store import AssistantAuditStore
from market_platform_foundation.assistant.context_assembler import build_evidence_context
from market_platform_foundation.assistant.grounded_inference import GroundedEvidenceInference
from market_platform_foundation.assistant.intent_router import route_intent
from market_platform_foundation.assistant.service import AssistantResearchService
from market_platform_foundation.ui_api.projections import build_explain_payload
from market_platform_foundation.ui_api.store import ReplayStore


class GroundedAssistantTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_route_intent_quality(self) -> None:
        self.assertEqual(route_intent("explain quality"), "quality")

    def test_grounded_explain_returns_cited_answer(self) -> None:
        evidence_context = build_evidence_context(self.store)
        inference = GroundedEvidenceInference()
        outcome = inference.infer("Why is BIYA here?", evidence_context=evidence_context)
        self.assertFalse(outcome.abstained)
        self.assertTrue(outcome.content)
        self.assertNotEqual(outcome.content, "PROVIDER_NOT_AUTHORIZED")
        self.assertTrue(outcome.citations)

    def test_missing_evidence_abstains_explicitly(self) -> None:
        inference = GroundedEvidenceInference()
        outcome = inference.infer(
            "Explain ZZZZ microstructure",
            evidence_context={
                "instrument_id": "ZZZZ",
                "available_explain_refs": ("explain:replay:context",),
                "resolve_explain": lambda ref: (_ for _ in ()).throw(ValueError("missing")),
            },
        )
        self.assertTrue(outcome.abstained)
        self.assertIn(outcome.abstention_reason, {"REF_NOT_FOUND", "EVIDENCE_NOT_AVAILABLE"})

    def test_no_fabricated_citation_refs(self) -> None:
        evidence_context = build_evidence_context(self.store)
        inference = GroundedEvidenceInference()
        outcome = inference.infer("explain quality", evidence_context=evidence_context)
        for citation in outcome.citations:
            ref = citation.get("ref", "")
            self.assertTrue(ref.startswith("explain:") or ref.startswith("inspect:"))
            if ref.startswith("explain:"):
                build_explain_payload(self.store, ref)

    def test_selection_ref_routes_to_explain(self) -> None:
        selection_ref = "explain:quality:system"
        evidence_context = build_evidence_context(self.store, selection_ref=selection_ref)
        inference = GroundedEvidenceInference()
        outcome = inference.infer("Explain selection", evidence_context=evidence_context)
        self.assertFalse(outcome.abstained)
        refs = {row.get("ref") for row in outcome.citations}
        self.assertIn(selection_ref, refs)

    def test_service_grounded_prompt_with_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = AssistantAuditStore(Path(tmp))
            service = AssistantResearchService(audit, inference=GroundedEvidenceInference())
            conversation = service.create_conversation("Grounded")
            evidence_context = service.build_evidence_context(self.store)
            result = service.submit_prompt(
                conversation["conversation_id"],
                "explain quality",
                evidence_context=evidence_context,
            )
            self.assertFalse(result["assistant_message"]["provenance"]["abstained"])


if __name__ == "__main__":
    unittest.main()
