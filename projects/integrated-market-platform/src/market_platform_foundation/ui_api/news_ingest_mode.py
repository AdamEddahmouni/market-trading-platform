"""Select IngestionMode for POST /intelligence/ingest/news Finviz admits.

Live receipt (``LIVE_OBSERVED``) requires active campaign live gates, a caller-
supplied observation window, and a trustworthy publication time at or after that
window. Everything else fails closed to ``HISTORICAL_RECONSTRUCTED``. Publication
before the window and live gates are independent facts — never collapse them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from ..intelligence.normalization.models import IngestionMode
from ..intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    prospective_catalyst_ingress_gates_active,
)
from ..news.contracts import PublicationTimeQuality
from ..news.timestamps import epoch_ns_from_iso
from ..providers.adapters.finviz_elite_context import finviz_live_enabled

_LIVE_OBSERVATIONAL_ENV = "IMP_LIVE_OBSERVATIONAL"


def news_ingest_live_gates_active(env: Mapping[str, str] | None = None) -> bool:
    """True when campaign live-prospective Finviz ingress gates are all set.

    Requires ``IMP_LIVE_OBSERVATIONAL``, ``IMP_FINVIZ_LIVE``, and
    ``IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS`` (via prospective ingress gate helper).
    """

    mapping: Mapping[str, str] = env if env is not None else os.environ
    if str(mapping.get(_LIVE_OBSERVATIONAL_ENV, "")).strip() != "1":
        return False
    if not finviz_live_enabled(mapping):
        return False
    return prospective_catalyst_ingress_gates_active(mapping)


def parse_observation_window_start_ns(body: Mapping[str, Any]) -> int | None:
    """Caller-supplied observation window start. Invalid values fail closed to None."""

    raw_ns = body.get("observation_window_start_ns")
    if raw_ns is not None and str(raw_ns).strip() != "":
        try:
            value = int(raw_ns)
        except (TypeError, ValueError):
            return None
        if value < 0:
            return None
        return value
    raw_iso = body.get("observation_window_start")
    if raw_iso is None:
        return None
    text = str(raw_iso).strip()
    if not text:
        return None
    return epoch_ns_from_iso(text)


def select_news_ingest_ingestion_mode(
    *,
    published_time_ns: int | None,
    published_time_quality: PublicationTimeQuality | str | None,
    observation_window_start_ns: int | None,
    live_gates_active: bool,
) -> IngestionMode:
    """Fail-closed mode stamp for the HTTP Finviz news ingest path.

    ``LIVE_OBSERVED`` only when:
    - live prospective gates are active, and
    - observation window start is supplied, and
    - publication time is trustworthy (``KNOWN``), and
    - publication/event time is not before the observation window.

    Missing/unknown/inferred publication, missing window, inactive gates, or
    publication before the window → ``HISTORICAL_RECONSTRUCTED``.
    """

    if not live_gates_active:
        return IngestionMode.HISTORICAL_RECONSTRUCTED
    if observation_window_start_ns is None:
        return IngestionMode.HISTORICAL_RECONSTRUCTED
    if published_time_ns is None:
        return IngestionMode.HISTORICAL_RECONSTRUCTED
    quality = (
        published_time_quality
        if isinstance(published_time_quality, PublicationTimeQuality)
        else PublicationTimeQuality(str(published_time_quality or PublicationTimeQuality.UNKNOWN.value))
    )
    if quality != PublicationTimeQuality.KNOWN:
        return IngestionMode.HISTORICAL_RECONSTRUCTED
    if int(published_time_ns) < int(observation_window_start_ns):
        return IngestionMode.HISTORICAL_RECONSTRUCTED
    return IngestionMode.LIVE_OBSERVED


__all__ = [
    "news_ingest_live_gates_active",
    "parse_observation_window_start_ns",
    "select_news_ingest_ingestion_mode",
]
