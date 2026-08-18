"""Research assistant orchestration per ADR-LLM-001 (no execution authority)."""

from __future__ import annotations

from typing import Any

from .audit_store import AssistantAuditStore, InferenceProvenanceRecord, MessageRecord
from .anthropic_inference import AnthropicInference
from .context_assembler import build_evidence_context
from .grounded_inference import GroundedEvidenceInference
from .inference_boundary import AbstainingInferenceStub, ProviderNeutralInferenceBoundary

DEFAULT_PRINCIPAL_ID = "RESEARCH-UI-001"
AUTHORITY_BOUNDARY = "READ_ONLY_NO_EXECUTION"
EPISTEMIC_STUB = "RESEARCH_ASSISTANT_STUB"
EPISTEMIC_GROUNDED = "RESEARCH_ASSISTANT_GROUNDED"
EPISTEMIC_LLM = "RESEARCH_ASSISTANT_LLM"


def _message_payload(message: MessageRecord) -> dict[str, Any]:
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
        "content": message.content,
        "conversation_id": message.conversation_id,
        "created_at_ns": message.created_at_ns,
        "message_id": message.message_id,
        "provenance": provenance,
        "role": message.role,
    }


class AssistantResearchService:
    """Read-only research assistant with audited prompts and provenance."""

    def __init__(
        self,
        audit_store: AssistantAuditStore,
        *,
        inference: ProviderNeutralInferenceBoundary | None = None,
    ) -> None:
        self.audit_store = audit_store
        self.inference = inference or AbstainingInferenceStub()

    def build_status(self) -> dict[str, Any]:
        stub = self.inference
        provider_id = getattr(stub, "provider_id", "unknown")
        model_id = getattr(stub, "model_id", "unknown")
        epistemic_class = EPISTEMIC_STUB
        if provider_id == AnthropicInference.provider_id:
            epistemic_class = EPISTEMIC_LLM
        elif provider_id == GroundedEvidenceInference.provider_id:
            epistemic_class = EPISTEMIC_GROUNDED
        return {
            "authority_boundary": AUTHORITY_BOUNDARY,
            "available": True,
            "citation_required": True,
            "default_principal_id": DEFAULT_PRINCIPAL_ID,
            "epistemic_class": epistemic_class,
            "logical_id": "assistant.status",
            "llm_configured": provider_id == AnthropicInference.provider_id,
            "model_id": model_id,
            "provider_id": provider_id,
            "store_fingerprint": self.audit_store.store_fingerprint(),
        }

    def list_conversations(self, principal_id: str | None = None) -> list[dict[str, Any]]:
        conversations = self.audit_store.list_conversations(principal_id)
        return [
            {
                "conversation_id": row.conversation_id,
                "created_at_ns": row.created_at_ns,
                "message_count": len(row.message_ids),
                "principal_id": row.principal_id,
                "title": row.title,
                "updated_at_ns": row.updated_at_ns,
            }
            for row in conversations
        ]

    def create_conversation(self, title: str, *, principal_id: str = DEFAULT_PRINCIPAL_ID) -> dict[str, Any]:
        conversation = self.audit_store.create_conversation(principal_id, title)
        return {
            "conversation_id": conversation.conversation_id,
            "created_at_ns": conversation.created_at_ns,
            "message_count": 0,
            "principal_id": conversation.principal_id,
            "title": conversation.title,
            "updated_at_ns": conversation.updated_at_ns,
        }

    def list_messages(self, conversation_id: str) -> dict[str, Any]:
        if self.audit_store.get_conversation(conversation_id) is None:
            raise KeyError(conversation_id)
        messages = self.audit_store.list_messages(conversation_id)
        accounting = self.audit_store.token_accounting_summary(conversation_id)
        return {
            "conversation_id": conversation_id,
            "messages": [_message_payload(message) for message in messages],
            "token_accounting": accounting,
        }

    def submit_prompt(
        self,
        conversation_id: str,
        prompt: str,
        *,
        context_citations: tuple[dict[str, str], ...] = (),
        selection_ref: str | None = None,
        evidence_context: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        if self.audit_store.get_conversation(conversation_id) is None:
            raise KeyError(conversation_id)
        cleaned = prompt.strip()
        if not cleaned:
            raise ValueError("ASSISTANT_PROMPT_EMPTY")

        citations: list[dict[str, str]] = list(context_citations)
        if selection_ref:
            citations.append({"ref": selection_ref, "kind": "selection"})

        user_message = self.audit_store.append_message(conversation_id, "user", cleaned)
        outcome = self.inference.infer(
            cleaned,
            context_citations=tuple(citations),
            evidence_context=evidence_context,
        )
        assistant_content = outcome.content
        if outcome.abstained and not assistant_content:
            assistant_content = outcome.abstention_reason or "ABSTAINED"

        citation_refs: list[str] = [ref.get("ref", "") for ref in citations if ref.get("ref")]
        for cited in outcome.citations:
            ref_value = cited.get("ref", "")
            if ref_value and ref_value not in citation_refs:
                citation_refs.append(ref_value)

        provenance = InferenceProvenanceRecord(
            provider_id=outcome.provider_id,
            model_id=outcome.model_id,
            tokens_prompt=outcome.tokens_prompt,
            tokens_completion=outcome.tokens_completion,
            citation_refs=tuple(citation_refs),
            abstained=outcome.abstained,
            abstention_reason=outcome.abstention_reason,
        )
        assistant_message = self.audit_store.append_message(
            conversation_id,
            "assistant",
            assistant_content,
            provenance=provenance,
        )
        return {
            "assistant_message": _message_payload(assistant_message),
            "citations": [dict(ref) for ref in citations] + [dict(ref) for ref in outcome.citations],
            "conversation_id": conversation_id,
            "user_message": _message_payload(user_message),
        }

    def build_evidence_context(self, store: Any, *, selection_ref: str | None = None) -> dict[str, object]:
        """Build server-assembled evidence context for grounded inference."""
        return build_evidence_context(store, selection_ref=selection_ref)

    def build_context_citations(self, store: Any) -> tuple[dict[str, str], ...]:
        """Build replay-context citations from a loaded ReplayStore."""
        citations: list[dict[str, str]] = [
            {
                "ref": f"replay:session:{store.session_id}",
                "kind": "replay_session",
            },
            {
                "ref": f"instrument:{store.instrument_id}",
                "kind": "instrument",
            },
            {
                "ref": f"as_of:{store.as_of_time()}",
                "kind": "as_of_time",
            },
        ]
        return tuple(citations)

    def resolve_citation_refs(
        self,
        refs: tuple[str, ...],
        *,
        allowed_prefixes: tuple[str, ...] = (
            "replay:",
            "instrument:",
            "as_of:",
            "explain:",
            "inspect:",
            "selection:",
        ),
    ) -> dict[str, object]:
        """Validate citation refs before inference; unsupported refs fail closed."""
        resolved: list[dict[str, str]] = []
        rejected: list[str] = []
        for ref in refs:
            if not ref:
                rejected.append(ref)
                continue
            if any(ref.startswith(prefix) for prefix in allowed_prefixes):
                resolved.append({"ref": ref, "status": "RESOLVED"})
            else:
                rejected.append(ref)
        return {
            "logical_id": "assistant.citation_resolution",
            "rejected_refs": rejected,
            "resolved_refs": resolved,
            "status": "PASS" if not rejected else "FAIL",
        }
