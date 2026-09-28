"""Grounded Screener news synthesis on the canonical inference boundary (S11).

Runs the ``news.screener_synthesis.v1`` prompt through any ``InferenceProvider``
(Anthropic in production, ``FixtureInferenceProvider`` or a stub in tests) and
validates the structured result before anything reaches the UI:

* every item's ``refs`` must name story ids that were in the packet;
* unsupported certainty (BUY/SELL, "guaranteed", "will rally/crash/soar/plunge")
  outside quoted attribution rejects the whole output (``INVALID_OUTPUT``);
* malformed or refused output is a state, never an empty-but-"current" synthesis.

Results are cached by the input hash (stories + prompt + model), so a render
never calls a model; changed stories produce a new hash and a new call.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import IntelligenceInferenceConfig
from .contracts import ArticleInputRef, IntelligenceInputPacket, IntelligenceTaskType
from .hashing import input_hash_from_dict
from .prompts import PromptRegistry
from .provider import InferenceProvider

PROMPT_ID = "news.screener_synthesis.v1"
SCHEMA_VERSION = "screener-news-synthesis/1.0.0"
MAX_STORIES = 12
CACHE_SIZE = 64
CACHE_TTL_S = 30 * 60
_LIST_FIELDS = ("observed_facts", "derived_context", "conflicting_evidence", "potential_market_relevance")
# Recommendation/certainty forms only. Attributed analyst actions in prose ("upgraded to Buy") and
# market vocabulary ("sell-off", "buyback") are not recommendations.
_UNSUPPORTED = re.compile(
    r"\b(?:BUY|SELL)\b|(?i:\b(?:investors|you|traders)\s+should\s+(?:buy|sell)\b|\b(?:buy|sell)\s+(?:signal|now)\b|"
    r"\bguarantee(?:d|s)?\b|\bwill\s+(?:rally|crash|soar|plunge|surge|collapse|skyrocket|tank|moon)\b|"
    r"\bcertain\s+to\s+(?:rise|fall|rally|drop)\b|\bcan(?:not|'t)\s+lose\b)")
_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']{8,}'")


@dataclass(frozen=True, slots=True)
class SynthesisStory:
    story_id: str
    headline: str
    summary: str
    published_time: str
    retrieved_time: str
    source_type: str
    source_count: int
    publishers: tuple[str, ...]
    categories: tuple[str, ...]


def unsupported_certainty(text: str) -> bool:
    """True when certainty/trade language appears outside quoted attribution."""

    return bool(_UNSUPPORTED.search(_QUOTED.sub(" ", text or "")))


def _items(value: Any, story_ids: set[str], *, with_refs: bool) -> list[Any] | None:
    if not isinstance(value, list):
        return None
    out: list[Any] = []
    for entry in value[:12]:
        if with_refs:
            if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
                return None
            refs = entry.get("refs")
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref in story_ids for ref in refs):
                return None
            out.append({"text": entry["text"].strip(), "refs": list(dict.fromkeys(refs))})
        else:
            if not isinstance(entry, str):
                return None
            out.append(entry.strip())
    return out


def parse_synthesis(raw_text: str, story_ids: set[str]) -> tuple[dict[str, Any] | None, str | None]:
    """(synthesis, None) or (None, reason). Never repairs or invents content."""

    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, "MALFORMED_JSON"
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), str) or not payload["summary"].strip():
        return None, "MISSING_SUMMARY"
    result: dict[str, Any] = {"summary": payload["summary"].strip()}
    for name in _LIST_FIELDS:
        parsed = _items(payload.get(name, []), story_ids, with_refs=True)
        if parsed is None:
            return None, f"INVALID_{name.upper()}"
        result[name] = parsed
    uncertainties = _items(payload.get("uncertainties", []), story_ids, with_refs=False)
    if uncertainties is None:
        return None, "INVALID_UNCERTAINTIES"
    result["uncertainties"] = uncertainties
    texts = [result["summary"], *result["uncertainties"], *(item["text"] for name in _LIST_FIELDS for item in result[name])]
    if any(unsupported_certainty(item) for item in texts):
        return None, "UNSUPPORTED_CERTAINTY"
    if not result["observed_facts"]:
        return None, "NO_GROUNDED_FACTS"
    return result, None


class ScreenerSynthesizer:
    """Cached, validated synthesis over the canonical inference provider."""

    def __init__(self, *, provider: InferenceProvider | None, config: IntelligenceInferenceConfig | None = None,
                 registry: PromptRegistry | None = None, clock=time.time) -> None:
        self._provider = provider
        self._config = config or IntelligenceInferenceConfig(max_tokens=1400, timeout_seconds=45.0, prompt_id=PROMPT_ID)
        self._registry = registry or PromptRegistry()
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self.calls = 0

    def input_hash(self, stories: list[SynthesisStory], instruments: tuple[str, ...]) -> str:
        prompt = self._registry.get_by_id(PROMPT_ID)
        model = getattr(self._provider, "model_id", "") if self._provider else ""
        return input_hash_from_dict({
            "prompt": prompt.content_hash, "model": model, "instruments": list(instruments),
            "stories": [[story.story_id, story.headline, story.summary, story.published_time, story.source_count]
                        for story in stories],
        })

    def synthesize(self, stories: list[SynthesisStory], *, instruments: tuple[str, ...], as_of: str) -> dict[str, Any]:
        prompt = self._registry.get_by_id(PROMPT_ID)
        base = {"schema_version": SCHEMA_VERSION, "epistemic_class": "AI_SYNTHESIS", "prompt_id": prompt.prompt_id,
                "prompt_version": prompt.version, "generated_at": as_of, "story_ids": [story.story_id for story in stories],
                "provider_id": getattr(self._provider, "provider_id", None) if self._provider else None,
                "model_id": getattr(self._provider, "model_id", None) if self._provider else None,
                "input_hash": None, "cache": None, "synthesis": None}
        if self._provider is None:
            return {**base, "state": "NOT_CONFIGURED", "reason": "ANTHROPIC_API_KEY_NOT_SET"}
        if not stories:
            return {**base, "state": "INSUFFICIENT_EVIDENCE", "reason": "NO_STORIES_IN_WINDOW"}
        stories = stories[:MAX_STORIES]
        digest = self.input_hash(stories, instruments)
        now = self._clock()
        with self._lock:
            cached = self._cache.get(digest)
            if cached is not None and cached[0] > now:
                self._cache.move_to_end(digest)
                return {**cached[1], "cache": "HIT"}
        articles = tuple(ArticleInputRef(event_id=story.story_id, source_id=",".join(story.publishers)[:120],
                                         provider_id=story.source_type, published_time=story.published_time,
                                         retrieved_time=story.retrieved_time, headline=story.headline,
                                         summary=story.summary, instrument_ids=instruments,
                                         deterministic_catalyst_ids=story.categories,
                                         source_trust_tier=f"{story.source_count} source(s)",
                                         publication_time_quality="KNOWN" if story.published_time else "UNKNOWN")
                         for story in stories)
        packet = IntelligenceInputPacket(
            input_id=uuid.uuid4().hex, task_type=IntelligenceTaskType.NEWS_SCREENER_SYNTHESIS, as_of=as_of,
            articles=articles, instrument_ids=instruments, prompt_id=prompt.prompt_id, prompt_version=prompt.version,
            prompt_hash=prompt.content_hash, output_schema_version=prompt.output_schema_version,
            model_policy_id="screener-news-synthesis", candidate_article_count=len(stories),
            supplied_article_count=len(stories), input_hash=digest)
        articles_json = json.dumps([{**{key: getattr(article, key) for key in ("event_id", "headline", "summary",
                                                                                 "published_time", "provider_id",
                                                                                 "source_trust_tier")},
                                     "categories": list(article.deterministic_catalyst_ids)} for article in articles],
                                   ensure_ascii=False)
        rendered = self._registry.render(prompt, as_of=as_of, instrument_ids=instruments, articles_json=articles_json)
        self.calls += 1
        response = self._provider.infer(packet, rendered_prompt=rendered, config=self._config)
        base = {**base, "input_hash": digest, "cache": "MISS", "provider_id": response.provider_id,
                "model_id": response.model_id}
        if response.error_code is not None:
            reason = response.error_message if response.error_message == "API_KEY_MISSING" else response.error_code.value
            state = "NOT_CONFIGURED" if response.error_message == "API_KEY_MISSING" else "UNAVAILABLE"
            return {**base, "state": state, "reason": reason}
        synthesis, reason = parse_synthesis(response.raw_text, {story.story_id for story in stories})
        if synthesis is None:
            return {**base, "state": "INVALID_OUTPUT", "reason": reason}
        result = {**base, "state": "CURRENT", "reason": None, "synthesis": synthesis,
                  "generated_at": datetime.fromtimestamp(self._clock(), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
        with self._lock:
            self._cache[digest] = (now + CACHE_TTL_S, result)
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return result


__all__ = ["PROMPT_ID", "SCHEMA_VERSION", "ScreenerSynthesizer", "SynthesisStory", "parse_synthesis",
           "unsupported_certainty"]
