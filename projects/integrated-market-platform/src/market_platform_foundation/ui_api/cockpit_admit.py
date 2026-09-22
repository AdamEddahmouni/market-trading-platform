"""Admit FTEP prospective ingress into the running UI API (two-process RTH boundary).

Production RTH runs ``ftep_watch_catalysts --live-ingress`` and ``run_ui_api --serve``
as separate processes. Cockpit ranked reads come from the UI API handler store only;
this module POSTs already-fetched rows to ``POST /intelligence/ingest/news``.

``register_cockpit_replay_store`` is a **same-process test helper only** — not RTH admission.
"""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path
from typing import Any, Mapping
from urllib import request as urllib_request

from ..intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    ProspectiveCatalystIngressResult,
)
from ..news.observational_admit import finviz_export_item_from_prospective_row
from .news_ingest import NEWS_INGEST_ROUTE

DEFAULT_UI_API_BASE_URL = "http://127.0.0.1:8766"
UI_API_BASE_URL_ENV = "IMP_UI_API_BASE_URL"
FTEP_NEWS_INGEST_SOURCE_HOP = "FTEP_PROSPECTIVE_CLI"

_registered_cockpit_store: Any | None = None


def register_cockpit_replay_store(store: Any) -> Any:
    """TEST ONLY: bind handler store for same-process unit tests (not production RTH)."""

    global _registered_cockpit_store
    _registered_cockpit_store = store
    return store


def get_registered_cockpit_replay_store() -> Any | None:
    return _registered_cockpit_store


def reset_registered_cockpit_replay_store_for_tests() -> None:
    global _registered_cockpit_store
    _registered_cockpit_store = None


def resolve_ui_api_base_url() -> str:
    raw = os.environ.get(UI_API_BASE_URL_ENV, DEFAULT_UI_API_BASE_URL).strip()
    return raw.rstrip("/") or DEFAULT_UI_API_BASE_URL


def resolve_imp_collection_root(repository_root: Path) -> Path:
    """Monorepo collection root that ``ReplayStore.load()`` expects (legacy helpers)."""

    from ..intelligence.paper_forward_bridge.ftep_catalyst_watch import (
        operator_primary_imp_root_for_evidence,
    )

    imp_root = operator_primary_imp_root_for_evidence(repository_root)
    project = imp_root if imp_root is not None else repository_root
    if (project / "phase0-dependency-lock.json").is_file():
        return project.parent
    return repository_root


def _observation_window_from_ingress(
    ingress: ProspectiveCatalystIngressResult | Mapping[str, Any],
) -> tuple[str | None, int | None]:
    """Pull caller-supplied window from ingress mapping/stats when present."""

    if isinstance(ingress, ProspectiveCatalystIngressResult):
        mapping: Mapping[str, Any] = {"stats": ingress.stats}
        stats = ingress.stats if isinstance(ingress.stats, dict) else {}
    else:
        mapping = ingress
        stats = mapping.get("stats") if isinstance(mapping.get("stats"), dict) else {}
    raw_iso = mapping.get("observation_window_start")
    if raw_iso is None and isinstance(stats, dict):
        raw_iso = stats.get("observation_window_start")
    raw_ns = mapping.get("observation_window_start_ns")
    if raw_ns is None and isinstance(stats, dict):
        raw_ns = stats.get("observation_window_start_ns")
    iso = str(raw_iso).strip() if raw_iso is not None and str(raw_iso).strip() else None
    ns: int | None = None
    if raw_ns is not None and str(raw_ns).strip() != "":
        try:
            value = int(raw_ns)
        except (TypeError, ValueError):
            value = -1
        if value >= 0:
            ns = value
    return iso, ns


def build_news_ingest_body_from_prospective_ingress(
    ingress: ProspectiveCatalystIngressResult | Mapping[str, Any],
    *,
    observation_window_start: str | None = None,
    observation_window_start_ns: int | None = None,
) -> dict[str, Any]:
    """Build POST /intelligence/ingest/news body from #207 prospective rows.

    Observation window is caller-supplied only (explicit args, or fields already
    present on the ingress mapping/stats). Missing window is omitted so the
    ingest path stays ``HISTORICAL_RECONSTRUCTED``. Never invents 09:30 or other
    clock defaults.
    """

    if isinstance(ingress, ProspectiveCatalystIngressResult):
        rows = ingress.rows
    else:
        rows = tuple(ingress.get("rows") or ())
    articles: list[dict[str, Any]] = []
    default_retrieved = ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        export_item = finviz_export_item_from_prospective_row(row)
        retrieved_time = str(export_item.pop("retrieved_time", "") or "").strip()
        if retrieved_time and not default_retrieved:
            default_retrieved = retrieved_time
        article = dict(export_item)
        if retrieved_time:
            article["retrieved_time"] = retrieved_time
        published = str(row.get("published_time") or article.get("published_time") or "").strip()
        if published:
            article["published_time"] = published
        articles.append(article)
    body: dict[str, Any] = {
        "articles": articles,
        "source_hop": FTEP_NEWS_INGEST_SOURCE_HOP,
    }
    if default_retrieved:
        body["retrieved_time"] = default_retrieved
    ingress_iso, ingress_ns = _observation_window_from_ingress(ingress)
    window_iso = (
        str(observation_window_start).strip()
        if observation_window_start is not None and str(observation_window_start).strip()
        else ingress_iso
    )
    window_ns = (
        int(observation_window_start_ns)
        if observation_window_start_ns is not None
        else ingress_ns
    )
    if window_ns is not None and window_ns >= 0:
        body["observation_window_start_ns"] = int(window_ns)
    if window_iso:
        body["observation_window_start"] = window_iso
    return body


