"""Server-owned live feature-corpus service for the Paper forecast (default off).

Enabled only by ``IMP_PAPER_FORECAST_CORPUS=1`` in LIVE_OBSERVATIONAL mode. It subscribes the
configured instruments to Moomoo ``BASIC_QUOTE`` and ``TRADES`` through the existing subscription
manager (vendor quota and entitlement refusals are recorded, never worked around), attaches a
bounded in-memory window to the runtime's existing observation-ingress hook, and runs
``LiveFeatureCorpusRecorder.tick`` once a second during the regular US session.

It writes only JSONL rows and a status file under ``IMP_PAPER_FORECAST_CORPUS_DIR``. It writes
nothing to the canonical store, calls no model, and has no order, Paper or broker capability.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ENABLE_ENV = "IMP_PAPER_FORECAST_CORPUS"
DIR_ENV = "IMP_PAPER_FORECAST_CORPUS_DIR"
SYMBOLS_ENV = "IMP_PAPER_FORECAST_CORPUS_SYMBOLS"
MAX_SYMBOLS = 12
CAPABILITIES = ("BASIC_QUOTE", "TRADES")
RUNTIME_WAIT_SECONDS = 600

_SERVICE: "PaperForecastCorpusService | None" = None


def configured_symbols(environ=os.environ) -> list[str]:
    raw = [s.strip().upper() for s in str(environ.get(SYMBOLS_ENV) or "").split(",") if s.strip()]
    symbols = list(dict.fromkeys(raw))
    if not symbols or len(symbols) > MAX_SYMBOLS or not all(s.replace(".", "").replace("-", "").isalnum() for s in symbols):
        raise ValueError("PAPER_FORECAST_CORPUS_SYMBOLS_INVALID")
    return symbols


def regular_session_open(at_ns: int) -> bool:
    from ..market_sessions import us_equity_session_label

    return us_equity_session_label(datetime.fromtimestamp(at_ns / 1e9, UTC)) == "REGULAR"


class PaperForecastCorpusService:
    def __init__(self, *, directory: Path, symbols: list[str], runtime_getter=None, clock=time.time_ns) -> None:
        from ..intelligence.production.live_feature_corpus import (
            DEFAULT_TERMINAL_TOLERANCE_NS,
            LiveFeatureCorpusRecorder,
            RollingEventWindow,
            WINDOW_NS,
        )
        from ..intelligence.production.identity import path_a_horizon

        self.directory = Path(directory)
        self.symbols = list(symbols)
        self.runtime_getter = runtime_getter
        retain = WINDOW_NS + path_a_horizon().duration_ns + DEFAULT_TERMINAL_TOLERANCE_NS + 120 * 1_000_000_000
        self.window = RollingEventWindow(retain_ns=retain, instruments=lambda: self.symbols, clock=clock)
        self.recorder = LiveFeatureCorpusRecorder(window=self.window, directory=self.directory, instruments=lambda: self.symbols,
                                                  session_open=regular_session_open, clock=clock)
        self.subscriptions: dict[str, Any] = {}
        self.state = "STARTING"
        self.error: str | None = None
        self._stop = threading.Event()
        self.thread: threading.Thread | None = None

    def _runtime(self):
        if self.runtime_getter is not None:
            return self.runtime_getter()
        from ..market_data.live_runtime import get_live_runtime

        return get_live_runtime(create=False)

    def attach(self) -> bool:
        runtime = self._runtime()
        if runtime is None:
            return False
        existing = getattr(runtime, "observation_ingress_router", None)
        if existing is not None and existing is not self.window:
            raise ValueError("OBSERVATION_INGRESS_ALREADY_ATTACHED")
        runtime.attach_observation_ingress(self.window)
        from ..intelligence.production.live_feature_corpus import CONSUMER_ID

        for symbol in self.symbols:
            try:
                results = runtime.subscribe(instrument_id=symbol, capabilities=list(CAPABILITIES), consumer_id=CONSUMER_ID)
            except Exception as exc:  # noqa: BLE001 - recorded; the symbol simply records no rows
                results = [dict(accepted=False, reason=type(exc).__name__)]
            self.subscriptions[symbol] = [dict(capability=c, accepted=bool(r.get("accepted")), reason=r.get("reason"))
                                          for c, r in zip(CAPABILITIES, results)]
        return True

    def write_status(self) -> dict[str, Any]:
        status = dict(schema_version="paper-forecast-corpus-status/1.0.0", state=self.state, error=self.error,
                      at=datetime.now(UTC).isoformat(), symbols=self.symbols, subscriptions=self.subscriptions,
                      recorder={k: v for k, v in self.recorder.status.items()}, writes_canonical_store=False,
                      calls_models=False, order_capability=False)
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.directory / "status.json.tmp"
        tmp.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, self.directory / "status.json")
        return status

    def run(self) -> None:
        try:
            deadline = time.monotonic() + RUNTIME_WAIT_SECONDS
            while not self.attach():
                if self._stop.wait(5) or time.monotonic() > deadline:
                    self.state = "RUNTIME_UNAVAILABLE"
                    self.write_status()
                    return
            self.state = "RUNNING"
            last_status = 0.0
            while not self._stop.wait(1.0):
                try:
                    self.recorder.tick()
                    self.error = None
                except Exception as exc:  # noqa: BLE001 - one failed tick is reported; the next grid point is independent
                    self.error = f"{type(exc).__name__}:{str(exc)[:200]}"
                if time.monotonic() - last_status >= 10:
                    self.write_status()
                    last_status = time.monotonic()
        except Exception as exc:  # noqa: BLE001
            self.state, self.error = "FAILED", f"{type(exc).__name__}:{str(exc)[:200]}"
            self.write_status()

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name="paper-forecast-corpus", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()


def start_paper_forecast_corpus(store, environ=os.environ) -> dict[str, Any]:
    """Start the service if enabled. Never raises into server startup."""
    global _SERVICE
    if environ.get(ENABLE_ENV) != "1":
        return dict(started=False, reason="DISABLED")
    if str(getattr(store, "data_mode", "")) != "LIVE_OBSERVATIONAL":
        return dict(started=False, reason="NOT_LIVE_OBSERVATIONAL")
    try:
        directory = Path(str(environ.get(DIR_ENV) or ""))
        if not str(environ.get(DIR_ENV) or "").strip() or not directory.is_absolute():
            raise ValueError("PAPER_FORECAST_CORPUS_DIR_REQUIRED")
        _SERVICE = PaperForecastCorpusService(directory=directory, symbols=configured_symbols(environ))
        _SERVICE.start()
        return dict(started=True, symbols=_SERVICE.symbols, directory=str(directory))
    except Exception as exc:  # noqa: BLE001
        return dict(started=False, reason=f"{type(exc).__name__}:{exc}")


def corpus_service() -> "PaperForecastCorpusService | None":
    return _SERVICE
