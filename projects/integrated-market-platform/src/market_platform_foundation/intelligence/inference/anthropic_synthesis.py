"""Paid Claude path for Screener news synthesis, with a hard daily budget.

``AnthropicSynthesisProvider`` calls the Messages API with one schema-typed tool whose
input schema is the task's output schema, and a bounded ``max_tokens``. The request body
is built per model by ``anthropic_models``: a model that accepts them gets temperature 0
and a forced tool call; a model that rejects them gets neither, and a reply without the
tool call is an error. A model with no known request shape is refused before any network
call (``MODEL_REQUEST_CONTRACT_UNSUPPORTED``); the provider never substitutes another
model. The application parser still validates every result.

``preflight`` sends the same request to the token-count endpoint, which bills nothing and
generates nothing: it reports the input tokens and whether the provider accepts the body.

``BudgetedProvider`` wraps any provider with ``DailyBudget``, a persisted per-day
limit on requests and tokens. Before each call it reserves the worst case (the prompt
estimate plus ``max_tokens``). A call that could cross either limit is refused before
any network request, with a stable reason. The file lives in the external IMP cache
(``quota/anthropic-synthesis.json``, shared by every paid engine), so a restart cannot reset the count.

A multi-call run (the full-universe AI Screener) first places a ``hold`` for its whole plan. Every other
caller sees the held requests and tokens as used; the run's own calls draw from the hold and can never
exceed it; what the run did not use is released when it ends. A local model has no budget at all.

No retries anywhere: a 429, overload, timeout, or truncated answer is a state the
operator sees, never a loop that keeps billing.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .anthropic_models import (
    CLAUDE_MODELS, TOOL_NAME, UNSUPPORTED, ModelRequestContractUnsupported, build_request, contract_status,
    count_request, output_tokens,
)
from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceInputPacket, IntelligenceTaskType, ParsingStatus
from .errors import InferenceErrorCode
from .provider import ANTHROPIC_API_URL, ProviderInferenceResponse
from .run_progress import report_stage

PROVIDER_ID = "anthropic.messages"
# Used only when neither the operator's saved choice nor IMP_SYNTHESIS_ANTHROPIC_MODEL names a model.
DEFAULT_MODEL = "claude-sonnet-5-5"
MODEL_ENV = "IMP_SYNTHESIS_ANTHROPIC_MODEL"
DAILY_REQUESTS_ENV, DAILY_TOKENS_ENV = "IMP_SYNTHESIS_DAILY_REQUESTS", "IMP_SYNTHESIS_DAILY_TOKENS"
DEFAULT_DAILY_REQUESTS = 30
DEFAULT_DAILY_TOKENS = 200_000
BUDGET_RELATIVE = Path("quota") / "anthropic-synthesis.json"
COUNT_TOKENS_URL = ANTHROPIC_API_URL + "/count_tokens"
API_VERSION = "2023-06-01"
# UTF-8 bytes per input token, set BELOW what the provider counted on the controlled 50-candidate packet
# (2026-10-07 count_tokens: 2.66 for Haiku 4.5, 1.80 for Sonnet 5.5 and Opus 5.5), so an estimate is never under
# the bill. A model with no measurement takes the lowest ratio. The former three-characters rule under-counted
# every Claude model by 12% to 67%.
BYTES_PER_TOKEN = {"claude-haiku-4-5-20251001": 2.2, "claude-sonnet-5-5": 1.5, "claude-opus-5-5": 1.5}
DEFAULT_BYTES_PER_TOKEN = 1.5
# A hold nobody has drawn from for this long belongs to a run that is gone (a crash, or an engine switched under
# it): it lapses instead of locking shared budget until the UTC day ends. A live run draws at least once per
# request, and a request times out in at most 300 seconds.
HOLD_IDLE_SECONDS = 900
# The run hold a model call on this thread draws from: (run id, tokens planned for this call).
_HOLD: ContextVar[tuple[str, int] | None] = ContextVar("imp_synthesis_budget_hold", default=None)
_BUDGET_LOCKS: dict[str, threading.RLock] = {}
_BUDGET_LOCKS_LOCK = threading.Lock()

Poster = Callable[[str, bytes, dict[str, str], float], tuple[int, bytes]]


def _http_post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read() or b""


def rejection_reason(status: int, payload: dict[str, Any]) -> str:
    """A stable reason for a refused request. The provider's message is read for its class and never kept."""

    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    kind = str(error.get("type") or "").upper() or f"HTTP_{status}"
    if status == 400:
        message = str(error.get("message") or "").lower()
        for reason, markers in (
            ("ANTHROPIC_CONTEXT_EXCEEDED", ("prompt is too long", "context window", "context limit")),
            ("ANTHROPIC_GRAMMAR_TOO_LARGE", ("grammar", "too complex", "compil")),
            ("ANTHROPIC_TOOL_CHOICE_UNSUPPORTED", ("tool_choice",)),
            ("ANTHROPIC_PARAMETER_UNSUPPORTED", ("temperature", "top_p", "top_k", "thinking", "max_tokens")),
            ("ANTHROPIC_SCHEMA_REJECTED", ("schema", "strict", "additionalproperties", "const", "enum")),
        ):
            if any(marker in message for marker in markers):
                return reason
    return f"ANTHROPIC_{kind}"


