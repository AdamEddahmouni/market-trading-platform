"""Hypothesis engine registry for BUILD 13."""

from __future__ import annotations

from dataclasses import dataclass

from .short_squeeze import ShortSqueezeHypothesisEngine
from .types import HypothesisType


@dataclass(frozen=True, slots=True)
class HypothesisEngineRegistry:
    engines: dict[str, object]

    def get(self, hypothesis_type: str):
        engine = self.engines.get(hypothesis_type)
        if engine is None:
            raise KeyError(f"HYPOTHESIS_ENGINE_NOT_REGISTERED:{hypothesis_type}")
        return engine


DEFAULT_HYPOTHESIS_ENGINE_REGISTRY = HypothesisEngineRegistry(
    engines={
        HypothesisType.SHORT_SQUEEZE_SETUP.value: ShortSqueezeHypothesisEngine(),
    }
)


__all__ = ["DEFAULT_HYPOTHESIS_ENGINE_REGISTRY", "HypothesisEngineRegistry"]
