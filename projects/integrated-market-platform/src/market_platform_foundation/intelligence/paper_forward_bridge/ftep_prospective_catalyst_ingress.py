"""Opt-in Finviz Elite prospective catalyst ingress for FTEP watch (SIGNAL_ONLY, no writes)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...news.config import default_pipeline_config
from ...news.contracts import PipelineConfig
from ...news.normalize import normalize_finviz_export_item
from ...news.pipeline import NewsPipeline
from ...news.sources import SourceTrustCatalog
from ...providers.adapters.finviz_elite_context import configured_token, finviz_live_enabled
from .activation import ActivationManifest, load_activation_manifest, manifest_universe_symbols

_INGRESS_ENV = "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS"
_SOURCE_LABEL = "live:finviz_elite_prospective"


def _env_mapping(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is not None:
        return env
    return os.environ


def prospective_catalyst_ingress_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Master gate: explicit opt-in + Finviz live + configured token (fail closed)."""

    mapping = _env_mapping(env)
    if not finviz_live_enabled(mapping):
        return False
    # Pass through original env (None → process env + credential store), not mapping.
    if not configured_token(env):
        return False
    return str(mapping.get(_INGRESS_ENV, "")).strip().lower() in {"1", "true", "yes"}


def pipeline_config_from_manifest(manifest: ActivationManifest) -> PipelineConfig:
    """Frozen manifest catalyst binding → governed pipeline config (no manifest mutation)."""

    binding = manifest.raw.get("catalyst_taxonomy_binding") or {}
    if not isinstance(binding, dict):
        binding = {}
    enabled_catalysts = frozenset(
        str(item) for item in (binding.get("enabled_catalyst_ids") or []) if item
    )
    registry_version = str(binding.get("registry_version") or "news/catalysts/1.0.0")
    base = default_pipeline_config()
    return PipelineConfig(
        recency_max_age_seconds=base.recency_max_age_seconds,
        recency_reject_future_seconds=base.recency_reject_future_seconds,
        recency_unknown_publication_policy=base.recency_unknown_publication_policy,
        require_catalyst_match=True,
        source_policy_version=base.source_policy_version,
        catalyst_registry_version=registry_version,
        filter_chain_version=base.filter_chain_version,
        enabled_source_ids=frozenset({"finviz_elite"}),
        enabled_catalyst_ids=enabled_catalysts or base.enabled_catalyst_ids,
    )


def _tier_for_event(event: Any, catalog: SourceTrustCatalog) -> int:
    entry = catalog.resolve_for_event(
        source_id=event.source_id,
        publisher_source=event.publisher_source,
    )
    if entry is None:
        return 3
    return int(entry.tier)


def _pipeline_result_to_attention_row(result: Any, *, tier: int) -> dict[str, object]:
    event = result.event
    symbol = ""
    if event.instrument_linkages:
        symbol = str(event.instrument_linkages[0].instrument_id or "").upper()
    catalyst_ids: tuple[str, ...] = ()
    for decision in result.decisions:
        if decision.matched_catalyst_ids:
            catalyst_ids = decision.matched_catalyst_ids
            break
    return {
        "attention_id": f"att-live-{event.event_id[:24]}",
        "symbol": symbol,
        "headline": event.headline,
        "tier": tier,
        "catalyst_ids": catalyst_ids,
        "attention_data_kind": "LIVE_PROSPECTIVE",
        "provider_id": event.provider_id,
        "source_id": event.source_id,
        "published_time": event.published_time,
        "retrieved_time": event.retrieved_time,
        "source_event_id": event.event_id,
    }


@dataclass(frozen=True)
class ProspectiveCatalystIngressResult:
    attempted: bool
    ready: bool
    reason: str | None
    source_label: str
    rows: tuple[dict[str, object], ...]
    stats: dict[str, object]
    fetch_error: str | None = None

    def to_report_dict(self) -> dict[str, object]:
        return {
            "attempted": self.attempted,
            "ready": self.ready,
            "reason": self.reason,
            "source_label": self.source_label,
            "row_count": len(self.rows),
            "stats": self.stats,
            "fetch_error": self.fetch_error,
            "test_mode": "SIGNAL_ONLY",
            "durable_lock": False,
        }


def collect_finviz_prospective_attention_rows(
    repository_root: Path,
    campaign_slug: str,
    *,
    live_ingress: bool,
    news_client: Any | None = None,
    as_of_ns: int | None = None,
    env: Mapping[str, str] | None = None,
) -> ProspectiveCatalystIngressResult:
    """Fetch Finviz news at ingest time, normalize, filter, map to attention rows."""

    empty_stats: dict[str, object] = {}
    if not live_ingress:
        return ProspectiveCatalystIngressResult(
            attempted=False,
            ready=False,
            reason="LIVE_INGRESS_NOT_REQUESTED",
            source_label="",
            rows=(),
            stats=empty_stats,
        )
    if not prospective_catalyst_ingress_enabled(env):
        return ProspectiveCatalystIngressResult(
            attempted=True,
            ready=False,
            reason="INGRESS_GATES_INACTIVE",
            source_label="",
            rows=(),
            stats=empty_stats,
        )

    manifest = load_activation_manifest(campaign_slug)
    universe = frozenset(manifest_universe_symbols(manifest))
    pipeline_config = pipeline_config_from_manifest(manifest)
    catalog = SourceTrustCatalog()
    pipeline = NewsPipeline()
    as_of = as_of_ns if as_of_ns is not None else time.time_ns()

    if news_client is None:
        from ...finviz.news import FinvizNewsClient

        token = configured_token(env)
        news_client = FinvizNewsClient(api_key=token)

    fetch = news_client.fetch_news(force=True)
    if not fetch.get("success"):
        return ProspectiveCatalystIngressResult(
            attempted=True,
            ready=False,
            reason="FINVIZ_FETCH_FAILED",
            source_label="",
            rows=(),
            stats=empty_stats,
            fetch_error=str(fetch.get("error") or "UNKNOWN"),
        )

    received_at = str(fetch.get("received_at") or "")
    items = [item for item in (fetch.get("items") or []) if isinstance(item, dict)]
    events = [
        normalize_finviz_export_item(item, retrieved_time=received_at) for item in items
    ]
    results = pipeline.process(events, as_of_ns=as_of, config=pipeline_config)
    rows: list[dict[str, object]] = []
    ingested = len(events)
    accepted = 0
    universe_filtered = 0
    for result in results:
        if not result.accepted:
            continue
        row = _pipeline_result_to_attention_row(
            result,
            tier=_tier_for_event(result.event, catalog),
        )
        symbol = str(row.get("symbol") or "")
        if universe and symbol not in universe:
            universe_filtered += 1
            continue
        if not symbol:
            continue
        accepted += 1
        rows.append(row)

    stats = {
        "as_of_ns": as_of,
        "ingested_events": ingested,
        "accepted_pipeline_events": accepted,
        "universe_filtered": universe_filtered,
        "manifest_universe_size": len(universe),
        "pipeline_config": pipeline_config.to_dict(),
    }
    return ProspectiveCatalystIngressResult(
        attempted=True,
        ready=True,
        reason=None,
        source_label=_SOURCE_LABEL,
        rows=tuple(rows),
        stats=stats,
    )


__all__ = [
    "ProspectiveCatalystIngressResult",
    "collect_finviz_prospective_attention_rows",
    "pipeline_config_from_manifest",
    "prospective_catalyst_ingress_enabled",
]
