"""Provider-neutral inference boundary and implementations."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceInputPacket, ParsingStatus
from .errors import InferenceErrorCode
from .hashing import raw_response_hash
from .input_builder import articles_json_for_prompt
from .prompts import PromptRegistry
from .prompts import PromptDefinition


@dataclass(frozen=True, slots=True)
class ProviderInferenceResponse:
    raw_text: str
    provider_id: str
    model_id: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    latency_ms: int | None = None
    provider_request_id: str = ""
    provider_response_id: str = ""
    error_code: InferenceErrorCode | None = None
    error_message: str = ""
    parsing_status: ParsingStatus = ParsingStatus.VALID
    simulated: bool = False


class InferenceProvider(Protocol):
    provider_id: str
    model_id: str

    def infer(
        self,
        packet: IntelligenceInputPacket,
        *,
        rendered_prompt: str,
        config: IntelligenceInferenceConfig,
    ) -> ProviderInferenceResponse:
        ...


DEFAULT_FIXTURE_RESPONSES: dict[str, str] = {
    "NEWS_SENTIMENT": json.dumps(
        {
            "sentiment_label": "BULLISH",
            "sentiment_score": 0.35,
            "rationale": "Curated articles indicate modest positive sentiment.",
            "model_confidence": 0.62,
            "warnings": [],
        }
    ),
    "NEWS_CATALYST_ANALYSIS": json.dumps(
        {
            "catalyst_interpretation": "Deterministic catalyst matches appear materially relevant.",
            "catalyst_strength": "MODERATE",
            "sentiment_label": "BULLISH",
            "rationale": "Catalyst context supports near-term positive interpretation.",
            "model_confidence": 0.58,
            "warnings": [],
        }
    ),
    "NEWS_MARKET_IMPACT": json.dumps(
        {
            "market_impact_level": "MODERATE",
            "impact_horizon": "SHORT_TERM",
            "sentiment_label": "BULLISH",
            "rationale": "Impact likely moderate over short horizon; non-executable assessment.",
            "model_confidence": 0.55,
            "warnings": [],
        }
    ),
}


class FixtureInferenceProvider:
    """Deterministic offline provider for tests and replay — no network."""

    provider_id = "inference.fixture"
    model_id = "fixture.news-intelligence.v1"

    def __init__(
        self,
        *,
        responses: dict[str, str] | None = None,
        simulate_error: InferenceErrorCode | None = None,
        simulate_timeout: bool = False,
        simulate_malformed: bool = False,
    ) -> None:
        self._responses = responses or DEFAULT_FIXTURE_RESPONSES
        self._simulate_error = simulate_error
        self._simulate_timeout = simulate_timeout
        self._simulate_malformed = simulate_malformed

    def infer(
        self,
        packet: IntelligenceInputPacket,
        *,
        rendered_prompt: str,
        config: IntelligenceInferenceConfig,
    ) -> ProviderInferenceResponse:
        started = time.perf_counter()
        prompt_len = len(rendered_prompt)
        if self._simulate_timeout:
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=InferenceErrorCode.PROVIDER_TIMEOUT,
                error_message="simulated timeout",
                parsing_status=ParsingStatus.TIMEOUT,
                latency_ms=int((time.perf_counter() - started) * 1000),
                simulated=True,
            )
        if self._simulate_error:
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=self._simulate_error,
                error_message=f"simulated {self._simulate_error.value}",
                parsing_status=ParsingStatus.PROVIDER_ERROR,
                latency_ms=int((time.perf_counter() - started) * 1000),
                simulated=True,
            )
        if self._simulate_malformed:
            return ProviderInferenceResponse(
                raw_text="{not valid json",
                provider_id=self.provider_id,
                model_id=self.model_id,
                latency_ms=int((time.perf_counter() - started) * 1000),
                simulated=True,
            )
        raw = self._responses.get(packet.task_type.value, DEFAULT_FIXTURE_RESPONSES["NEWS_SENTIMENT"])
        return ProviderInferenceResponse(
            raw_text=raw,
            provider_id=self.provider_id,
            model_id=self.model_id,
            tokens_input=max(1, prompt_len // 4),
            tokens_output=max(1, len(raw) // 4),
            latency_ms=int((time.perf_counter() - started) * 1000),
            provider_request_id=f"fix-req-{packet.input_hash[:12]}",
            provider_response_id=f"fix-res-{uuid.uuid4().hex[:12]}",
            simulated=True,
        )


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _anthropic_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    prompt_tokens = usage.get("input_tokens")
    completion_tokens = usage.get("output_tokens")
    return (
        int(prompt_tokens) if prompt_tokens is not None else None,
        int(completion_tokens) if completion_tokens is not None else None,
    )


def _anthropic_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(part for part in parts if part).strip()


class AnthropicInferenceProvider:
    """Governed Claude path behind canonical intelligence boundary — no strategy coupling."""

    provider_id = "anthropic.messages"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        self.model_id = (
            model if model is not None else os.environ.get("ANTHROPIC_NEWS_MODEL", "")
        ).strip() or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()

    def infer(
        self,
        packet: IntelligenceInputPacket,
        *,
        rendered_prompt: str,
        config: IntelligenceInferenceConfig,
    ) -> ProviderInferenceResponse:
        started = time.perf_counter()
        if not self.api_key:
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=InferenceErrorCode.PROVIDER_AUTH_FAILURE,
                error_message="API_KEY_MISSING",
                parsing_status=ParsingStatus.PROVIDER_ERROR,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        body = {
            "model": self.model_id,
            "max_tokens": config.max_tokens,
            "system": "Return ONLY valid JSON matching the schema in the user prompt.",
            "messages": [{"role": "user", "content": rendered_prompt}],
        }
        request = Request(
            ANTHROPIC_API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError:
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=InferenceErrorCode.PROVIDER_TIMEOUT,
                error_message="request timed out",
                parsing_status=ParsingStatus.TIMEOUT,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except HTTPError as exc:
            code = InferenceErrorCode.PROVIDER_RATE_LIMIT if exc.code == 429 else InferenceErrorCode.PROVIDER_UNAVAILABLE
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=code,
                error_message=f"http {exc.code}",
                parsing_status=ParsingStatus.PROVIDER_ERROR,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except (URLError, json.JSONDecodeError, ValueError) as exc:
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED,
                error_message=str(exc),
                parsing_status=ParsingStatus.MALFORMED,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        if not isinstance(payload, dict):
            return ProviderInferenceResponse(
                raw_text="",
                provider_id=self.provider_id,
                model_id=self.model_id,
                error_code=InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED,
                error_message="response must be object",
                parsing_status=ParsingStatus.MALFORMED,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        text = _anthropic_text(payload)
        tokens_in, tokens_out = _anthropic_usage(payload)
        return ProviderInferenceResponse(
            raw_text=text,
            provider_id=self.provider_id,
            model_id=self.model_id,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            latency_ms=int((time.perf_counter() - started) * 1000),
            provider_request_id=str(payload.get("id", "")),
            provider_response_id=str(payload.get("id", "")),
        )


def render_prompt_for_packet(
    packet: IntelligenceInputPacket,
    *,
    prompt_registry: PromptRegistry | None = None,
) -> str:
    registry = prompt_registry or PromptRegistry()
    prompt: PromptDefinition = registry.get_by_id(packet.prompt_id)
    return registry.render(
        prompt,
        as_of=packet.as_of,
        instrument_ids=packet.instrument_ids,
        articles_json=articles_json_for_prompt(packet.articles),
    )


__all__ = [
    "AnthropicInferenceProvider",
    "DEFAULT_FIXTURE_RESPONSES",
    "FixtureInferenceProvider",
    "InferenceProvider",
    "ProviderInferenceResponse",
    "render_prompt_for_packet",
]
