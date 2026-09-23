"""Progress-aware loopback service liveness (operator tokens only).

Distinguishes transport reachability (port bound) from application progress
(HTTP probe or owned process). A bound port alone is never HEALTHY.
"""

from __future__ import annotations

from typing import Any, Mapping

_PLATFORM_SERVICE_ROLES: dict[str, str] = {
    "api": "UI_API",
    "ui": "OPERATOR_UI",
    "control": "LIFECYCLE_CONTROL",
}

_CONNECTED_STATES = frozenset({"CONNECTED", "CONNECTED_DEGRADED"})
_TERMINAL_DOWN_STATES = frozenset({"DISCONNECTED", "ERROR", "ENTITLEMENT_MISSING"})


def classify_loopback_service_liveness(
    *,
    service_name: str,
    port_bound: bool,
    http_alive: bool | None,
    process_alive: bool,
    identity_owned: bool,
) -> dict[str, Any]:
    """Classify one launcher-managed loopback service."""
    role = _PLATFORM_SERVICE_ROLES.get(service_name, service_name.upper())
    transport_up = port_bound
    expects_http = http_alive is not None

    if not process_alive:
        status = "UNAVAILABLE"
        if port_bound:
            reason = "PORT_BOUND_WITHOUT_PROCESS"
        else:
            reason = "PROCESS_NOT_RUNNING"
        application_progress = False
    elif not identity_owned:
        status = "UNREADY"
        reason = "PROCESS_IDENTITY_MISMATCH"
        application_progress = False
    elif expects_http:
        application_progress = bool(http_alive)
        if port_bound and not http_alive:
            status = "UNREADY"
            reason = "TRANSPORT_UP_APPLICATION_NOT_PROGRESSED"
        elif http_alive:
            status = "HEALTHY"
            reason = None
        else:
            status = "UNREADY"
            reason = "HTTP_NOT_ALIVE"
    else:
        application_progress = process_alive and identity_owned
        status = "HEALTHY" if application_progress else "UNREADY"
        reason = None if application_progress else "CONTROL_PROCESS_NOT_READY"

    return {
        "application_progress": application_progress,
        "healthy": status == "HEALTHY",
        "http_alive": http_alive,
        "identity_owned": identity_owned,
        "port_bound": port_bound,
        "process_alive": process_alive,
        "reason": reason,
        "service": service_name,
        "service_role": role,
        "status": status,
        "transport_up": transport_up,
    }


