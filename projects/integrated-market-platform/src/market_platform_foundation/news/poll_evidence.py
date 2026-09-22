"""Bounded poll/tick rejection observability and campaign-evidence envelopes.

Counts and reason buckets only for diagnostics. Never dumps raw provider
payloads. Missing or undetermined reasons use ``UNKNOWN``; stages that are not
part of the current hop use ``UNAVAILABLE`` (never invent counters).

Shared by Finviz prospective ingress (hop 1) and optional admit/persist
enrichment (hop 2). Provider-linkage contradiction detection is intentionally
out of scope — see ``PROVIDER_LINKAGE_QUALITY_HOOK``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .contracts import (
    FilterStage,
    NewsArticleEvent,
    PipelineEventResult,
    PublicationTimeQuality,
)
from .timestamps import epoch_ns_from_iso

UNAVAILABLE = "UNAVAILABLE"
UNKNOWN = "UNKNOWN"

# Opt-in root for bounded poll manifests. Never defaults to RTH campaign dirs.
POLL_EVIDENCE_DIR_ENV = "IMP_CAMPAIGN_POLL_EVIDENCE_DIR"
POLL_EVIDENCE_RETENTION_ENABLED_ENV = "IMP_CAMPAIGN_POLL_EVIDENCE_RETENTION"
POLL_EVIDENCE_MAX_ITEMS_ENV = "IMP_CAMPAIGN_POLL_EVIDENCE_MAX_ITEMS"
POLL_EVIDENCE_MAX_POLLS_ENV = "IMP_CAMPAIGN_POLL_EVIDENCE_MAX_POLLS"
POLL_EVIDENCE_HEADLINE_CHARS_ENV = "IMP_CAMPAIGN_POLL_EVIDENCE_HEADLINE_CHARS"

_DEFAULT_MAX_ITEMS = 128
_DEFAULT_MAX_POLLS = 48
_DEFAULT_HEADLINE_CHARS = 80
_DIGEST_VERSION = "poll-evidence-digest/1.0.0"
_ENVELOPE_SCHEMA = "imp.poll_evidence_envelope/1.0.0"
_SUMMARY_SCHEMA = "imp.poll_rejection_summary/1.0.0"

_SECRET_KEY_RE = re.compile(
    r"(?i)(auth|api[_-]?key|token|password|passwd|secret|session|authorization|cookie)"
)
# Query-secret-like key=value pairs in headlines/strings (not only ?/& delimited).
_SENSITIVE_PARAM = (
    r"auth|authorization|token|access[_-]?token|api[_-]?key|"
    r"password|passwd|secret|session|key|credential|cookie"
)
_SENSITIVE_VALUE_RE = re.compile(
    rf"(?i)((?:[?&]|^|(?<=\W))(?:{_SENSITIVE_PARAM})=)[^&\s\"']+"
)
_RTH_CAMPAIGN_DIR_PREFIX = "rth-campaign-"

# Extension point owned by another lane. Leave unset / no-op here.
PROVIDER_LINKAGE_QUALITY_HOOK: Callable[..., Any] | None = None

_HOP1_BUCKETS = (
    "fetched",
    "normalization_success",
    "normalization_fail",
    "missing_identity",
    "publication_known",
    "publication_inferred",
    "publication_unknown",
    "source_filter_reject",
    "recency_reject",
    "catalyst_reject",
    "observability_reject",
    "pipeline_accepted",
    "universe_filtered",
    "duplicate_already_present",
)

_WINDOW_BUCKETS = (
    "pre_window",
    "post_window_or_current_candidate",
)

_HOP2_BUCKETS = (
    "pit_reject",
    "event_v1_persisted",
    "persistence_conflict",
    "opportunity_v1_minted",
    "ranked",
)


def _unavailable_map(keys: Sequence[str]) -> dict[str, object]:
    return {key: UNAVAILABLE for key in keys}


def _increment(counts: dict[str, object], key: str, amount: int = 1) -> None:
    current = counts.get(key, 0)
    if current is UNAVAILABLE or not isinstance(current, int):
        counts[key] = int(amount)
        return
    counts[key] = int(current) + int(amount)


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def scrub_secrets(value: Any, *, secret: str | None = None) -> Any:
    """Drop secret-shaped keys and redact credential-looking substrings."""

    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                cleaned[key_text] = "<REDACTED>"
                continue
            cleaned[key_text] = scrub_secrets(nested, secret=secret)
        return cleaned
    if isinstance(value, list):
        return [scrub_secrets(item, secret=secret) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_secrets(item, secret=secret) for item in value)
    if isinstance(value, str):
        text = _SENSITIVE_VALUE_RE.sub(r"\1<REDACTED>", value)
        if secret and secret in text:
            text = text.replace(secret, "<REDACTED>")
        return text
    return value


def _path_contains_rth_campaign_dir(path: Path) -> bool:
    """True when any path component is an ``rth-campaign-*`` directory.

    Refuses nested campaign trees (including ``.../rth-campaign-<date>/state``)
    for any date — not only a hard-coded campaign id.
    """

    return any(
        str(part).lower().startswith(_RTH_CAMPAIGN_DIR_PREFIX) for part in Path(path).parts
    )


def redact_headline(headline: str, *, max_chars: int = _DEFAULT_HEADLINE_CHARS) -> str:
    """Bounded headline for forensic envelopes — never a full payload dump."""

    text = " ".join(str(headline or "").split())
    text = _SENSITIVE_VALUE_RE.sub(r"\1<REDACTED>", text)
    limit = max(0, int(max_chars))
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def url_identifier(url: str) -> str:
    """Stable URL identity without query secrets (host + path only)."""

    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    # Match Finviz canonical news URL identity: lowercase host+path, drop query.
    path = parsed.path.rstrip("/").lower()
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def digest_fetched_item(item: Mapping[str, Any]) -> str:
    """Cryptographic digest of identity-bearing fields only (stable, no process salt)."""

    tickers_raw = item.get("tickers") or []
    tickers: list[str] = []
    if isinstance(tickers_raw, list):
        tickers = sorted(
            {str(ticker).strip().upper() for ticker in tickers_raw if str(ticker).strip()}
        )
    elif isinstance(tickers_raw, str) and tickers_raw.strip():
        tickers = [tickers_raw.strip().upper()]
    payload = {
        "digest_version": _DIGEST_VERSION,
        "provider_native_id": str(
            item.get("provider_native_id")
            or item.get("provider_news_id")
            or item.get("id")
            or ""
        ).strip(),
        "url_identifier": url_identifier(str(item.get("url") or "")),
        "headline": " ".join(str(item.get("headline") or item.get("title") or "").lower().split()),
        "tickers": tickers,
        "published_time": str(item.get("published_time") or item.get("publishedAt") or "").strip(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_symbol(event: NewsArticleEvent) -> str:
    if not event.instrument_linkages:
        return ""
    return str(event.instrument_linkages[0].instrument_id or "").strip().upper()


def _reject_reason(result: PipelineEventResult) -> str:
    for decision in result.decisions:
        if decision.accepted:
            continue
        code = str(decision.reason_code or "").strip()
        return code or UNKNOWN
    if result.accepted:
        return ""
    return UNKNOWN


def _reject_stage(result: PipelineEventResult) -> FilterStage | None:
    for decision in result.decisions:
        if decision.accepted:
            continue
        return decision.stage
    return None


@dataclass
class PollRejectionSummary:
    """Privacy-safe per-poll counts and reason buckets."""

    counts: dict[str, object] = field(default_factory=dict)
    reason_buckets: dict[str, int] = field(default_factory=dict)
    schema_version: str = _SUMMARY_SCHEMA

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_version": self.schema_version,
            "counts": dict(self.counts),
            "reason_buckets": dict(sorted(self.reason_buckets.items())),
        }
        return scrub_secrets(payload)


def build_poll_rejection_summary(
    *,
    fetched_count: int,
    events: Sequence[NewsArticleEvent],
    results: Sequence[PipelineEventResult],
    universe: frozenset[str] | set[str] | None = None,
    observation_window_start_ns: int | None = None,
    normalization_fail_count: int | None = None,
    pit_reject_count: int | None = None,
    event_v1_persisted_count: int | None = None,
    persistence_conflict_count: int | None = None,
    opportunity_v1_minted_count: int | None = None,
    ranked_count: int | None = None,
    hop2_duplicate_already_present_count: int | None = None,
) -> PollRejectionSummary:
    """Map existing pipeline decisions into bounded diagnostic counts.

    Does not alter qualification. Stages absent from this hop remain
    ``UNAVAILABLE`` unless an explicit count is supplied by a later hop.
    """

    universe_set = frozenset(str(symbol).strip().upper() for symbol in (universe or ()))
    counts: dict[str, object] = {key: 0 for key in _HOP1_BUCKETS}
    counts.update(_unavailable_map(_WINDOW_BUCKETS))
    counts.update(_unavailable_map(_HOP2_BUCKETS))

    fetched = max(0, int(fetched_count))
    event_list = list(events)
    fail_count = (
        int(normalization_fail_count)
        if normalization_fail_count is not None
        else max(0, fetched - len(event_list))
    )
    success_count = len(event_list)
    counts["fetched"] = fetched
    counts["normalization_success"] = success_count
    counts["normalization_fail"] = fail_count

    for event in event_list:
        quality = event.published_time_quality
        if quality == PublicationTimeQuality.KNOWN:
            _increment(counts, "publication_known")
        elif quality == PublicationTimeQuality.INFERRED_LOW_CONFIDENCE:
            _increment(counts, "publication_inferred")
        else:
            _increment(counts, "publication_unknown")

    if observation_window_start_ns is not None:
        counts["pre_window"] = 0
        counts["post_window_or_current_candidate"] = 0
        window_ns = int(observation_window_start_ns)
        for event in event_list:
            published_ns = epoch_ns_from_iso(event.published_time)
            if published_ns is None:
                continue
            if int(published_ns) < window_ns:
                _increment(counts, "pre_window")
            else:
                _increment(counts, "post_window_or_current_candidate")

    reason_buckets: dict[str, int] = {}
    for result in results:
        stage = _reject_stage(result)
        reason = _reject_reason(result)
        if result.duplicate_of or (
            stage == FilterStage.DEDUPLICATION and not result.accepted
        ):
            _increment(counts, "duplicate_already_present")
            bucket = reason or "DUPLICATE"
            reason_buckets[bucket] = reason_buckets.get(bucket, 0) + 1
            continue
        if not result.accepted:
            if not reason:
                reason = UNKNOWN
            reason_buckets[reason] = reason_buckets.get(reason, 0) + 1
            if stage == FilterStage.SOURCE_POLICY:
                _increment(counts, "source_filter_reject")
            elif stage == FilterStage.RECENCY:
                _increment(counts, "recency_reject")
            elif stage == FilterStage.CATALYST_KEYWORD:
                _increment(counts, "catalyst_reject")
            elif stage == FilterStage.OBSERVABILITY:
                _increment(counts, "observability_reject")
            continue

        _increment(counts, "pipeline_accepted")
        symbol = _event_symbol(result.event)
        if not symbol:
            _increment(counts, "missing_identity")
            reason_buckets["MISSING_SYMBOL"] = reason_buckets.get("MISSING_SYMBOL", 0) + 1
            continue
        if universe_set and symbol not in universe_set:
            _increment(counts, "universe_filtered")
            reason_buckets["UNIVERSE_FILTERED"] = reason_buckets.get("UNIVERSE_FILTERED", 0) + 1

    if hop2_duplicate_already_present_count is not None:
        current = counts.get("duplicate_already_present", 0)
        base = int(current) if isinstance(current, int) else 0
        counts["duplicate_already_present"] = base + int(hop2_duplicate_already_present_count)

    if pit_reject_count is not None:
        counts["pit_reject"] = int(pit_reject_count)
    if event_v1_persisted_count is not None:
        counts["event_v1_persisted"] = int(event_v1_persisted_count)
    if persistence_conflict_count is not None:
        counts["persistence_conflict"] = int(persistence_conflict_count)
    if opportunity_v1_minted_count is not None:
        counts["opportunity_v1_minted"] = int(opportunity_v1_minted_count)
    if ranked_count is not None:
        counts["ranked"] = int(ranked_count)

    # Optional no-op extension point — another lane owns contradiction heuristics.
    if PROVIDER_LINKAGE_QUALITY_HOOK is not None:
        try:
            PROVIDER_LINKAGE_QUALITY_HOOK(events=event_list, counts=counts)
        except Exception:
            pass

    return PollRejectionSummary(counts=counts, reason_buckets=reason_buckets)


@dataclass(frozen=True, slots=True)
class CampaignEvidenceRetentionPolicy:
    """Bounded retention knobs for forensic reconstruction (not payload hoarding)."""

    enabled: bool = False
    max_items_per_poll: int = _DEFAULT_MAX_ITEMS
    max_polls_retained: int = _DEFAULT_MAX_POLLS
    max_headline_chars: int = _DEFAULT_HEADLINE_CHARS
    include_url_identifier: bool = True
    include_redacted_headline: bool = True
    evidence_root: Path | None = None

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        evidence_root: Path | None = None,
    ) -> CampaignEvidenceRetentionPolicy:
        mapping = env if env is not None else os.environ
        root = evidence_root
        if root is None:
            raw_root = str(mapping.get(POLL_EVIDENCE_DIR_ENV) or "").strip()
            root = Path(raw_root).expanduser() if raw_root else None
        max_items = _DEFAULT_MAX_ITEMS
        max_polls = _DEFAULT_MAX_POLLS
        headline_chars = _DEFAULT_HEADLINE_CHARS
        try:
            if str(mapping.get(POLL_EVIDENCE_MAX_ITEMS_ENV) or "").strip():
                max_items = max(0, int(mapping[POLL_EVIDENCE_MAX_ITEMS_ENV]))
        except (TypeError, ValueError):
            max_items = _DEFAULT_MAX_ITEMS
        try:
            if str(mapping.get(POLL_EVIDENCE_MAX_POLLS_ENV) or "").strip():
                max_polls = max(0, int(mapping[POLL_EVIDENCE_MAX_POLLS_ENV]))
        except (TypeError, ValueError):
            max_polls = _DEFAULT_MAX_POLLS
        try:
            if str(mapping.get(POLL_EVIDENCE_HEADLINE_CHARS_ENV) or "").strip():
                headline_chars = max(0, int(mapping[POLL_EVIDENCE_HEADLINE_CHARS_ENV]))
        except (TypeError, ValueError):
            headline_chars = _DEFAULT_HEADLINE_CHARS
        enabled = _truthy(mapping.get(POLL_EVIDENCE_RETENTION_ENABLED_ENV)) and root is not None
        return cls(
            enabled=enabled,
            max_items_per_poll=max_items,
            max_polls_retained=max_polls,
            max_headline_chars=headline_chars,
            evidence_root=root,
        )


@dataclass(frozen=True, slots=True)
class ItemEvidenceRecord:
    item_digest: str
    provider_ticker: str
    published_time: str
    retrieved_time: str
    publication_quality: str
    pipeline_disposition: str
    rejection_reason: str
    url_identifier: str = ""
    headline_redacted: str = ""
    event_id: str = ""
    provider_native_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return scrub_secrets(
            {
                "item_digest": self.item_digest,
                "provider_ticker": self.provider_ticker,
                "published_time": self.published_time,
                "retrieved_time": self.retrieved_time,
                "publication_quality": self.publication_quality,
                "pipeline_disposition": self.pipeline_disposition,
                "rejection_reason": self.rejection_reason,
                "url_identifier": self.url_identifier,
                "headline_redacted": self.headline_redacted,
                "event_id": self.event_id,
                "provider_native_id": self.provider_native_id,
            }
        )


@dataclass
class PollEvidenceEnvelope:
    """Minimal per-poll forensic envelope — digests + dispositions, not raw payloads."""

    poll_id: str
    as_of_ns: int
    provider_id: str
    source_id: str
    rejection_summary: PollRejectionSummary
    items: tuple[ItemEvidenceRecord, ...] = ()
    schema_version: str = _ENVELOPE_SCHEMA
    retention_policy: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return scrub_secrets(
            {
                "schema_version": self.schema_version,
                "poll_id": self.poll_id,
                "as_of_ns": int(self.as_of_ns),
                "provider_id": self.provider_id,
                "source_id": self.source_id,
                "rejection_summary": self.rejection_summary.to_dict(),
                "item_count": len(self.items),
                "items": [item.to_dict() for item in self.items],
                "retention_policy": dict(self.retention_policy),
                "raw_payloads_retained": False,
            }
        )


def _result_by_event_id(
    results: Sequence[PipelineEventResult],
) -> dict[str, PipelineEventResult]:
    mapping: dict[str, PipelineEventResult] = {}
    for result in results:
        mapping[result.event.event_id] = result
    return mapping


def _disposition_for_result(
    result: PipelineEventResult | None,
    *,
    universe: frozenset[str],
) -> tuple[str, str]:
    if result is None:
        return "UNKNOWN", UNKNOWN
    if result.duplicate_of or any(
        (not decision.accepted and decision.stage == FilterStage.DEDUPLICATION)
        for decision in result.decisions
    ):
        return "DUPLICATE", _reject_reason(result) or "DUPLICATE"
    if not result.accepted:
        return "REJECTED", _reject_reason(result) or UNKNOWN
    symbol = _event_symbol(result.event)
    if not symbol:
        return "MISSING_IDENTITY", "MISSING_SYMBOL"
    if universe and symbol not in universe:
        return "UNIVERSE_FILTERED", "UNIVERSE_FILTERED"
    return "PIPELINE_ACCEPTED", ""


def build_item_evidence_records(
    *,
    fetched_items: Sequence[Mapping[str, Any]],
    events: Sequence[NewsArticleEvent],
    results: Sequence[PipelineEventResult],
    universe: frozenset[str] | set[str] | None = None,
    policy: CampaignEvidenceRetentionPolicy | None = None,
) -> tuple[ItemEvidenceRecord, ...]:
    """Build bounded per-item evidence rows aligned to normalized events when present."""

    retention = policy or CampaignEvidenceRetentionPolicy()
    universe_set = frozenset(str(symbol).strip().upper() for symbol in (universe or ()))
    by_event = _result_by_event_id(results)
    records: list[ItemEvidenceRecord] = []
    # Prefer event-aligned rows (have dispositions). Cap by policy.
    for event in events:
        if len(records) >= int(retention.max_items_per_poll):
            break
        result = by_event.get(event.event_id)
        disposition, reason = _disposition_for_result(result, universe=universe_set)
        item_like = {
            "provider_native_id": event.provider_native_id,
            "url": event.url,
            "headline": event.headline,
            "tickers": [_event_symbol(event)] if _event_symbol(event) else [],
            "published_time": event.published_time,
        }
        records.append(
            ItemEvidenceRecord(
                item_digest=digest_fetched_item(item_like),
                provider_ticker=_event_symbol(event),
                published_time=event.published_time,
                retrieved_time=event.retrieved_time,
                publication_quality=str(event.published_time_quality.value),
                pipeline_disposition=disposition,
                rejection_reason=reason or "",
                url_identifier=url_identifier(event.url) if retention.include_url_identifier else "",
                headline_redacted=(
                    redact_headline(event.headline, max_chars=retention.max_headline_chars)
                    if retention.include_redacted_headline
                    else ""
                ),
                event_id=event.event_id,
                provider_native_id=event.provider_native_id,
            )
        )
    # If normalization produced fewer rows than fetched, retain digests for extras
    # without inventing dispositions.
    if len(records) < int(retention.max_items_per_poll):
        seen_digests = {row.item_digest for row in records}
        for item in fetched_items:
            if len(records) >= int(retention.max_items_per_poll):
                break
            if not isinstance(item, Mapping):
                continue
            digest = digest_fetched_item(item)
            if digest in seen_digests:
                continue
            seen_digests.add(digest)
            tickers = item.get("tickers") or []
            ticker = ""
            if isinstance(tickers, list) and tickers:
                ticker = str(tickers[0]).strip().upper()
            records.append(
                ItemEvidenceRecord(
                    item_digest=digest,
                    provider_ticker=ticker,
                    published_time=str(item.get("published_time") or item.get("publishedAt") or ""),
                    retrieved_time=str(item.get("retrieved_time") or ""),
                    publication_quality=UNKNOWN,
                    pipeline_disposition="NOT_NORMALIZED",
                    rejection_reason=UNKNOWN,
                    url_identifier=(
                        url_identifier(str(item.get("url") or ""))
                        if retention.include_url_identifier
                        else ""
                    ),
                    headline_redacted=(
                        redact_headline(
                            str(item.get("headline") or item.get("title") or ""),
                            max_chars=retention.max_headline_chars,
                        )
                        if retention.include_redacted_headline
                        else ""
                    ),
                    provider_native_id=str(
                        item.get("provider_native_id") or item.get("id") or ""
                    ),
                )
            )
    return tuple(records)


def build_poll_evidence_envelope(
    *,
    poll_id: str,
    as_of_ns: int,
    fetched_items: Sequence[Mapping[str, Any]],
    events: Sequence[NewsArticleEvent],
    results: Sequence[PipelineEventResult],
    universe: frozenset[str] | set[str] | None = None,
    observation_window_start_ns: int | None = None,
    provider_id: str = "finviz",
    source_id: str = "finviz_elite",
    policy: CampaignEvidenceRetentionPolicy | None = None,
    include_items: bool = True,
    **summary_kwargs: Any,
) -> PollEvidenceEnvelope:
    """Compose the shared poll evidence envelope (summary + optional item digests)."""

    retention = policy or CampaignEvidenceRetentionPolicy()
    summary = build_poll_rejection_summary(
        fetched_count=len(fetched_items),
        events=events,
        results=results,
        universe=universe,
        observation_window_start_ns=observation_window_start_ns,
        **summary_kwargs,
    )
    items: tuple[ItemEvidenceRecord, ...] = ()
    if include_items:
        items = build_item_evidence_records(
            fetched_items=fetched_items,
            events=events,
            results=results,
            universe=universe,
            policy=retention,
        )
    return PollEvidenceEnvelope(
        poll_id=str(poll_id),
        as_of_ns=int(as_of_ns),
        provider_id=provider_id,
        source_id=source_id,
        rejection_summary=summary,
        items=items,
        retention_policy={
            "enabled": bool(retention.enabled),
            "max_items_per_poll": int(retention.max_items_per_poll),
            "max_polls_retained": int(retention.max_polls_retained),
            "max_headline_chars": int(retention.max_headline_chars),
            "include_url_identifier": bool(retention.include_url_identifier),
            "include_redacted_headline": bool(retention.include_redacted_headline),
            "evidence_root_configured": retention.evidence_root is not None,
        },
    )


def _manifest_sort_key(path: Path) -> tuple[int, str]:
    try:
        return (path.stat().st_mtime_ns, path.name)
    except OSError:
        return (0, path.name)


def retain_poll_evidence_manifest(
    envelope: PollEvidenceEnvelope,
    *,
    policy: CampaignEvidenceRetentionPolicy | None = None,
) -> Path | None:
    """Persist a bounded per-poll manifest when retention is explicitly enabled.

    Never writes into implicit RTH campaign trees. Opt-in only via policy/env.
    """

    retention = policy or CampaignEvidenceRetentionPolicy()
    if not retention.enabled or retention.evidence_root is None:
        return None
    if retention.max_items_per_poll <= 0 or retention.max_polls_retained <= 0:
        return None
    root = Path(retention.evidence_root)
    # Refuse any path under an rth-campaign-* directory (any date / nesting).
    if _path_contains_rth_campaign_dir(root):
        return None
    target_dir = root / "poll-evidence-manifests"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    # Cap items again at write time.
    capped = PollEvidenceEnvelope(
        poll_id=envelope.poll_id,
        as_of_ns=envelope.as_of_ns,
        provider_id=envelope.provider_id,
        source_id=envelope.source_id,
        rejection_summary=envelope.rejection_summary,
        items=tuple(envelope.items[: int(retention.max_items_per_poll)]),
        retention_policy=envelope.retention_policy,
    )
    safe_poll = re.sub(r"[^A-Za-z0-9._-]+", "_", capped.poll_id)[:96] or "poll"
    path = target_dir / f"{safe_poll}.json"
    payload = capped.to_dict()
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        return None
    # Rotate oldest manifests beyond max_polls_retained.
    try:
        manifests = sorted(target_dir.glob("*.json"), key=_manifest_sort_key)
    except OSError:
        return path
    overflow = len(manifests) - int(retention.max_polls_retained)
    for stale in manifests[: max(0, overflow)]:
        try:
            stale.unlink()
        except OSError:
            continue
    return path


__all__ = [
    "UNAVAILABLE",
    "UNKNOWN",
    "POLL_EVIDENCE_DIR_ENV",
    "POLL_EVIDENCE_RETENTION_ENABLED_ENV",
    "PROVIDER_LINKAGE_QUALITY_HOOK",
    "CampaignEvidenceRetentionPolicy",
    "ItemEvidenceRecord",
    "PollEvidenceEnvelope",
    "PollRejectionSummary",
    "build_item_evidence_records",
    "build_poll_evidence_envelope",
    "build_poll_rejection_summary",
    "digest_fetched_item",
    "redact_headline",
    "retain_poll_evidence_manifest",
    "scrub_secrets",
    "url_identifier",
]
