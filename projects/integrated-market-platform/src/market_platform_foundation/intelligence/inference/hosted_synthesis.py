"""Paid OpenAI and Gemini paths for Screener news synthesis.

``HostedChatSynthesisProvider`` speaks the Chat Completions protocol that OpenAI serves
and Gemini mirrors on its OpenAI-compatible endpoint. The output is schema-typed
(``response_format`` json_schema from ``output_json_schema``, refs limited to the
packet's story ids) and ``parse_synthesis`` still validates every result.

Both vendors' current models reason before answering. ``reasoning_effort`` comes from
the model catalog (``synthesis_engines``); when it is not ``none`` the request carries
no temperature (the APIs reject it), and the output cap gets ``reasoning_headroom``
extra tokens so thinking cannot truncate the answer. ``BudgetedProvider`` reserves that
headroom too, so the daily budget and the UI cost preview state the true worst case.

No retries: a 429, timeout, or truncated answer is a state, never a loop that keeps billing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import URLError

from .anthropic_synthesis import Poster, _http_post
from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceInputPacket, ParsingStatus
from .errors import InferenceErrorCode
from .provider import ProviderInferenceResponse

REASONING_HEADROOM = 2_048


@dataclass(frozen=True, slots=True)
class HostedVendor:
    engine: str            # openai | gemini
    provider_id: str
    url: str
    reason_prefix: str     # stable reason-code prefix (OPENAI_, GEMINI_)


OPENAI = HostedVendor("openai", "openai.chat_completions", "https://api.openai.com/v1/chat/completions", "OPENAI_")
GEMINI = HostedVendor("gemini", "gemini.openai_compatible",
                      "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_")
VENDORS = {vendor.engine: vendor for vendor in (OPENAI, GEMINI)}


class HostedChatSynthesisProvider:
    """Chat Completions with a schema-typed response; no retries."""

    runtime = "PAID_API"

    def __init__(self, *, vendor: HostedVendor, api_key: str, model: str, reasoning_effort: str | None,
                 poster: Poster = _http_post) -> None:
        self._vendor = vendor
        self._api_key = (api_key or "").strip()
        self.provider_id = vendor.provider_id
        self.model_id = model
        self.reasoning_effort = reasoning_effort
        # Thinking tokens are billed output; they get their own room so they cannot crowd out the answer.
        self.reasoning_headroom = REASONING_HEADROOM if reasoning_effort not in (None, "none") else 0
        self._post = poster

    def _error(self, code: InferenceErrorCode, suffix: str, status: ParsingStatus, started: float,
               usage: tuple[int | None, int | None] = (None, None)) -> ProviderInferenceResponse:
        message = suffix if suffix == "API_KEY_MISSING" else f"{self._vendor.reason_prefix}{suffix}"
        return ProviderInferenceResponse(raw_text="", provider_id=self.provider_id, model_id=self.model_id, error_code=code,
                                         error_message=message, parsing_status=status, tokens_input=usage[0],
                                         tokens_output=usage[1], latency_ms=int((time.perf_counter() - started) * 1000))

    def request_body(self, packet: IntelligenceInputPacket, rendered_prompt: str,
                     config: IntelligenceInferenceConfig) -> dict:
        from .screener_synthesis import output_json_schema

        body: dict = {
            "model": self.model_id,
            "max_completion_tokens": int(config.max_tokens) + self.reasoning_headroom,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "screener_synthesis", "strict": True,
                "schema": output_json_schema([article.event_id for article in packet.articles])}},
            "messages": [{"role": "system", "content": "You write grounded news syntheses. Use only the supplied stories "
                                                       "and return JSON matching the schema."},
                         {"role": "user", "content": rendered_prompt}],
        }
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        if self.reasoning_effort in (None, "none"):
            body["temperature"] = 0
        return body

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        started = time.perf_counter()
        if not self._api_key:
            return self._error(InferenceErrorCode.PROVIDER_AUTH_FAILURE, "API_KEY_MISSING", ParsingStatus.PROVIDER_ERROR, started)
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}
        body = json.dumps(self.request_body(packet, rendered_prompt, config)).encode("utf-8")
        try:
            status, raw = self._post(self._vendor.url, body, headers, config.timeout_seconds)
        except TimeoutError:
            return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "TIMEOUT", ParsingStatus.TIMEOUT, started)
        except (URLError, OSError) as exc:
            if "timed out" in str(exc).lower():
                return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "TIMEOUT", ParsingStatus.TIMEOUT, started)
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, "UNREACHABLE", ParsingStatus.PROVIDER_ERROR, started)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if status != 200:
            if status in (401, 403):
                return self._error(InferenceErrorCode.PROVIDER_AUTH_FAILURE, "AUTH_FAILED", ParsingStatus.PROVIDER_ERROR, started)
            code = InferenceErrorCode.PROVIDER_RATE_LIMIT if status == 429 else InferenceErrorCode.PROVIDER_UNAVAILABLE
            # Status only: error bodies can echo request fragments.
            return self._error(code, f"HTTP_{status}", ParsingStatus.PROVIDER_ERROR, started)
        usage_block = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        usage = (usage_block.get("prompt_tokens"), usage_block.get("completion_tokens"))
        choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        if choice.get("finish_reason") == "length":
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "OUTPUT_TRUNCATED", ParsingStatus.MALFORMED,
                               started, usage)
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        if message.get("refusal"):
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "REFUSED", ParsingStatus.MALFORMED, started, usage)
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "RESPONSE_MALFORMED", ParsingStatus.MALFORMED,
                               started, usage)
        return ProviderInferenceResponse(raw_text=text.strip(), provider_id=self.provider_id, model_id=self.model_id,
                                         tokens_input=usage[0], tokens_output=usage[1],
                                         latency_ms=int((time.perf_counter() - started) * 1000),
                                         provider_request_id=str(payload.get("id") or ""),
                                         provider_response_id=str(payload.get("id") or ""))


__all__ = ["GEMINI", "OPENAI", "REASONING_HEADROOM", "VENDORS", "HostedChatSynthesisProvider", "HostedVendor"]
