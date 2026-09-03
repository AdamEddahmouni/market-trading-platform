"""Localhost HTTP server for the research screener.

Standard library only: no framework, no build step, no external asset. The server binds
``127.0.0.1`` and refuses to bind anything else, so nothing is exposed off the machine.

Every route is read-only with respect to research artifacts. The single writing route,
``POST /api/export``, writes a snapshot into the export directory and nowhere else.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import socket
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import export as export_module
from . import data_logger as data_logger_module
from . import snapshot as snapshot_module
from .api_contract import compatible_envelope, envelope, integration_manifest
from .deployment import DeploymentMode, deployment_mode as parse_deployment_mode
from .frozen import FrozenResearchUnavailable

HOST = "127.0.0.1"
DEFAULT_PORT = 8787
STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_BODY_BYTES = 2 * 1024 * 1024

CSRF_TOKEN_COOKIE = "squeeze_csrf"
CSRF_TOKEN_HEADER = "X-CSRF-Token"

RATE_LIMIT_WINDOW_S = 60
RATE_LIMIT_MAX_REQUESTS = 300

request_log = logging.getLogger("squeeze.screener.request")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def default_export_dir() -> Path:
    from .paths import repository_root

    return repository_root() / "exports" / "research-screener"


class ScreenerHandler(BaseHTTPRequestHandler):
    server_version = "SqueezeResearchScreener/1.0"
    export_dir: Path = Path(".")

    _rate_map: dict[str, list[float]] = {}
    _csrf_token: str = secrets.token_hex(32)
    _req_counter: int = 0

    # -------------------------------------------------------------- plumbing

    @classmethod
    def _check_rate(cls, client_ip: str) -> bool:
        now = time.monotonic()
        window = cls._rate_map.setdefault(client_ip, [])
        window[:] = [t for t in window if now - t < RATE_LIMIT_WINDOW_S]
        window.append(now)
        return len(window) <= RATE_LIMIT_MAX_REQUESTS

    @classmethod
    def csrf_token(cls) -> str:
        return cls._csrf_token

    def _request_id(self) -> str:
        rid = self.headers.get("X-Request-ID") or str(uuid.uuid4())
        return str(rid)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        """Quiet by default. Request lines can carry a manually typed symbol."""
        if self.server.verbose:  # type: ignore[attr-defined]
            request_log.info(
                "rid=%s ip=%s method=%s path=%s status=%s",
                self._request_id(), self.client_address[0],
                self.command, self.path, fmt % args if args else fmt,
            )
            super().log_message(fmt, *args)

    def _check_csrf(self, method: str) -> bool:
        return True

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Request-ID", self._request_id())
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message, "status": status}, status)

    def _static(self, name: str) -> None:
        candidate = (STATIC_DIR / name).resolve()
        if not candidate.is_file() or STATIC_DIR.resolve() not in candidate.parents:
            self._error(404, f"{name} not found")
            return
        content_type = CONTENT_TYPES.get(candidate.suffix, "application/octet-stream")
        self._send(200, candidate.read_bytes(), content_type)

    def _gateway_check(self, method: str) -> bool:
        """Returns True if the request passes all gateway checks."""
        client_ip = self.client_address[0]
        if not self._check_rate(client_ip):
            self._error(429, "Too many requests. Retry after " + str(RATE_LIMIT_WINDOW_S) + " seconds.")
            return False
        if not self._check_csrf(method):
            self._error(403, "CSRF token missing or invalid.")
            return False
        return True

    # ----------------------------------------------------------------- verbs

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
        if not self._gateway_check("GET"):
            return
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)
        try:
            self._route_get(route, query)
        except FrozenResearchUnavailable as exc:
            self._error(503, str(exc))
        except Exception as exc:  # noqa: BLE001 - a route fault must not kill the server
            self._error(500, f"{type(exc).__name__}: {exc}")

    def _route_get(self, route: str, query: dict[str, list[str]]) -> None:
        if route == "/":
            self._static("scanner.html")
        elif route in ("/advanced", "/index.html", "/research"):
            self._static("index.html")
        elif route.startswith("/static/"):
            self._static(route[len("/static/"):])
        elif route == "/health":
            self._json(envelope(
                {"server": "alive", "methodology_engine": "AVAILABLE"},
                mode=str(self.server.deployment_mode),  # type: ignore[attr-defined]
            ))
        elif route == "/ready":
            from .paths import FrozenLayout
            from .frozen_demo import load_frozen_demo

            local_mode = str(self.server.deployment_mode) == "LOCAL_FULL"  # type: ignore[attr-defined]
            private_loaded = local_mode and FrozenLayout().available
            demo_loaded = bool(load_frozen_demo()["rows"])
            self._json(envelope(
                {
                    "application_operational": True,
                    "api_available": True,
                    "methodology_engine_available": True,
                    "selected_frozen_source_loaded": private_loaded or demo_loaded,
                    "frozen_source": "PRIVATE_CANONICAL" if private_loaded else "FROZEN_DEMO",
                    "optional_ibkr_required": False,
                },
                mode=str(self.server.deployment_mode),  # type: ignore[attr-defined]
            ))
        elif route == "/api/health":
            payload = snapshot_module.health(
                cloud_mode=str(self.server.deployment_mode) != "LOCAL_FULL",  # type: ignore[attr-defined]
                deployment_mode=str(self.server.deployment_mode),  # type: ignore[attr-defined]
            )
            self._json(compatible_envelope(
                payload, mode=str(self.server.deployment_mode),  # type: ignore[attr-defined]
            ))
        elif route == "/api/readiness":
            self._json(compatible_envelope(
                snapshot_module.demo_readiness(),
                mode=str(self.server.deployment_mode),  # type: ignore[attr-defined]
            ))
        elif route == "/api/providers":
            payload = snapshot_module.health(
                cloud_mode=str(self.server.deployment_mode) != "LOCAL_FULL",  # type: ignore[attr-defined]
            )
            self._json(compatible_envelope(
                payload, mode=str(self.server.deployment_mode),  # type: ignore[attr-defined]
            ))
        elif route == "/api/capabilities":
            self._json(self._provider_capabilities())
        elif route == "/api/coverage":
            self._json(self._coverage_summary())
        elif route == "/api/screener":
            self._json(self._screener(query))
        elif route == "/api/symbol":
            self._json(self._symbol(query))
        elif route == "/api/frozen/candidates":
            payload = self._screener({**query, "mode": ["FROZEN_RESEARCH"]})
            self._json(compatible_envelope(payload, mode="FROZEN_RESEARCH"))
        elif route == "/api/frozen/candidate":
            payload = self._symbol({**query, "mode": ["FROZEN_RESEARCH"]})
            self._json(compatible_envelope(payload, mode="FROZEN_RESEARCH"))
        elif route.startswith("/api/frozen/candidate/"):
            symbol = route.rsplit("/", 1)[-1]
            self._json(envelope(
                self._symbol({"symbol": [symbol], "mode": ["FROZEN_RESEARCH"]}),
                mode="FROZEN_RESEARCH",
            ))
        elif route == "/api/live/candidates":
            self._json(self._screener({**query, "mode": ["CURRENT"]}))
        elif route == "/api/live/candidate":
            self._json(self._symbol({**query, "mode": ["CURRENT"]}))
        elif route == "/api/current/candidates":
            self._json(envelope(
                self._screener({**query, "mode": ["CURRENT"]}),
                mode="CURRENT",
            ))
        elif route.startswith("/api/current/candidate/"):
            symbol = route.rsplit("/", 1)[-1]
            self._json(envelope(
                self._symbol({"symbol": [symbol], "mode": ["CURRENT"]}),
                mode="CURRENT",
            ))
        elif route == "/api/methodologies":
            from . import session_state

            rows = session_state.get_session().rows()
            self._json(envelope(
                {
                    "methodology_ids": [
                        "legacy_prime_setup",
                        "peer_reference_methodology",
                        "adam_evidence_gated_prime.v1",
                    ],
                    "candidate_count": len(rows),
                    "rows": [
                        {
                            "symbol": row["symbol"],
                            "why_listed": row["why_listed"],
                            "methodologies": row["methodologies"],
                            "pressure": row["pressure"],
                            "ignition": row["ignition"],
                            "coverage": row["methodology_coverage"],
                            "trend": row["trend"],
                            "fields": row["fields"],
                            "phase3a": row["phase3a"],
                            "research_detection": row["research_detection"],
                            "freshness": row["freshness"],
                            "updated": row["last_updated"],
                        }
                        for row in rows
                    ],
                },
                mode="CURRENT",
            ))
        elif route.startswith("/api/methodologies/"):
            from . import session_state

            symbol = route.rsplit("/", 1)[-1].upper()
            detail = session_state.get_session().detail(symbol)
            if detail is None:
                self._json(envelope(
                    {"symbol": symbol, "methodologies": []},
                    mode="CURRENT", status="NOT_FOUND",
                    missingness=[{"field": "candidate", "reason": "symbol not tracked"}],
                ), 404)
            else:
                self._json(envelope(
                    {
                        "symbol": symbol,
                        "methodologies": detail["methodologies"],
                        "comparison": detail["methodology_comparison"],
                    },
                    mode="CURRENT",
                ))
        elif route == "/api/v1/integration/manifest":
            mode = str(self.server.deployment_mode)  # type: ignore[attr-defined]
            self._json(envelope(integration_manifest(mode), mode=mode))
        elif route == "/api/export":
            mode = (query.get("mode") or ["FROZEN_RESEARCH"])[0].upper()
            payload = (
                snapshot_module.current_snapshot(self._symbols(query))
                if mode == "CURRENT"
                else self._frozen_snapshot()
            )
            self._json(envelope(payload, mode=mode))
        elif route == "/api/discovery/profiles":
            from . import session_state

            session = session_state.get_session()
            self._json(
                {
                    "profiles": [item.as_dict() for item in session.profiles.values()],
                    "selected": session.profile_id,
                }
            )
        elif route in ("/api/research-summary", "/api/professor"):
            self._json(snapshot_module.research_summary())
        elif route == "/api/news/feed":
            self._json(self._news_feed(query))
        elif route == "/api/news/status":
            from .news_live import get_news_orchestrator
            orch = get_news_orchestrator()
            self._json(envelope(orch.status(), mode=str(self.server.deployment_mode)))
        elif route == "/api/collectors/status":
            from .collectors import get_collector_bundle

            bundle = get_collector_bundle()
            self._json(
                envelope(bundle.status(), mode=str(self.server.deployment_mode))
            )
        elif route == "/api/collectors/symbol":
            symbol = (query.get("symbol") or [""])[0].upper()
            if not symbol:
                self._json(
                    envelope({"error": "symbol required"}, mode=str(self.server.deployment_mode)),
                    400,
                )
                return
            from .collectors import get_collector_bundle

            detail = get_collector_bundle().store.symbol_detail(symbol)
            self._json(envelope(detail, mode=str(self.server.deployment_mode)))
        elif route == "/api/news/symbol":
            symbol = (query.get("symbol") or [""])[0].upper()
            if not symbol:
                self._json(envelope({"error": "symbol required"}, mode=str(self.server.deployment_mode)), 400)
                return
            from . import session_state
            session = session_state.get_session()
            detail = session.detail(symbol)
            if detail is None:
                self._json(envelope({"error": f"{symbol} not found"}, mode="CURRENT"), 404)
                return
            news = detail.get("news", [])
            self._json(envelope({
                "symbol": symbol,
                "headlines": news,
                "count": len(news),
            }, mode="CURRENT"))
        elif route == "/api/sentiment/status":
            from .sentiment_live import get_sentiment_analyzer
            sa = get_sentiment_analyzer()
            s = sa.status()
            self._json(envelope({
                "enabled": s.get("enabled", False),
                "model_id": s.get("model_id", "none"),
                "status": s,
            }, mode=str(self.server.deployment_mode)))
        elif route == "/api/sentiment/symbol":
            symbol = (query.get("symbol") or [""])[0].upper()
            if not symbol:
                self._json(envelope({"error": "symbol required"}, mode=str(self.server.deployment_mode)), 400)
                return
            from . import session_state
            session = session_state.get_session()
            detail = session.detail(symbol)
            if detail is None:
                self._json(envelope({"error": f"{symbol} not found"}, mode="CURRENT"), 404)
                return
            sentiment_data = detail.get("sentiment", {})
            self._json(envelope({
                "symbol": symbol,
                "sentiment": sentiment_data,
            }, mode="CURRENT"))
        elif route == "/api/logs/replay/raw":
            at = (query.get("at") or [None])[0]
            session = (query.get("session") or [None])[0]
            self._json(data_logger_module.log_replay_from_raw(at=at, session=session))
        elif route == "/api/logs/replay/timeline":
            session = (query.get("session") or [None])[0]
            self._json(data_logger_module.log_replay_timeline(session=session))
        elif route == "/api/logs/replay":
            at = (query.get("at") or [None])[0]
            session = (query.get("session") or [None])[0]
            self._json(data_logger_module.log_replay(at=at, session=session))
        elif route == "/api/discovery/cadence":
            from . import session_state
            self._json(session_state.discovery_cadence())
        elif route == "/api/logs/status":
            lines = self._number(query, "lines", int) or 20
            self._json(data_logger_module.log_status(tail_lines=min(lines, 200)))
        elif route == "/api/logs/archive":
            self._json(data_logger_module.list_archives())
        elif route.startswith("/api/logs/archive/download/"):
            name = route[len("/api/logs/archive/download/"):]
            self._serve_archive(name)
        elif route == "/api/enrichment/policies":
            self._json(snapshot_module.enrichment_policies_summary())
        elif route == "/api/phase-3d/registry":
            self._json(self._phase_3d_registry(query))
        elif route == "/healthz":
            """Bare health check for load balancers / Railway.

            Returns ``200`` with the deployment mode.  If the ``?expected=``
            query parameter is provided, returns ``200`` only when the actual
            mode matches the expected value; otherwise returns ``503`` so
            orchestration layers can reject a deployment running the wrong
            mode without inspecting the body.

            Example::

                GET /healthz?expected=CLOUD_PROVIDER_MODE    → 200 OK
                GET /healthz?expected=LOCAL_FULL             → 503 Service Unavailable
                GET /healthz                                 → 200 OK
            """
            _mode = str(self.server.deployment_mode)  # type: ignore[attr-defined]
            _expected_raw = (query.get("expected") or [None])[0]
            if _expected_raw is not None:
                _expected = _expected_raw.upper()
                if _expected != _mode:
                    self._json(
                        {
                            "status": "WRONG_DEPLOYMENT_MODE",
                            "deployment_mode": _mode,
                            "expected": _expected,
                            "message": f"Running {_mode}, expected {_expected}.",
                        },
                        status=503,
                    )
                    return
            self._json({"status": "ok", "deployment_mode": _mode})
        elif route == "/api/deployment":
            """Full deployment configuration for programmatic inspection."""
            _mode = str(self.server.deployment_mode)  # type: ignore[attr-defined]
            _cloud = _mode == "CLOUD_PROVIDER_MODE"
            _local = _mode == "LOCAL_FULL"
            _frozen_source = "PRIVATE_CANONICAL" if _local else "FROZEN_DEMO"
            self._json(envelope(
                {
                    "deployment_mode": _mode,
                    "bind_host": "0.0.0.0" if _cloud else "127.0.0.1",
                    "port": self.server.server_address[1],  # type: ignore[attr-defined]
                    "ibkr_enabled": _local,
                    "ibkr_probed": _local,
                    "frozen_source": _frozen_source,
                    "private_configuration_loaded": _local,
                    "browser_enabled": _local,
                    "capabilities_url": "/api/capabilities",
                    "health_url": "/healthz",
                    "health_url_with_mode": f"/healthz?expected={_mode}",
                },
                mode=_mode,
            ))
        elif route == "/api/meta":
            self._json(
                {
                    "title": snapshot_module.APP_TITLE,
                    "disclaimer": snapshot_module.DISCLAIMER,
                    "sort_keys": list(snapshot_module.SORT_KEYS),
                    "modes": [str(mode) for mode in snapshot_module.Mode],
                    "export_dir": str(self.export_dir),
                }
            )
        else:
            self._error(404, f"no route {route}")

    @staticmethod
    def _symbols(query: dict[str, list[str]]) -> list[str]:
        return [
            part
            for value in query.get("symbols", [])
            for part in value.replace(",", " ").split()
        ]

    def _provider_capabilities(self=None) -> dict[str, Any]:
        from .provider_capabilities import (
            Capability, CapabilityStatus, ProviderCapabilities, ProviderCapabilityRegistry,
        )

        registry = ProviderCapabilityRegistry()
        from .live_providers import get_runtime
        runtime = get_runtime()
        from . import session_state
        current_rows = session_state.get_session().rows()
        from .config import resolve_application_config

        ibkr_config = resolve_application_config(
            cli={"SQUEEZE_APP_MODE": str(self.server.deployment_mode)},  # type: ignore[attr-defined]
        ).providers.ibkr
        cloud = bool(
            self is not None
            and str(self.server.deployment_mode) != "LOCAL_FULL"  # type: ignore[attr-defined]
        )
        ibkr_disabled = not ibkr_config.enabled
        ibkr = ProviderCapabilities(
            provider="IBKR",
            configured=ibkr_config.enabled,
            connected=(
                session_state.get_session().provider.connected
                if ibkr_config.enabled
                else False
            ),
        )
        if ibkr_disabled:
            ibkr.set_not_configured(
                Capability.DISCOVERY, Capability.DELAYED_QUOTE,
                Capability.HISTORICAL_BARS, Capability.SHORTABILITY,
                Capability.BORROW_FEE, Capability.SHORTABLE_SHARES, Capability.HALTS,
                detail=(
                    "IBKR is disabled. Set IBKR_ENABLED=true and IBKR_HOST / IBKR_PORT / "
                    "IBKR_CLIENT_ID to connect a gateway."
                ),
            )
        elif cloud:
            ibkr.set_available(
                Capability.DISCOVERY, Capability.DELAYED_QUOTE, Capability.HISTORICAL_BARS,
                detail=(
                    f"Configured for remote gateway at {ibkr_config.host}:{ibkr_config.port}. "
                    "Connection is established on first use."
                ),
            )
            ibkr.set_permission_unavailable(
                Capability.BORROW_FEE, Capability.SHORTABLE_SHARES,
                detail="Requires market data entitlement not available.",
            )
            ibkr.set_available(
                Capability.SHORTABILITY,
                detail="Generic tick 236 (shortable indicator) when gateway is connected.",
            )
        else:
            ibkr.set_available(
                Capability.DISCOVERY, Capability.DELAYED_QUOTE, Capability.HISTORICAL_BARS,
                detail="Available through local IB Gateway on 127.0.0.1.",
            )
        ibkr.set_not_supported(
            Capability.REALTIME_QUOTE,
            detail="Real-time quotes require a market data subscription not present.",
        )
        if not ibkr_disabled and not cloud:
            ibkr.set_permission_unavailable(
                Capability.BORROW_FEE, Capability.SHORTABLE_SHARES,
                detail="Requires market data entitlement not available.",
            )
            ibkr.set_available(
                Capability.SHORTABILITY,
                detail="Generic tick 236 (shortable indicator) available.",
            )
        halt_observed = any(
            row.get("fields", {}).get("halted", {}).get("status") == "KNOWN"
            for row in current_rows
        )
        if ibkr_disabled or cloud:
            if cloud and ibkr_config.enabled and halt_observed:
                ibkr.set_available(
                    Capability.HALTS,
                    detail="Generic callback tick type 49 (halted) observed.",
                )
        elif halt_observed:
            ibkr.set_available(
                Capability.HALTS,
                detail="Generic callback tick type 49 (halted) observed.",
            )
        else:
            ibkr.set_permission_unavailable(
                Capability.HALTS,
                detail=(
                    "Gateway connected, but callback tick type 49 was not returned under "
                    "the current market-data entitlement."
                ),
            )
        ibkr.set_not_supported(
            Capability.FLOAT, Capability.SHORT_INTEREST,
            Capability.SHORT_FLOAT, Capability.DAYS_TO_COVER,
            Capability.NEWS, Capability.SENTIMENT,
            detail="Not supported by IBKR market data feeds.",
        )
        registry.register(ibkr)

        # SEC EDGAR
        sec = ProviderCapabilities(
            provider="SEC_EDGAR", configured=runtime.sec.configured, connected=False,
        )
        if runtime.sec.configured:
            sec.set_available(
                Capability.FILINGS,
                detail=(
                    "AVAILABLE · filings active · "
                    f"{runtime.status()['sec_edgar'].get('result_count', 0)} symbol result(s)."
                ),
            )
        else:
            sec.set_not_configured(
                Capability.FILINGS,
                detail="SEC EDGAR is disabled in this offline runtime.",
            )
        sec.set_not_supported(
            Capability.DISCOVERY, Capability.REALTIME_QUOTE, Capability.DELAYED_QUOTE,
            Capability.HISTORICAL_BARS, Capability.VOLUME, Capability.FLOAT,
            Capability.SHORT_INTEREST, Capability.BORROW_FEE, Capability.SHORTABILITY,
            Capability.NEWS, Capability.HALTS, Capability.SENTIMENT,
            detail="SEC EDGAR provides filing data only.",
        )
        registry.register(sec)

        fv_client = runtime.finviz
        na_client = runtime.news
        fh_client = runtime.finnhub

        # Finviz Elite
        runtime_status = runtime.status()
        fv_configured = fv_client.configured
        fv_verified = bool(runtime_status["finviz"]["fetched"])
        finviz = ProviderCapabilities(provider="Finviz Elite", configured=fv_configured,
                                       connected=fv_verified)
        if fv_verified:
            fv_status = fv_client.status()
            columns = set(fv_status.get("columns", []))
            finviz.set_available(
                Capability.DISCOVERY,
                detail=(
                    "CONFIGURED · AUTHENTICATED · EXPORT ACTIVE · "
                    f"{runtime_status['finviz']['rows']} rows · "
                    f"last success {fv_status.get('last_success_at')} · "
                    f"TTL {fv_status.get('ttl_seconds')}s."
                ),
            )
            column_capabilities = {
                Capability.FLOAT: {"Shares Float", "Float"},
                Capability.SHARES_OUTSTANDING: {"Shares Out."},
                Capability.SHORT_FLOAT: {"Short Float"},
                Capability.SHORT_RATIO: {"Short Ratio"},
                Capability.RELATIVE_VOLUME: {"Relative Volume"},
            }
            for capability, aliases in column_capabilities.items():
                if columns.intersection(aliases):
                    finviz.set_available(
                        capability,
                        detail="Field present in the authenticated Finviz export.",
                    )
                else:
                    finviz.set_permission_unavailable(
                        capability,
                        detail=(
                            "Authenticated export is active, but this field was not "
                            "present in the returned CSV columns."
                        ),
                    )
            finviz.set_not_supported(
                Capability.REALTIME_QUOTE, Capability.DELAYED_QUOTE,
                Capability.HISTORICAL_BARS, Capability.BORROW_FEE,
                Capability.SHORTABILITY, Capability.HALTS, Capability.SENTIMENT,
                Capability.FILINGS,
                detail="Not supported by Finviz Elite export API.",
            )
        elif not fv_configured:
            finviz.set_not_configured(
                Capability.DISCOVERY, Capability.FLOAT, Capability.SHARES_OUTSTANDING,
                Capability.SHORT_FLOAT,
                Capability.SHORT_RATIO, Capability.RELATIVE_VOLUME,
                detail="Not configured. Set FINVIZ_API_KEY in .private/providers.env.",
            )
        registry.register(finviz)

        # NewsAPI
        na_configured = na_client.configured
        na_verified = bool(runtime_status["newsapi"]["fetched"])
        newsapi = ProviderCapabilities(provider="NewsAPI", configured=na_configured,
                                        connected=na_verified)
        if na_verified:
            newsapi.set_available(
                Capability.NEWS,
                detail="Official NewsAPI v2/everything endpoint. ~90 req/day.",
            )
        elif not na_configured:
            newsapi.set_not_configured(
                Capability.NEWS,
                detail="Not configured. Set NEWSAPI_KEY in .private/providers.env.",
            )
        registry.register(newsapi)

        # Finnhub
        fh_configured = fh_client.configured
        fh_verified = bool(runtime_status["finnhub"].get("fetched"))
        finnhub = ProviderCapabilities(provider="Finnhub", configured=fh_configured,
                                        connected=fh_verified)
        if fh_verified:
            finnhub.set_available(
                Capability.REALTIME_QUOTE,
                detail=(
                    "AUTHENTICATED · quote fallback active · "
                    f"{runtime_status['finnhub'].get('price_count', 0)} price(s)."
                ),
            )
        if not fh_configured:
            finnhub.set_not_configured(
                Capability.REALTIME_QUOTE,
                detail="Not configured. Set FINNHUB_KEY in .private/providers.env.",
            )
        registry.register(finnhub)

        # Finnhub News
        from .news_live import get_news_orchestrator
        news_orch = get_news_orchestrator()
        news_orch_status = news_orch.status()
        fh_news_configured = False
        fh_news_status = "NOT_CONFIGURED"
        for pid, pinfo in news_orch_status.get("providers", {}).items():
            if pid == "Finnhub News" and pinfo.get("configured"):
                fh_news_configured = True
                fh_news_status = pinfo.get("status", "NOT_CONFIGURED")

        finnhub_news = ProviderCapabilities(
            provider="Finnhub News", configured=fh_news_configured,
            connected=(fh_news_status == "READY"),
        )
        if fh_news_status == "READY":
            finnhub_news.set_available(
                Capability.NEWS,
                detail=f"Finnhub company-news endpoint active. Status: {fh_news_status}.",
            )
        elif fh_news_configured:
            finnhub_news.set_available(
                Capability.NEWS,
                detail=f"Finnhub company-news endpoint configured. Status: {fh_news_status}.",
            )
        else:
            finnhub_news.set_not_configured(
                Capability.NEWS,
                detail="Finnhub news requires FINNHUB_KEY with a plan that includes company news access.",
            )
        registry.register(finnhub_news)

        # FinBERT Sentiment
        from .sentiment_live import get_sentiment_analyzer
        sa = get_sentiment_analyzer()
        sentiment_status = sa.status()
        sentiment_configured = sentiment_status.get("enabled", False)
        sentiment_ready = sentiment_status.get("model_loaded", False)

        finbert = ProviderCapabilities(
            provider="FinBERT Sentiment", configured=sentiment_configured,
            connected=sentiment_ready,
        )
        if sentiment_ready:
            finbert.set_available(
                Capability.SENTIMENT,
                detail=(
                    f"EXPERIMENTAL · model {sentiment_status.get('model_id', 'unknown')} · "
                    "loaded"
                ),
            )
        elif sentiment_configured:
            finbert.set_available(
                Capability.SENTIMENT,
                detail=(
                    "CONFIGURED · model loading failed or pending: "
                    f"{sentiment_status.get('load_error') or sa.load_error or 'unknown'}"
                ),
            )
        else:
            finbert.set_not_configured(
                Capability.SENTIMENT,
                detail="MODEL_NOT_DEPLOYED — FinBERT sentiment is local-only. "
                "Not available in cloud deployments.",
            )
        registry.register(finbert)

        # Schwab
        schwab_configured = bool(runtime.credentials.values.get("SCHWAB_APP_KEY"))
        schwab = ProviderCapabilities(provider="Schwab",
                                       configured=schwab_configured, connected=False,
                                       missing_config_keys=["SCHWAB_APP_KEY"])
        schwab.set_not_supported(
            Capability.DISCOVERY, Capability.REALTIME_QUOTE, Capability.DELAYED_QUOTE,
            Capability.HISTORICAL_BARS, Capability.VOLUME, Capability.FLOAT,
            Capability.SHORT_INTEREST, Capability.BORROW_FEE, Capability.SHORTABILITY,
            Capability.NEWS, Capability.FILINGS, Capability.HALTS, Capability.SENTIMENT,
            detail="Schwab API exists in archived code but is not active. Token store excluded by policy.",
        )
        registry.register(schwab)

        return registry.as_dict()

    @staticmethod
    def _refresh_all_providers_async() -> dict[str, Any]:
        """Launch a background refresh; return 202 Accepted immediately."""
        from . import session_state

        session = session_state.get_session()
        total = len(session.states)

        def _background_refresh():
            try:
                session.refresh_all(limit=total)
                from .session_state import _sec_cache
                _sec_cache.clear()
            except Exception:
                request_log.exception("Background refresh failed")

        t = threading.Thread(target=_background_refresh, daemon=True)
        t.start()
        return {
            "accepted": True,
            "total": total,
            "message": f"Background refresh started for {total} symbol(s). Poll /api/screener?mode=CURRENT for results.",
            "at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _coverage_summary() -> dict[str, Any]:
        from . import session_state

        session = session_state.get_session()
        summary = session.summary()
        rows = session.rows()

        field_coverage: dict[str, dict[str, Any]] = {
            "quote": {"fields": ["last", "bid", "ask", "high", "low", "open", "previous_close"],
                      "available": 0, "total": 7},
            "short_pressure": {"fields": ["shortable", "borrow_availability", "shares_outstanding",
                                          "float_shares", "short_float", "published_short_interest",
                                          "borrow_fee", "days_to_cover", "halted"],
                               "available": 0, "total": 9},
            "catalyst": {"fields": ["sec_filings", "catalyst", "sentiment"],
                         "available": 0, "total": 3},
        }

        if rows:
            sample = rows[0]
            for category in field_coverage:
                for field_name in field_coverage[category]["fields"]:
                    cell = sample.get("fields", {}).get(field_name, {})
                    if cell.get("status") == "KNOWN":
                        field_coverage[category]["available"] += 1

        return {
            "field_coverage": field_coverage,
            "total_fields": sum(c["total"] for c in field_coverage.values()),
            "total_available": sum(c["available"] for c in field_coverage.values()),
            "evaluable_rules": summary.get("evaluable_rule_count", 0),
            "total_rules": 25,
            "candidate_count": summary.get("candidate_count", 0),
            "market_data_mode": summary.get("market_data_mode", "UNKNOWN"),
        }

    @staticmethod
    def _news_feed(query: dict[str, list[str]]) -> dict[str, Any]:
        """Aggregate headlines across all current screener candidates.

        Query params:
        - ``classification``: comma-separated filter (e.g. PRIME,SUBPRIME)
        - ``limit``: max headlines returned (default 30, max 100)
        """
        from . import session_state
        from .news_live import get_news_orchestrator

        # Parse filter params
        raw_cls = (query.get("classification") or [""])[0]
        wanted = {
            c.strip().upper()
            for c in raw_cls.split(",")
            if c.strip()
        } if raw_cls else None

        raw_limit = (query.get("limit") or ["30"])[0]
        try:
            limit = min(max(int(raw_limit), 1), 100)
        except (ValueError, TypeError):
            limit = 30

        # Classification extraction helper (mirrors scanner.js)
        def _classification(row: dict[str, Any]) -> str:
            for m in row.get("methodologies") or []:
                if m.get("methodology_id") == "adam_evidence_gated_prime.v1":
                    return m.get("classification", "UNEVALUABLE")
            return "UNEVALUABLE"

        # Get rows: try live first, fall back to frozen
        rows: list[dict[str, Any]] = []
        try:
            session = session_state.get_session()
            rows = session.rows()
        except Exception:
            pass
        if not rows:
            try:
                frozen = snapshot_module.frozen_snapshot()
                rows = frozen.get("rows", [])
            except Exception:
                pass

        if not rows:
            return {"headlines": [], "count": 0, "symbols_scanned": 0}

        # Build priority-ordered symbol list: PRIME → SUBPRIME → WATCH → rest
        priority_order = {"PRIME": 0, "SUBPRIME": 1, "WATCH": 2}
        all_candidates: list[tuple[dict[str, Any], str]] = []
        for row in rows:
            cls = _classification(row)
            all_candidates.append((row, cls))
        all_candidates.sort(key=lambda t: priority_order.get(t[1], 99))

        all_symbols = [(row["symbol"], cls) for row, cls in all_candidates]

        if not all_symbols:
            return {"headlines": [], "count": 0, "counts": {},
                    "symbols_scanned": 0, "symbols": []}

        # Always fetch ALL candidates so counts are accurate for every pill.
        # The orchestrator caches per-symbol results, so repeated calls are cheap.
        orch = get_news_orchestrator()
        all_items: list[dict[str, Any]] = []
        fetched = 0
        for sym, cls in all_symbols:
            try:
                headlines = orch.fetch_news(sym)
            except Exception:
                headlines = []
            if headlines:
                fetched += 1
            for h in headlines:
                all_items.append({
                    "symbol": sym,
                    "classification": cls,
                    "headline": h.get("headline", ""),
                    "time": h.get("timestamp", None),
                    "source": h.get("source") or h.get("provider", None),
                    "url": h.get("url", None),
                })

        # Sort by time descending (nulls last)
        def _sort_key(item: dict[str, Any]) -> float:
            t = item.get("time")
            if not t:
                return 0
            try:
                return datetime.fromisoformat(
                    str(t).replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, TypeError):
                return 0

        all_items.sort(key=_sort_key, reverse=True)

        # Compute per-classification counts from ALL items (always accurate)
        counts: dict[str, int] = {}
        for item in all_items:
            c = item.get("classification", "UNKNOWN")
            counts[c] = counts.get(c, 0) + 1

        # Filter headlines by requested classification
        if wanted:
            all_items = [
                i for i in all_items
                if i.get("classification") in wanted
            ]

        all_items = all_items[:limit]

        return {
            "headlines": all_items,
            "count": len(all_items),
            "counts": counts,
            "symbols_scanned": len(all_symbols),
            "symbols_fetched": fetched,
            "symbols": [s for s, _ in all_symbols],
        }

    @staticmethod
    def _phase_3d_registry(query: dict[str, list[str]]) -> dict[str, Any]:
        """Expose Phase 3D Batch 01/02 registry entries and audit results.

        Reads the deterministic build artifacts from ``build/acquisition/batch-01/``
        and ``build/acquisition/batch-02/``. Returns summary counts, per-case
        registry entries with audit results, and the batch interpretation.

        Query params:
        - ``batch``: "01", "02", or "all" (default "all")
        """
        import json as _json

        batch_filter = (query.get("batch") or ["all"])[0].lower()

        from .paths import repository_root
        root = repository_root()
        build_root = root / "build" / "acquisition"

        def _read_json(path: Path) -> dict[str, Any] | None:
            try:
                return _json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, _json.JSONDecodeError):
                return None

        def _load_batch(batch_dir: str) -> dict[str, Any] | None:
            d = build_root / batch_dir
            summary = _read_json(d / "batch-summary.json")
            if summary is None:
                return None
            registry = _read_json(d / "phase3b-registry-candidates.json")
            leakage = _read_json(d / "leakage-audit.json")
            identity = _read_json(d / "identity-review.json")
            eligibility = _read_json(d / "eligibility-review.json")
            boundaries = _read_json(d / "boundary-freeze-manifest.json")
            outcome_source = _read_json(d / "outcome-source-search.json")

            leakage_map: dict[str, dict[str, Any]] = {}
            if leakage:
                for a in leakage.get("audits", []):
                    leakage_map[a["case_attempt_id"]] = a

            registry_map: dict[str, dict[str, Any]] = {}
            if registry:
                for e in registry.get("entries", []):
                    registry_map[e["case_id"]] = e

            # Build symbol→case_id lookup for cross-artifact matching.
            symbol_to_eid: dict[str, str] = {
                entry.get("symbol", ""): eid
                for eid, entry in registry_map.items()
            }

            identity_map: dict[str, dict[str, Any]] = {}
            if identity:
                for r in identity.get("resolutions", []):
                    sym = r.get("canonical_symbol") or ""
                    eid = symbol_to_eid.get(sym)
                    if eid is not None:
                        identity_map[eid] = r

            eligibility_map: dict[str, dict[str, Any]] = {}
            if eligibility:
                for d2 in eligibility.get("decisions", []):
                    cid = d2.get("case_attempt_id") or ""
                    eid = symbol_to_eid.get(
                        next((entry.get("symbol", "")
                              for entry in registry_map.values()
                              if entry.get("case_id") == cid), "")
                    )
                    if eid is not None:
                        eligibility_map[eid] = d2

            boundaries_map: dict[str, dict[str, Any]] = {}
            if boundaries:
                for b in boundaries.get("boundaries", []):
                    boundaries_map[b.get("case_attempt_id", "")] = b

            cases: list[dict[str, Any]] = []
            for eid, entry in sorted(registry_map.items()):
                case = {
                    "case_id": entry.get("case_id"),
                    "symbol": entry.get("symbol"),
                    "case_status": entry.get("case_status"),
                    "case_type": entry.get("case_type"),
                    "fixture_classification": entry.get("fixture_classification"),
                    "leakage_audit_passed": leakage_map.get(eid, {}).get("passed"),
                    "leakage_diagnostic_codes": leakage_map.get(eid, {}).get("diagnostic_codes", []),
                    "identity_state": identity_map.get(eid, {}).get("state"),
                    "eligibility_included": eligibility_map.get(eid, {}).get("included"),
                    "eligibility_exclusion_codes": list(
                        eligibility_map.get(eid, {}).get("exclusion_codes", [])
                    ),
                    "boundary_timestamp": boundaries_map.get(eid, {}).get("boundary_timestamp"),
                    "boundary_rule": boundaries_map.get(eid, {}).get("boundary_rule"),
                    "limitations": entry.get("limitations", []),
                }
                cases.append(case)

            result: dict[str, Any] = {
                "batch_id": summary.get("batch_id"),
                "acquisition_plan_id": summary.get("acquisition_plan_id"),
                "acquisition_plan_version": summary.get("acquisition_plan_version"),
                "discovery_source_class": summary.get("discovery_source_class"),
                "outcome_blinding_state": summary.get("outcome_blinding_state"),
                "attempted_case_count": summary.get("attempted_case_count"),
                "unique_identity_count": summary.get("unique_identity_count"),
                "registry_only_case_count": summary.get("registry_only_case_count"),
                "complete_dataset_candidate_count": summary.get("complete_dataset_candidate_count"),
                "boundaries_frozen_count": summary.get("boundaries_frozen_count"),
                "leakage_passed_count": summary.get("leakage_passed_count"),
                "leakage_failed_count": summary.get("leakage_failed_count"),
                "outcome_windows_captured_count": summary.get("outcome_windows_captured_count"),
                "outcome_source_acceptable": summary.get("outcome_source_acceptable"),
                "outcome_source_conclusion_code": summary.get("outcome_source_conclusion_code"),
                "cases": cases,
                "interpretation": summary.get("interpretation"),
            }
            if outcome_source:
                result["outcome_source_search"] = {
                    "sources_evaluated": len(outcome_source.get("candidate_sources", [])),
                    "candidate_sources": [
                        {
                            "source_name": s.get("source_name"),
                            "source_kind": s.get("source_kind"),
                            "disposition_code": s.get("disposition_code"),
                            "detail": s.get("detail"),
                            "acceptable": s.get("acceptable"),
                        }
                        for s in outcome_source.get("candidate_sources", [])
                    ],
                }
            return result

        batches: dict[str, Any] = {}
        if batch_filter in ("all", "01"):
            b01 = _load_batch("batch-01")
            if b01:
                batches["batch-01"] = b01

        if batch_filter in ("all", "02"):
            b02 = _load_batch("batch-02")
            if b02:
                batches["batch-02"] = b02

        if not batches:
            return {
                "available": False,
                "message": (
                    "No Phase 3D registry artifacts found. Run "
                    "scripts/acquisition/generate_batch01_outputs.py and "
                    "scripts/acquisition/generate_batch02_outputs.py first."
                ),
                "batches": {},
            }

        return {
            "available": True,
            "batches": batches,
        }

    @staticmethod
    def _number(query: dict[str, list[str]], name: str, cast=float):
        raw = (query.get(name) or [None])[0]
        if raw in (None, ""):
            return None
        try:
            return cast(raw)
        except (TypeError, ValueError):
            return None

    def _screener(self, query: dict[str, list[str]]) -> dict[str, Any]:
        mode = (query.get("mode") or ["FROZEN_RESEARCH"])[0].upper()
        if mode == "CURRENT":
            payload = snapshot_module.current_snapshot(
                self._symbols(query),
                refresh=(query.get("refresh") or ["false"])[0].lower()
                in ("1", "true", "yes"),
            )
        else:
            payload = self._frozen_snapshot()

        rows = payload.get("rows", [])
        payload["unfiltered_row_count"] = len(rows)
        rows = snapshot_module.filter_rows(
            rows,
            symbol=(query.get("symbol") or [None])[0],
            research_detection=(query.get("detection") or [None])[0],
            data_mode=(query.get("data_mode") or [None])[0],
            freshness=(query.get("freshness") or [None])[0],
            discovery_profile=(query.get("profile") or [None])[0],
            market_data_mode=(query.get("market_mode") or [None])[0],
            min_pass=self._number(query, "min_pass", int),
            max_unknown=self._number(query, "max_unknown", int),
            min_coverage=self._number(query, "min_coverage", int),
            min_price=self._number(query, "min_price"),
            max_price=self._number(query, "max_price"),
            min_percentage_change=self._number(query, "min_change"),
            min_relative_volume=self._number(query, "min_relvol"),
        )
        rows = snapshot_module.sort_rows(
            rows,
            (query.get("sort") or ["symbol"])[0],
            (query.get("desc") or ["false"])[0].lower() in ("1", "true", "yes"),
        )
        payload["rows"] = rows
        payload["row_count"] = len(rows)
        return payload

    def _symbol(self, query: dict[str, list[str]]) -> dict[str, Any]:
        symbol = (query.get("symbol") or [""])[0]
        mode = (query.get("mode") or ["FROZEN_RESEARCH"])[0].upper()
        if not symbol:
            return {"error": "symbol is required"}
        if mode == "CURRENT":
            return snapshot_module.current_detail(symbol)
        detail = self._frozen_detail(symbol)
        if detail is None:
            return {
                "error": f"{symbol.upper()} is not one of the 13 frozen research cases.",
                "available": False,
            }
        return detail

    def do_POST(self) -> None:  # noqa: N802
        if not self._gateway_check("POST"):
            return
        content_len = self.headers.get("Content-Length")
        if content_len and int(content_len) > MAX_BODY_BYTES:
            self._error(413, f"Request body exceeds {MAX_BODY_BYTES // 1024 // 1024} MB limit.")
            return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/export":
                self._export(query)
                return
            if parsed.path == "/api/discovery/refresh":
                payload = snapshot_module.discovery_refresh(
                    (query.get("profile") or [None])[0]
                )
                self._json(compatible_envelope(payload, mode="CURRENT"))
                return
            if parsed.path == "/api/live/refresh":
                self._json(snapshot_module.live_refresh())
                return
            if parsed.path == "/api/current/refresh":
                self._json(envelope(snapshot_module.live_refresh(), mode="CURRENT"))
                return
            if parsed.path == "/api/refresh/all":
                self._json(self._refresh_all_providers_async(), 202)
                return
            if parsed.path == "/api/live/auto":
                enabled = (query.get("enabled") or ["false"])[0].lower() in (
                    "1", "true", "yes", "on",
                )
                self._json(snapshot_module.set_auto_refresh(enabled))
                return
            if parsed.path == "/api/live/clear":
                from . import session_state

                session_state.get_session().clear()
                self._json({"cleared": True})
                return
            if parsed.path == "/api/logs/rotate":
                self._json(data_logger_module.rotate_logs())
                return
            self._error(404, f"no route {parsed.path}")
        except FrozenResearchUnavailable as exc:
            self._error(503, str(exc))
        except Exception as exc:  # noqa: BLE001 - a route fault must not kill the server
            self._error(500, f"{type(exc).__name__}: {exc}")

    def _serve_archive(self, name: str) -> None:
        """Serve a .tar.gz archive file as a downloadable attachment.

        Delegates all path-traversal and existence checks to
        ``resolve_archive_path()`` which is the single public entry point.
        """
        from .data_logger import resolve_archive_path

        archive_path = resolve_archive_path(name)
        if archive_path is None:
            self._error(404, f"Archive {name!r} not found.")
            return

        try:
            body = archive_path.read_bytes()
        except Exception as exc:
            self._error(500, f"Failed to read archive: {exc}")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", self._request_id())
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ snapshots

    def _frozen_snapshot(self) -> dict[str, Any]:
        if str(self.server.deployment_mode) == "LOCAL_FULL":  # type: ignore[attr-defined]
            return snapshot_module.frozen_snapshot()
        from .frozen_demo import frozen_demo_snapshot

        return frozen_demo_snapshot()

    def _frozen_detail(self, symbol: str) -> dict[str, Any] | None:
        if str(self.server.deployment_mode) == "LOCAL_FULL":  # type: ignore[attr-defined]
            return snapshot_module.frozen_detail(symbol)
        from .frozen_demo import frozen_demo_detail

        return frozen_demo_detail(symbol)

    def _export(self, query: dict[str, list[str]]) -> None:
        try:
            mode = (query.get("mode") or ["FROZEN_RESEARCH"])[0].upper()
            if mode == "CURRENT":
                payload = snapshot_module.current_snapshot(self._symbols(query))
                details: dict[str, Any] = {
                    row["symbol"]: snapshot_module.current_detail(row["symbol"])
                    for row in payload["rows"]
                }
                for detail in details.values():
                    if detail is not None:
                        detail.pop("chart", None)
            else:
                payload = self._frozen_snapshot()
                details = {
                    row["symbol"]: self._frozen_detail(row["symbol"])
                    for row in payload["rows"]
                }
                for detail in details.values():
                    if detail is not None:
                        detail.pop("chart", None)
            written = export_module.write_export(payload, self.export_dir, details=details)
            if str(self.server.deployment_mode) != "LOCAL_FULL":  # type: ignore[attr-defined]
                written = {key: Path(value).name for key, value in written.items()}
            result = {"written": written, "row_count": payload["row_count"]}
            self._json(compatible_envelope(result, mode=mode))
        except FrozenResearchUnavailable as exc:
            self._error(503, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._error(500, f"{type(exc).__name__}: {exc}")


class ScreenerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        handler,
        *,
        verbose: bool = False,
        mode: DeploymentMode = DeploymentMode.LOCAL_FULL,
    ) -> None:
        host, _port = address
        # Allow 0.0.0.0 in CLOUD_PROVIDER_MODE (cloud deployments) or in
        # LOCAL_FULL when HOST=0.0.0.0 is explicitly set (Docker compose).
        _docker_local = (
            host == "0.0.0.0"
            and mode is DeploymentMode.LOCAL_FULL
            and os.environ.get("HOST") == "0.0.0.0"
        )
        _cloud = host == "0.0.0.0" and mode is DeploymentMode.CLOUD_PROVIDER_MODE
        if host not in ("127.0.0.1", "localhost") and not _cloud and not _docker_local:
            raise ValueError(
                f"refusing to bind {host!r} outside explicit CLOUD_PROVIDER_MODE"
            )
        self.verbose = verbose
        self.deployment_mode = mode
        super().__init__(address, handler)


def find_free_port(preferred: int = DEFAULT_PORT, attempts: int = 20) -> int:
    """First free port at or after ``preferred``."""
    for offset in range(attempts):
        candidate = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((HOST, candidate))
            except OSError:
                continue
            return candidate
    raise OSError(f"no free port found in [{preferred}, {preferred + attempts})")


def build_server(
    port: int = DEFAULT_PORT,
    *,
    export_dir: Path | None = None,
    verbose: bool = False,
    host: str = HOST,
    deployment_mode: str | DeploymentMode = DeploymentMode.LOCAL_FULL,
) -> ScreenerServer:
    mode = (
        deployment_mode
        if isinstance(deployment_mode, DeploymentMode)
        else parse_deployment_mode(deployment_mode)
    )
    handler = type(
        "BoundScreenerHandler",
        (ScreenerHandler,),
        {"export_dir": Path(export_dir) if export_dir else default_export_dir()},
    )
    return ScreenerServer((host, port), handler, verbose=verbose, mode=mode)


__all__ = [
    "DEFAULT_PORT",
    "HOST",
    "STATIC_DIR",
    "ScreenerHandler",
    "ScreenerServer",
    "build_server",
    "default_export_dir",
    "find_free_port",
]
