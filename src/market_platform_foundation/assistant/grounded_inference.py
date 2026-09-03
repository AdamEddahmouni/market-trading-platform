"""Deterministic grounded evidence inference per MRA-001 (no LLM, no network)."""

from __future__ import annotations

from typing import Any

from .evidence_pack import build_conflict_answer, format_explanation, pick_explain_ref
from .inference_boundary import InferenceOutcome
from .intent_router import route_intent


class GroundedEvidenceInference:
    """Retrieve and cite canonical explain/inspect projections without an LLM."""

    provider_id = "grounded.evidence"
    model_id = "deterministic.v1"

    def infer(
        self,
        prompt: str,
        *,
        context_citations: tuple[dict[str, str], ...] = (),
        evidence_context: dict[str, object] | None = None,
    ) -> InferenceOutcome:
        del context_citations
        if not evidence_context:
            return InferenceOutcome(
                content="",
                citations=(),
                abstained=True,
                abstention_reason="EVIDENCE_CONTEXT_MISSING",
                model_id=self.model_id,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=0,
            )

        resolve_explain = evidence_context.get("resolve_explain")
        resolve_inspect = evidence_context.get("resolve_inspect")
        if not callable(resolve_explain):
            return InferenceOutcome(
                content="",
                citations=(),
                abstained=True,
                abstention_reason="EVIDENCE_RESOLVER_MISSING",
                model_id=self.model_id,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=0,
            )

        intent = route_intent(prompt)
        if intent == "conflict":
            content, refs = build_conflict_answer(evidence_context, resolve_explain)
            citations = tuple({"ref": ref, "kind": "explain"} for ref in refs)
            return InferenceOutcome(
                content=content,
                citations=citations,
                abstained=False,
                abstention_reason=None,
                model_id=self.model_id,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=len(content.split()),
            )

        explain_ref = pick_explain_ref(intent, evidence_context=evidence_context, prompt=prompt)
        if not explain_ref:
            return InferenceOutcome(
                content="",
                citations=(),
                abstained=True,
                abstention_reason="EVIDENCE_NOT_AVAILABLE",
                model_id=self.model_id,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=0,
            )

        try:
            explain_payload = resolve_explain(explain_ref)
        except ValueError:
            return InferenceOutcome(
                content="",
                citations=(),
                abstained=True,
                abstention_reason="REF_NOT_FOUND",
                model_id=self.model_id,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=0,
            )

        content = format_explanation(explain_payload, ref=explain_ref)
        inspector_ref = str(explain_payload.get("inspector_ref", explain_ref.replace("explain:", "inspect:", 1)))
        citations: list[dict[str, str]] = [{"ref": explain_ref, "kind": "explain"}]
        if intent in {"show_source", "what_changed"} and callable(resolve_inspect):
            try:
                inspect_payload = resolve_inspect(inspector_ref)
                tabs = inspect_payload.get("tabs", {})
                if isinstance(tabs, dict):
                    summary = tabs.get("SUMMARY", {})
                    if isinstance(summary, dict) and summary.get("summary"):
                        content = f"{content} Source detail: {summary.get('summary')}"
                citations.append({"ref": inspector_ref, "kind": "inspect"})
            except ValueError:
                pass

        return InferenceOutcome(
            content=content,
            citations=tuple(citations),
            abstained=False,
            abstention_reason=None,
            model_id=self.model_id,
            provider_id=self.provider_id,
            tokens_prompt=len(prompt.split()),
            tokens_completion=len(content.split()),
        )
