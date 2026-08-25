"""Error hierarchy for BUILD 13 composite hypothesis engines."""

from __future__ import annotations


class HypothesisEngineError(Exception):
    """Base error for hypothesis engine failures."""


class HypothesisConfigurationError(HypothesisEngineError):
    """Invalid engine or policy configuration."""


class HypothesisIntegrityError(HypothesisEngineError):
    """Blackboard, relation report, or evidence integrity violation."""


class HypothesisEvidenceError(HypothesisEngineError):
    """Evidence resolution or adapter failure."""


__all__ = [
    "HypothesisConfigurationError",
    "HypothesisEngineError",
    "HypothesisEvidenceError",
    "HypothesisIntegrityError",
]
