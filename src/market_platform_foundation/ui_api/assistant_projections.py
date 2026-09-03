"""Assistant API projections for UI-001 read-only sidecar."""

from __future__ import annotations

from typing import Any

from ..assistant.service import AssistantResearchService
from .store import ReplayStore


def build_assistant_status(store: ReplayStore) -> dict[str, Any]:
    status = store.assistant_service.build_status()
    status["as_of_context"] = {
        "as_of_time": store.as_of_time(),
        "instrument_id": store.instrument_id,
        "mode": store.mode,
        "replay_session_id": store.session_id,
        "timezone": store.timezone,
    }
    return status


def build_assistant_conversations(store: ReplayStore, principal_id: str | None = None) -> dict[str, Any]:
    return {
        "conversations": store.assistant_service.list_conversations(principal_id),
        "principal_id": principal_id,
    }


def build_assistant_messages(store: ReplayStore, conversation_id: str) -> dict[str, Any]:
    return store.assistant_service.list_messages(conversation_id)


def create_assistant_conversation(
    store: ReplayStore,
    *,
    title: str,
    principal_id: str | None = None,
) -> dict[str, Any]:
    from ..assistant.service import DEFAULT_PRINCIPAL_ID

    return store.assistant_service.create_conversation(
        title,
        principal_id=principal_id or DEFAULT_PRINCIPAL_ID,
    )


def submit_assistant_prompt(
    store: ReplayStore,
    conversation_id: str,
    prompt: str,
    *,
    selection_ref: str | None = None,
    extra_citations: tuple[dict[str, str], ...] = (),
) -> dict[str, Any]:
    evidence_context = store.assistant_service.build_evidence_context(
        store,
        selection_ref=selection_ref,
    )
    context = store.assistant_service.build_context_citations(store)
    merged = context + extra_citations
    return store.assistant_service.submit_prompt(
        conversation_id,
        prompt,
        context_citations=merged,
        selection_ref=selection_ref,
        evidence_context=evidence_context,
    )
