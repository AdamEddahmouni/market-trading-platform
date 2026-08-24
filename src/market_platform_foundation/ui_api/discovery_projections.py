"""UI API projections for Finviz discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..discovery import DiscoveryEngine, get_screen, list_screens
from ..discovery.capture import load_discovery_capture, replay_capture_equivalence
from ..finviz import (
    authority_matrix_payload,
    finviz_api_key,
    finviz_can_execute,
    get_finviz_credential_manager,
    get_finviz_request_manager,
)
from ..finviz.news import FinvizNewsClient
from ..finviz.provider_role import EXECUTION_ROLE, PROVIDER_ID
from ..finviz.symbols import canonical_to_moomoo, finviz_to_canonical
from ..market_data.live_config import live_observational_enabled, moomoo_live_enabled
from ..market_data.live_runtime import get_live_runtime
from ..market_data.subscription_manager import SubscriptionPriority
from ..ui_api.operator_instrument import persist_explore_selected_instrument


def build_finviz_diagnostics_payload() -> dict[str, Any]:
    manager = get_finviz_request_manager()
    credential_manager = get_finviz_credential_manager()
    auth_health = credential_manager.health()
    configured = auth_health.credential_present
    auth_state = auth_health.state.value
    connection = "HEALTHY" if auth_state == "HEALTHY" else (
        "AUTH_REQUIRED" if auth_state.startswith("AUTH_") or auth_state == "UNCONFIGURED" else "DEGRADED"
    )
    return {
        "provider": PROVIDER_ID,
        "role": "DISCOVERY / CONTEXT",
        "execution_role": EXECUTION_ROLE,
        "configured": configured,
        "connection": connection,
        "authentication": auth_state,
        "credential_source": auth_health.source.value,
        "finviz_credential_generation": auth_health.finviz_credential_generation,
        "last_validated": auth_health.last_validated,
        "last_rotation": auth_health.last_rotation,
        "recovery_mode": auth_health.recovery_mode.value,
        "automatic_recovery": auth_health.automatic_recovery,
        "last_auth_error": auth_health.last_auth_error,
        "screener": "AVAILABLE" if configured and connection == "HEALTHY" else (
            "UNAVAILABLE" if not configured else "DEGRADED"
        ),
        "news": "AVAILABLE" if configured and connection == "HEALTHY" else (
            "UNAVAILABLE" if not configured else "DEGRADED"
        ),
        "options": "PARTIAL" if configured else "NOT_CONFIGURED",
        "rate": "PASS",
        "requests": manager.metrics.request_count,
        "cache_hits": manager.metrics.cache_hits,
        "cache_misses": manager.metrics.cache_misses,
        "auth_recoveries": manager.metrics.auth_recoveries,
        "authority": authority_matrix_payload(),
    }


def build_discover_screens_payload() -> dict[str, Any]:
    return {
        "screens": list_screens(),
        "provider": PROVIDER_ID,
        "execution_role": EXECUTION_ROLE,
    }


def build_discover_run_payload(screen_id: str, *, force: bool = False) -> dict[str, Any]:
    engine = DiscoveryEngine()
    candidate_set = engine.run_screen(screen_id, force=force, persist=True)
    return {
        "available": candidate_set.quality != "UNAVAILABLE",
        "candidate_set": candidate_set.to_dict(),
        "screen": get_screen(screen_id).to_dict() if get_screen(screen_id) else None,
    }


def load_latest_capture_for_screen(screen_id: str) -> dict[str, Any] | None:
    from ..finviz.config import finviz_capture_root

    root = finviz_capture_root()
    if not root.is_dir():
        return None
    matches: list[Path] = []
    for day_dir in sorted(root.iterdir(), reverse=True):
        screen_dir = day_dir / screen_id
        if screen_dir.is_dir():
            for run_dir in screen_dir.iterdir():
                artifact = run_dir / "candidate-set.json"
                if artifact.is_file():
                    matches.append(artifact)
    if not matches:
        return None
    newest = max(
        matches,
        key=lambda artifact: (
            artifact.parents[2].name,
            artifact.stat().st_mtime_ns,
            str(artifact),
        ),
    )
    return load_discovery_capture(newest)


def promote_to_live_analysis(instrument_id: str) -> dict[str, Any]:
    """PROMOTE TO LIVE ANALYSIS — subscriptions only, never orders."""
    mapping = finviz_to_canonical(instrument_id)
    persist_explore_selected_instrument(mapping.instrument_id)
    subscriptions: list[dict[str, Any]] = []
    quota_before = None
    quota_after = None
    if live_observational_enabled() and moomoo_live_enabled():
        runtime = get_live_runtime(create=True)
        if runtime is not None:
            quota_before = len(runtime.subscription_manager.active_keys)
            results = runtime.subscribe(
                instrument_id=mapping.instrument_id,
                capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
                consumer_id="discover-promote",
                priority=int(SubscriptionPriority.ACTIVE_WORKSPACE),
            )
            subscriptions = [
                {
                    "capability": r.key.capability,
                    "accepted": r.accepted,
                    "reason": r.reason,
                }
                for r in results
            ]
            quota_after = len(runtime.subscription_manager.active_keys)
    return {
        "action": "PROMOTE_TO_LIVE_ANALYSIS",
        "instrument_id": mapping.instrument_id,
        "provider_symbol": mapping.provider_symbol,
        "moomoo_symbol": canonical_to_moomoo(mapping.instrument_id),
        "order_intent_created": False,
        "paper_order_created": False,
        "broker_order_created": False,
        "subscriptions": subscriptions,
        "quota_before": quota_before,
        "quota_after": quota_after,
        "finviz_execution_possible": finviz_can_execute(),
    }


def enrich_workspace_discovery_evidence(
    instrument_id: str,
    *,
    screen_id: str | None = None,
) -> dict[str, Any] | None:
    screen = screen_id or "SHORT_SQUEEZE_DISCOVERY"
    captured = load_latest_capture_for_screen(screen)
    if captured is None:
        return None
    needle = instrument_id.upper()
    for candidate in captured.get("candidates") or []:
        if candidate.get("instrument_id") == needle:
            return {
                "lane": "DISCOVERY",
                "evidence_type": "FINVIZ_DISCOVERY_MATCH",
                "quality": candidate.get("quality", "PASS"),
                "relevance": "HIGH",
                "direction": "NEUTRAL",
                "summary": " · ".join(candidate.get("matched_reasons") or []),
                "freshness_label": captured.get("received_at", ""),
                "sources": ["FINVIZ_ELITE"],
                "details": {
                    "screen_id": captured.get("screen_id"),
                    "screen_version": captured.get("screen_version"),
                    "metrics": candidate.get("metrics"),
                    "transition": candidate.get("transition"),
                    "inspection_priority": candidate.get("inspection_priority"),
                },
            }
    return None
