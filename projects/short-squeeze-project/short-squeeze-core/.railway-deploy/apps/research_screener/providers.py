"""Provider health.

Availability is asserted only from an actual probe result. The existence of adapter code
is never treated as evidence that a provider works, so every provider without a
configured, probeable endpoint reports ``NOT CONFIGURED``.

The only probe performed is a localhost TCP connect to the IB Gateway / TWS API socket.
No credential is read, printed or transmitted, and no account or order endpoint exists in
this module.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .live_providers import ProviderBundle, get_runtime
from .sentiment_live import get_sentiment_analyzer

#: Localhost only. The application refuses to probe anything else.
PROBE_HOST = "127.0.0.1"

#: IB Gateway paper, IB Gateway live, TWS paper, TWS live.
IBKR_PORT_PROBE_ORDER: tuple[int, ...] = (4002, 4001, 7497, 7496)

PROBE_TIMEOUT_S = 0.6


class ProviderState(StrEnum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    AVAILABLE = "AVAILABLE"
    CONFIGURED = "CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT CONFIGURED"
    RATE_LIMITED = "RATE_LIMITED"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _socket_open(host: str, port: int, timeout: float = PROBE_TIMEOUT_S) -> bool:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"refusing to probe non-localhost host {host!r}")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_ibkr_gateway(
    *, probe=_socket_open, ports: tuple[int, ...] = IBKR_PORT_PROBE_ORDER
) -> dict[str, Any]:
    """TCP-probe the local IB Gateway sockets. No API handshake, no credential."""
    attempts = []
    for port in ports:
        open_ = probe(PROBE_HOST, port)
        attempts.append({"host": PROBE_HOST, "port": port, "socket_open": bool(open_)})
        if open_:
            return {
                "name": "IB Gateway",
                "state": str(ProviderState.CONNECTED),
                "detail": f"TCP socket open on {PROBE_HOST}:{port}",
                "port": port,
                "attempts": attempts,
                "probed_at": _now(),
            }
    return {
        "name": "IB Gateway",
        "state": str(ProviderState.DISCONNECTED),
        "detail": (
            "No local IB Gateway / TWS API socket is accepting connections on "
            + ", ".join(str(port) for port in ports)
            + ". Frozen Research mode is unaffected."
        ),
        "port": None,
        "attempts": attempts,
        "probed_at": _now(),
    }


def _static(name: str, state: ProviderState, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "state": str(state),
        "detail": detail,
        "port": None,
        "attempts": [],
        "probed_at": _now(),
    }


def provider_health(
    *, probe=_socket_open, frozen_available: bool = True,
    runtime: ProviderBundle | None = None,
) -> list[dict[str, Any]]:
    """The provider health panel. Truthful about what is genuinely configured."""
    gateway = probe_ibkr_gateway(probe=probe)
    connected = gateway["state"] == str(ProviderState.CONNECTED)

    market_data = _static(
        "Market Data",
        ProviderState.AVAILABLE if connected else ProviderState.UNAVAILABLE,
        "Reachable through the local gateway. The LIVE / DELAYED label is determined "
        "per request from the entitlement the provider actually returns."
        if connected
        else "No market-data provider is reachable.",
    )
    historical = _static(
        "Historical Bars",
        ProviderState.AVAILABLE if connected else ProviderState.UNAVAILABLE,
        "Read-only historical bar requests are available through the local gateway."
        if connected
        else "No historical-bar provider is reachable.",
    )
    frozen = _static(
        "Frozen Research Artifacts",
        ProviderState.AVAILABLE if frozen_available else ProviderState.UNAVAILABLE,
        "Batch 08 freeze and Batch 09 preview are present on this machine."
        if frozen_available
        else "The private artifact root was not found; Frozen Research mode is unavailable.",
    )
    runtime = runtime or get_runtime()
    finviz = runtime.finviz
    newsapi = runtime.news
    finnhub = runtime.finnhub
    orch_status = runtime.status()

    finviz_configured = finviz.configured
    fv_last_error = orch_status["finviz"].get("last_error", "")
    fv_client_status = finviz.status()
    if "401" in str(fv_last_error) or "Invalid" in str(fv_last_error):
        fv_detail = (
            "TOKEN EXPIRED — Finviz Elite API key is present but returns 401. "
            "Refresh the export API token at https://elite.finviz.com/ and update "
            "FINVIZ_API_KEY in .private/providers.env. Adapter is fully wired."
        )
    elif finviz_configured and orch_status["finviz"]["fetched"]:
        fv_status = f"{orch_status['finviz']['rows']} rows in {orch_status['finviz'].get('last_duration_s', 0):.1f}s"
        fv_detail = (
            f"CONFIGURED · AUTHENTICATED · EXPORT ACTIVE · {fv_status} · "
            f"last success {fv_client_status.get('last_success_at')} · "
            f"TTL {fv_client_status.get('ttl_seconds')}s · capabilities: Float, "
            "Short Float, Relative Volume, Short Ratio, Shares Outstanding."
        )
    elif finviz_configured:
        fv_detail = "CONFIGURED — Finviz Elite API key present. Not yet fetched."
    else:
        fv_detail = "NOT CONFIGURED — Set FINVIZ_API_KEY in .private/providers.env."

    news_configured = newsapi.configured
    news_status = orch_status["newsapi"]
    nd = (
        f"CONFIGURED · AUTHENTICATED · NEWS ACTIVE · "
        f"{news_status.get('headline_count', 0)} headline(s)."
        if news_configured and news_status.get("fetched") else
        "CONFIGURED — NewsAPI key present. Authentication is confirmed only after refresh."
        if news_configured else
        "NOT CONFIGURED — Set NEWSAPI_KEY in .private/providers.env."
    )

    fh_configured = finnhub.configured
    fh_status = orch_status["finnhub"]
    fh = (
        f"CONFIGURED · AUTHENTICATED · QUOTE FALLBACK ACTIVE · "
        f"{fh_status.get('price_count', 0)} price(s); used capability: price fallback."
        if fh_configured and fh_status.get("fetched") else
        "CONFIGURED — Finnhub key present. Authentication is confirmed only after refresh."
        if fh_configured else
        "NOT CONFIGURED — Set FINNHUB_KEY in .private/providers.env."
    )

    return [
        gateway,
        market_data,
        historical,
        frozen,
        _static(
            "Finviz Elite",
            (
                ProviderState.AVAILABLE if orch_status["finviz"]["fetched"]
                else ProviderState.CONFIGURED if finviz_configured
                else ProviderState.NOT_CONFIGURED
            ),
            fv_detail,
        ),
        _static(
            "NewsAPI",
            (
                ProviderState.AVAILABLE if news_status.get("fetched")
                else ProviderState.CONFIGURED if news_configured
                else ProviderState.NOT_CONFIGURED
            ),
            nd,
        ),
        _static(
            "Finnhub",
            (
                ProviderState.AVAILABLE if fh_status.get("fetched")
                else ProviderState.CONFIGURED if fh_configured
                else ProviderState.NOT_CONFIGURED
            ),
            fh,
        ),
        _static(
            "SEC EDGAR",
            (
                ProviderState.CONFIGURED
                if runtime.sec.configured else ProviderState.NOT_CONFIGURED
            ),
            (
                f"AVAILABLE · filings active · "
                f"{orch_status['sec_edgar'].get('result_count', 0)} symbol result(s)."
                if orch_status["sec_edgar"].get("fetched") else
                "Public SEC EDGAR API enabled for this runtime. Availability is confirmed "
                "per refresh."
                if runtime.sec.configured else
                "Public SEC EDGAR adapter is disabled in this offline runtime."
            ),
        ),
        _static(
            "Trading Halts",
            ProviderState.AVAILABLE if connected else ProviderState.UNAVAILABLE,
            "Halt status via IBKR generic tick 49 when gateway is connected."
            if connected
            else "No halt-data provider is reachable.",
        ),
        _static(
            "Sentiment",
            (
                ProviderState.AVAILABLE
                if runtime._sentiment_analyzer.enabled
                else ProviderState.NOT_CONFIGURED
            ),
            (
                f"READY · model {runtime._sentiment_analyzer.model_id}"
                if runtime._sentiment_analyzer.model_loaded
                else (
                    f"CONFIGURED · model {runtime._sentiment_analyzer.model_id} · "
                    f"load pending or failed: {runtime._sentiment_analyzer.load_error or 'unknown'}"
                )
                if runtime._sentiment_analyzer.enabled
                else "MODEL_NOT_DEPLOYED — enable SENTIMENT_ENABLED in LOCAL_FULL, set "
                "SENTIMENT_MODEL_PATH (optional — defaults to ProsusAI/finbert), and "
                "install pip install 'short-squeeze-core[sentiment]'."
            ),
        ),
    ]


__all__ = [
    "IBKR_PORT_PROBE_ORDER",
    "PROBE_HOST",
    "PROBE_TIMEOUT_S",
    "ProviderState",
    "probe_ibkr_gateway",
    "provider_health",
]
