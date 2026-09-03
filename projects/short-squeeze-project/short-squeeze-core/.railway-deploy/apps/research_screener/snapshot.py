"""Assembles what the interface shows, per mode.

This is the controller. It selects a source, labels the result, and never computes a
metric, a rule outcome, a score or a ranking.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def _with_timeout(fn, timeout: float = 3.0, default=None):
    """Call ``fn()`` in a thread; return ``default`` if it does not finish in time."""
    result = [default]
    exc = []

    def _worker():
        try:
            result[0] = fn()
        except Exception as e:  # noqa: BLE001
            exc.append(e)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return default
    if exc:
        raise exc[0]
    return result[0]

from . import live as live_mode
from . import providers
from .frozen import FROZEN_MODE_LABEL, FrozenResearchUnavailable, get_frozen_source
from .truth import DataMode, Freshness, ValueStatus, known
from . import data_logger

import json
import logging
from functools import lru_cache
from pathlib import Path

_enrich_log = logging.getLogger("squeeze.screener.enrichment")

#: Path to the JSON policy file that controls Finviz enrichment field mappings.
_FINVIZ_ENRICHMENT_POLICY_PATH = (
    Path(__file__).resolve().parent / "policies" / "finviz_enrichment_policy.json"
)

#: Path to the JSON policy file that controls NewsAPI enrichment field mappings.
_NEWSAPI_ENRICHMENT_POLICY_PATH = (
    Path(__file__).resolve().parent / "policies" / "newsapi_enrichment_policy.json"
)

#: Path to the JSON policy file that controls Finnhub enrichment field mappings.
_FINNHUB_ENRICHMENT_POLICY_PATH = (
    Path(__file__).resolve().parent / "policies" / "finnhub_enrichment_policy.json"
)

APP_TITLE = "Short Squeeze Research Screener"
DISCLAIMER = "RESEARCH TOOL"
SCHEMA_VERSION = "1.0.0"

#: Sort keys the interface offers. There is deliberately no score, rank or probability key.
SORT_KEYS = (
    "symbol",
    "pass_count",
    "fail_count",
    "unknown_count",
    "research_detection",
    "data_mode",
    "freshness",
    "percentage_change",
    "last",
    "relative_volume",
    "days_to_cover",
    "news_count",
    "sentiment",
    "evidence_coverage",
    "updated",
    "provider_scanner_order",
)

#: Sort keys whose value comes from a possibly-missing evidence cell. Missing sorts last
#: in both directions; it is never coerced to zero.
_FIELD_SORT_KEYS = {
    "percentage_change": "percentage_change",
    "last": "last",
    "relative_volume": "relative_volume",
    "days_to_cover": "days_to_cover",
    "news_count": "news_count",
}


class Mode(StrEnum):
    FROZEN_RESEARCH = "FROZEN_RESEARCH"
    CURRENT = "CURRENT"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _known_field_float(row: dict[str, Any], name: str) -> float | None:
    cell = row.get("fields", {}).get(name) or {}
    if cell.get("status") != "KNOWN":
        return None
    value = cell.get("value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _days_to_cover_float(row: dict[str, Any]) -> float | None:
    for name in ("days_to_cover", "short_ratio", "short_ratio_provider"):
        value = _known_field_float(row, name)
        if value is not None:
            return value
    return None


def _sort_value(row: dict[str, Any], key: str) -> tuple[int, Any]:
    """``(missing_flag, value)``. ``missing_flag`` is 1 for absent, so missing sorts last."""
    counts = row["phase3a"]["counts"]
    if key in _FIELD_SORT_KEYS:
        if key == "days_to_cover":
            value = _days_to_cover_float(row)
        else:
            value = _known_field_float(row, _FIELD_SORT_KEYS[key])
        # Missing is never coerced to zero; it is flagged and pushed to the end.
        return (1, 0.0) if value is None else (0, value)
    if key == "sentiment":
        cell = row.get("fields", {}).get("sentiment") or {}
        value = cell.get("value")
        if value is None:
            return (1, 9)
        order = {"POSITIVE": 0, "MIXED": 1, "NEUTRAL": 2, "NEGATIVE": 3}
        return (0, order.get(str(value).upper(), 9))
    if key == "updated":
        value = row.get("last_updated")
        return (1, "") if not value else (0, str(value))
    if key == "provider_scanner_order":
        value = row.get("provider_scanner_order")
        return (1, 0) if value is None else (0, int(value))
    if key == "evidence_coverage":
        return (0, row["evidence_coverage"]["supported"])
    simple = {
        "symbol": row["symbol"],
        "pass_count": counts.get("PASS", 0),
        "fail_count": counts.get("FAIL", 0),
        "unknown_count": counts.get("UNKNOWN", 0),
        "research_detection": row["research_detection"]["status"],
        "data_mode": row["data_mode"],
        "freshness": row["freshness"],
    }
    return (0, simple.get(key, row["symbol"]))


def sort_rows(rows: list[dict[str, Any]], key: str, descending: bool = False) -> list[dict[str, Any]]:
    """Sort by an evidence-bearing column. Rows with no value always sort last."""
    if key not in SORT_KEYS:
        key = "symbol"

    def ordering(row: dict[str, Any]):
        missing, value = _sort_value(row, key)
        # ``missing`` is negated under reverse so absent values stay at the bottom in
        # both directions rather than flipping to the top.
        return (-missing if descending else missing, value, row["symbol"])

    return sorted(rows, key=ordering, reverse=descending)


def _cell_value(row: dict[str, Any], name: str) -> float | None:
    return _known_field_float(row, name)


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    symbol: str | None = None,
    research_detection: str | None = None,
    data_mode: str | None = None,
    freshness: str | None = None,
    discovery_profile: str | None = None,
    market_data_mode: str | None = None,
    min_pass: int | None = None,
    max_unknown: int | None = None,
    min_coverage: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_percentage_change: float | None = None,
    min_relative_volume: float | None = None,
) -> list[dict[str, Any]]:
    """Filter on evidence-bearing columns.

    A numeric filter excludes rows whose value is *missing*: a row with no observed price
    cannot be asserted to fall inside a price band. It is excluded from that filtered view,
    never silently treated as zero and never counted as satisfying the bound.
    """
    out = rows
    if symbol:
        needle = symbol.strip().upper()
        out = [row for row in out if needle in row["symbol"]]
    if research_detection:
        out = [row for row in out if row["research_detection"]["status"] == research_detection]
    if data_mode:
        out = [row for row in out if row["data_mode"] == data_mode]
    if freshness:
        out = [row for row in out if row["freshness"] == freshness]
    if discovery_profile:
        out = [row for row in out if row.get("discovery_profile") == discovery_profile]
    if market_data_mode:
        out = [row for row in out if row.get("market_data_mode") == market_data_mode]
    if min_pass is not None:
        out = [row for row in out if row["phase3a"]["counts"].get("PASS", 0) >= min_pass]
    if max_unknown is not None:
        out = [row for row in out if row["phase3a"]["counts"].get("UNKNOWN", 0) <= max_unknown]
    if min_coverage is not None:
        out = [row for row in out if row["evidence_coverage"]["supported"] >= min_coverage]

    numeric = (
        ("last", min_price, max_price),
        ("percentage_change", min_percentage_change, None),
        ("relative_volume", min_relative_volume, None),
    )
    for name, low, high in numeric:
        if low is None and high is None:
            continue
        kept = []
        for row in out:
            value = _cell_value(row, name)
            if value is None and name == "last":
                # Fall back to the labelled historical close, which is the same evidence
                # the current price rule uses when no quote tick arrived.
                value = _cell_value(row, "historical_close")
            if value is None:
                continue
            if low is not None and value < low:
                continue
            if high is not None and value > high:
                continue
            kept.append(row)
        out = kept
    return out


def header(mode: Mode, *, mode_label: str, extra_banners: list[str] | None = None) -> dict[str, Any]:
    return {
        "title": APP_TITLE,
        "disclaimer": DISCLAIMER,
        "mode": str(mode),
        "mode_label": mode_label,
        "banners": extra_banners or [],
        "generated_at": _now(),
        "schema_version": SCHEMA_VERSION,
    }


def _enrichment_provider_status() -> dict[str, Any]:
    """Collect current provider status for archival alongside snapshots."""
    try:
        from .live_providers import get_runtime
        return get_runtime().status()
    except (ImportError, ModuleNotFoundError):
        return {}


def frozen_snapshot() -> dict[str, Any]:
    """MODE A payload. Works with every provider down."""
    source = get_frozen_source()
    if not source.available:
        from .frozen_demo import frozen_demo_snapshot

        return frozen_demo_snapshot()
    rows = source.screener_rows()
    _enrich_frozen_rows_with_finviz(rows)
    _enrich_frozen_rows_with_newsapi(rows)
    _enrich_frozen_rows_with_finnhub(rows)
    # Archive the complete enriched frozen view for replay.
    try:
        data_logger.log_full_snapshot(
            "FROZEN_RESEARCH", rows,
            provider_status=_enrichment_provider_status(),
        )
    except Exception:
        pass
    summary = source.summary
    research = source.research_summary()
    return {
        "header": header(
            Mode.FROZEN_RESEARCH,
            mode_label=FROZEN_MODE_LABEL,
            extra_banners=[
                "Real historical research data. Not synthetic, not a replay.",
                f"Global acquisition preflight: {summary['global_preflight_verdict']}",
            ],
        ),
        "rows": rows,
        "row_count": len(rows),
        "boundary_time": source.boundary_time,
        "policy_version": summary["phase3a_policy_version"],
        "evaluation_version": summary["phase3a_evaluation_version"],
        "global_preflight_verdict": summary["global_preflight_verdict"],
        "outcome_totals": research["outcome_totals"],
        "phase3e_started": research["phase3e_started"],
        "sort_keys": list(SORT_KEYS),
    }


def frozen_detail(symbol: str) -> dict[str, Any] | None:
    source = get_frozen_source()
    if not source.available:
        from .frozen_demo import frozen_demo_detail

        return frozen_demo_detail(symbol)
    detail = source.detail(symbol)
    if detail is None:
        return None
    # Enrich the detail drawer's market-data block with live Finviz fields.
    _enrich_detail_market_data(detail)
    _enrich_detail_market_data_newsapi(detail)
    _enrich_detail_market_data_finnhub(detail)
    detail["chart"] = source.chart(symbol)
    detail["header"] = header(Mode.FROZEN_RESEARCH, mode_label=FROZEN_MODE_LABEL)
    return detail


def research_summary() -> dict[str, Any]:
    """Two separate panels. Historical and current statistics are never combined."""
    from . import session_state

    source = get_frozen_source()
    historical = source.research_summary()
    historical["panel"] = "FROZEN RESEARCH RESULTS"

    session = session_state.get_session()
    current = session.summary()
    current["panel"] = "CURRENT OPERATIONAL SCREEN"

    return {
        "header": header(Mode.FROZEN_RESEARCH, mode_label=FROZEN_MODE_LABEL),
        "historical_research": historical,
        "current_operational_screen": current,
        "separation_note": (
            "These two panels are reported separately and are never summed. The 13 frozen "
            "cases are a fixed research cohort with frozen Batch 08 outcomes. Current "
            "candidates are ephemeral snapshots of whatever the provider scanner returned "
            "moments ago; combining them would create a selection effect and would not "
            "mean anything."
        ),
        # Kept at the top level so the existing Batch 10 consumers keep working.
        **{key: value for key, value in historical.items() if key != "panel"},
    }


def health(
    *,
    cloud_mode: bool = False,
    deployment_mode: str | None = None,
) -> dict[str, Any]:
    """Provider health. Never claims availability from the presence of code."""
    from . import session_state

    session = session_state.get_session()
    try:
        frozen_available = get_frozen_source().available
    except Exception:  # noqa: BLE001
        frozen_available = False
    if not frozen_available:
        from .frozen_demo import load_frozen_demo
        frozen_available = bool(load_frozen_demo()["rows"])

    from .provider_session import CloudUnavailableProvider
    from .config import resolve_application_config

    ibkr_enabled = resolve_application_config(
        cli=(
            {"SQUEEZE_APP_MODE": deployment_mode}
            if deployment_mode
            else (
                {"SQUEEZE_APP_MODE": "CLOUD_PROVIDER_MODE"}
                if cloud_mode
                else None
            )
        ),
    ).providers.ibkr.enabled
    if isinstance(session.provider, CloudUnavailableProvider) or (
        cloud_mode and not ibkr_enabled
    ):
        cloud_detail = (
            "IBKR is disabled for this cloud deployment. Set IBKR_ENABLED=true and "
            "configure IBKR_HOST, IBKR_PORT, and IBKR_CLIENT_ID."
        )
        entries = [
            {"name": "IB Gateway", "state": "UNAVAILABLE", "detail": cloud_detail},
            {"name": "Market Data", "state": "UNAVAILABLE", "detail": cloud_detail},
            {"name": "Historical Bars", "state": "UNAVAILABLE", "detail": cloud_detail},
            {
                "name": "Frozen Research Artifacts",
                "state": "AVAILABLE" if frozen_available else "UNAVAILABLE",
                "detail": "Sanitized frozen demo is available in the deployment image.",
            },
        ]
    else:
        entries = providers.provider_health(frozen_available=frozen_available)

    try:
        call_statuses = _with_timeout(
            lambda: session.provider.statuses(), timeout=3.0, default=[],
        )
        if call_statuses is None:
            call_statuses = []
    except Exception:  # noqa: BLE001 - health must never fail
        call_statuses = []

    result = {
        "providers": entries,
        "provider_calls": call_statuses,
        "probed_at": _now(),
        "frozen_research_available": frozen_available,
        "current_mode_available": any(
            entry["name"] == "IB Gateway" and entry["state"] == "CONNECTED" for entry in entries
        ),
        "market_data_mode": session.summary().get("market_data_mode", "UNKNOWN"),
        "auto_refresh": session.auto_refresh,
        "readiness": demo_readiness(),
    }

    if not cloud_mode and entries:
        from . import data_logger
        data_logger.log_provider_status(result)

    return result


CURRENT_BANNERS = [
    "Current candidates are an EXPERIMENTAL RESEARCH SCREEN. They are not research cases, "
    "are never outcome-labelled.",
    "Rule outcomes here are computed by the same canonical 25-rule Phase 3A evaluator used "
    "for the frozen cases, over current evidence only. Missing evidence stays UNKNOWN.",
]


def current_snapshot(symbols: list[str] | None = None, *, refresh: bool = False) -> dict[str, Any]:
    """The current operational screen. Degrades to an explanatory payload, never to fake data."""
    from . import session_state

    session = session_state.get_session()
    errors: list[dict[str, str]] = []
    if symbols:
        for raw in symbols:
            try:
                live_mode.normalize_symbol(raw)
            except live_mode.InvalidSymbolError as exc:
                errors.append({"input": raw, "error": str(exc)})
        session.add_manual_symbols(symbols)
        if refresh:
            for raw in symbols:
                try:
                    session.refresh_symbol(live_mode.normalize_symbol(raw))
                except live_mode.InvalidSymbolError:
                    continue

    rows = session.rows()
    summary = session.summary()
    label = (
        session_state.CURRENT_MODE_LABEL
        if rows
        else "CURRENT DISCOVERY — NO CANDIDATES YET"
    )
    return {
        "header": header(Mode.CURRENT, mode_label=label, extra_banners=CURRENT_BANNERS),
        "rows": rows,
        "row_count": len(rows),
        "available": bool(rows),
        "errors": errors,
        "reason": None
        if rows
        else (
            "No current candidates yet. Run discovery, or enter one or more ticker symbols. "
            "Frozen Research mode does not depend on any of this."
        ),
        "summary": summary,
        "profiles": [profile.as_dict() for profile in session.profiles.values()],
        "sort_keys": list(SORT_KEYS),
    }


def current_detail(symbol: str) -> dict[str, Any]:
    """Detail for one current candidate, including the full 25-rule table."""
    from . import session_state

    session = session_state.get_session()
    normalized = symbol.strip().upper()
    if normalized not in session.states:
        session.add_manual_symbols([normalized])
        session.refresh_symbol(normalized)
    detail = session.detail(normalized)
    if detail is None:
        return {
            "header": header(Mode.CURRENT, mode_label="CURRENT — SYMBOL NOT TRACKED",
                             extra_banners=CURRENT_BANNERS),
            "available": False,
            "error": f"{normalized} is not a tracked current candidate.",
        }
    detail["header"] = header(
        Mode.CURRENT, mode_label=session_state.CURRENT_MODE_LABEL,
        extra_banners=CURRENT_BANNERS,
    )
    return detail


def discovery_refresh(profile_id: str | None = None) -> dict[str, Any]:
    """Re-run provider discovery. Falls back to Finviz screener if IBKR fails."""
    from . import session_state

    session = session_state.get_session()
    if profile_id:
        session.set_profile(profile_id)

    # Try IBKR discovery first
    result = session.refresh_discovery(profile_id)
    discovered = result.get("discovered", 0)
    error = result.get("error")

    # Fall back to Finviz screener if IBKR failed or returned nothing
    if (discovered == 0 or error) and _finviz_fallback_available():
        fv_result = _finviz_discovery_fallback(session)
        if fv_result.get("discovered", 0) > 0:
            result["discovered"] = fv_result["discovered"]
            result["source"] = "FINVIZ_FALLBACK"
            result["fallback_note"] = (
                "IBKR scanner was unavailable or returned no results. "
                "Discovery fell back to authenticated Finviz Elite screener export."
            )
            if error:
                result["ibkr_error"] = error
                result.pop("error", None)

    result["summary"] = session.summary()
    return result


def _finviz_fallback_available() -> bool:
    """Check if Finviz screener fallback is configured and has data."""
    from .live_providers import get_runtime
    runtime = get_runtime()
    return runtime.finviz.configured


def _finviz_discovery_fallback(session) -> dict[str, Any]:
    """Use Finviz Elite screener export as a fallback discovery source."""
    from .live_providers import get_runtime
    from .discovery import CurrentDiscoveryCandidate

    runtime = get_runtime()
    fv = runtime.finviz

    try:
        fv_response = fv.fetch_screener(force=False)
        if not fv_response.get("success"):
            return {"discovered": 0, "error": fv_response.get("error", "Finviz fetch failed")}
    except Exception as exc:
        return {"discovered": 0, "error": f"Finviz fallback error: {type(exc).__name__}: {exc}"}

    rows = fv.get_cached_rows()
    # Filter to top gainers with reasonable price (mimics discovery intent)
    candidates = []
    for row in rows:
        if not row.ticker or not row.price or row.price <= 0:
            continue
        if row.price > 200:  # Reasonable price band
            continue
        candidates.append(
            CurrentDiscoveryCandidate(
                symbol=row.ticker,
                profile_id="FINVIZ_FALLBACK",
                long_name=row.company or "",
                provider_rank=len(candidates) + 1,
            )
        )
        if len(candidates) >= 25:
            break

    if candidates:
        # Sort by change% descending (top gainers first)
        candidates.sort(
            key=lambda c: (
                next((r.change_pct or 0 for r in rows if r.ticker == c.symbol), 0)
            ),
            reverse=True,
        )
        # Re-rank
        for i, c in enumerate(candidates):
            c.provider_rank = i + 1

    # Add to session as manual candidates (they'll get enriched on next refresh)
    symbols = [c.symbol for c in candidates[:15]]
    if symbols:
        session.add_manual_symbols(symbols)

    return {
        "discovered": len(candidates[:15]),
        "total_available": len(candidates),
        "source": "Finviz Elite",
    }


def _enrich_frozen_rows_with_finviz(rows: list[dict[str, Any]]) -> None:
    """Replace NOT_COLLECTED frozen fields with live Finviz Elite data.

    Frozen research cases were collected before Finviz Elite was configured.
    This enriches the display snapshot with current Finviz data so every
    column shows real values instead of dashes.

    The enrichment is purely cosmetic: research admissibility is explicitly
    marked NOT_ADMISSIBLE_FOR_RESEARCH so no consumer mistakes live
    enrichment data for frozen research evidence.

    Field mappings are driven by ``finviz_enrichment_policy.json``.
    """
    try:
        from .live_providers import get_runtime

        runtime = get_runtime()
        finviz = runtime.finviz
        if not finviz.configured:
            return

        # Fetch screener (force=False uses cache if fresh)
        finviz.fetch_screener(force=False)

        now_iso = _now()
        matched = 0

        for row in rows:
            symbol = row["symbol"]
            fv_row = finviz.get_row(symbol)
            if fv_row is None:
                continue
            matched += 1

            existing: dict[str, Any] = row["fields"]
            try:
                _apply_finviz_enrichment(existing, fv_row, symbol, now_iso)
            except Exception:
                _enrich_log.debug(
                    "Finviz enrichment failed for row %s", symbol, exc_info=True,
                )

            # Also add company/sector/industry context for the detail drawer
            if fv_row.company:
                existing["finviz_company"] = known(
                    fv_row.company, unit="TEXT", provider="Finviz Elite",
                    event_time=now_iso, received_time=now_iso,
                    freshness=Freshness.CURRENT, data_mode=DataMode.HISTORICAL,
                    evidence_id=f"finviz:{symbol}:company:{now_iso}",
                    readiness="DISPLAY_ONLY",
                ).as_dict()

        if matched:
            _enrich_log.info("Finviz enriched %d/%d frozen rows", matched, len(rows))
            try:
                data_logger.log_enrichment_event(
                    "Finviz Elite", "frozen_snapshot",
                    matched_count=matched, total_rows=len(rows),
                    frozen_keys=[m["frozen_key"] for m in _load_finviz_enrichment_policy()],
                )
            except Exception:
                pass

    except Exception as exc:
        # Never break the frozen snapshot for enrichment failure.
        # The frozen data is always the authoritative fallback.
        _enrich_log.warning("Finviz frozen enrichment failed: %s", exc)


def _enrich_detail_market_data(detail: dict[str, Any]) -> None:
    """Enrich the detail drawer's market-data block with live Finviz fields.

    Same enrichment as ``_enrich_frozen_rows_with_finviz`` but operates on the
    detail payload's ``market_data`` dict (a flat ``{field_key: field_dict}``
    rather than a row).
    """
    try:
        from .live_providers import get_runtime

        runtime = get_runtime()
        finviz = runtime.finviz
        if not finviz.configured:
            return

        symbol = (detail.get("identity") or {}).get("symbol", "")

        # Fetch first to populate cache, then look up
        finviz.fetch_screener(force=False)
        fv_row = finviz.get_row(symbol)
        if fv_row is None:
            return

        now_iso = _now()
        market = detail.get("market_data") or {}
        _apply_finviz_enrichment(market, fv_row, symbol, now_iso)
    except Exception as exc:
        _enrich_log.warning("Finviz detail enrichment failed for %s: %s",
                           (detail.get("identity") or {}).get("symbol", "?"), exc)


def _load_enrichment_policy(
    path: Path,
    provider_name: str,
    fallback_mappings: list[dict[str, str]],
    *,
    attr_key: str = "provider_attr",
    alt_attr_key: str | None = None,
) -> list[dict[str, str]]:
    """Load enrichment mappings from a JSON policy file.

    Returns a list of mapping dicts.  Falls back to *fallback_mappings* if the
    file is missing, unreadable, or invalid — the screener must never break
    because of a missing policy file.

    Each mapping dict in the returned list is normalised to have the key
    *attr_key* (default ``"provider_attr"``).  If the JSON uses *alt_attr_key*
    instead (e.g. ``"finviz_attr"``), that value is promoted to *attr_key* so
    callers always read a single key.

    This function is NOT cached — the per-provider wrappers each apply their
    own :func:`lru_cache` so policy-file changes require a server restart.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
        mappings = doc.get("mappings", [])
        if mappings:
            # Normalise attribute key so callers always read attr_key.
            if alt_attr_key:
                for m in mappings:
                    if alt_attr_key in m and attr_key not in m:
                        m[attr_key] = m.pop(alt_attr_key)
            _enrich_log.info(
                "Loaded %s enrichment policy v%s with %d mapping(s)",
                provider_name, doc.get("policy_version", "?"), len(mappings),
            )
            return mappings
    except Exception as exc:
        _enrich_log.warning(
            "%s enrichment policy file missing or invalid (%s). "
            "Using hardcoded defaults.", provider_name, exc,
        )
    return list(fallback_mappings)


