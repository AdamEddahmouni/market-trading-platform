"""Screener setup: what a degraded state means and the one step that fixes it.

Degraded states stay truthful (the reason code is never hidden); this module adds a
plain-language ``remedy`` beside them and a setup checklist built from the status
builders the Screener already uses. No new probes run on render.

``connect_provider`` is the only mutating entry point. It is a strict allowlist of
local processes IMP may start on the operator's click: moomoo OpenD (the installed
Windows executable), the local FinBERT load, and the loopback synthesis server. It
never downloads, installs, or accepts credentials; keys and flags stay operator steps.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

AUTH_COMMAND = "python tools/news/auth.py configure"
RESTART = "then restart the API"


def _remedy(title: str, step: str, action: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"title": title, "step": step, "action": action}


def _connect(provider: str, label: str) -> dict[str, Any]:
    return {"kind": "CONNECT", "provider": provider, "label": label}


def _command(command: str) -> dict[str, Any]:
    return {"kind": "COMMAND", "command": command}


def _flag(flag: str, what: str) -> dict[str, Any]:
    return _remedy(f"{what} is switched off", f"Set {flag}=1 in the API environment, {RESTART}.")


_OPEND_DOWN = _remedy("moomoo OpenD isn't running",
                      "Start OpenD and log in to load {scope}.", _connect("opend", "Start OpenD"))
_KEYS = _command(AUTH_COMMAND)

REMEDIES: dict[str, dict[str, Any]] = {
    # moomoo OpenD (ETF and Futures catalogs, live quotes)
    "OPEND_UNAVAILABLE": _OPEND_DOWN,
    "OPEN_D_NOT_RUNNING": _OPEND_DOWN,
    "PORT_UNREACHABLE": _remedy("OpenD is starting or not logged in",
                                "Finish the OpenD login; {scope} load once it accepts connections.",
                                _connect("opend", "Retry OpenD")),
    "OPEN_D_NOT_INSTALLED": _remedy("moomoo OpenD isn't installed",
                                    "Install moomoo OpenD to %APPDATA%\\moomoo_OpenD, then start it."),
    "SDK_MISSING": _remedy("The moomoo SDK isn't installed", "Install it into the IMP interpreter, " + RESTART + ".",
                           _command("python tools/imp.py env install-opend")),
    "SDK_INCOMPATIBLE": _remedy("The moomoo SDK version doesn't match", "Reinstall it into the IMP interpreter, " + RESTART + ".",
                                _command("python tools/imp.py env install-opend")),
    "QUOTE_CONTEXT_FAILED": _remedy("OpenD is up but refuses quotes", "Check the OpenD login and market-data entitlements."),
    # SEC (EDGAR filings, SEC press RSS)
    "SEC_USER_AGENT_NOT_SET": _remedy("SEC requires a contact User-Agent",
                                      "Set SEC_USER_AGENT to your name and email (e.g. \"Jane Doe jane@example.com\") "
                                      f"in the API environment, {RESTART}."),
    "IMP_EDGAR_LIVE_NOT_SET": _flag("IMP_EDGAR_LIVE", "SEC EDGAR"),
    # Live gates
    "IMP_NEWSAPI_LIVE_NOT_SET": _remedy("NewsAPI is switched off", f"Store a NewsAPI key (this also enables it), {RESTART}.", _KEYS),
    "IMP_FINNHUB_LIVE_NOT_SET": _remedy("Finnhub is switched off", f"Store a Finnhub key (this also enables it), {RESTART}.", _KEYS),
    "FINVIZ_LIVE_DISABLED": _flag("IMP_FINVIZ_LIVE", "Finviz Elite"),
    "IMP_NEWS_RSS_LIVE_NOT_SET": _flag("IMP_NEWS_RSS_LIVE", "Public RSS feeds"),
    "IMP_PUBLIC_RECORDS_LIVE_NOT_SET": _flag("IMP_PUBLIC_RECORDS_LIVE", "Public records"),
    "NO_NEWS_PROVIDER_CONFIGURED": _remedy("No news provider is switched on",
                                           f"Enable at least one source (RSS is free: IMP_NEWS_RSS_LIVE=1), {RESTART}."),
    # Keys
    "NEWSAPI_API_KEY_NOT_SET": _remedy("NewsAPI has no key", f"Store a free Developer key, {RESTART}.", _KEYS),
    "FINNHUB_API_KEY_NOT_SET": _remedy("Finnhub has no key", f"Store a free account key, {RESTART}.", _KEYS),
    "FINVIZ_API_KEY_NOT_SET": _remedy("Finviz Elite has no key", f"Set FINVIZ_API_KEY in .private/providers.env, {RESTART}."),
    "ANTHROPIC_API_KEY_NOT_SET": _remedy("AI synthesis has no provider",
                                         f"Store an Anthropic key, or install the free local model, {RESTART}.", _KEYS),
    "NO_SYNTHESIS_PROVIDER_CONFIGURED": _remedy("AI synthesis has no provider",
                                                f"Install the free local model, {RESTART}.",
                                                _command("python tools/news/setup_local_synthesis.py")),
    # Local models
    "IMP_FINBERT_MODEL_PATH_NOT_SET": _remedy("Sentiment model isn't installed", f"Install local FinBERT once, {RESTART}.",
                                              _command("python tools/news/setup_finbert.py")),
    "MODEL_PATH_NOT_FOUND": _remedy("Sentiment model files are missing", f"Reinstall local FinBERT, {RESTART}.",
                                    _command("python tools/news/setup_finbert.py")),
    "TRANSFORMERS_NOT_INSTALLED": _remedy("Sentiment runtime isn't installed", f"Install local FinBERT, {RESTART}.",
                                          _command("python tools/news/setup_finbert.py")),
    "MODEL_LOAD_FAILED": _remedy("Sentiment model failed to load", "Check the install, then restart the API.",
                                 _command("python tools/news/setup_finbert.py --check")),
    "NOT_LOADED_YET": _remedy("Sentiment model isn't loaded yet", "It loads on first use; load it now to score stories sooner.",
                              _connect("finbert", "Load model")),
    "MODEL_LOADING": _remedy("Sentiment model is loading", "Takes up to a minute; sentiment fills in automatically."),
    "LOCAL_RUNTIME_NOT_FOUND": _remedy("Local AI runtime isn't installed", f"Install it once, {RESTART}.",
                                       _command("python tools/news/setup_local_synthesis.py")),
    "LOCAL_MODEL_FILE_NOT_FOUND": _remedy("Local AI model isn't installed", f"Install it once, {RESTART}.",
                                          _command("python tools/news/setup_local_synthesis.py")),
    "STARTS_ON_REQUEST": _remedy("Local AI model starts on request", "Start it now so the first synthesis is faster.",
                                 _connect("local_synthesis", "Start model")),
    "LOCAL_MODEL_PORT_IN_USE": _remedy("Another program holds the local AI port", "Close it, then start the model again."),
    # Senate eFD (operator import)
    "SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE": _remedy(
        "Senate eFD needs your terms acceptance",
        "Accept the terms at efdsearch.senate.gov, save report pages to a folder, and set IMP_SENATE_EFD_IMPORT_DIR to it."),
    "SENATE_EFD_IMPORT_DIR_MISSING": _remedy("Senate import folder not found",
                                             "Point IMP_SENATE_EFD_IMPORT_DIR at an existing folder of saved eFD pages."),
    "OPERATOR_ATTESTATION_MISSING": _remedy("Senate import has no attestation",
                                            "Add the terms-acceptance attestation file to the import folder."),
}


def remedy_for(reason: str | None, *, scope: str = "this universe") -> dict[str, Any] | None:
    """The fix for a reason code, or None when the code needs no operator step."""

    if not reason:
        return None
    remedy = REMEDIES.get(reason)
    if remedy is None:
        return None
    return {**remedy, "reason": reason, "title": remedy["title"].format(scope=scope), "step": remedy["step"].format(scope=scope)}


def with_remedy(status: dict[str, Any], *, scope: str = "this universe") -> dict[str, Any]:
    """Adds ``remedy`` to a provider status that is not current (never to a working provider)."""

    if status.get("state") in ("CURRENT", "DELAYED", "NOT_APPLICABLE", "READY", "PUBLICATION_CURRENT"):
        # FinBERT reports CURRENT while it is not yet loaded; its reason still carries a step.
        if status.get("reason") not in ("MODEL_LOADING", "NOT_LOADED_YET", "STARTS_ON_REQUEST"):
            return status
    remedy = remedy_for(status.get("reason"), scope=scope)
    return {**status, "remedy": remedy} if remedy else status


# ------------------------------------------------------------------ OpenD
OPEND_CHECK_TTL_S = 15.0
_opend_lock = threading.Lock()
_opend_cache: tuple[float, dict[str, Any]] | None = None


def _diagnose_opend(start: bool) -> dict[str, Any]:
    from ..local_state.opend import diagnose_opend

    return diagnose_opend(start=start)


def opend_status(*, diagnose: Callable[[bool], dict[str, Any]] = _diagnose_opend, force: bool = False,
                 clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Setup row for OpenD from the existing check; cached briefly because the check shells out."""

    global _opend_cache
    with _opend_lock:
        if not force and _opend_cache is not None and clock() - _opend_cache[0] < OPEND_CHECK_TTL_S:
            return _opend_cache[1]
    try:
        report = diagnose(False)
    except Exception:  # noqa: BLE001 — a failed check is a state
        report = {"status": "CHECK_FAILED"}
    row = _opend_row(report)
    with _opend_lock:
        _opend_cache = (clock(), row)
    return row


