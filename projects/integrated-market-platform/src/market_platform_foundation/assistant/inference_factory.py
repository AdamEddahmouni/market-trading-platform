"""Resolve assistant inference provider from environment."""

from __future__ import annotations

import os

from .anthropic_inference import AnthropicInference
from .grounded_inference import GroundedEvidenceInference
from .inference_boundary import AbstainingInferenceStub, ProviderNeutralInferenceBoundary


def resolve_assistant_inference() -> ProviderNeutralInferenceBoundary:
    """Select inference adapter: stub, grounded, or Anthropic (when configured)."""
    if os.environ.get("IMP_ASSISTANT_STUB", "").lower() in {"1", "true", "yes"}:
        return AbstainingInferenceStub()

    provider = os.environ.get("IMP_ASSISTANT_PROVIDER", "").strip().lower()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if provider == "grounded":
        return GroundedEvidenceInference()
    if provider == "anthropic" or (provider == "" and api_key):
        return AnthropicInference(fallback=GroundedEvidenceInference())
    return GroundedEvidenceInference()
