"""Assistant service tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.assistant.audit_store import AssistantAuditStore
from market_platform_foundation.assistant.service import AssistantResearchService, DEFAULT_PRINCIPAL_ID


class AssistantServiceTests(unittest.TestCase):
    def test_submit_prompt_abstains_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AssistantAuditStore(Path(tmp))
            service = AssistantResearchService(store)
            conversation = service.create_conversation("Test", principal_id=DEFAULT_PRINCIPAL_ID)
            result = service.submit_prompt(
                conversation["conversation_id"],
                "What changed?",
                context_citations=({"ref": "as_of:2026", "kind": "as_of_time"},),
            )
            self.assertEqual(result["user_message"]["role"], "user")
            self.assertEqual(result["assistant_message"]["role"], "assistant")
            self.assertTrue(result["assistant_message"]["provenance"]["abstained"])

    def test_list_conversations_after_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AssistantAuditStore(Path(tmp))
            service = AssistantResearchService(store)
            conversation = service.create_conversation("History test")
            service.submit_prompt(conversation["conversation_id"], "Hello")
            rows = service.list_conversations()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["message_count"], 2)


if __name__ == "__main__":
    unittest.main()