def _opend_row(report: dict[str, Any]) -> dict[str, Any]:
    status = str(report.get("status") or "CHECK_FAILED")
    ready = status == "READY"
    return {"state": "CURRENT" if ready else "UNAVAILABLE", "reason": None if ready else status}


def _invalidate_opend_consumers() -> None:
    """Next reads retry OpenD at once instead of serving the cached failure until its TTL expires."""

    from .screener_multi import multi_screener_service
    from .screener_news import news_service

    multi_screener_service().invalidate_catalogs()
    news_service().invalidate_indexes()


# ------------------------------------------------------------------ connect
CONNECTABLE = ("opend", "finbert", "local_synthesis")


def connect_provider(provider_id: str, *, diagnose: Callable[[bool], dict[str, Any]] = _diagnose_opend,
                     invalidate: Callable[[], None] = _invalidate_opend_consumers) -> dict[str, Any]:
    """Start or connect one allowlisted local provider. Raises ValueError for anything else."""

    global _opend_cache
    if provider_id not in CONNECTABLE:
        raise ValueError("PROVIDER_NOT_CONNECTABLE")
    if provider_id == "opend":
        try:
            report = diagnose(True)
        except Exception:  # noqa: BLE001
            report = {"status": "CHECK_FAILED"}
        status = str(report.get("status") or "CHECK_FAILED")
        started = bool((report.get("opend") or {}).get("running"))
        with _opend_lock:
            _opend_cache = None
        invalidate()
        if status == "READY":
            return {"provider": provider_id, "state": "CONNECTED", "reason": None, "remedy": None}
        # Just launched: OpenD needs its login before the port answers.
        state = "STARTING" if started and status in ("PORT_UNREACHABLE", "QUOTE_CONTEXT_FAILED", "OPEN_D_NOT_RUNNING") else "FAILED"
        return {"provider": provider_id, "state": state, "reason": status, "remedy": remedy_for(status, scope="ETFs and Futures")}
    from .screener_news import news_service

    if provider_id == "finbert":
        model = news_service().sentiment_model()
        model.start_load()
        status = model.status()
        loaded = bool(status.get("loaded"))
        failed = status["state"] != "CURRENT"
        reason = status.get("reason")
        return {"provider": provider_id, "state": "CONNECTED" if loaded else "FAILED" if failed else "STARTING",
                "reason": reason, "remedy": None if loaded else remedy_for(reason)}
    server = news_service().local_synthesis_server()
    if server is None:
        ai = news_service().ai_status()
        return {"provider": provider_id, "state": "FAILED", "reason": ai.get("reason"), "remedy": remedy_for(ai.get("reason"))}
    if server.running():
        return {"provider": provider_id, "state": "CONNECTED", "reason": None, "remedy": None}
    # Loading the model can take minutes; start it off the request thread.
    threading.Thread(target=server.ensure_running, name="local-synthesis-start", daemon=True).start()
    return {"provider": provider_id, "state": "STARTING", "reason": "STARTING", "remedy": None}