@lru_cache(maxsize=1)
def _load_finviz_enrichment_policy() -> list[dict[str, str]]:
    """Load Finviz enrichment mappings from the JSON policy file.

    Returns a list of mapping dicts, each with keys:
    ``provider_attr``, ``frozen_key``, ``unit``, ``readiness``.

    Falls back to hardcoded defaults if the file is missing, unreadable, or
    invalid — the screener must never break because of a missing policy file.

    The result is cached with ``lru_cache(maxsize=1)``.  Policy-file changes
    require a server restart to take effect.
    """
    # Hardcoded fallback — keep in sync with finviz_enrichment_policy.json.
    _FINVIZ_FALLBACK = [
        {"provider_attr": "float_shares", "frozen_key": "float_shares",
         "unit": "SHARES", "readiness": "PROVIDER_SNAPSHOT_FLOAT_FINVIZ"},
        {"provider_attr": "short_float_pct", "frozen_key": "short_float",
         "unit": "PERCENT", "readiness": "PROVIDER_SNAPSHOT_SHORT_FLOAT_FINVIZ"},
        {"provider_attr": "short_ratio", "frozen_key": "short_ratio",
         "unit": "RATIO", "readiness": "PROVIDER_SNAPSHOT_SHORT_RATIO_FINVIZ"},
        {"provider_attr": "rel_volume", "frozen_key": "relative_volume",
         "unit": "RATIO", "readiness": "PROVIDER_SNAPSHOT_REL_VOLUME_FINVIZ"},
        {"provider_attr": "price", "frozen_key": "reference_price",
         "unit": "PRICE", "readiness": "PROVIDER_SNAPSHOT_PRICE_FINVIZ"},
        {"provider_attr": "market_cap", "frozen_key": "market_cap",
         "unit": "USD", "readiness": "PROVIDER_SNAPSHOT_MARKET_CAP_FINVIZ"},
    ]
    return _load_enrichment_policy(
        _FINVIZ_ENRICHMENT_POLICY_PATH,
        "Finviz",
        _FINVIZ_FALLBACK,
        attr_key="provider_attr",
        alt_attr_key="finviz_attr",
    )