def estimate_tokens(text: str, model_id: str | None = None) -> int:
    """A conservative input-token bound for this model: never below a provider count measured so far."""

    ratio = BYTES_PER_TOKEN.get(model_id or "", DEFAULT_BYTES_PER_TOKEN)
    return int(len((text or "").encode("utf-8")) / ratio) + 1


@contextmanager
def drawing_from_hold(run_id: str, planned_tokens: int = 0) -> Iterator[None]:
    """Model calls made on this thread inside the block draw from ``run_id``'s hold instead of the open budget."""

    token = _HOLD.set((run_id, max(0, int(planned_tokens))))
    try:
        yield
    finally:
        _HOLD.reset(token)


class DailyBudget:
    """Persisted per-UTC-day request and token limits for a paid provider."""

    def __init__(self, path: Path | None, *, max_requests: int = DEFAULT_DAILY_REQUESTS,
                 max_tokens: int = DEFAULT_DAILY_TOKENS, clock: Callable[[], float] = time.time) -> None:
        self._path = path
        self.max_requests = max(0, int(max_requests))
        self.max_tokens = max(0, int(max_tokens))
        self._clock = clock
        # Engine switches construct new instances for the same account budget. Serialize their
        # read/modify/write operations and reload under that lock before using persisted state.
        with _BUDGET_LOCKS_LOCK:
            self._lock = (_BUDGET_LOCKS.setdefault(str(path.resolve()), threading.RLock())
                          if path is not None else threading.RLock())
        with self._locked():
            self._state = self._load()

    @contextmanager
    def _locked(self):
        """Serialize account mutations across processes as well as engine instances."""
        with self._lock:
            connection = None
            try:
                if self._path is not None:
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    connection = sqlite3.connect(str(self._path) + ".lock.sqlite", timeout=10)
                    connection.execute("BEGIN IMMEDIATE")
                yield
            except sqlite3.Error as exc:
                raise ValueError("SYNTHESIS_BUDGET_LOCK_UNAVAILABLE") from exc
            finally:
                if connection is not None:
                    connection.rollback()
                    connection.close()

    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), tz=UTC).date().isoformat()

    def _load(self) -> dict[str, Any]:
        state: dict[str, Any] = {}
        if self._path is not None:
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                if not loaded:
                    raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                if loaded:
                    if not isinstance(loaded.get("day"),str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",loaded["day"]):
                        raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                    datetime.fromisoformat(loaded["day"])
                    for key in ("requests","input_tokens","output_tokens","reserved_tokens"):
                        if type(loaded.get(key)) is not int or loaded[key] < 0:
                            raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                    if not isinstance(loaded.get("holds",{}),dict):
                        raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                    for item in loaded.get("holds",{}).values():
                        if not isinstance(item,dict) or any(type(item.get(k)) is not int or item[k] < 0 for k in ("requests","tokens")):
                            raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                        if not isinstance(item.get("touched"),(int,float)) or not math.isfinite(item["touched"]):
                            raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE")
                state = loaded
            except FileNotFoundError:
                state = {}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                # Unknown persisted usage cannot become a fresh allowance. Preserve the file
                # for repair and stop before a reservation can authorize any generation.
                raise ValueError("SYNTHESIS_BUDGET_STATE_UNREADABLE") from exc
        return state

    def _rolled(self) -> dict[str, Any]:
        if self._path is not None:
            self._state = self._load()
        today = self._today()
        if self._state.get("day") != today:
            # A hold belongs to the day it was placed on: a run that crosses midnight finds none and stops.
            self._state = {"day": today, "requests": 0, "input_tokens": 0, "output_tokens": 0, "reserved_tokens": 0,
                           "holds": {}}
        return self._state

    def _holds(self, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        holds = state.get("holds")
        if not isinstance(holds, dict):
            holds = state["holds"] = {}
        now = self._clock()
        for run_id in [key for key, item in holds.items() if now - float(item.get("touched", now)) > HOLD_IDLE_SECONDS]:
            del holds[run_id]
        return holds

    def _held(self, state: dict[str, Any], key: str) -> int:
        return sum(int(item.get(key, 0)) for item in self._holds(state).values())

    def _save(self) -> None:
        if self._path is None:
            return
        from ...local_state.external_cache import write_json_atomic

        # A reservation that cannot be persisted must not permit a paid call. A failed
        # settlement leaves the previously persisted worst-case reservation charged.
        write_json_atomic(self._path, {**self._state, "max_requests": self.max_requests, "max_tokens": self.max_tokens})

    def _used(self, state: dict[str, Any]) -> int:
        return (int(state.get("input_tokens", 0)) + int(state.get("output_tokens", 0))
                + int(state.get("reserved_tokens", 0)) + self._held(state, "tokens"))

    def _requests(self, state: dict[str, Any]) -> int:
        return int(state.get("requests", 0)) + self._held(state, "requests")

    def reserve(self, worst_case_tokens: int, *, hold: str | None = None) -> str | None:
        """Count one request and hold its worst-case tokens, or return the reason it is refused.

        With ``hold``, the request and tokens come out of that run's hold and nothing else: a call the hold cannot
        cover is refused even when the open budget could."""

        with self._locked():
            state = self._rolled()
            if state.get("usage_overrun"):
                return "SYNTHESIS_USAGE_EXCEEDED_RESERVATION"
            if self._used(state) > self.max_tokens:
                return "SYNTHESIS_DAILY_TOKEN_LIMIT"
            if hold is not None:
                held = self._holds(state).get(hold)
                if held is None:
                    return "SYNTHESIS_RUN_HOLD_MISSING"
                if int(held["requests"]) < 1 or int(held["tokens"]) < worst_case_tokens:
                    return "SYNTHESIS_RUN_HOLD_EXHAUSTED"
                held["requests"] = int(held["requests"]) - 1
                held["tokens"] = int(held["tokens"]) - worst_case_tokens
                held["touched"] = self._clock()
            else:
                if self._requests(state) >= self.max_requests:
                    return "SYNTHESIS_DAILY_REQUEST_LIMIT"
                if self._used(state) + worst_case_tokens > self.max_tokens:
                    return "SYNTHESIS_DAILY_TOKEN_LIMIT"
            state["requests"] = int(state.get("requests", 0)) + 1
            state["reserved_tokens"] = int(state.get("reserved_tokens", 0)) + worst_case_tokens
            self._save()
            return None

    def hold(self, run_id: str, *, requests: int, tokens: int) -> dict[str, Any]:
        """Set aside a whole run's requests and tokens, or state exactly why they do not fit. Spends nothing."""

        requests, tokens = max(0, int(requests)), max(0, int(tokens))
        with self._locked():
            state = self._rolled()
            available_requests = max(0, self.max_requests - self._requests(state))
            available_tokens = max(0, self.max_tokens - self._used(state))
            reason = ("SYNTHESIS_USAGE_EXCEEDED_RESERVATION" if state.get("usage_overrun")
                      else "SYNTHESIS_RUN_HOLD_EXISTS" if run_id in self._holds(state)
                      else "SYNTHESIS_DAILY_REQUEST_LIMIT" if requests > available_requests
                      else "SYNTHESIS_DAILY_TOKEN_LIMIT" if tokens > available_tokens else None)
            if reason is None:
                self._holds(state)[run_id] = {"requests": requests, "tokens": tokens, "touched": self._clock()}
                self._save()
            return {"held": reason is None, "reason": reason, "required_requests": requests, "required_tokens": tokens,
                    "available_requests": available_requests, "available_tokens": available_tokens}

    def release(self, run_id: str) -> dict[str, int]:
        """Return what a run's hold did not use to the open budget. Reservations and usage already made stay."""

        with self._locked():
            state = self._rolled()
            held = self._holds(state).pop(run_id, None)
            if held is not None:
                self._save()
            return {"requests": int((held or {}).get("requests", 0)), "tokens": int((held or {}).get("tokens", 0))}

    def held(self, run_id: str) -> dict[str, int] | None:
        with self._locked():
            held = self._holds(self._rolled()).get(run_id)
            return {"requests": int(held["requests"]), "tokens": int(held["tokens"])} if held is not None else None

    def settle(self, worst_case_tokens: int, tokens_input: int | None, tokens_output: int | None) -> None:
        """Replace a reservation with reported usage; with no usage reported, the worst case stays charged."""

        with self._locked():
            state = self._rolled()
            if any(value is not None and (type(value) is not int or value < 0) for value in (tokens_input,tokens_output)):
                tokens_input = tokens_output = None
            state["reserved_tokens"] = max(0, int(state.get("reserved_tokens", 0)) - worst_case_tokens)
            if tokens_input is None or tokens_output is None:
                charged = max(worst_case_tokens,int(tokens_input or 0)+int(tokens_output or 0))
                state["input_tokens"] = int(state.get("input_tokens", 0)) + charged
                if charged > worst_case_tokens:
                    state["usage_overrun"] = True
            else:
                state["input_tokens"] = int(state.get("input_tokens", 0)) + int(tokens_input or 0)
                state["output_tokens"] = int(state.get("output_tokens", 0)) + int(tokens_output or 0)
                if int(tokens_input or 0) + int(tokens_output or 0) > worst_case_tokens:
                    state["usage_overrun"] = True
            self._save()

    def status(self) -> dict[str, Any]:
        with self._locked():
            state = self._rolled()
            # Held requests and tokens count as used: nothing else may spend what a run in progress set aside.
            return {"day": state["day"], "requests": self._requests(state), "max_requests": self.max_requests,
                    "tokens": self._used(state), "max_tokens": self.max_tokens,
                    "usage_overrun":bool(state.get("usage_overrun")),
                    "held_requests": self._held(state, "requests"), "held_tokens": self._held(state, "tokens")}


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

    @property
    def reasoning_headroom(self) -> int:
        """Output tokens added for a model that reasons before answering; the budget reserves them too."""

        return output_tokens(self.model_id, 0)

    def request_contract(self, task_type: IntelligenceTaskType) -> dict[str, Any]:
        """Whether the selected model can run this task. Calls nothing."""

        return contract_status(self.model_id, task_type)

    def request_body(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
                     config: IntelligenceInferenceConfig) -> dict[str, Any]:
        """The exact generation body for this model, or ``ModelRequestContractUnsupported``."""

        from .schema_dispatch import schema_for_packet

        return build_request(self.model_id, task_type=packet.task_type, input_schema=schema_for_packet(packet),
                             rendered_prompt=rendered_prompt, max_tokens=config.max_tokens)

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-api-key": self._api_key, "anthropic-version": API_VERSION}

    def preflight(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
                  config: IntelligenceInferenceConfig) -> dict[str, Any]:
        """Count the generation request's input tokens. Bills nothing, generates nothing, reserves no budget.

        ``accepted`` is the provider's verdict on the body (model, parameters, tool schema). It does not show that
        a strict schema's grammar compiles: only a generation request compiles it."""

        result: dict[str, Any] = {"model_id": self.model_id, "accepted": False, "input_tokens": None,
                                  "context_window": None, "context_fit": None, "reason": None}
        if not self._api_key:
            return {**result, "reason": "API_KEY_MISSING"}
        try:
            body = self.request_body(packet, rendered_prompt=rendered_prompt, config=config)
        except ModelRequestContractUnsupported as exc:
            return {**result, "reason": UNSUPPORTED, **exc.details()}
        capabilities = CLAUDE_MODELS[self.model_id]
        result["context_window"] = capabilities.context_window
        if not capabilities.count_tokens:
            return {**result, "reason": "COUNT_TOKENS_UNSUPPORTED"}
        try:
            status, raw = self._post(COUNT_TOKENS_URL, json.dumps(count_request(body)).encode("utf-8"), self._headers(),
                                     config.timeout_seconds)
        except TimeoutError:
            return {**result, "reason": "ANTHROPIC_TIMEOUT"}
        except (URLError, OSError) as exc:
            return {**result, "reason": "ANTHROPIC_TIMEOUT" if "timed out" in str(exc).lower() else "ANTHROPIC_UNREACHABLE"}
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if status != 200:
            return {**result, "reason": "ANTHROPIC_AUTH_FAILED" if status in (401, 403) else rejection_reason(status, payload)}
        tokens = payload.get("input_tokens")
        if type(tokens) is not int:
            return {**result, "reason": "ANTHROPIC_RESPONSE_MALFORMED"}
        fits = tokens + body["max_tokens"] <= capabilities.context_window
        return {**result, "accepted": True, "input_tokens": tokens, "context_fit": fits,
                "reason": None if fits else "ANTHROPIC_CONTEXT_EXCEEDED"}

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        started = time.perf_counter()
        if not self._api_key:
            return self._error(InferenceErrorCode.PROVIDER_AUTH_FAILURE, "API_KEY_MISSING", ParsingStatus.PROVIDER_ERROR, started)
        try:
            body = self.request_body(packet, rendered_prompt=rendered_prompt, config=config)
        except ModelRequestContractUnsupported:
            # Refused here, before any request: the selected model stays on the receipt and nothing replaces it.
            return self._error(InferenceErrorCode.INFERENCE_UNAVAILABLE, UNSUPPORTED, ParsingStatus.PROVIDER_ERROR, started)
        try:
            status, raw = self._post(ANTHROPIC_API_URL, json.dumps(body).encode("utf-8"), self._headers(), config.timeout_seconds)
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
            if status in (401, 403):
                return self._error(InferenceErrorCode.PROVIDER_AUTH_FAILURE, "ANTHROPIC_AUTH_FAILED",
                                   ParsingStatus.PROVIDER_ERROR, started)
            code = InferenceErrorCode.PROVIDER_RATE_LIMIT if status == 429 else InferenceErrorCode.PROVIDER_UNAVAILABLE
            # A stable class only (e.g. INVALID_REQUEST_ERROR for a bad model id or an empty credit balance).
            return self._error(code, rejection_reason(status, payload), ParsingStatus.PROVIDER_ERROR, started)
        usage_block = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        usage = (usage_block.get("input_tokens"), usage_block.get("output_tokens"))
        if payload.get("stop_reason") == "max_tokens":
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "ANTHROPIC_OUTPUT_TRUNCATED",
                               ParsingStatus.MALFORMED, started, usage)
        if payload.get("stop_reason") == "refusal":
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, "ANTHROPIC_REFUSAL", ParsingStatus.PROVIDER_ERROR,
                               started, usage)
        blocks = payload.get("content") if isinstance(payload.get("content"), list) else []
        calls = [block.get("input") for block in blocks if isinstance(block, dict)
                 and block.get("type") == "tool_use" and block.get("name") == TOOL_NAME]
        if not calls:
            # Text in place of the tool call is never parsed: the structured contract is the only accepted answer.
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "ANTHROPIC_TOOL_NOT_CALLED",
                               ParsingStatus.MALFORMED, started, usage)
        tool_input = calls[0]
        if len(calls) != 1 or not isinstance(tool_input, dict):
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "ANTHROPIC_RESPONSE_MALFORMED",
                               ParsingStatus.MALFORMED, started, usage)
        return ProviderInferenceResponse(raw_text=json.dumps(tool_input, ensure_ascii=False), provider_id=self.provider_id,
                                         model_id=self.model_id, tokens_input=usage[0], tokens_output=usage[1],
                                         latency_ms=int((time.perf_counter() - started) * 1000),
                                         provider_request_id=str(payload.get("id") or ""),
                                         provider_response_id=str(payload.get("id") or ""))


