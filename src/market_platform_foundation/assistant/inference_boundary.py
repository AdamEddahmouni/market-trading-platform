"""Provider-neutral inference boundary per ADR-LLM-001 (GridIQ Gemini path is DO_NOT_USE)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class InferenceOutcome:
    """Read-only assistant response with mandatory citation and abstention support."""

    content: str
    citations: tuple[dict[str, str], ...] = ()
    abstained: bool = False
    abstention_reason: str | None = None
    model_id: str = ""
    provider_id: str = ""
    tokens_prompt: int | None = None
    tokens_completion: int | None = None


class ProviderNeutralInferenceBoundary(Protocol):
    """Inference adapter with no order, risk, or execution authority."""

    def infer(
        self,
        prompt: str,
        *,
        context_citations: tuple[dict[str, str], ...] = (),
    ) -> InferenceOutcome:
        ...


class AbstainingInferenceStub:
    """Offline-safe stub that always abstains until a provider adapter is authorized."""

    provider_id = "stub.abstain"
    model_id = "stub.none"

    def infer(
        self,
        prompt: str,
        *,
        context_citations: tuple[dict[str, str], ...] = (),
    ) -> InferenceOutcome:
        del prompt, context_citations
        return InferenceOutcome(
            content="",
            citations=(),
            abstained=True,
            abstention_reason="PROVIDER_NOT_AUTHORIZED",
            model_id=self.model_id,
            provider_id=self.provider_id,
            tokens_prompt=0,
            tokens_completion=0,
        )
