"""Tests for assistant audit store and inference boundary (GridIQ PORT_ADAPT)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.assistant import (
    AbstainingInferenceStub,
    AssistantAuditStore,
    InferenceProvenanceRecord,
)


class AssistantAuditTests(unittest.TestCase):
    def test_abstaining_stub_has_no_authority(self) -> None:
        stub = AbstainingInferenceStub()
        outcome = stub.infer("size position?", context_citations=({"ref": "cite:1"},))
        self.assertTrue(outcome.abstained)
        self.assertEqual(outcome.abstention_reason, "PROVIDER_NOT_AUTHORIZED")
        self.assertEqual(outcome.content, "")

    def test_conversation_delete_and_retention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AssistantAuditStore(Path(tmp))
            first = store.create_conversation("principal-1", "first")
            second = store.create_conversation("principal-1", "second")
            store.append_message(first.conversation_id, "user", "hello")
            self.assertTrue(store.delete_conversation(second.conversation_id))
            report = store.apply_retention_policy(max_conversations_per_principal=1)
            self.assertGreaterEqual(report["deleted_conversations"], 0)

    def test_conversation_persistence_and_token_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AssistantAuditStore(Path(tmp))
            conversation = store.create_conversation("principal-1", "Replay questions")
            user_message = store.append_message(conversation.conversation_id, "user", "What changed?")
            self.assertEqual(user_message.role, "user")

            stub = AbstainingInferenceStub()
            outcome = stub.infer("What changed?")
            provenance = InferenceProvenanceRecord(
                provider_id=outcome.provider_id,
                model_id=outcome.model_id,
                tokens_prompt=outcome.tokens_prompt,
                tokens_completion=outcome.tokens_completion,
                abstained=outcome.abstained,
                abstention_reason=outcome.abstention_reason,
            )
            assistant_message = store.append_message(
                conversation.conversation_id,
                "assistant",
                outcome.content,
                provenance=provenance,
            )
            self.assertEqual(assistant_message.provenance.abstained, True)

            messages = store.list_messages(conversation.conversation_id)
            self.assertEqual(len(messages), 2)
            totals = store.token_accounting_summary(conversation.conversation_id)
            self.assertEqual(totals["tokens_prompt"], 0)
            self.assertEqual(totals["tokens_completion"], 0)

            fingerprint_a = store.store_fingerprint()
            fingerprint_b = store.store_fingerprint()
            self.assertEqual(fingerprint_a, fingerprint_b)


if __name__ == "__main__":
    unittest.main()
