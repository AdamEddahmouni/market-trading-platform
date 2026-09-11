"""Deterministic evaluation replay harness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import EvaluationConfig
from .contracts import EvaluationReport
from .evaluator import NewsStrategyEvaluator
from .fixture_loader import DEFAULT_FIXTURE_PATH, load_fixture_pack


@dataclass(frozen=True, slots=True)
class EvaluationReplayResult:
    report: EvaluationReport
    replay_count: int
    report_hashes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "replay_count": self.replay_count,
            "report_hashes": list(self.report_hashes),
            "deterministic": len(set(self.report_hashes)) == 1,
        }


class EvaluationReplayHarness:
    """Replay fixture evaluation with stable hashes."""

    def __init__(
        self,
        *,
        config: EvaluationConfig | None = None,
        fixture_path: Path | None = None,
    ) -> None:
        self._config = config or EvaluationConfig()
        self._fixture_path = fixture_path or DEFAULT_FIXTURE_PATH

    def replay(self, *, iterations: int = 2) -> EvaluationReplayResult:
        pack = load_fixture_pack(self._fixture_path)
        hashes: list[str] = []
        report: EvaluationReport | None = None
        for _ in range(max(1, iterations)):
            evaluator = NewsStrategyEvaluator(config=self._config)
            report = evaluator.evaluate_fixture_pack(pack)
            hashes.append(report.report_hash)
        assert report is not None
        return EvaluationReplayResult(
            report=report,
            replay_count=len(hashes),
            report_hashes=tuple(hashes),
        )


__all__ = ["EvaluationReplayHarness", "EvaluationReplayResult"]
