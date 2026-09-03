import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .semantics import (
    NewsDateOnlyPolicy,
    NewsLifecycleStatus,
    NewsSourceShape,
)


FixtureOrigin = Literal[
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
]


def _assign_alias(data: dict[str, Any], canonical: str, value: Any) -> None:
    if value is None:
        return
    if canonical in data and data[canonical] is not None and data[canonical] != value:
        raise ValueError(f"conflicting values for {canonical}")
    data[canonical] = value


class NewsRecord(BaseModel):
    """Strict local-only objective news metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_record_id: str = Field(min_length=1)
    provider_schema: Literal["NEWS_ITEM_V1"]
    record_type: Literal["NEWS_ITEM"]
    fixture_origin: FixtureOrigin
    source_shape: NewsSourceShape
    provider: str = Field(min_length=1)
    provider_record_id: str | None = None
    headline: str = Field(min_length=1)
    summary: str | None = None
    publisher: str | None = None
    author: str | None = None
    url: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    provider_available_at: str | None = None
    capture_timestamp: str | None = None
    symbols: tuple[str, ...] | None = None
    language: str | None = None
    content_type: str | None = None
    status: NewsLifecycleStatus = NewsLifecycleStatus.ORIGINAL
    supersedes_provider_record_id: str | None = None
    prior_canonical_url: str | None = None
    timezone: str | None = None
    date_only_policy: NewsDateOnlyPolicy = NewsDateOnlyPolicy.STRICT
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def documented_aliases(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        shape = str(data.get("source_shape", ""))
        if shape == NewsSourceShape.FINVIZ.value:
            for alias, canonical in (
                ("Title", "headline"),
                ("Date", "published_at"),
                ("Url", "url"),
                ("Ticker", "symbols"),
            ):
                if alias in data:
                    _assign_alias(data, canonical, data.pop(alias))
        elif shape == NewsSourceShape.YAHOO.value:
            content = data.pop("content", None)
            if content is not None:
                if not isinstance(content, Mapping):
                    raise ValueError("Yahoo content must be an object")
                _assign_alias(data, "headline", content.get("title"))
                _assign_alias(data, "summary", content.get("summary"))
                _assign_alias(data, "published_at", content.get("pubDate"))
                canonical = content.get("canonicalUrl") or {}
                click = content.get("clickThroughUrl") or {}
                if not isinstance(canonical, Mapping) or not isinstance(click, Mapping):
                    raise ValueError("Yahoo URL aliases must be objects")
                _assign_alias(data, "url", canonical.get("url") or click.get("url"))
        elif shape == NewsSourceShape.NEWSAPI.value:
            for alias, canonical in (
                ("title", "headline"),
                ("description", "summary"),
                ("publishedAt", "published_at"),
            ):
                if alias in data:
                    _assign_alias(data, canonical, data.pop(alias))
            source = data.pop("source", None)
            if source is not None:
                if not isinstance(source, Mapping):
                    raise ValueError("NewsAPI source must be an object")
                _assign_alias(data, "publisher", source.get("name"))
        return data

    @field_validator("headline")
    @classmethod
    def normalize_headline(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("headline must not be empty")
        return normalized

    @field_validator("summary", "publisher", "author", "language", "content_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("symbols", mode="before")
    @classmethod
    def normalize_symbols(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        items = value.split(",") if isinstance(value, str) else value
        normalized: set[str] = set()
        for item in items:
            symbol = str(item).strip().upper()
            if not symbol:
                continue
            if not re.fullmatch(r"[A-Z0-9.\-]{1,32}", symbol):
                raise ValueError("symbol has an unsupported format")
            normalized.add(symbol)
        return tuple(sorted(normalized))
