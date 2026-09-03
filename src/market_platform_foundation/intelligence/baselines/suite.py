"""Multi-baseline orchestration (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .engine import BaselinePredictionEngine
from .types import BaselineModel, BaselinePredictionRequest, BaselinePredictionResult


@dataclass
class BaselineSuiteResult:
    results: tuple[BaselinePredictionResult, ...]


@dataclass
class BaselineSuite:
    models: tuple[BaselineModel, ...] = field(default_factory=tuple)
    engine: BaselinePredictionEngine = field(default_factory=BaselinePredictionEngine)

    def run(self, request: BaselinePredictionRequest) -> BaselineSuiteResult:
        ordered = sorted(self.models, key=lambda model: getattr(model, "model_kind", ""))
        results = [self.engine.predict(request, model) for model in ordered]
        return BaselineSuiteResult(results=tuple(results))


def default_control_suite(
    *,
    target,
    random_seed: str = "build08-control",
) -> BaselineSuite:
    from .controls.momentum import MomentumBaseline
    from .controls.naive import (
        AlwaysDownBaseline,
        AlwaysUpBaseline,
        DeterministicRandomBaseline,
    )

    return BaselineSuite(
        models=(
            AlwaysUpBaseline().bind_target(target),
            AlwaysDownBaseline().bind_target(target),
            DeterministicRandomBaseline(seed=random_seed).bind_target(target),
            MomentumBaseline().bind_target(target),
        )
    )


__all__ = ["BaselineSuite", "BaselineSuiteResult", "default_control_suite"]
