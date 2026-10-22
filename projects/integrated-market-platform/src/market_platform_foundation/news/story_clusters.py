"""Deterministic story clusters over canonical news records (S11).

Canonical ``dedupe`` removes exact duplicates of one provider item; a story
cluster groups *independent copies of the same story* (syndication, the same
wire carried by several publishers, one item returned by two providers) while
keeping every member source visible. Five syndicated copies are one story with
five sources, never five events.

Membership evidence, in order:

1. the same canonical URL (host/path; fragment and tracking query dropped, an
   article-id parameter kept);
2. the same provider-native id from the same provider;
3. near-identical normalized headlines (token Jaccard >= ``SIMILARITY``) whose
   times are within ``WINDOW_S`` of the cluster's first member.

Distinct developments about the same instrument are *not* merged: two
headlines must share nearly all of their content words. The cluster id derives
from the earliest member's normalized headline and UTC publication date, so it
is stable across input order and across refreshes that only add later copies.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlparse

from .timestamps import parse_utc_iso

CLUSTER_VERSION = "news/story-clusters/1.0.0"
SIMILARITY = 0.8
WINDOW_S = 12 * 3600
MIN_TOKENS = 4
METHOD = (f"Story clusters ({CLUSTER_VERSION}): same canonical URL, same provider item id, or normalized "
          f"headline token overlap >= {SIMILARITY:.0%} within {WINDOW_S // 3600}h of the first copy.")

_STOPWORDS = frozenset(
    "a an the and or of to in on for at by with from as is are was were be been its it this that these those "
    "after before over into amid says said new report reports update updates".split())
# Publisher suffixes such as " - Reuters" or " | CNBC" are not story content.
_SUFFIX = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")
# Query parameters that name the article itself; every other parameter is tracking and is dropped.
_IDENTITY_PARAMS = frozenset({"id", "p", "article", "articleid", "story", "storyid"})


def canonical_url(url: str | None) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    base = f"{host}{parsed.path.rstrip('/')}".lower()
    # Some providers address every article through one path and an id parameter
    # (Finnhub: /api/news?id=...). Dropping it would make all of them one URL.
    identity = sorted((key.lower(), value) for key, value in parse_qsl(parsed.query) if key.lower() in _IDENTITY_PARAMS)
    return base + "".join(f"?{key}={value}" for key, value in identity)


def normalized_headline(headline: str) -> str:
    text = _SUFFIX.sub("", (headline or "").strip())
    text = re.sub(r"[^\w\s%$.]", " ", text.lower())
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return " ".join(text.split())


def headline_tokens(headline: str) -> frozenset[str]:
    return frozenset(token for token in normalized_headline(headline).split() if token not in _STOPWORDS)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


@dataclass(frozen=True, slots=True)
class ClusterInput:
    """The identity facts clustering needs from one canonical news record."""

    key: str                    # unique record key (canonical event id)
    headline: str
    url: str
    provider_id: str
    provider_native_id: str
    published_time: str         # "" when unknown
    retrieved_time: str


@dataclass(slots=True)
class StoryCluster:
    cluster_id: str
    member_keys: list[str] = field(default_factory=list)
    first_time: datetime | None = None
    tokens: frozenset[str] = frozenset()
    normalized: str = ""
    urls: set[str] = field(default_factory=set)
    native_ids: set[tuple[str, str]] = field(default_factory=set)


def _time_of(item: ClusterInput) -> datetime | None:
    return parse_utc_iso(item.published_time) or parse_utc_iso(item.retrieved_time)


def _cluster_id(item: ClusterInput) -> str:
    published = parse_utc_iso(item.published_time)
    day = published.date().isoformat() if published else "unknown-date"
    basis = normalized_headline(item.headline) or canonical_url(item.url) or item.key
    return "story:" + hashlib.sha256(f"{CLUSTER_VERSION}|{basis}|{day}".encode("utf-8")).hexdigest()[:20]


def _order_key(item: ClusterInput) -> tuple[int, str, str]:
    moment = _time_of(item)
    return (int(moment.timestamp()) if moment else 2**62, normalized_headline(item.headline), item.key)


def cluster_stories(items: list[ClusterInput]) -> list[StoryCluster]:
    """Group records into stories. Deterministic for any input order."""

    clusters: list[StoryCluster] = []
    for item in sorted(items, key=_order_key):
        url = canonical_url(item.url)
        native = (item.provider_id, item.provider_native_id) if item.provider_native_id else None
        tokens = headline_tokens(item.headline)
        normalized = normalized_headline(item.headline)
        moment = _time_of(item)
        target: StoryCluster | None = None
        for cluster in clusters:
            if (url and url in cluster.urls) or (native and native in cluster.native_ids):
                target = cluster
                break
            within = (moment is None or cluster.first_time is None or
                      abs((moment - cluster.first_time).total_seconds()) <= WINDOW_S)
            if not within:
                continue
            if normalized and normalized == cluster.normalized:
                target = cluster
                break
            if len(tokens) >= MIN_TOKENS and len(cluster.tokens) >= MIN_TOKENS and jaccard(tokens, cluster.tokens) >= SIMILARITY:
                target = cluster
                break
        if target is None:
            target = StoryCluster(cluster_id=_cluster_id(item), first_time=moment, tokens=tokens, normalized=normalized)
            clusters.append(target)
        target.member_keys.append(item.key)
        if url:
            target.urls.add(url)
        if native:
            target.native_ids.add(native)
    # Two stories can share an id only if the same headline recurs on the same UTC
    # day beyond the window; disambiguate deterministically by order.
    seen: dict[str, int] = {}
    for cluster in clusters:
        count = seen.get(cluster.cluster_id, 0)
        seen[cluster.cluster_id] = count + 1
        if count:
            cluster.cluster_id = f"{cluster.cluster_id}-{count + 1}"
    return clusters


__all__ = ["CLUSTER_VERSION", "ClusterInput", "METHOD", "SIMILARITY", "StoryCluster", "WINDOW_S", "canonical_url",
           "cluster_stories", "headline_tokens", "jaccard", "normalized_headline"]