@lru_cache(maxsize=1)
def _load_newsapi_enrichment_policy() -> list[dict[str, str]]:
    """Load NewsAPI enrichment mappings from the JSON policy file.

    The result is cached with ``lru_cache(maxsize=1)``.  Policy-file changes
    require a server restart to take effect.
    """
    # Hardcoded fallback — keep in sync with newsapi_enrichment_policy.json.
    _NEWSAPI_FALLBACK = [
        {"provider_attr": "headline_count", "frozen_key": "catalyst",
         "unit": "HEADLINE_COUNT", "readiness": "PROVIDER_SNAPSHOT_CATALYST_NEWSAPI"},
        {"provider_attr": "headline_count", "frozen_key": "news_count",
         "unit": "HEADLINE_COUNT", "readiness": "PROVIDER_SNAPSHOT_NEWS_COUNT_NEWSAPI"},
    ]
    return _load_enrichment_policy(
        _NEWSAPI_ENRICHMENT_POLICY_PATH,
        "NewsAPI",
        _NEWSAPI_FALLBACK,
    )


@lru_cache(maxsize=1)
def _load_finnhub_enrichment_policy() -> list[dict[str, str]]:
    """Load Finnhub enrichment mappings from the JSON policy file.

    The result is cached with ``lru_cache(maxsize=1)``.  Policy-file changes
    require a server restart to take effect.
    """
    # Hardcoded fallback — keep in sync with finnhub_enrichment_policy.json.
    _FINNHUB_FALLBACK = [
        {"provider_attr": "price", "frozen_key": "finnhub_price",
         "unit": "PRICE", "readiness": "PROVIDER_SNAPSHOT_PRICE_FINNHUB"},
    ]
    return _load_enrichment_policy(
        _FINNHUB_ENRICHMENT_POLICY_PATH,
        "Finnhub",
        _FINNHUB_FALLBACK,
    )