def post_prospective_ingress_to_running_ui_api(
    ingress: ProspectiveCatalystIngressResult | Mapping[str, Any],
    *,
    base_url: str | None = None,
    timeout_s: float = 30.0,
    observation_window_start: str | None = None,
    observation_window_start_ns: int | None = None,
) -> dict[str, Any]:
    """POST #207 rows to the running UI API; fail closed when the API is unreachable."""

    base = (base_url or resolve_ui_api_base_url()).rstrip("/")
    if isinstance(ingress, ProspectiveCatalystIngressResult):
        ready = ingress.ready
        reason = ingress.reason or ingress.classification
        rows = ingress.rows
    else:
        ready = bool(ingress.get("ready"))
        reason = ingress.get("reason") or ingress.get("classification")
        rows = tuple(ingress.get("rows") or ())
    if not ready:
        return {
            "ok": False,
            "reason": str(reason or "INGRESS_NOT_READY"),
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "ui_api_base_url": base,
            "transport": "HTTP",
        }
    if not rows:
        return {
            "ok": True,
            "reason": "LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS",
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "ui_api_base_url": base,
            "transport": "HTTP",
            "post_skipped": True,
        }
    body = build_news_ingest_body_from_prospective_ingress(
        ingress,
        observation_window_start=observation_window_start,
        observation_window_start_ns=observation_window_start_ns,
    )
    payload = json.dumps(body).encode("utf-8")
    url = f"{base}{NEWS_INGEST_ROUTE}"
    req = urllib_request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout_s) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {
            "ok": False,
            "reason": "UI_API_COCKPIT_ADMIT_HTTP_ERROR",
            "http_status": exc.code,
            "detail": detail[:512],
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "ui_api_base_url": base,
            "transport": "HTTP",
        }
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "reason": "UI_API_COCKPIT_ADMIT_UNREACHABLE",
            "detail": str(exc.reason or exc),
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "ui_api_base_url": base,
            "transport": "HTTP",
        }
    if status != 200:
        return {
            "ok": False,
            "reason": "UI_API_COCKPIT_ADMIT_HTTP_ERROR",
            "http_status": status,
            "detail": raw[:512],
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "ui_api_base_url": base,
            "transport": "HTTP",
        }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "reason": "UI_API_COCKPIT_ADMIT_MALFORMED_RESPONSE",
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "ui_api_base_url": base,
            "transport": "HTTP",
        }
    if not isinstance(parsed, dict):
        parsed = {}
    return {
        "ok": True,
        "reason": None,
        "admitted_count": int(parsed.get("admitted_count") or 0),
        "opportunity_count": int(parsed.get("opportunity_count") or 0),
        "skipped_count": int(parsed.get("skipped_count") or 0),
        "opportunity_ids": list(parsed.get("opportunity_ids") or []),
        "ui_api_base_url": base,
        "transport": "HTTP",
        "live_authority": False,
        "auto_fetch": False,
        "news_event_build09": "INACTIVE",
    }


# Legacy name used by early #205 commits — production callers must use HTTP helper above.
admit_prospective_catalyst_ingress_into_cockpit = post_prospective_ingress_to_running_ui_api


__all__ = [
    "DEFAULT_UI_API_BASE_URL",
    "FTEP_NEWS_INGEST_SOURCE_HOP",
    "UI_API_BASE_URL_ENV",
    "admit_prospective_catalyst_ingress_into_cockpit",
    "build_news_ingest_body_from_prospective_ingress",
    "get_registered_cockpit_replay_store",
    "post_prospective_ingress_to_running_ui_api",
    "register_cockpit_replay_store",
    "reset_registered_cockpit_replay_store_for_tests",
    "resolve_imp_collection_root",
    "resolve_ui_api_base_url",
]
