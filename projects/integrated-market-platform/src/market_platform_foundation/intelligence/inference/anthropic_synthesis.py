"""Paid Claude path for Screener news synthesis, with a hard daily budget.

``AnthropicSynthesisProvider`` calls the Messages API with a forced tool whose input
schema is ``output_json_schema`` (refs limited to the packet's story ids), temperature
0, and a bounded ``max_tokens``. Forced tool use keeps the structure on contract, so a
paid call is rarely spent on output that validation then rejects. ``parse_synthesis``
still validates every result.

``BudgetedProvider`` wraps any provider with ``DailyBudget``, a persisted per-day
limit on requests and tokens. Before each call it reserves the worst case (the prompt
estimate plus ``max_tokens``). A call that could cross either limit is refused before
any network request, with a stable reason. The file lives in the external IMP cache
(``quota/anthropic-synthesis.json``), so a restart cannot reset the count.

No retries anywhere: a 429, overload, timeout, or truncated answer is a state the
operator sees, never a loop that keeps billing.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceInputPacket, ParsingStatus
from .errors import InferenceErrorCode
from .provider import ANTHROPIC_API_URL, ProviderInferenceResponse

PROVIDER_ID = "anthropic.messages"
# Sonnet: strong grounding and conflict handling at a moderate per-call cost. Override with IMP_SYNTHESIS_ANTHROPIC_MODEL.
DEFAULT_MODEL = "claude-sonnet-5-5"
MODEL_ENV = "IMP_SYNTHESIS_ANTHROPIC_MODEL"
DAILY_REQUESTS_ENV, DAILY_TOKENS_ENV = "IMP_SYNTHESIS_DAILY_REQUESTS", "IMP_SYNTHESIS_DAILY_TOKENS"
DEFAULT_DAILY_REQUESTS = 30
DEFAULT_DAILY_TOKENS = 200_000
BUDGET_RELATIVE = Path("quota") / "anthropic-synthesis.json"
TOOL_NAME = "record_synthesis"
API_VERSION = "2023-06-01"
_CHARS_PER_TOKEN = 3          # conservative: over-estimates tokens, so the reservation errs toward refusing

Poster = Callable[[str, bytes, dict[str, str], float], tuple[int, bytes]]


def _http_post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read() or b""


def estimate_tokens(text: str) -> int:
    return len(text or "") // _CHARS_PER_TOKEN + 1


class DailyBudget:
    """Persisted per-UTC-day request and token limits for a paid provider."""

    def __init__(self, path: Path | None, *, max_requests: int = DEFAULT_DAILY_REQUESTS,
                 max_tokens: int = DEFAULT_DAILY_TOKENS, clock: Callable[[], float] = time.time) -> None:
        self._path = path
        self.max_requests = max(0, int(max_requests))
        self.max_tokens = max(0, int(max_tokens))
        self._clock = clock
        self._lock = threading.Lock()
        self._state = self._load()

    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), tz=UTC).date().isoformat()

    def _load(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        if self._path is not None:
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                state = loaded if isinstance(loaded, dict) else {}
            except (OSError, ValueError):
                state = {}
        return state

    def _rolled(self) -> dict[str, Any]:
        today = self._today()
        if self._state.get("day") != today:
            self._state = {"day": today, "requests": 0, "input_tokens": 0, "output_tokens": 0, "reserved_tokens": 0}
        return self._state

    def _save(self) -> None:
        if self._path is None:
            return
        from ...local_state.external_cache import write_json_atomic

        try:
            write_json_atomic(self._path, {**self._state, "max_requests": self.max_requests, "max_tokens": self.max_tokens})
        except OSError:
            pass  # the in-memory count still enforces the limit for this process

    def _used(self, state: dict[str, Any]) -> int:
        return int(state.get("input_tokens", 0)) + int(state.get("output_tokens", 0)) + int(state.get("reserved_tokens", 0))

    def reserve(self, worst_case_tokens: int) -> str | None:
        """Count one request and hold its worst-case tokens, or return the reason it is refused."""

        with self._lock:
            state = self._rolled()
            if int(state.get("requests", 0)) >= self.max_requests:
                return "SYNTHESIS_DAILY_REQUEST_LIMIT"
            if self._used(state) + worst_case_tokens > self.max_tokens:
                return "SYNTHESIS_DAILY_TOKEN_LIMIT"
            state["requests"] = int(state.get("requests", 0)) + 1
            state["reserved_tokens"] = int(state.get("reserved_tokens", 0)) + worst_case_tokens
            self._save()
            return None

    def settle(self, worst_case_tokens: int, tokens_input: int | None, tokens_output: int | None) -> None:
        """Replace a reservation with reported usage; with no usage reported, the worst case stays charged."""

        with self._lock:
            state = self._rolled()
            state["reserved_tokens"] = max(0, int(state.get("reserved_tokens", 0)) - worst_case_tokens)
            if tokens_input is None and tokens_output is None:
                state["input_tokens"] = int(state.get("input_tokens", 0)) + worst_case_tokens
            else:
                state["input_tokens"] = int(state.get("input_tokens", 0)) + int(tokens_input or 0)
                state["output_tokens"] = int(state.get("output_tokens", 0)) + int(tokens_output or 0)
            self._save()

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = self._rolled()
            return {"day": state["day"], "requests": int(state.get("requests", 0)), "max_requests": self.max_requests,
                    "tokens": self._used(state), "max_tokens": self.max_tokens}


class AnthropicSynthesisProvider:
    """Claude Messages API with a forced, schema-typed tool; no retries."""

    provider_id = PROVIDER_ID
    runtime = "PAID_API"

    def __init__(self, *, api_key: str, model: str | None = None, poster: Poster = _http_post) -> None:
        self._api_key = (api_key or "").strip()
        self.model_id = (model or "").strip() or DEFAULT_MODEL
        self._post = poster

    def _error(self, code: InferenceErrorCode, message: str, status: ParsingStatus, started: float,
               usage: tuple[int | None, int | None] = (None, None)) -> ProviderInferenceResponse:
        return ProviderInferenceResponse(raw_text="", provider_id=self.provider_id, model_id=self.model_id, error_code=code,
                                         error_message=message, parsing_status=status, tokens_input=usage[0],
                                         tokens_output=usage[1], latency_ms=int((time.perf_counter() - started) * 1000))

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        from .screener_synthesis import output_json_schema

        started = time.perf_counter()
        if not self._api_key:
            return self._error(InferenceErrorCode.PROVIDER_AUTH_FAILURE, "API_KEY_MISSING", ParsingStatus.PROVIDER_ERROR, started)
        body = {
            "model": self.model_id, "max_tokens": config.max_tokens, "temperature": 0,
            "system": "You write grounded news syntheses. Use only the supplied stories and record the result with the tool.",
            "messages": [{"role": "user", "content": rendered_prompt}],
            "tools": [{"name": TOOL_NAME, "description": "Record the grounded synthesis of the supplied stories.",
                       "input_schema": output_json_schema([article.event_id for article in packet.articles])}],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
        }
        headers = {"Content-Type": "application/json", "x-api-key": self._api_key, "anthropic-version": API_VERSION}
        try:
            status, raw = self._post(ANTHROPIC_API_URL, json.dumps(body).encode("utf-8"), headers, config.timeout_seconds)
        except TimeoutError:
            return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "ANTHROPIC_TIMEOUT", ParsingStatus.TIMEOUT, started)
        except (URLError, OSError) as exc:
            if "timed out" in str(exc).lower():
                return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "ANTHROPIC_TIMEOUT", ParsingStatus.TIMEOUT, started)
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, "ANTHROPIC_UNREACHABLE", ParsingStatus.PROVIDER_ERROR,
                               started)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if status != 200:
            error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
            kind = str(error.get("type") or "").upper() or f"HTTP_{status}"
            if status in (401, 403):
                return self._error(InferenceErrorCode.PROVIDER_AUTH_FAILURE, "ANTHROPIC_AUTH_FAILED",
                                   ParsingStatus.PROVIDER_ERROR, started)
            code = InferenceErrorCode.PROVIDER_RATE_LIMIT if status == 429 else InferenceErrorCode.PROVIDER_UNAVAILABLE
            # The error type only (e.g. INVALID_REQUEST_ERROR for a bad model id or an empty credit balance).
            return self._error(code, f"ANTHROPIC_{kind}", ParsingStatus.PROVIDER_ERROR, started)
        usage_block = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        usage = (usage_block.get("input_tokens"), usage_block.get("output_tokens"))
        if payload.get("stop_reason") == "max_tokens":
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "ANTHROPIC_OUTPUT_TRUNCATED",
                               ParsingStatus.MALFORMED, started, usage)
        blocks = payload.get("content") if isinstance(payload.get("content"), list) else []
        tool_input = next((block.get("input") for block in blocks if isinstance(block, dict)
                           and block.get("type") == "tool_use" and block.get("name") == TOOL_NAME), None)
        if not isinstance(tool_input, dict):
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "ANTHROPIC_RESPONSE_MALFORMED",
                               ParsingStatus.MALFORMED, started, usage)
        return ProviderInferenceResponse(raw_text=json.dumps(tool_input, ensure_ascii=False), provider_id=self.provider_id,
                                         model_id=self.model_id, tokens_input=usage[0], tokens_output=usage[1],
                                         latency_ms=int((time.perf_counter() - started) * 1000),
                                         provider_request_id=str(payload.get("id") or ""),
                                         provider_response_id=str(payload.get("id") or ""))


class BudgetedProvider:
    """Any provider behind a ``DailyBudget``: over-limit calls are refused before a request is sent."""

    def __init__(self, provider: Any, budget: DailyBudget) -> None:
        self._provider = provider
        self.budget = budget
        self.provider_id = getattr(provider, "provider_id", "")
        self.model_id = getattr(provider, "model_id", "")
        self.runtime = getattr(provider, "runtime", "PAID_API")

    def budget_status(self) -> dict[str, Any]:
        return self.budget.status()

    def worst_case_tokens(self, rendered_prompt: str, config: IntelligenceInferenceConfig) -> int:
        """What a call reserves against the daily budget; the UI cost preview states this same number."""

        return estimate_tokens(rendered_prompt) + 1_500 + int(config.max_tokens)   # + tool schema and system text

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        worst_case = self.worst_case_tokens(rendered_prompt, config)
        reason = self.budget.reserve(worst_case)
        if reason is not None:
            return ProviderInferenceResponse(raw_text="", provider_id=self.provider_id, model_id=self.model_id,
                                             error_code=InferenceErrorCode.PROVIDER_RATE_LIMIT, error_message=reason,
                                             parsing_status=ParsingStatus.PROVIDER_ERROR, latency_ms=0)
        response = None
        try:
            response = self._provider.infer(packet, rendered_prompt=rendered_prompt, config=config)
            return response
        finally:
            if response is None or response.parsing_status == ParsingStatus.TIMEOUT:
                # Unknown outcome: the request may have been billed, so the worst case stays charged.
                self.budget.settle(worst_case, None, None)
            elif response.error_code is not None and response.tokens_input is None and response.tokens_output is None:
                # Refused before generation (auth, 4xx, unreachable): nothing billed.
                self.budget.settle(worst_case, 0, 0)
            else:
                self.budget.settle(worst_case, response.tokens_input, response.tokens_output)


def _int_setting(value: Callable[[str], str | None], name: str, default: int) -> int:
    try:
        return max(0, int((value(name) or "").strip() or default))
    except ValueError:
        return default


def build_paid_provider(value: Callable[[str], str | None], *, cache_dir: Path | None) -> BudgetedProvider:
    """The production paid provider: key and limits from process env / private provider file, budget in the cache."""

    budget = DailyBudget(cache_dir / BUDGET_RELATIVE if cache_dir is not None else None,
                         max_requests=_int_setting(value, DAILY_REQUESTS_ENV, DEFAULT_DAILY_REQUESTS),
                         max_tokens=_int_setting(value, DAILY_TOKENS_ENV, DEFAULT_DAILY_TOKENS))
    provider = AnthropicSynthesisProvider(api_key=value("ANTHROPIC_API_KEY") or "", model=value(MODEL_ENV))
    return BudgetedProvider(provider, budget)


__all__ = ["AnthropicSynthesisProvider", "BUDGET_RELATIVE", "BudgetedProvider", "DAILY_REQUESTS_ENV", "DAILY_TOKENS_ENV",
           "DEFAULT_DAILY_REQUESTS", "DEFAULT_DAILY_TOKENS", "DEFAULT_MODEL", "DailyBudget", "MODEL_ENV", "build_paid_provider",
           "estimate_tokens"]
