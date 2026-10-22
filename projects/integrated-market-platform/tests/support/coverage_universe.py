"""Controlled Screener universes and engines for full-universe AI Screener tests. No provider, no spend.

A row is made "controlled-strong" by an ``rsi_14`` at or above ``STRONG``. ``RankingProvider`` selects the
strong rows it is shown, strongest first, at most five. That rule is a test fixture with a known expected
outcome; it is not a trading method and exists nowhere in ``src``.
"""
from __future__ import annotations

import json
import threading

from market_platform_foundation.intelligence.inference.contracts import ParsingStatus
from market_platform_foundation.intelligence.inference.errors import InferenceErrorCode
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse

NOW = 1790953200.0  # 2026-10-02T15:00:00Z
NOW_ISO = "2026-10-02T15:00:00Z"
STRONG = 80.0
SCOPE = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True, "filters": [], "result_set": None}


def instrument_id(index: int) -> str:
    return f"EQ:S{index:05d}"


def row(index: int, *, rsi: float = 50.0, price: float | None = 100.0, as_of: str = NOW_ISO, state: str = "LIVE") -> dict:
    identifier = instrument_id(index)
    fields = {"change_pct": {"value": 1.0, "source": "IMP_TEST", "state": state, "as_of": as_of},
              "rsi_14": {"value": rsi, "source": "IMP_TEST", "state": state, "as_of": as_of}}
    if price is not None:
        fields["price"] = {"value": price, "source": "IMP_TEST", "state": state, "as_of": as_of}
    return {"instrument": {"instrument_id": identifier, "symbol": identifier.split(":")[-1], "universe": "US_EQUITIES",
                           "asset_class": "EQUITY"}, "symbol": identifier.split(":")[-1], "fields": fields}


def universe(size: int, *, strong: dict[int, float] | None = None) -> list[dict]:
    """``size`` rows; ``strong`` maps a zero-based position to that row's controlled strength."""
    strong = strong or {}
    return [row(index, rsi=strong.get(index, 50.0)) for index in range(size)]


class PagingReader:
    """The Screener read contract: offset/limit windows of one pinned result set, with a truthful total."""

    def __init__(self, rows: list[dict], *, result_set: str = "set-1") -> None:
        self.rows = rows
        self.result_set = result_set
        self.calls: list[dict] = []

    def read(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("result_set") not in (None, self.result_set):
            raise ValueError("RESULT_SET_CHANGED")
        offset, limit = kwargs["offset"], kwargs["limit"]
        window = self.rows[offset:offset + limit]
        return {"rows": window, "result_count": len(self.rows), "offset": offset, "limit": limit, "returned": len(window),
                "has_more": offset + len(window) < len(self.rows), "query_id": "query-1", "result_set_id": self.result_set,
                "universe_as_of": NOW_ISO, "screener_as_of": NOW_ISO}


def strength(candidate: dict) -> float:
    return max((item["facts"].get("rsi_14", 0.0) for item in candidate["current_market_evidence"]), default=0.0)


def answer(candidates: list[dict], picks: list[dict]) -> str:
    """A valid compact-wire answer selecting ``picks`` (packet candidates), in the order given."""
    by_key = {id(candidate): index for index, candidate in enumerate(candidates)}
    selected = []
    for rank, candidate in enumerate(picks, 1):
        refs = [index for index, item in enumerate(candidate["current_market_evidence"]) if not item["weak_reasons"]]
        selected.append({"candidate_key": by_key[id(candidate)], "rank": rank,
                         "rationale": "Candidate for review based on admitted observations.",
                         "supporting_refs": refs, "conflicting_refs": [], "uncertainties": ["Coverage is limited."]})
    return json.dumps({"schema_version": "ai-screener-output/1.0.0", "candidates": selected,
                       "limitations": ["Candidate reduction only."]})


class RankingProvider:
    """Selects the controlled-strong candidates it is shown, strongest first, at most five. Records every request."""

    provider_id = "inference.test"
    model_id = "candidate-reduction.controlled"
    runtime = "FIXTURE"

    def __init__(self) -> None:
        self.calls = 0
        self.seen: list[list[str]] = []
        self.lock = threading.Lock()

    def respond(self, packet) -> ProviderInferenceResponse:
        strong = sorted((c for c in packet.candidates if strength(c) >= STRONG),
                        key=lambda c: (-strength(c), c["instrument"]["instrument_id"]))[:5]
        return ProviderInferenceResponse(answer(packet.candidates, strong), self.provider_id, self.model_id,
                                         tokens_input=1000, tokens_output=100, latency_ms=1, simulated=True)

    def infer(self, packet, *, rendered_prompt, config):
        with self.lock:
            self.calls += 1
            self.seen.append([c["instrument"]["instrument_id"] for c in packet.candidates])
            call = self.calls
        return self.on_call(call, packet)

    def on_call(self, call: int, packet) -> ProviderInferenceResponse:
        return self.respond(packet)

    def failure(self, reason: str, *, timeout: bool = False) -> ProviderInferenceResponse:
        return ProviderInferenceResponse(
            raw_text="", provider_id=self.provider_id, model_id=self.model_id, error_message=reason,
            error_code=InferenceErrorCode.PROVIDER_TIMEOUT if timeout else InferenceErrorCode.PROVIDER_UNAVAILABLE,
            parsing_status=ParsingStatus.TIMEOUT if timeout else ParsingStatus.PROVIDER_ERROR, latency_ms=1)


class FailingProvider(RankingProvider):
    """Answers normally until call ``fail_on``; that call returns ``reason`` (or raw text when ``raw`` is given)."""

    def __init__(self, *, fail_on: int, reason: str = "ANTHROPIC_OVERLOADED_ERROR", timeout: bool = False, raw: str | None = None) -> None:
        super().__init__()
        self.fail_on, self.reason, self.timeout, self.raw = fail_on, reason, timeout, raw

    def on_call(self, call, packet):
        if call != self.fail_on:
            return self.respond(packet)
        if self.raw is not None:
            return ProviderInferenceResponse(self.raw, self.provider_id, self.model_id, tokens_input=1000, tokens_output=100,
                                             latency_ms=1, simulated=True)
        return self.failure(self.reason, timeout=self.timeout)


class GatedProvider(RankingProvider):
    """Holds each call open until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Semaphore(0)
        self.release = threading.Semaphore(0)

    def on_call(self, call, packet):
        self.entered.release()
        if not self.release.acquire(timeout=10):
            raise TimeoutError("test never released the controlled engine")
        return self.respond(packet)


class News:
    """News service stand-in: the engine and its status, no stories."""

    def __init__(self, provider) -> None:
        self.provider = provider

    def synthesis_provider(self):
        return self.provider

    def ai_status(self):
        if self.provider is None:
            return {"state": "NOT_CONFIGURED", "reason": "ANTHROPIC_API_KEY_NOT_SET", "provider_id": None, "model_id": None,
                    "runtime": None, "engines": []}
        budget = self.provider.budget_status() if hasattr(self.provider, "budget_status") else None
        spent = budget is not None and (budget["requests"] >= budget["max_requests"] or budget["tokens"] >= budget["max_tokens"])
        return {"state": "UNAVAILABLE" if spent else "AVAILABLE", "reason": "SYNTHESIS_DAILY_BUDGET_EXHAUSTED" if spent else None,
                "provider_id": self.provider.provider_id, "model_id": self.provider.model_id,
                "runtime": "PAID_API" if budget is not None else "LOCAL_MODEL", "budget": budget, "engines": []}
