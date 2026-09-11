"""Build canonical intelligence input from curated news events."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace

from market_platform_foundation.news.contracts import FilterDecision, NewsArticleEvent, PipelineConfig
from market_platform_foundation.news.pipeline import order_accepted_events, stable_event_order_key
from market_platform_foundation.news.sources import SourceTrustCatalog
from market_platform_foundation.news.timestamps import is_observable_at

from .config import IntelligenceInferenceConfig
from .contracts import ArticleInputRef, IntelligenceInputPacket, IntelligenceTaskType
from .hashing import compute_input_hash
from .prompts import PromptDefinition, PromptRegistry


def _catalyst_ids_from_decisions(decisions: tuple[FilterDecision, ...]) -> tuple[str, ...]:
    matched: list[str] = []
    for decision in decisions:
        matched.extend(decision.matched_catalyst_ids)
    return tuple(dict.fromkeys(matched))


def _article_ref(
    event: NewsArticleEvent,
    *,
    decisions: tuple[FilterDecision, ...] = (),
    source_catalog: SourceTrustCatalog | None = None,
) -> ArticleInputRef:
    catalog = source_catalog or SourceTrustCatalog()
    source = catalog.get(event.source_id)
    trust_tier = str(source.tier) if source else ""
    instrument_ids = tuple(
        dict.fromkeys(link.instrument_id for link in event.instrument_linkages if link.instrument_id)
    )
    asset_classes = tuple(
        dict.fromkeys(link.asset_class for link in event.instrument_linkages if link.asset_class)
    )
    return ArticleInputRef(
        event_id=event.event_id,
        source_id=event.source_id,
        provider_id=event.provider_id,
        published_time=event.published_time,
        retrieved_time=event.retrieved_time,
        headline=event.headline,
        summary=event.summary,
        instrument_ids=instrument_ids,
        asset_classes=asset_classes,
        deterministic_catalyst_ids=_catalyst_ids_from_decisions(decisions),
        source_trust_tier=trust_tier,
        publication_time_quality=event.published_time_quality.value,
    )


def _content_length(articles: tuple[ArticleInputRef, ...]) -> int:
    total = 0
    for article in articles:
        total += len(article.headline) + len(article.summary)
    return total


def select_articles_deterministic(
    events: list[NewsArticleEvent],
    *,
    as_of_ns: int,
    config: IntelligenceInferenceConfig,
    event_decisions: dict[str, tuple[FilterDecision, ...]] | None = None,
) -> tuple[tuple[ArticleInputRef, ...], bool, str]:
    """Deterministic prioritization before AI — never ask another model."""
    observable = [event for event in events if is_observable_at(event, as_of_ns)]
    ordered = order_accepted_events(observable)
    refs: list[ArticleInputRef] = []
    for event in ordered:
        decisions = (event_decisions or {}).get(event.event_id, ())
        refs.append(_article_ref(event, decisions=decisions))
    candidate_count = len(refs)
    truncated = False
    reason = ""
    if len(refs) > config.max_articles:
        refs = refs[: config.max_articles]
        truncated = True
        reason = "MAX_ARTICLES"
    while refs and _content_length(tuple(refs)) > config.max_content_chars:
        refs = refs[:-1]
        truncated = True
        reason = reason or "MAX_CONTENT_CHARS"
    return tuple(refs), truncated, reason


def build_input_packet(
    *,
    events: list[NewsArticleEvent],
    as_of: str,
    as_of_ns: int,
    task_type: IntelligenceTaskType,
    pipeline_config: PipelineConfig,
    inference_config: IntelligenceInferenceConfig,
    prompt_registry: PromptRegistry | None = None,
    event_decisions: dict[str, tuple[FilterDecision, ...]] | None = None,
    input_id: str | None = None,
) -> IntelligenceInputPacket:
    registry = prompt_registry or PromptRegistry()
    prompt: PromptDefinition
    if inference_config.prompt_id:
        prompt = registry.get_by_id(inference_config.prompt_id)
    else:
        prompt = registry.get_for_task(task_type)

    articles, truncated, truncation_reason = select_articles_deterministic(
        events,
        as_of_ns=as_of_ns,
        config=inference_config,
        event_decisions=event_decisions,
    )
    instrument_ids = tuple(
        dict.fromkeys(
            instrument_id
            for article in articles
            for instrument_id in article.instrument_ids
        )
    )
    base = IntelligenceInputPacket(
        input_id=input_id or f"inp-{uuid.uuid4().hex[:16]}",
        task_type=task_type,
        as_of=as_of,
        articles=articles,
        instrument_ids=instrument_ids,
        prompt_id=prompt.prompt_id,
        prompt_version=prompt.version,
        prompt_hash=prompt.content_hash,
        output_schema_version=prompt.output_schema_version,
        model_policy_id=f"{inference_config.provider_id}:{inference_config.model_id}",
        source_policy_version=pipeline_config.source_policy_version,
        catalyst_policy_version=pipeline_config.catalyst_registry_version,
        filter_chain_version=pipeline_config.filter_chain_version,
        candidate_article_count=len(events),
        supplied_article_count=len(articles),
        truncated=truncated,
        truncation_reason=truncation_reason,
    )
    return replace(base, input_hash=compute_input_hash(base))


def articles_json_for_prompt(articles: tuple[ArticleInputRef, ...]) -> str:
    payload: list[dict[str, Any]] = []
    for article in articles:
        payload.append(
            {
                "event_id": article.event_id,
                "headline": article.headline,
                "summary": article.summary,
                "published_time": article.published_time,
                "retrieved_time": article.retrieved_time,
                "instrument_ids": list(article.instrument_ids),
                "deterministic_catalyst_ids": list(article.deterministic_catalyst_ids),
                "source_trust_tier": article.source_trust_tier,
            }
        )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


__all__ = [
    "articles_json_for_prompt",
    "build_input_packet",
    "select_articles_deterministic",
    "stable_event_order_key",
]
