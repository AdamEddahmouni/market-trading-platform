"""Anthropic Messages API adapter per ADR-LLM-001 (stdlib HTTP, env-injected credentials)."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .evidence_pack import build_evidence_pack, evidence_pack_prompt_text
from .grounded_inference import GroundedEvidenceInference
from .inference_boundary import InferenceOutcome, ProviderNeutralInferenceBoundary

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT = 60.0

CITATION_PATTERN = re.compile(r"\b((?:explain|inspect):[^\s\]\),]+)")

SYSTEM_PROMPT = """You are a read-only market research assistant embedded in a replay-only trading research platform.

Authority boundary: READ_ONLY_NO_EXECUTION. You cannot place orders, override risk, or mutate positions.

Rules:
1. Answer ONLY using the evidence pack provided. Do not invent prices, filings, or market data.
2. Cite every factual claim with one or more exact refs from allowed_citation_refs, using bracket form like [explain:disclosure:BIYA].
3. If the evidence pack is insufficient, say explicitly that you cannot determine from available evidence.
4. Treat disclosure and institutional data as delayed research evidence, never as live trading signals.
5. Do not recommend trades, position sizes, or guaranteed outcomes.
"""


def extract_citation_refs(content: str, allowed_refs: set[str]) -> tuple[str, ...]:
    found: list[str] = []
    for match in CITATION_PATTERN.findall(content):
        ref = match.rstrip(".,;:")
        if ref in allowed_refs and ref not in found:
            found.append(ref)
    return tuple(found)


def call_anthropic_messages(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    request = Request(
        ANTHROPIC_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise ConnectionError(f"anthropic messages request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("anthropic response must be object")
    return payload


def _usage_tokens(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    prompt_tokens = usage.get("input_tokens")
    completion_tokens = usage.get("output_tokens")
    return (
        int(prompt_tokens) if prompt_tokens is not None else None,
        int(completion_tokens) if completion_tokens is not None else None,
    )


def _response_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(part for part in parts if part).strip()


class AnthropicInference:
    """Grounded RAG-style Anthropic adapter with deterministic fallback."""

    provider_id = "anthropic.messages"

    def __init__(
        self,
        *,
        fallback: ProviderNeutralInferenceBoundary | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.fallback = fallback or GroundedEvidenceInference()
        self.api_key = (api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        self.model = (model if model is not None else os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)).strip()

    def infer(
        self,
        prompt: str,
        *,
        context_citations: tuple[dict[str, str], ...] = (),
        evidence_context: dict[str, object] | None = None,
    ) -> InferenceOutcome:
        if not self.api_key:
            return InferenceOutcome(
                content="",
                citations=(),
                abstained=True,
                abstention_reason="API_KEY_MISSING",
                model_id=self.model,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=0,
            )
        if not evidence_context:
            return self.fallback.infer(
                prompt,
                context_citations=context_citations,
                evidence_context=evidence_context,
            )

        pack = build_evidence_pack(prompt, evidence_context)
        allowed_refs = {str(ref) for ref in pack.get("allowed_citation_refs", []) if ref}
        for citation in context_citations:
            ref = citation.get("ref", "")
            if ref:
                allowed_refs.add(ref)

        user_prompt = (
            "Evidence pack (JSON):\n"
            f"{evidence_pack_prompt_text(pack)}\n\n"
            f"User question: {prompt.strip()}\n\n"
            "Respond in plain language with bracketed citation refs from allowed_citation_refs."
        )

        try:
            payload = call_anthropic_messages(
                api_key=self.api_key,
                model=self.model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except (ConnectionError, ValueError):
            return self.fallback.infer(
                prompt,
                context_citations=context_citations,
                evidence_context=evidence_context,
            )

        content = _response_text(payload)
        if not content:
            return InferenceOutcome(
                content="",
                citations=(),
                abstained=True,
                abstention_reason="PROVIDER_EMPTY_RESPONSE",
                model_id=self.model,
                provider_id=self.provider_id,
                tokens_prompt=len(prompt.split()),
                tokens_completion=0,
            )

        cited_refs = extract_citation_refs(content, allowed_refs)
        citations = tuple({"ref": ref, "kind": "explain" if ref.startswith("explain:") else "inspect"} for ref in cited_refs)
        tokens_prompt, tokens_completion = _usage_tokens(payload)

        if not cited_refs and "cannot determine" not in content.lower():
            fallback = self.fallback.infer(
                prompt,
                context_citations=context_citations,
                evidence_context=evidence_context,
            )
            if not fallback.abstained and fallback.citations:
                return InferenceOutcome(
                    content=content,
                    citations=fallback.citations,
                    abstained=False,
                    abstention_reason=None,
                    model_id=self.model,
                    provider_id=self.provider_id,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion or len(content.split()),
                )

        return InferenceOutcome(
            content=content,
            citations=citations,
            abstained=False,
            abstention_reason=None,
            model_id=self.model,
            provider_id=self.provider_id,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion or len(content.split()),
        )