class BudgetedProvider:
    """Any provider behind a ``DailyBudget``: over-limit calls are refused before a request is sent."""

    reports_stages = True  # announces BUDGET_RESERVED, then MODEL_CALL, only once the reservation is held

    def __init__(self, provider: Any, budget: DailyBudget) -> None:
        self._provider = provider
        self.budget = budget
        self.provider_id = getattr(provider, "provider_id", "")
        self.model_id = getattr(provider, "model_id", "")
        self.runtime = getattr(provider, "runtime", "PAID_API")

    def budget_status(self) -> dict[str, Any]:
        return self.budget.status()

    @property
    def reasoning_headroom(self) -> int:
        return int(getattr(self._provider,"reasoning_headroom",0) or 0)

    def request_accounting(self, packet, *, rendered_prompt, config):
        builder = getattr(self._provider,"request_body",None)
        prompt_tokens = estimate_tokens(rendered_prompt,self.model_id)
        request = builder(packet,rendered_prompt=rendered_prompt,config=config) if callable(builder) else None
        if isinstance(request, dict):
            body = count_request(request)
            text = json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            inputs = estimate_tokens(text,self.model_id)
        else:
            inputs = prompt_tokens + 1500
        output = int(config.max_tokens) + self.reasoning_headroom
        return {"basis":"MODEL_CALIBRATED_UTF8_ESTIMATE", "input_tokens":inputs,
                "system_and_schema_tokens":max(0,inputs-prompt_tokens), "output_tokens":int(config.max_tokens),
                "reasoning_tokens":self.reasoning_headroom, "total_tokens":inputs+output}

    def request_contract(self, task_type: IntelligenceTaskType) -> dict[str, Any] | None:
        """The wrapped provider's verdict on whether its model can run this task; None where it states none."""

        check = getattr(self._provider, "request_contract", None)
        return check(task_type) if callable(check) else None

    def preflight(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
                  config: IntelligenceInferenceConfig) -> dict[str, Any] | None:
        """The wrapped provider's free token count for this request. Reserves and spends nothing."""

        check = getattr(self._provider, "preflight", None)
        return check(packet, rendered_prompt=rendered_prompt, config=config) if callable(check) else None

    def worst_case_tokens(self, rendered_prompt: str, config: IntelligenceInferenceConfig) -> int:
        """What a call reserves against the daily budget; the UI cost preview states this same number."""

        # + tool schema and system text; + a reasoning model's thinking room (hosted providers)
        headroom = int(getattr(self._provider, "reasoning_headroom", 0) or 0)
        return estimate_tokens(rendered_prompt, self.model_id) + 1_500 + int(config.max_tokens) + headroom

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        try:
            accounting = self.request_accounting(packet,rendered_prompt=rendered_prompt,config=config)
            worst_case = max(self.worst_case_tokens(rendered_prompt, config),accounting["total_tokens"])
        except ModelRequestContractUnsupported:
            return ProviderInferenceResponse(raw_text="",provider_id=self.provider_id,model_id=self.model_id,
                error_code=InferenceErrorCode.INFERENCE_UNAVAILABLE,error_message=UNSUPPORTED,parsing_status=ParsingStatus.PROVIDER_ERROR)
        if packet.task_type == IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION:
            # Count the freshly acquired request, including a changed or global-comparison packet,
            # before any paid generation. A byte ratio is an estimate, not a tokenizer proof.
            counted = self.preflight(packet,rendered_prompt=rendered_prompt,config=config)
            if isinstance(counted, dict):
                exact = counted.get("input_tokens")
                if counted.get("accepted") and type(exact) is int and exact >= 0:
                    worst_case = max(worst_case,exact+accounting["output_tokens"]+accounting["reasoning_tokens"])
                elif counted.get("reason") not in {"COUNT_TOKENS_UNSUPPORTED","ANTHROPIC_TIMEOUT","ANTHROPIC_UNREACHABLE"}:
                    return ProviderInferenceResponse(raw_text="",provider_id=self.provider_id,model_id=self.model_id,
                        error_code=InferenceErrorCode.INFERENCE_UNAVAILABLE,
                        error_message="SYNTHESIS_PREFLIGHT_REJECTED:"+str(counted.get("reason")),
                        parsing_status=ParsingStatus.PROVIDER_ERROR)
                if counted.get("context_fit") is False:
                    return ProviderInferenceResponse(raw_text="",provider_id=self.provider_id,model_id=self.model_id,
                        error_code=InferenceErrorCode.INFERENCE_UNAVAILABLE,error_message="SYNTHESIS_CONTEXT_EXCEEDED",
                        parsing_status=ParsingStatus.PROVIDER_ERROR)
        held = _HOLD.get()
        if held is not None:
            # Never reserve less than the run planned for this call (a plan calibrated by a provider count).
            worst_case = max(worst_case, held[1])
        reason = self.budget.reserve(worst_case, hold=held[0] if held is not None else None)
        if reason is not None:
            return ProviderInferenceResponse(raw_text="", provider_id=self.provider_id, model_id=self.model_id,
                                             error_code=InferenceErrorCode.PROVIDER_RATE_LIMIT, error_message=reason,
                                             parsing_status=ParsingStatus.PROVIDER_ERROR, latency_ms=0)
        report_stage("BUDGET_RESERVED", reserved_tokens=worst_case)
        response = None
        try:
            report_stage("MODEL_CALL")
            response = self._provider.infer(packet, rendered_prompt=rendered_prompt, config=config)
            return response
        finally:
            if response is None or response.parsing_status == ParsingStatus.TIMEOUT:
                # Unknown outcome: the request may have been billed, so the worst case stays charged.
                self.budget.settle(worst_case, None, None)
            elif response.error_code is not None and response.tokens_input is None and response.tokens_output is None:
                # Only a known pre-generation refusal establishes zero usage. Unknown transport/server
                # outcomes retain the reservation. No automatic retry is made.
                refused = response.error_message in {"API_KEY_MISSING",UNSUPPORTED,"ANTHROPIC_AUTH_FAILED",
                    "ANTHROPIC_RATE_LIMIT_ERROR","ANTHROPIC_OVERLOADED_ERROR","ANTHROPIC_INVALID_REQUEST_ERROR",
                    "ANTHROPIC_SCHEMA_REJECTED","ANTHROPIC_GRAMMAR_TOO_LARGE","ANTHROPIC_CONTEXT_EXCEEDED",
                    "ANTHROPIC_TOOL_CHOICE_UNSUPPORTED","ANTHROPIC_PARAMETER_UNSUPPORTED"}
                self.budget.settle(worst_case,0 if refused else None,0 if refused else None)
            else:
                self.budget.settle(worst_case, response.tokens_input, response.tokens_output)