def enrichment_policies_summary() -> dict[str, Any]:
    """Return a summary of all enrichment policy files.

    Reads each JSON policy file directly (NOT through the cached loaders) so
    the response always reflects the current file contents.  This lets the
    integration team verify their JSON edits before restarting the server.

    Returns a dict with keys ``policies`` (list of per-provider summaries),
    ``total_mappings``, ``provider_count``, and ``generated_at``.
    """
    policy_defs: list[tuple[str, Path, str]] = [
        ("Finviz Elite", _FINVIZ_ENRICHMENT_POLICY_PATH, "finviz_attr"),
        ("NewsAPI", _NEWSAPI_ENRICHMENT_POLICY_PATH, "provider_attr"),
        ("Finnhub", _FINNHUB_ENRICHMENT_POLICY_PATH, "provider_attr"),
    ]

    policies: list[dict[str, Any]] = []
    total_mappings = 0

    for provider_name, path, attr_key in policy_defs:
        try:
            raw = path.read_text(encoding="utf-8")
            doc = json.loads(raw)
        except Exception:
            policies.append({
                "provider": provider_name,
                "source_file": str(path.resolve()),
                "loaded": False,
                "error": "File missing or unreadable — using hardcoded fallback.",
            })
            continue

        mappings = doc.get("mappings", [])
        # If the JSON uses a legacy attr key, normalise it for display
        frozen_keys: list[str] = []
        for m in mappings:
            key = m.get(attr_key, m.get("provider_attr", "?"))
            fk = m.get("frozen_key", "?")
            frozen_keys.append(fk)

        policies.append({
            "provider": doc.get("provider", provider_name),
            "source_file": str(path.resolve()),
            "policy_version": doc.get("policy_version", "?"),
            "description": doc.get("description", ""),
            "mapping_count": len(mappings),
            "frozen_keys": frozen_keys,
            "loaded": True,
        })
        total_mappings += len(mappings)

    return {
        "policies": policies,
        "total_mappings": total_mappings,
        "loaded_provider_count": len([p for p in policies if p.get("loaded")]),
        "provider_count": len(policy_defs),
        "note": (
            "Policy summaries are read directly from disk — no server restart needed "
            "to see edits here.  However, the running enrichment uses a cached copy "
            "(@lru_cache).  Edits only take full effect after a server restart."
        ),
        "generated_at": _now(),
    }


