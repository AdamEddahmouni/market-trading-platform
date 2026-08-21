"""Conversation persistence and inference provenance accounting (GridIQ pattern, stdlib JSON)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json

STORE_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class InferenceProvenanceRecord:
    provider_id: str
    model_id: str
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    citation_refs: tuple[str, ...] = ()
    abstained: bool = False
    abstention_reason: str | None = None


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at_ns: int
    provenance: InferenceProvenanceRecord | None = None


@dataclass(frozen=True)
class ConversationRecord:
    conversation_id: str
    principal_id: str
    title: str
    created_at_ns: int
    updated_at_ns: int
    message_ids: tuple[str, ...] = ()


def _now_ns() -> int:
    import time

    return time.time_ns()


def _message_body(message: MessageRecord) -> dict[str, Any]:
    provenance = None
    if message.provenance is not None:
        provenance = {
            "abstained": message.provenance.abstained,
            "abstention_reason": message.provenance.abstention_reason,
            "citation_refs": list(message.provenance.citation_refs),
            "model_id": message.provenance.model_id,
            "provider_id": message.provenance.provider_id,
            "tokens_completion": message.provenance.tokens_completion,
            "tokens_prompt": message.provenance.tokens_prompt,
        }
    return {
        "conversation_id": message.conversation_id,
        "content": message.content,
        "created_at_ns": message.created_at_ns,
        "message_id": message.message_id,
        "provenance": provenance,
        "role": message.role,
    }


class AssistantAuditStore:
    """Append-only JSON audit store for research assistant conversations."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._conversations_path = self.root / "conversations.json"
        self._messages_path = self.root / "messages.json"
        if not self._conversations_path.exists():
            write_canonical_json(
                self._conversations_path,
                {"conversations": [], "schema_version": STORE_SCHEMA_VERSION},
            )
        if not self._messages_path.exists():
            write_canonical_json(
                self._messages_path,
                {"messages": [], "schema_version": STORE_SCHEMA_VERSION},
            )

    def _load_conversations(self) -> dict[str, Any]:
        payload = load_json_strict(self._conversations_path)
        if not isinstance(payload, dict):
            raise ValueError("conversations store corrupt")
        return payload

    def _load_messages(self) -> dict[str, Any]:
        payload = load_json_strict(self._messages_path)
        if not isinstance(payload, dict):
            raise ValueError("messages store corrupt")
        return payload

    def create_conversation(self, principal_id: str, title: str) -> ConversationRecord:
        now = _now_ns()
        conversation_id = sha256_bytes(
            canonical_bytes({"principal_id": principal_id, "title": title, "ts": now})
        )[:16]
        record = {
            "conversation_id": conversation_id,
            "created_at_ns": now,
            "message_ids": [],
            "principal_id": principal_id,
            "title": title,
            "updated_at_ns": now,
        }
        payload = self._load_conversations()
        conversations = payload.get("conversations", [])
        if not isinstance(conversations, list):
            raise ValueError("conversations list corrupt")
        conversations.append(record)
        payload["conversations"] = conversations
        write_canonical_json(self._conversations_path, payload)
        return ConversationRecord(
            conversation_id=conversation_id,
            principal_id=principal_id,
            title=title,
            created_at_ns=now,
            updated_at_ns=now,
        )

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        provenance: InferenceProvenanceRecord | None = None,
    ) -> MessageRecord:
        now = _now_ns()
        message_id = sha256_bytes(
            canonical_bytes(
                {
                    "conversation_id": conversation_id,
                    "content": content,
                    "role": role,
                    "ts": now,
                }
            )
        )[:16]
        message = MessageRecord(
            message_id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at_ns=now,
            provenance=provenance,
        )
        conv_payload = self._load_conversations()
        conversations = conv_payload.get("conversations", [])
        if not isinstance(conversations, list):
            raise ValueError("conversations list corrupt")
        found = False
        for conversation in conversations:
            if not isinstance(conversation, dict):
                continue
            if str(conversation.get("conversation_id")) != conversation_id:
                continue
            found = True
            message_ids = conversation.get("message_ids", [])
            if not isinstance(message_ids, list):
                message_ids = []
            message_ids.append(message_id)
            conversation["message_ids"] = message_ids
            conversation["updated_at_ns"] = now
            break
        if not found:
            raise KeyError(conversation_id)
        write_canonical_json(self._conversations_path, conv_payload)

        msg_payload = self._load_messages()
        messages = msg_payload.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        messages.append(_message_body(message))
        msg_payload["messages"] = messages
        write_canonical_json(self._messages_path, msg_payload)
        return message

    def list_conversations(self, principal_id: str | None = None) -> list[ConversationRecord]:
        payload = self._load_conversations()
        conversations = payload.get("conversations", [])
        if not isinstance(conversations, list):
            return []
        result: list[ConversationRecord] = []
        for item in conversations:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("principal_id", ""))
            if principal_id is not None and pid != principal_id:
                continue
            message_ids = item.get("message_ids", [])
            if not isinstance(message_ids, list):
                message_ids = []
            result.append(
                ConversationRecord(
                    conversation_id=str(item.get("conversation_id", "")),
                    principal_id=pid,
                    title=str(item.get("title", "")),
                    created_at_ns=int(item.get("created_at_ns", 0)),
                    updated_at_ns=int(item.get("updated_at_ns", 0)),
                    message_ids=tuple(str(mid) for mid in message_ids),
                )
            )
        result.sort(key=lambda row: row.updated_at_ns, reverse=True)
        return result

    def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        for conversation in self.list_conversations():
            if conversation.conversation_id == conversation_id:
                return conversation
        return None

    def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        payload = self._load_messages()
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            return []
        result: list[MessageRecord] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            if str(item.get("conversation_id")) != conversation_id:
                continue
            provenance_raw = item.get("provenance")
            provenance = None
            if isinstance(provenance_raw, dict):
                provenance = InferenceProvenanceRecord(
                    provider_id=str(provenance_raw.get("provider_id", "")),
                    model_id=str(provenance_raw.get("model_id", "")),
                    tokens_prompt=provenance_raw.get("tokens_prompt"),
                    tokens_completion=provenance_raw.get("tokens_completion"),
                    citation_refs=tuple(provenance_raw.get("citation_refs", []) or []),
                    abstained=bool(provenance_raw.get("abstained", False)),
                    abstention_reason=provenance_raw.get("abstention_reason"),
                )
            result.append(
                MessageRecord(
                    message_id=str(item.get("message_id", "")),
                    conversation_id=str(item.get("conversation_id", "")),
                    role=str(item.get("role", "")),
                    content=str(item.get("content", "")),
                    created_at_ns=int(item.get("created_at_ns", 0)),
                    provenance=provenance,
                )
            )
        result.sort(key=lambda row: row.created_at_ns)
        return result

    def token_accounting_summary(self, conversation_id: str) -> dict[str, int]:
        totals = {"tokens_completion": 0, "tokens_prompt": 0}
        for message in self.list_messages(conversation_id):
            if message.provenance is None:
                continue
            if message.provenance.tokens_prompt is not None:
                totals["tokens_prompt"] += int(message.provenance.tokens_prompt)
            if message.provenance.tokens_completion is not None:
                totals["tokens_completion"] += int(message.provenance.tokens_completion)
        return totals

    def delete_conversation(self, conversation_id: str) -> bool:
        conv_payload = self._load_conversations()
        conversations = conv_payload.get("conversations", [])
        if not isinstance(conversations, list):
            return False
        kept = [
            row
            for row in conversations
            if not (isinstance(row, dict) and str(row.get("conversation_id")) == conversation_id)
        ]
        if len(kept) == len(conversations):
            return False
        conv_payload["conversations"] = kept
        write_canonical_json(self._conversations_path, conv_payload)

        msg_payload = self._load_messages()
        messages = msg_payload.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        msg_payload["messages"] = [
            row
            for row in messages
            if not (isinstance(row, dict) and str(row.get("conversation_id")) == conversation_id)
        ]
        write_canonical_json(self._messages_path, msg_payload)
        return True

    def apply_retention_policy(self, *, max_conversations_per_principal: int) -> dict[str, int]:
        if max_conversations_per_principal < 0:
            raise ValueError("RETENTION_LIMIT_INVALID")
        principals = {row.principal_id for row in self.list_conversations()}
        deleted = 0
        for principal_id in sorted(principals):
            rows = self.list_conversations(principal_id)
            overflow = len(rows) - max_conversations_per_principal
            if overflow <= 0:
                continue
            oldest = sorted(rows, key=lambda row: row.created_at_ns)[:overflow]
            for conversation in oldest:
                if self.delete_conversation(conversation.conversation_id):
                    deleted += 1
        return {"deleted_conversations": deleted}

    def contains_secret_like_content(self) -> bool:
        """Heuristic scan for credential-like strings in persisted messages."""
        needles = (
            "api_key",
            "password",
            "secret",
            "token=",
            "BEGIN PRIVATE KEY",
            "finra_client_id",
            "finra_client_secret",
            "access_token",
            "authorization:",
        )
        for message in self.list_messages_for_all():
            lowered = message.content.lower()
            if any(needle in lowered for needle in needles):
                return True
        return False

    def list_messages_for_all(self) -> list[MessageRecord]:
        payload = self._load_messages()
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            return []
        result: list[MessageRecord] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            provenance_raw = item.get("provenance")
            provenance = None
            if isinstance(provenance_raw, dict):
                provenance = InferenceProvenanceRecord(
                    provider_id=str(provenance_raw.get("provider_id", "")),
                    model_id=str(provenance_raw.get("model_id", "")),
                    tokens_prompt=provenance_raw.get("tokens_prompt"),
                    tokens_completion=provenance_raw.get("tokens_completion"),
                    citation_refs=tuple(provenance_raw.get("citation_refs", []) or []),
                    abstained=bool(provenance_raw.get("abstained", False)),
                    abstention_reason=provenance_raw.get("abstention_reason"),
                )
            result.append(
                MessageRecord(
                    message_id=str(item.get("message_id", "")),
                    conversation_id=str(item.get("conversation_id", "")),
                    role=str(item.get("role", "")),
                    content=str(item.get("content", "")),
                    created_at_ns=int(item.get("created_at_ns", 0)),
                    provenance=provenance,
                )
            )
        return result

    def store_fingerprint(self) -> str:
        conv_hash = sha256_bytes(self._conversations_path.read_bytes())
        msg_hash = sha256_bytes(self._messages_path.read_bytes())
        return sha256_bytes(canonical_bytes({"conversations": conv_hash, "messages": msg_hash}))