def _int_setting(value: Callable[[str], str | None], name: str, default: int) -> int:
    try:
        return max(0, int((value(name) or "").strip() or default))
    except ValueError:
        return default


def build_paid_provider(value: Callable[[str], str | None], *, cache_dir: Path | None, provider: Any = None,
                        model: str | None = None) -> BudgetedProvider:
    """A production paid provider behind the daily budget: limits from process env / private provider file.

    Every paid engine (Anthropic, OpenAI, Gemini) shares one budget file, so switching vendors never resets or
    multiplies the cap. ``provider`` defaults to Claude with the key from ``value``."""

    budget = DailyBudget(cache_dir / BUDGET_RELATIVE if cache_dir is not None else None,
                         max_requests=_int_setting(value, DAILY_REQUESTS_ENV, DEFAULT_DAILY_REQUESTS),
                         max_tokens=_int_setting(value, DAILY_TOKENS_ENV, DEFAULT_DAILY_TOKENS))
    if provider is None:
        provider = AnthropicSynthesisProvider(api_key=value("ANTHROPIC_API_KEY") or "", model=model or value(MODEL_ENV))
    wrapped = BudgetedProvider(provider, budget)
    try:
        wrapped.price_schedule = json.loads(value("IMP_SYNTHESIS_PRICE_SCHEDULE") or "null")
    except (TypeError,ValueError):
        wrapped.price_schedule = None
    return wrapped


__all__ = ["AnthropicSynthesisProvider", "BUDGET_RELATIVE", "BYTES_PER_TOKEN", "BudgetedProvider", "COUNT_TOKENS_URL",
           "DAILY_REQUESTS_ENV", "DAILY_TOKENS_ENV", "DEFAULT_BYTES_PER_TOKEN", "DEFAULT_DAILY_REQUESTS", "HOLD_IDLE_SECONDS",
           "DEFAULT_DAILY_TOKENS", "DEFAULT_MODEL", "DailyBudget", "MODEL_ENV", "TOOL_NAME", "build_paid_provider",
           "drawing_from_hold", "estimate_tokens", "rejection_reason"]