def classify_platform_services_liveness(services: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for svc in services or []:
        if not isinstance(svc, dict):
            continue
        health = svc.get("health") if isinstance(svc.get("health"), dict) else {}
        http_alive = health.get("http_alive")
        if http_alive is not None:
            http_alive = bool(http_alive)
        rows.append(
            classify_loopback_service_liveness(
                service_name=str(svc.get("name") or "unknown"),
                port_bound=bool(health.get("port_bound")),
                http_alive=http_alive,
                process_alive=bool(health.get("process_alive")),
                identity_owned=bool(health.get("identity_owned")),
            )
        )
    if not rows:
        return {"services": [], "status": "NOT_APPLICABLE", "healthy": False}
    if all(row["status"] == "HEALTHY" for row in rows):
        aggregate = "HEALTHY"
    elif any(row["status"] == "UNAVAILABLE" for row in rows):
        aggregate = "UNAVAILABLE"
    else:
        aggregate = "UNREADY"
    return {
        "healthy": aggregate == "HEALTHY",
        "services": rows,
        "status": aggregate,
    }


def classify_observational_market_data_liveness(
    *,
    live_enabled: bool,
    moomoo_configured: bool,
    provider_id: str,
    provider_role: str,
    process_id: int | None,
    connection_state: str,
    opend_loopback_reachable: bool,
    probe_stale: bool,
    receiving: bool,
    entitled: bool,
    active_subscription_count: int,
    last_successful_event_ns: int | None,
    max_subscribed_freshness_ms: int | None,
    quote_stale_threshold_ms: int,
) -> dict[str, Any]:
    """Live observational ingest liveness using existing cycle semantics.

    ``process_id`` is diagnostic metadata for the classifying process only; it
    does not participate in status classification (unlike loopback
    ``identity_owned``, which gates platform services).
    """
    base = {
        "last_successful_event_ns": last_successful_event_ns,
        "process_id": process_id,
        "provider_id": provider_id,
        "provider_role": provider_role,
        "quote_stale_threshold_ms": quote_stale_threshold_ms,
    }
    if not live_enabled:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "NOT_APPLICABLE",
            "healthy": False,
            "reason": "IMP_LIVE_OBSERVATIONAL_DISABLED",
            "status": "NOT_APPLICABLE",
            "transport_up": False,
        }

    conn = connection_state.upper()
    transport_up = opend_loopback_reachable if moomoo_configured else conn in _CONNECTED_STATES

    if probe_stale:
        return {
            **base,
            "application_progress": receiving,
            "expected_cycle": "CAPABILITY_PROBE",
            "healthy": False,
            "reason": "PROBE_STALE",
            "status": "PROBE_STALE",
            "transport_up": transport_up,
        }

    if conn in _TERMINAL_DOWN_STATES:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "INGEST",
            "healthy": False,
            "reason": "PROVIDER_DOWN",
            "status": "PROVIDER_DOWN",
            "transport_up": transport_up,
        }

    if conn in {"CONNECTING", "RECONNECTING"}:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "SESSION_CONNECT",
            "healthy": False,
            "reason": "SESSION_NOT_READY",
            "status": "UNREADY",
            "transport_up": transport_up,
        }

    if moomoo_configured and opend_loopback_reachable and conn not in _CONNECTED_STATES:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "SESSION_CONNECT",
            "healthy": False,
            "reason": "TRANSPORT_UP_APPLICATION_NOT_PROGRESSED",
            "status": "UNREADY",
            "transport_up": True,
        }

    # Zero subscriptions: expected idle. Never HEALTHY, never a false failure.
    # receiving=True with no subscription cycle is inconsistent, not progress.
    if active_subscription_count == 0:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "NOT_APPLICABLE",
            "healthy": False,
            "reason": "NO_ACTIVE_SUBSCRIPTION_CYCLE",
            "status": "NOT_APPLICABLE",
            "transport_up": transport_up,
        }

    if not entitled:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "INGEST",
            "healthy": False,
            "reason": "NOT_ENTITLED",
            "status": "UNREADY",
            "transport_up": transport_up,
        }

    if receiving:
        # Fail closed: subscribed + receiving without measurable freshness is
        # not HEALTHY. Do not invent a generic timeout; require the existing
        # quote-cycle freshness sample.
        if max_subscribed_freshness_ms is None:
            return {
                **base,
                "application_progress": True,
                "expected_cycle": "INGEST",
                "healthy": False,
                "reason": "FRESHNESS_UNAVAILABLE",
                "status": "UNAVAILABLE",
                "transport_up": transport_up,
            }
        stale = max_subscribed_freshness_ms > quote_stale_threshold_ms
        if stale:
            return {
                **base,
                "application_progress": True,
                "expected_cycle": "INGEST",
                "healthy": False,
                "reason": "QUOTE_STALE",
                "status": "STALE",
                "transport_up": transport_up,
            }
        return {
            **base,
            "application_progress": True,
            "expected_cycle": "INGEST",
            "healthy": True,
            "reason": None,
            "status": "HEALTHY",
            "transport_up": transport_up,
        }

    if last_successful_event_ns is None:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "INGEST",
            "healthy": False,
            "reason": "AWAITING_FIRST_EVENT",
            "status": "UNREADY",
            "transport_up": transport_up,
        }

    if max_subscribed_freshness_ms is None:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "INGEST",
            "healthy": False,
            "reason": "FRESHNESS_UNAVAILABLE",
            "status": "UNAVAILABLE",
            "transport_up": transport_up,
        }

    if max_subscribed_freshness_ms > quote_stale_threshold_ms:
        return {
            **base,
            "application_progress": False,
            "expected_cycle": "INGEST",
            "healthy": False,
            "reason": "QUOTE_STALE",
            "status": "STALE",
            "transport_up": transport_up,
        }

    return {
        **base,
        "application_progress": False,
        "expected_cycle": "INGEST",
        "healthy": False,
        "reason": "AWAITING_FIRST_EVENT",
        "status": "UNREADY",
        "transport_up": transport_up,
    }


def compose_readiness_vs_liveness(
    *,
    resilience: Mapping[str, Any],
    lifecycle: Mapping[str, Any] | None = None,
    provider_health: Mapping[str, Any] | None = None,
    campaign_supervision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge Lane B resilience liveness with progress-aware platform + market data views.

    Campaign supervision (armed ownership / heartbeat) is additive and does not
    imply market-data freshness or opportunity quality.
    """
    base = dict(resilience.get("readiness_vs_liveness") or {})
    readiness = base.get("readiness") if isinstance(base.get("readiness"), dict) else {}
    prior_liveness = base.get("liveness") if isinstance(base.get("liveness"), dict) else {}

    services = None
    if lifecycle is not None:
        raw = lifecycle.get("services")
        if isinstance(raw, list):
            services = raw
    platform = classify_platform_services_liveness(services)

    market_data: dict[str, Any] | None = None
    if isinstance(provider_health, dict):
        market_data = provider_health.get("service_liveness")
        if not isinstance(market_data, dict):
            market_data = None

    campaign: dict[str, Any] | None = None
    if isinstance(campaign_supervision, dict):
        campaign = {
            "status": campaign_supervision.get("status"),
            "healthy": campaign_supervision.get("healthy"),
            "progress": campaign_supervision.get("progress"),
            "arm_status": (
                (campaign_supervision.get("ownership") or {}).get("arm_status")
                if isinstance(campaign_supervision.get("ownership"), dict)
                else None
            ),
            "service_liveness_separate_from_data_freshness": True,
            "does_not_imply_data_freshness": True,
        }

    liveness = {
        **prior_liveness,
        "platform_services": platform,
        "market_data_observational": market_data,
        "campaign_supervision": campaign,
    }
    if market_data is not None:
        liveness["market_data_status"] = market_data.get("status")
    liveness["platform_status"] = platform.get("status")
    if campaign is not None:
        liveness["campaign_status"] = campaign.get("status")

    return {"readiness": readiness, "liveness": liveness}


__all__ = [
    "classify_loopback_service_liveness",
    "classify_platform_services_liveness",
    "classify_observational_market_data_liveness",
    "compose_readiness_vs_liveness",
]