# ------------------------------------------------------------------ setup checklist
SETUP_SCHEMA_VERSION = "screener-setup/1.0.0"


def _row(row_id: str, label: str, kind: str, state: str, reason: str | None, *, scope: str = "this universe",
         connectable: bool = False) -> dict[str, Any]:
    base = {"id": row_id, "label": label, "kind": kind, "state": state, "reason": reason}
    row = with_remedy(base, scope=scope)
    action = (row.get("remedy") or {}).get("action") or {}
    return {**row, "remedy": row.get("remedy"), "connectable": connectable and action.get("kind") == "CONNECT"}


def _key_gates() -> dict[str, tuple[bool, str | None]]:
    """(live flag on, key) for the keyed news providers; flags and keys may live in .private/providers.env."""

    from ..news import config as news_config

    return {"newsapi": (news_config.newsapi_live_enabled(), news_config.newsapi_api_key()),
            "finnhub": (news_config.finnhub_live_enabled(), news_config.finnhub_api_key())}


def setup_checklist(*, env: Callable[[str], str | None] = os.environ.get,
                    opend: Callable[[], dict[str, Any]] = opend_status,
                    key_gates: Callable[[], dict[str, tuple[bool, str | None]]] = _key_gates,
                    service: Any = None) -> dict[str, Any]:
    """One row per free capability: its state and the single step that enables it."""

    from ..congressional_ptr import senate as senate_ptr
    from ..news.rss_feeds import LIVE_ENV as RSS_LIVE_ENV
    from ..news.sec_filings_news import live_state as sec_live_state
    from ..public_records.http import live_state as public_live_state

    def gate(enabled: bool, key: str | None, flag_reason: str, key_reason: str) -> tuple[str, str | None]:
        if not enabled:
            return "LIVE_DISABLED", flag_reason
        if not key:
            return "NOT_CONFIGURED", key_reason
        return "CURRENT", None

    rows = []
    open_d = opend()
    rows.append(_row("opend", "moomoo OpenD (ETFs, Futures, quotes)", "MARKET_DATA", open_d["state"], open_d["reason"],
                     scope="ETFs and Futures", connectable=True))
    keys = key_gates()
    rows.append(_row("newsapi", "NewsAPI (free Developer)", "NEWS",
                     *gate(*keys["newsapi"], "IMP_NEWSAPI_LIVE_NOT_SET", "NEWSAPI_API_KEY_NOT_SET")))
    rows.append(_row("finnhub", "Finnhub (free company news)", "NEWS",
                     *gate(*keys["finnhub"], "IMP_FINNHUB_LIVE_NOT_SET", "FINNHUB_API_KEY_NOT_SET")))
    rss_on = (env(RSS_LIVE_ENV) or "").strip().lower() in {"1", "true", "yes"}
    rows.append(_row("rss", "Public RSS feeds", "NEWS", "CURRENT" if rss_on else "LIVE_DISABLED",
                     None if rss_on else f"{RSS_LIVE_ENV}_NOT_SET"))
    rows.append(_row("sec_filings", "SEC EDGAR (User-Agent)", "OFFICIAL_FILING", *sec_live_state(env)))
    public_state, public_reason = public_live_state(env)
    rows.append(_row("public_records", "Public records (House, lobbying, contracts)", "GOVERNMENT", public_state, public_reason))
    senate = senate_ptr.scan_import(senate_ptr.import_root_from_env(env))
    senate_ok = senate.state in ("READY", "PARTIAL")
    rows.append(_row("senate_efd", "Senate eFD pages (operator import)", "GOVERNMENT",
                     "CURRENT" if senate_ok else senate.state, None if senate_ok else senate.reason))
    if service is None:
        from .screener_news import news_service

        service = news_service()
    model = service.sentiment_model().status()
    rows.append(_row("finbert", "FinBERT sentiment (local)", "SENTIMENT", model["state"], model.get("reason"),
                     connectable=True))
    ai = service.ai_status()
    rows.append(_row("ai", "AI synthesis", "AI", "CURRENT" if ai["state"] == "AVAILABLE" else ai["state"], ai.get("reason"),
                     connectable=True))
    ready = sum(1 for row in rows if row["state"] == "CURRENT" and not row.get("remedy"))
    return {"schema_version": SETUP_SCHEMA_VERSION, "rows": rows, "ready_count": ready, "total": len(rows)}


__all__ = ["CONNECTABLE", "REMEDIES", "SETUP_SCHEMA_VERSION", "connect_provider", "opend_status", "remedy_for",
           "setup_checklist", "with_remedy"]