def _apply_newsapi_enrichment(
    fields: dict[str, Any],
    headlines: list[dict[str, Any]],
    symbol: str,
    retrieved_at: str,
) -> None:
    """Apply all policy-driven NewsAPI enrichment mappings to *fields*.

    Reads the enrichment policy (``newsapi_enrichment_policy.json``) and,
    for each mapping, looks up the value from a simple values dict built from
    the headline list (currently only ``headline_count`` = ``len(headlines)``).
    """
    mappings = _load_newsapi_enrichment_policy()
    # Build a values dict from the headline data.
    headline_count = len(headlines) if headlines else 0
    values: dict[str, float | int] = {"headline_count": headline_count}

    for m in mappings:
        value = values.get(m["provider_attr"])
        _enrich_field(
            fields,
            key=m["frozen_key"],
            value=value,
            unit=m["unit"],
            provider="NEWS",
            symbol=symbol,
            retrieved_at=retrieved_at,
            provider_field=m["provider_attr"],
            readiness=m["readiness"],
            evidence_prefix="news",
        )




def _enrich_frozen_rows_with_newsapi(rows: list[dict[str, Any]]) -> None:
    """Replace NOT_COLLECTED frozen fields with live news headline counts.

    Follows the same pattern as ``_enrich_frozen_rows_with_finviz`` but uses
    the ProviderBundle's ``news_for()`` method which aggregates headlines
    from all configured news providers (NewsAPI, Finviz News, Finnhub News).

    Field mappings are driven by ``newsapi_enrichment_policy.json``.
    """
    try:
        from .live_providers import get_runtime

        runtime = get_runtime()
        # news_for() returns [] when nothing is configured — no separate guard needed.

        now_iso = _now()
        matched = 0

        for row in rows:
            symbol = row["symbol"]
            try:
                headlines = runtime.news_for(symbol)
            except Exception:
                _enrich_log.debug(
                    "News fetch failed for row %s", symbol, exc_info=True,
                )
                continue

            if not headlines:
                continue
            matched += 1

            existing: dict[str, Any] = row["fields"]
            try:
                _apply_newsapi_enrichment(existing, headlines, symbol, now_iso)
            except Exception:
                _enrich_log.debug(
                    "News enrichment failed for row %s", symbol, exc_info=True,
                )

        if matched:
            _enrich_log.info("News enriched %d/%d frozen rows", matched, len(rows))
            try:
                data_logger.log_enrichment_event(
                    "NEWS", "frozen_snapshot",
                    matched_count=matched, total_rows=len(rows),
                    frozen_keys=[m["frozen_key"] for m in _load_newsapi_enrichment_policy()],
                )
            except Exception:
                pass

    except Exception as exc:
        # Never break the frozen snapshot for enrichment failure.
        _enrich_log.warning("News frozen enrichment failed: %s", exc)


