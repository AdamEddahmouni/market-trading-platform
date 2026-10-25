"""Resolve assistant inference provider from environment and the machine-wide AI engine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .anthropic_inference import AnthropicInference
from .grounded_inference import GroundedEvidenceInference
from .inference_boundary import AbstainingInferenceStub, InferenceOutcome, ProviderNeutralInferenceBoundary


class MachineEngineInference:
    """The assistant follows the AI engine chosen in Setup.

    Paid Claude answers only when Claude is the chosen engine and both paid AI dollar caps are set; its calls are
    charged to the same dollar ledger as every other paid call. Anything else (automatic, local, OpenAI, Gemini, no
    caps) answers with the grounded evidence answerer, which calls no model. Resolved on every question, so a switch
    in Setup applies to the next one. A saved key alone never makes the assistant paid."""

    def __init__(self, value: Callable[[str], str | None] | None = None, cache_dir: Path | None = None) -> None:
        self._value = value
        self._cache_dir = cache_dir
        self._grounded = GroundedEvidenceInference()

    def _inputs(self) -> tuple[Callable[[str], str | None], Path]:
        from ..local_state.external_cache import imp_cache_dir
        from ..news.config import configured_value

        return self._value or configured_value, self._cache_dir or imp_cache_dir()

    def current(self) -> ProviderNeutralInferenceBoundary:
        from ..intelligence.inference.paid_spend import ledger_for, paid_gate
        from ..intelligence.inference.synthesis_engines import SynthesisSettings, engine_models

        value, cache_dir = self._inputs()
        choice = SynthesisSettings(value, cache_dir).current()
        if choice["engine"] != "anthropic":
            return self._grounded
        api_key = (value("ANTHROPIC_API_KEY") or "").strip()
        model = choice["model"] or engine_models("anthropic", value)[0][0]
        if not api_key or paid_gate(value, model) is not None:
            return self._grounded
        return AnthropicInference(fallback=self._grounded, api_key=api_key, model=model,
                                  ledger=ledger_for(value, cache_dir))

    @property
    def provider_id(self) -> str:
        return getattr(self.current(), "provider_id", GroundedEvidenceInference.provider_id)

    @property
    def model_id(self) -> str:
        current = self.current()
        return str(getattr(current, "model", None) or getattr(current, "model_id", ""))

    def infer(self, prompt: str, *, context_citations: tuple[dict[str, str], ...] = (),
              evidence_context: dict[str, object] | None = None) -> InferenceOutcome:
        return self.current().infer(prompt, context_citations=context_citations, evidence_context=evidence_context)


def resolve_assistant_inference() -> ProviderNeutralInferenceBoundary:
    """Select inference adapter: stub, grounded, or the machine-wide AI engine (paid Claude only within caps)."""
    if os.environ.get("IMP_ASSISTANT_STUB", "").lower() in {"1", "true", "yes"}:
        return AbstainingInferenceStub()

    provider = os.environ.get("IMP_ASSISTANT_PROVIDER", "").strip().lower()
    if provider == "grounded":
        return GroundedEvidenceInference()
    # IMP_ASSISTANT_PROVIDER=anthropic no longer turns paid AI on by itself: the Setup engine and caps decide.
    return MachineEngineInference()
