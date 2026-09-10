"""Evaluation laboratory errors."""

from __future__ import annotations

from enum import StrEnum


class EvaluationErrorCode(StrEnum):
    CONFIG_INVALID = "CONFIG_INVALID"
    POLICY_UNKNOWN = "POLICY_UNKNOWN"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    FUTURE_NEWS_LEAK = "FUTURE_NEWS_LEAK"
    FUTURE_INFERENCE_LEAK = "FUTURE_INFERENCE_LEAK"
    FUTURE_MARKET_LEAK = "FUTURE_MARKET_LEAK"
    OUTCOME_BEFORE_DECISION = "OUTCOME_BEFORE_DECISION"
    INSTRUMENT_UNKNOWN = "INSTRUMENT_UNKNOWN"
    MARKET_DATA_MISSING = "MARKET_DATA_MISSING"
    INFERENCE_UNAVAILABLE = "INFERENCE_UNAVAILABLE"
    SHADOW_EXECUTION_AUTHORITY = "SHADOW_EXECUTION_AUTHORITY"


class EvaluationError(ValueError):
    def __init__(self, code: EvaluationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


__all__ = ["EvaluationError", "EvaluationErrorCode"]