def _enrich_detail_market_data_newsapi(detail: dict[str, Any]) -> None:
    """Enrich the detail drawer's market-data block with live news headline counts.

    Same enrichment as ``_enrich_frozen_rows_with_newsapi`` but operates on the
    detail payload's ``market_data`` dict.
    """
    try:
        from .live_providers import get_runtime

        runtime = get_runtime()

        symbol = (detail.get("identity") or {}).get("symbol", "")
        try:
            headlines = runtime.news_for(symbol)
        except Exception:
            return

        if not headlines:
            return

        now_iso = _now()
        market = detail.get("market_data") or {}
        _apply_newsapi_enrichment(market, headlines, symbol, now_iso)
    except Exception as exc:
        _enrich_log.warning("News detail enrichment failed for %s: %s",
                           (detail.get("identity") or {}).get("symbol", "?"), exc)


def _apply_finnhub_enrichment(
    fields: dict[str, Any],
    price: float | None,
    symbol: str,
    retrieved_at: str,
) -> None:
    """Apply all policy-driven Finnhub enrichment mappings to *fields*.

    Reads the enrichment policy (``finnhub_enrichment_policy.json``) and,
    for each mapping, looks up the value from a simple values dict built from
    the Finnhub price (currently only ``price`` = the raw Finnhub quote).
    """
    mappings = _load_finnhub_enrichment_policy()
    values: dict[str, float | None] = {"price": price}

    for m in mappings:
        value = values.get(m["provider_attr"])
        _enrich_field(
            fields,
            key=m["frozen_key"],
            value=value,
            unit=m["unit"],
            provider="Finnhub",
            symbol=symbol,
            retrieved_at=retrieved_at,
            provider_field=m["provider_attr"],
            readiness=m["readiness"],
            evidence_prefix="finnhub",
        )


