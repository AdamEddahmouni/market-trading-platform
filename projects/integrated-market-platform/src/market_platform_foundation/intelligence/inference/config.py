"""Configuration for governed news intelligence inference."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import IntelligenceTaskType


@dataclass(frozen=True, slots=True)
class IntelligenceInferenceConfig:
    provider_id: str = "inference.fixture"
    model_id: str = "fixture.news-intelligence.v1"
    timeout_seconds: float = 30.0
    max_retries: int = 0
    max_articles: int = 8
    max_content_chars: int = 12000
    max_tokens: int = 1024
    default_task_type: IntelligenceTaskType = IntelligenceTaskType.NEWS_SENTIMENT
    prompt_id: str = ""
    output_schema_version: str = "intelligence/inference/output/1.0.0"
    enable_cache: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_articles": self.max_articles,
            "max_content_chars": self.max_content_chars,
            "max_tokens": self.max_tokens,
            "default_task_type": self.default_task_type.value,
            "prompt_id": self.prompt_id,
            "output_schema_version": self.output_schema_version,
            "enable_cache": self.enable_cache,
        }


def default_inference_config() -> IntelligenceInferenceConfig:
    return IntelligenceInferenceConfig()


def verify_inference_config(config: IntelligenceInferenceConfig) -> tuple[str, ...]:
    issues: list[str] = []
    if config.max_articles < 1:
        issues.append("MAX_ARTICLES_INVALID")
    if config.max_content_chars < 256:
        issues.append("MAX_CONTENT_CHARS_INVALID")
    if config.timeout_seconds <= 0:
        issues.append("TIMEOUT_INVALID")
    if config.max_tokens < 64:
        issues.append("MAX_TOKENS_INVALID")
    if not config.provider_id:
        issues.append("PROVIDER_ID_MISSING")
    if not config.model_id:
        issues.append("MODEL_ID_MISSING")
    return tuple(issues)


__all__ = [
    "IntelligenceInferenceConfig",
    "default_inference_config",
    "verify_inference_config",
]