def _enrich_frozen_rows_with_finnhub(rows: list[dict[str, Any]]) -> None:
    """Replace NOT_COLLECTED frozen fields with live Finnhub real-time prices.

    Follows the same pattern as ``_enrich_frozen_rows_with_newsapi`` but uses
    the ProviderBundle's ``finnhub_price_for()`` method for real-time quotes.

    Field mappings are driven by ``finnhub_enrichment_policy.json``.
    """
    try:
        from .live_providers import get_runtime

        runtime = get_runtime()
        finnhub = runtime.finnhub
        if not finnhub.configured:
            return

        now_iso = _now()
        matched = 0

        for row in rows:
            symbol = row["symbol"]
            try:
                price = runtime.finnhub_price_for(symbol)
            except Exception:
                _enrich_log.debug(
                    "Finnhub fetch failed for row %s", symbol, exc_info=True,
                )
                continue

            if price is None:
                continue
            matched += 1

            existing: dict[str, Any] = row["fields"]
            try:
                _apply_finnhub_enrichment(existing, price, symbol, now_iso)
            except Exception:
                _enrich_log.debug(
                    "Finnhub enrichment failed for row %s", symbol, exc_info=True,
                )

        if matched:
            _enrich_log.info("Finnhub enriched %d/%d frozen rows", matched, len(rows))
            try:
                data_logger.log_enrichment_event(
                    "Finnhub", "frozen_snapshot",
                    matched_count=matched, total_rows=len(rows),
                    frozen_keys=[m["frozen_key"] for m in _load_finnhub_enrichment_policy()],
                )
            except Exception:
                pass

    except Exception as exc:
        # Never break the frozen snapshot for enrichment failure.
        _enrich_log.warning("Finnhub frozen enrichment failed: %s", exc)


def _enrich_detail_market_data_finnhub(detail: dict[str, Any]) -> None:
    """Enrich the detail drawer's market-data block with live Finnhub prices.

    Same enrichment as ``_enrich_frozen_rows_with_finnhub`` but operates on the
    detail payload's ``market_data`` dict.
    """
    try:
        from .live_providers import get_runtime

        runtime = get_runtime()
        finnhub = runtime.finnhub
        if not finnhub.configured:
            return

        symbol = (detail.get("identity") or {}).get("symbol", "")
        try:
            price = runtime.finnhub_price_for(symbol)
        except Exception:
            return

        if price is None:
            return

        now_iso = _now()
        market = detail.get("market_data") or {}
        _apply_finnhub_enrichment(market, price, symbol, now_iso)
    except Exception as exc:
        _enrich_log.warning("Finnhub detail enrichment failed for %s: %s",
                           (detail.get("identity") or {}).get("symbol", "?"), exc)


def _apply_finviz_enrichment(
    fields: dict[str, Any],
    fv_row: Any,
    symbol: str,
    retrieved_at: str,
) -> None:
    """Apply all policy-driven Finviz enrichment mappings to *fields*.

    Reads the enrichment policy (``finviz_enrichment_policy.json``) and,
    for each mapping, pulls the FinvizRow attribute via ``getattr`` and
    writes it into *fields* under the configured frozen key.
    """
    mappings = _load_finviz_enrichment_policy()
    for m in mappings:
        value = getattr(fv_row, m["provider_attr"], None)
        _enrich_field(
            fields,
            key=m["frozen_key"],
            value=value,
            unit=m["unit"],
            provider="Finviz Elite",
            symbol=symbol,
            retrieved_at=retrieved_at,
            provider_field=m["provider_attr"],
            readiness=m["readiness"],
            evidence_prefix="finviz",
        )


def _enrich_field(
    fields: dict[str, Any],
    key: str,
    value: float | int | None,
    unit: str,
    provider: str,
    symbol: str,
    retrieved_at: str,
    provider_field: str,
    *,
    readiness: str = "PROVIDER_SNAPSHOT_FINVIZ_LIVE_ENRICHMENT",
    evidence_prefix: str = "finviz",
) -> None:
    """Replace a single frozen field entry with live Finviz provenance."""
    if value is None:
        return  # Don't overwrite if Finviz doesn't have it; keep existing reason

    original = fields.get(key, {})
    original_reason = original.get("missing_reason", "")
    original_status = original.get("status", "")

    selection = (
        f"Live {provider} data enriching frozen research snapshot. "
        "NOT ADMISSIBLE FOR RESEARCH."
    )
    if original_status in ("NOT_COLLECTED", "BLOCKED", "UNKNOWN") and original_reason:
        selection += f" Original frozen-field reason: {original_reason}"

    fields[key] = known(
        value,
        unit=unit,
        provider=provider,
        event_time=retrieved_at,
        received_time=retrieved_at,
        freshness=Freshness.CURRENT,
        data_mode=DataMode.HISTORICAL,
        evidence_id=f"{evidence_prefix}:{symbol}:{provider_field}:{retrieved_at}",
        readiness=readiness,
        provider_field=provider_field,
        selection_reason=selection,
        research_admissibility="NOT_ADMISSIBLE_FOR_RESEARCH",
    ).as_dict()


def live_refresh() -> dict[str, Any]:
    """Refresh every tracked candidate. Per-symbol failures stay per-symbol."""
    from . import session_state

    session = session_state.get_session()
    result = session.refresh_all()
    result["summary"] = session.summary()
    return result


def set_auto_refresh(enabled: bool) -> dict[str, Any]:
    from . import session_state

    session = session_state.get_session()
    if enabled:
        session.start_auto_refresh()
    else:
        session.stop_auto_refresh()
    return session.summary()


def demo_readiness() -> dict[str, Any]:
    """``DEMO READY`` never depends on a live provider. ``LIVE SOURCES READY`` is separate."""
    from . import session_state

    checks: list[dict[str, Any]] = []
    frozen_ok = False
    case_count = 0
    results_ok = False
    try:
        source = get_frozen_source()
        frozen_ok = source.available
        if frozen_ok:
            case_count = len(source.cases)
            results_ok = all(
                len(source.rule_table(case["case_id"])) == 25 for case in source.cases
            )
    except Exception:  # noqa: BLE001 - sanitized demo fallback is checked next
        frozen_ok = False
    if not frozen_ok:
        from .frozen_demo import load_frozen_demo
        demo = load_frozen_demo()
        frozen_ok = bool(demo["rows"])
        case_count = len(demo["rows"])
        results_ok = all(len(row["rules"]) == 25 for row in demo["rows"])

    checks.append({"check": "Server running", "ok": True, "detail": "This response was served."})
    checks.append({
        "check": "Frozen Research data loaded", "ok": frozen_ok,
        "detail": "A canonical private freeze or sanitized frozen demo is present."
        if frozen_ok else "No frozen research source was found.",
    })
    checks.append({
        "check": "All 13 Phase 3A results available", "ok": case_count == 13 and results_ok,
        "detail": f"{case_count} case(s) with a 25-rule result table.",
    })
    demo_ready = all(item["ok"] for item in checks)

    session = session_state.get_session()
    summary = session.summary()
    gateway_ok = str(session.provider.connection_status.state) == "OK"
    scanner_ok = str(session.provider.scanner_status.state) == "OK"
    quotes_ok = str(session.provider.quote_status.state) == "OK"
    sec_ok = str(session.provider.sec_status.state) == "OK"

    live_checks = [
        {"check": "IB Gateway connected", "ok": gateway_ok,
         "detail": session.provider.connection_status.detail},
        {"check": "Discovery scanner available", "ok": scanner_ok,
         "detail": session.provider.scanner_status.detail},
        {"check": "Current quotes available", "ok": quotes_ok,
         "detail": session.provider.quote_status.detail},
        {"check": "SEC EDGAR filings", "ok": sec_ok,
         "detail": session.provider.sec_status.detail},
        {"check": "At least one current candidate", "ok": summary["candidate_count"] > 0,
         "detail": f"{summary['candidate_count']} candidate(s)."},
    ]
    return {
        "demo_ready": demo_ready,
        "demo_checks": checks,
        "demo_note": (
            "DEMO READY depends only on local frozen artifacts. Provider downtime cannot "
            "affect it."
        ),
        "live_sources_ready": all(item["ok"] for item in live_checks),
        "live_checks": live_checks,
        "generated_at": _now(),
    }


__all__ = [
    "APP_TITLE",
    "CURRENT_BANNERS",
    "DISCLAIMER",
    "SORT_KEYS",
    "FrozenResearchUnavailable",
    "Mode",
    "current_detail",
    "current_snapshot",
    "demo_readiness",
    "discovery_refresh",
    "enrichment_policies_summary",
    "filter_rows",
    "frozen_detail",
    "frozen_snapshot",
    "header",
    "health",
    "live_refresh",
    "research_summary",
    "set_auto_refresh",
    "sort_rows",
]

# Backward-compatible internal name for Batch 10-14 callers.
professor_summary = research_summary
