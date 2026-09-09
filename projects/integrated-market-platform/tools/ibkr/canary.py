"""Bounded IBKR read-only live canary harness (G11 / G11.1).

Fail-closed outer-tools evidence capture. Distinguishes safety-gate state
(``LIVE_ACCESS_NOT_ENABLED_BY_CONFIG``) from measured transport availability.
Does not modify production gates or enable execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __package__:
    from .capture import redact
    from .config import IbkrConfig, validate_gateway_url
    from .query_provider import build_query_provider
else:
    from tools.ibkr.capture import redact
    from tools.ibkr.config import IbkrConfig, validate_gateway_url
    from tools.ibkr.query_provider import build_query_provider


DEFAULT_OUTPUT = ROOT / "evidence" / "market_data" / "ibkr" / "canary-report.json"
DEFAULT_CAPABILITY_OUTPUT = (
    ROOT.parents[1]
    / "docs"
    / "audits"
    / "imp-reconciliation"
    / "g11-live-capability-evidence.json"
)
DEFAULT_SUMMARY_OUTPUT = (
    ROOT.parents[1]
    / "docs"
    / "audits"
    / "imp-reconciliation"
    / "g11-live-canary-summary.json"
)
DEFAULT_INSTRUMENT = "AAPL"
DEFAULT_DURATION_SECONDS = 15
DEFAULT_MAX_DEPTH_ROWS = 5
DEFAULT_MAX_HISTORY_BARS = 10
DEFAULT_MAX_REQUESTS = 12
CLIENT_ID_CANDIDATES = (1, 37, 38, 99, 101)
FORBIDDEN_EXECUTION_METHODS = (
    "placeOrder",
    "cancelOrder",
    "modifyOrder",
    "exerciseOptions",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _redact_account(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"acct:{digest}"


def probe_loopback(host: str, port: int, *, timeout: float = 0.35) -> bool:
    if host.strip().lower() not in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def classify_gate(config: IbkrConfig) -> dict[str, Any]:
    """Separate safety-gate state from environment reachability."""

    gate_enabled = config.live_enabled
    gate_state = "ENABLED" if gate_enabled else "LIVE_ACCESS_NOT_ENABLED_BY_CONFIG"
    blockers: list[str] = []
    if not gate_enabled:
        blockers.append("LIVE_ACCESS_NOT_ENABLED_BY_CONFIG: IMP_IBKR_LIVE is not enabled")
    try:
        validate_gateway_url(config.gateway_url)
    except Exception as exc:
        blockers.append(f"CONFIGURATION_MISMATCH: gateway URL invalid: {exc}")
    tws_reachable = probe_loopback(config.tws_host, config.tws_port)
    portal_host, portal_port = "127.0.0.1", 5000
    portal_reachable = probe_loopback(portal_host, portal_port)
    transport_probe = {
        "tws": {
            "host": config.tws_host,
            "port": config.tws_port,
            "reachable": tws_reachable,
        },
        "client_portal": {
            "host": portal_host,
            "port": portal_port,
            "reachable": portal_reachable,
        },
        "configured_transport": config.transport,
    }
    if gate_enabled and config.transport == "tws" and not tws_reachable:
        blockers.append("TRANSPORT_UNREACHABLE: configured TWS loopback endpoint not accepting TCP")
    if (
        gate_enabled
        and config.transport == "client_portal"
        and not portal_reachable
        and not tws_reachable
    ):
        blockers.append(
            "TRANSPORT_UNREACHABLE: neither Client Portal nor TWS loopback endpoints accept TCP"
        )
    return {
        "gate_state": gate_state,
        "blockers": blockers,
        "transport_probe": transport_probe,
    }


def _precheck(config: IbkrConfig) -> list[str]:
    return list(classify_gate(config)["blockers"])


def resolve_working_client_id(config: IbkrConfig) -> tuple[int, dict[str, Any]]:
    """Find a loopback client id that completes IB API handshake (read-only)."""

    from ib_insync import IB

    candidates = [config.tws_client_id] + [
        cid for cid in CLIENT_ID_CANDIDATES if cid != config.tws_client_id
    ]
    attempts: list[dict[str, Any]] = []
    for client_id in candidates:
        ib = IB()
        row: dict[str, Any] = {
            "host": config.tws_host,
            "port": config.tws_port,
            "client_id": client_id,
            "readonly": True,
            "observed_at": _now(),
        }
        try:
            t0 = time.perf_counter()
            ib.connect(
                config.tws_host,
                config.tws_port,
                clientId=client_id,
                timeout=20,
                readonly=True,
            )
            row["connection_result"] = "CONNECTED"
            row["connection_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            row["server_version"] = getattr(ib.client, "serverVersion", lambda: None)()
            managed = str(getattr(ib, "managedAccounts", lambda: "")() or "")
            row["account_count"] = len([part for part in managed.split(",") if part.strip()])
            ib.disconnect()
            return client_id, row
        except Exception as exc:
            row["connection_result"] = type(exc).__name__
            row["diagnostic"] = str(exc)[:256]
            attempts.append(row)
            try:
                ib.disconnect()
            except Exception:
                pass
    raise RuntimeError(json.dumps({"connection_attempts": attempts}))


class IbkrReadOnlyCanary:
    """Bounded read-only canary — one instrument, explicit request limits."""

    def __init__(
        self,
        *,
        instrument: str = DEFAULT_INSTRUMENT,
        duration_seconds: int = DEFAULT_DURATION_SECONDS,
        max_depth_rows: int = DEFAULT_MAX_DEPTH_ROWS,
        max_history_bars: int = DEFAULT_MAX_HISTORY_BARS,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        include_account: bool = False,
        include_streaming: bool = True,
        observed_at: Callable[[], str] = _now,
    ) -> None:
        self.instrument = instrument.strip().upper()
        self.duration_seconds = duration_seconds
        self.max_depth_rows = max_depth_rows
        self.max_history_bars = max_history_bars
        self.max_requests = max_requests
        self.include_account = include_account
        self.include_streaming = include_streaming
        self._observed_at = observed_at
        self._request_count = 0
        self._performance: dict[str, float] = {}

    def _bounded(self, label: str, operation: Callable[[], Any]) -> dict[str, Any]:
        if self._request_count >= self.max_requests:
            return {
                "capability": label,
                "status": "SKIPPED",
                "reason": "MAX_REQUESTS_EXCEEDED",
                "result": "LIVE_NOT_ATTEMPTED",
            }
        self._request_count += 1
        t0 = time.perf_counter()
        try:
            payload = operation()
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            self._performance[label] = elapsed_ms
            return {
                "capability": label,
                "status": "OBSERVED",
                "result": "LIVE_PROVIDER_VERIFIED",
                "latency_ms": elapsed_ms,
                "summary": _summarize(payload),
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            self._performance[label] = elapsed_ms
            return {
                "capability": label,
                "status": "ERROR",
                "result": _classify_error(exc),
                "latency_ms": elapsed_ms,
                "diagnostic": str(exc)[:256],
            }

    def run(self, config: IbkrConfig) -> dict[str, Any]:
        gate = classify_gate(config)
        report: dict[str, Any] = {
            "observed_at": self._observed_at(),
            "instrument": self.instrument,
            "duration_seconds": self.duration_seconds,
            "max_requests": self.max_requests,
            "gate_state": gate["gate_state"],
            "transport_probe": gate["transport_probe"],
            "live_verified": False,
            "blockers": gate["blockers"],
            "capabilities": [],
            "capability_matrix": [],
            "performance_ms": {},
        }
        if gate["blockers"]:
            report["status"] = "BLOCKED"
            report["environment_classification"] = (
                "LIVE_ACCESS_NOT_ENABLED_BY_CONFIG"
                if not config.live_enabled
                else "TRANSPORT_OR_CONFIG_BLOCKER"
            )
            return redact(report)

        if config.transport != "tws":
            config = IbkrConfig(
                live_enabled=config.live_enabled,
                gateway_url=config.gateway_url,
                capture_root=config.capture_root,
                transport="tws",
                tws_host=config.tws_host,
                tws_port=config.tws_port,
                tws_client_id=config.tws_client_id,
                requests_per_second=config.requests_per_second,
                history_min_spacing_seconds=config.history_min_spacing_seconds,
                history_window_max=config.history_window_max,
                penalty_box_seconds=config.penalty_box_seconds,
                timeout_seconds=config.timeout_seconds,
            )

        client_id, connection_row = resolve_working_client_id(config)
        if client_id != config.tws_client_id:
            config = IbkrConfig(
                live_enabled=config.live_enabled,
                gateway_url=config.gateway_url,
                capture_root=config.capture_root,
                transport=config.transport,
                tws_host=config.tws_host,
                tws_port=config.tws_port,
                tws_client_id=client_id,
                requests_per_second=config.requests_per_second,
                history_min_spacing_seconds=config.history_min_spacing_seconds,
                history_window_max=config.history_window_max,
                penalty_box_seconds=config.penalty_box_seconds,
                timeout_seconds=config.timeout_seconds,
            )
        report["connection"] = connection_row

        try:
            connection_row = self._run_query_path(config, report) or connection_row
            if self.include_streaming:
                try:
                    self._run_streaming_path(config, report, connection_row)
                except Exception as streaming_exc:
                    report["streaming_error"] = str(streaming_exc)[:512]
                    report["capabilities"].append(
                        {
                            "capability": "STREAMING_BUNDLE",
                            "status": "ERROR",
                            "result": _classify_error(streaming_exc),
                            "diagnostic": str(streaming_exc)[:256],
                        }
                    )
            report["status"] = "COMPLETE"
            report["request_count"] = self._request_count
            report["performance_ms"] = dict(self._performance)
            report["live_verified"] = any(
                row.get("result") == "LIVE_PROVIDER_VERIFIED"
                for row in report["capability_matrix"]
            )
            if connection_row is not None:
                report["connection"] = connection_row
        except Exception as exc:
            report["status"] = "ERROR"
            report["diagnostic"] = str(exc)[:512]
            report["environment_classification"] = _classify_error(exc)
        return redact(report)

    def _run_query_path(
        self,
        config: IbkrConfig,
        report: dict[str, Any],
    ) -> dict[str, Any] | None:
        provider = build_query_provider(config)
        connection_row: dict[str, Any] | None = None
        try:
            ib = getattr(getattr(provider, "_client", None), "_broker", None)
            if ib is not None:
                connection_row = {
                    "host": config.tws_host,
                    "port": config.tws_port,
                    "client_id": config.tws_client_id,
                    "connection_result": "CONNECTED" if ib.isConnected() else "DISCONNECTED",
                    "server_version": getattr(ib.client, "serverVersion", lambda: None)(),
                    "readonly": True,
                    "observed_at": _now(),
                }
            rows = provider.fetch_secdef_search(self.instrument)
            secdef = self._bounded("IBKR_CONTRACT_RESOLUTION", lambda: rows)
            report["capabilities"].append(secdef)
            report["capability_matrix"].append(_matrix_row(secdef, entitlement="UNKNOWN"))
            con_id = _first_conid(rows)
            if con_id is not None:
                report["contract_resolution"] = {
                    "symbol": self.instrument,
                    "provider_conid": con_id,
                    "canonical_instrument_id": self.instrument,
                    "sec_type": "STK",
                    "currency": "USD",
                    "exchange": "SMART",
                }
                hist = self._bounded(
                    "IBKR_HISTORICAL_BARS",
                    lambda: provider.fetch_historical_bars(
                        con_id=con_id, period="1d", bar="1h"
                    ),
                )
                report["capabilities"].append(hist)
                report["capability_matrix"].append(
                    _matrix_row(hist, entitlement="ENTITLED" if hist.get("status") == "OBSERVED" else "UNKNOWN")
                )
            if self.include_account:
                acct = self._bounded(
                    "IBKR_ACCOUNT_READ",
                    lambda: _redact_accounts(provider.fetch_portfolio_accounts()),
                )
                report["capabilities"].append(acct)
                report["capability_matrix"].append(_matrix_row(acct, entitlement="READ_ONLY_OBSERVATIONAL"))
        finally:
            provider.shutdown()
        return connection_row

    def _run_streaming_path(
        self,
        config: IbkrConfig,
        report: dict[str, Any],
        connection_row: dict[str, Any] | None,
    ) -> None:
        from market_platform_foundation.market_data.observational_state import ObservationalStateStore
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrObservationalAdapter,
            IbkrObservationalConfig,
        )
        from market_platform_foundation.providers.ibkr_observational.capability import IBKR_PROVIDER_ID
        from market_platform_foundation.providers.live_evidence import (
            CapabilityLiveEvidenceRow,
            LiveCapabilityResult,
            apply_live_evidence,
        )
        from market_platform_foundation.providers.runtime_capability import RuntimeCapabilityRegistry
        from market_platform_foundation.xa01.enums import IDENTITY_PROFILE, InstrumentKind, XaAssetClass
        from market_platform_foundation.xa01.contracts import (
            CanonicalInstrumentIdentity,
            InstrumentDescriptor,
            InstrumentRecord,
        )

        from tools.ibkr.observational_transport import IbkrObservationalTransport

        lookup_record = InstrumentRecord(
            descriptor=InstrumentDescriptor(
                identity=CanonicalInstrumentIdentity(
                    canonical_id=self.instrument,
                    instrument_kind=InstrumentKind.TRADABLE_SECURITY,
                    asset_class=XaAssetClass.EQUITY,
                    identity_profile=IDENTITY_PROFILE,
                    identity_key={"ticker": self.instrument},
                ),
                display_name=self.instrument,
            )
        )

        class _Lookup:
            def __init__(self, instrument: str, record: InstrumentRecord) -> None:
                self._instrument = instrument.upper()
                self._record = record

            def get(self, canonical_id: str) -> InstrumentRecord:
                if canonical_id.upper() != self._instrument:
                    raise KeyError(canonical_id)
                return self._record

        adapter_config = IbkrObservationalConfig(
            live_enabled=True,
            host=config.tws_host,
            port=config.tws_port,
            client_id=config.tws_client_id,
            readonly=True,
            capture_path=str(config.capture_root / "g111-live-callbacks.jsonl"),
        )
        store = ObservationalStateStore()
        transport = IbkrObservationalTransport(config)
        adapter = IbkrObservationalAdapter(
            adapter_config,
            transport=transport,
            store=store,
            lookup=_Lookup(self.instrument, lookup_record),
        )
        transport.attach_adapter(adapter)
        t_connect = time.perf_counter()
        adapter.connect()
        self._performance["streaming_connect_ms"] = round((time.perf_counter() - t_connect) * 1000, 2)
        broker = transport._broker
        set_market_data_type = getattr(broker, "reqMarketDataType", None)
        if callable(set_market_data_type):
            set_market_data_type(3)
        l1_result = adapter.subscribe_l1(instrument_id=self.instrument)
        l2_result = adapter.subscribe_l2(
            instrument_id=self.instrument,
            depth_levels=self.max_depth_rows,
        )
        trades_result = adapter.subscribe_trades(instrument_id=self.instrument)
        broker = transport._broker
        sleep = getattr(broker, "sleep", None)
        wait_seconds = min(self.duration_seconds, 20)
        if callable(sleep):
            sleep(wait_seconds)
        else:
            time.sleep(wait_seconds)
        quote = store.quote_for(self.instrument)
        book = store.canonical_books.get(self.instrument)
        trades = list(store.trades.get(self.instrument, ()))
        from market_platform_foundation.order_flow.order_book.projection import best_bid_ask

        best_bid, best_ask = (None, None)
        bid_levels, ask_levels = (0, 0)
        if book is not None:
            best_bid, best_ask = best_bid_ask(book)
            bid_levels, ask_levels = book.level_counts
        has_l2 = bid_levels > 0 or ask_levels > 0
        diag = adapter.diagnostics()
        entitlement = str(diag.get("entitlement_state") or diag.get("entitlement") or "UNKNOWN")
        subscription_diag = diag.get("subscriptions") or {}
        per_cap_entitlement = _subscription_entitlements(subscription_diag)

        l1_ent = per_cap_entitlement.get("L1", entitlement)
        l2_ent = per_cap_entitlement.get("L2", entitlement)
        trades_ent = per_cap_entitlement.get("TRADES", entitlement)

        has_l1 = quote is not None and (
            quote.bid_price is not None or quote.ask_price is not None or quote.last_price is not None
        )
        l1_delayed = bool(quote and getattr(quote, "delayed", False))
        if l1_delayed and l1_ent == "UNKNOWN":
            l1_ent = "ENTITLED_DELAYED"
        l1_row = _streaming_matrix_row(
            "IBKR_L1",
            l1_result.as_dict() if hasattr(l1_result, "as_dict") else {},
            has_l1,
            l1_ent,
            quote.to_dict() if quote else None,
            provider_delayed=l1_delayed,
        )
        l2_row = _streaming_matrix_row(
            "IBKR_L2",
            l2_result.as_dict() if hasattr(l2_result, "as_dict") else {},
            has_l2,
            l2_ent,
            {
                "best_bid": float(best_bid) if best_bid is not None else None,
                "best_ask": float(best_ask) if best_ask is not None else None,
                "bid_levels": bid_levels,
                "ask_levels": ask_levels,
            },
        )
        trades_row = _streaming_matrix_row(
            "IBKR_TRADES",
            trades_result.as_dict() if hasattr(trades_result, "as_dict") else {},
            len(trades) > 0,
            trades_ent,
            {"trade_count": len(trades), "cvd_path": "Lee-Ready/UNKNOWN unless provider aggressor"},
        )
        for row in (l1_row, l2_row, trades_row):
            report["capability_matrix"].append(row)
            report["capabilities"].append(
                {
                    "capability": row["capability"],
                    "status": "OBSERVED" if row["data_received"] else "NO_DATA",
                    "result": row["result"],
                }
            )
        report["entitlement"] = {
            "IBKR_L1": l1_row["entitlement"],
            "IBKR_L2": l2_row["entitlement"],
            "IBKR_TRADES": trades_row["entitlement"],
        }
        report["freshness"] = {
            "IBKR_L1": l1_row["freshness"],
            "IBKR_L2": l2_row["freshness"],
            "IBKR_TRADES": trades_row["freshness"],
        }
        adapter.shutdown()
        transport.disconnect()
        registry = RuntimeCapabilityRegistry()
        evidence = {
            row["capability"]: CapabilityLiveEvidenceRow(
                capability_id=row["capability"],
                connection=bool(
                    connection_row and connection_row.get("connection_result") == "CONNECTED"
                ),
                request_accepted=bool(row.get("request_accepted")),
                data_received=bool(row.get("data_received")),
                entitlement=str(row.get("entitlement") or "UNKNOWN"),
                freshness=str(row.get("freshness") or "UNKNOWN"),
                canonical_normalization=bool(row.get("canonical_normalization")),
                result=LiveCapabilityResult(row["result"]),
            )
            for row in report["capability_matrix"]
            if isinstance(row, dict) and row.get("capability")
        }
        apply_live_evidence(registry, IBKR_PROVIDER_ID, evidence)
        report["registry_manifest"] = registry.manifest()


def _subscription_entitlements(subscriptions: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not isinstance(subscriptions, dict):
        return mapping
    error_codes = {
        10092: "NOT_ENTITLED",
        10189: "NOT_ENTITLED",
        10089: "ENTITLED_DELAYED",
        354: "NOT_ENTITLED",
    }
    for payload in subscriptions.values():
        if not isinstance(payload, dict):
            continue
        capability = str(payload.get("capability") or "").upper()
        entitlement = str(payload.get("entitlement") or "UNKNOWN").upper()
        last_error = payload.get("last_error")
        if isinstance(last_error, dict):
            code = last_error.get("code")
            if isinstance(code, int) and code in error_codes:
                entitlement = error_codes[code]
        if entitlement == "DELAYED":
            entitlement = "ENTITLED_DELAYED"
        if capability in {"L1", "L2", "TRADES"}:
            mapping[capability] = entitlement
    return mapping


def _matrix_row(observed: dict[str, Any], *, entitlement: str) -> dict[str, Any]:
    verified = observed.get("status") == "OBSERVED"
    return {
        "capability": observed.get("capability"),
        "connection": verified,
        "request_accepted": verified,
        "data_received": verified,
        "entitlement": entitlement,
        "freshness": "UNKNOWN",
        "canonical_normalization": verified,
        "result": observed.get("result", "LIVE_NOT_ATTEMPTED"),
    }


def _streaming_matrix_row(
    capability: str,
    subscribe: Mapping[str, Any],
    data_received: bool,
    entitlement: str,
    payload_summary: Mapping[str, Any] | None,
    *,
    provider_delayed: bool = False,
) -> dict[str, Any]:
    accepted = bool(subscribe.get("accepted"))
    if not accepted:
        result = "LIVE_REQUEST_FAILED"
    elif entitlement.upper() in {"NOT_ENTITLED", "ERROR"}:
        result = "LIVE_CONNECTED_NOT_ENTITLED"
    elif not data_received and entitlement.upper() in {"DELAYED", "ENTITLED_DELAYED"}:
        result = "LIVE_CONNECTED_NO_DATA"
    elif not data_received:
        result = "LIVE_CONNECTED_NO_DATA"
    else:
        result = "LIVE_PROVIDER_VERIFIED"
    freshness = "UNKNOWN"
    if data_received:
        if provider_delayed or entitlement.upper() in {"DELAYED", "ENTITLED_DELAYED"}:
            freshness = "DELAYED"
        elif entitlement.upper() in {"NOT_ENTITLED", "ERROR"}:
            freshness = "UNKNOWN"
        else:
            freshness = "REALTIME"
    return {
        "capability": capability,
        "connection": True,
        "request_accepted": accepted,
        "data_received": data_received,
        "entitlement": entitlement,
        "freshness": freshness,
        "canonical_normalization": data_received,
        "result": result,
        "summary": dict(payload_summary or {}),
    }


def _classify_error(exc: BaseException) -> str:
    message = str(exc).lower()
    if "not enabled" in message or "imp_ibkr_live" in message:
        return "LIVE_ACCESS_NOT_ENABLED_BY_CONFIG"
    if "timeout" in message:
        return "LIVE_REQUEST_FAILED"
    if "client" in message and "id" in message:
        return "CLIENT_ID_CONFLICT"
    if "connection refused" in message or "unreachable" in message:
        return "TRANSPORT_UNREACHABLE"
    return "LIVE_REQUEST_FAILED"


def _first_conid(rows: Any) -> int | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get("conid") or row.get("conId")
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _summarize(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"type": "array", "count": len(payload)}
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return {"type": "object", "data_count": len(data)}
        accounts = payload.get("accounts")
        if isinstance(accounts, list):
            return {"type": "object", "account_count": len(accounts), "redacted": payload.get("redacted")}
        return {"type": "object", "keys": sorted(str(key) for key in payload)}
    return {"type": type(payload).__name__}


def _redact_accounts(payload: Mapping[str, Any]) -> dict[str, Any]:
    accounts = payload.get("accounts") or payload.get("data") or ()
    redacted: list[str] = []
    if isinstance(accounts, list):
        for item in accounts:
            redacted.append(_redact_account(str(item)))
    elif isinstance(accounts, dict):
        for key in accounts:
            redacted.append(_redact_account(str(key)))
    return {"accounts": redacted, "redacted": True}


def assert_no_execution_surface() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_EXECUTION_METHODS:
        if f"{forbidden}(" in source or f".{forbidden}(" in source:
            raise RuntimeError(f"canary module must not invoke execution method {forbidden}")


def main(argv: list[str] | None = None) -> int:
    assert_no_execution_surface()
    parser = argparse.ArgumentParser(description="IBKR read-only canary harness")
    parser.add_argument("--instrument", default=DEFAULT_INSTRUMENT)
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument("--include-account", action="store_true")
    parser.add_argument("--no-streaming", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--capability-output", type=Path, default=DEFAULT_CAPABILITY_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args(argv)
    config = IbkrConfig.from_env(os.environ, root=ROOT)
    canary = IbkrReadOnlyCanary(
        instrument=args.instrument,
        duration_seconds=args.duration,
        max_requests=args.max_requests,
        include_account=args.include_account,
        include_streaming=not args.no_streaming,
    )
    report = canary.run(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    summary = {
        "observed_at": report.get("observed_at"),
        "status": report.get("status"),
        "gate_state": report.get("gate_state"),
        "environment_classification": report.get("environment_classification"),
        "live_verified": report.get("live_verified"),
        "instrument": report.get("instrument"),
        "connection": report.get("connection"),
        "capability_results": {
            row.get("capability"): row.get("result")
            for row in report.get("capability_matrix", [])
            if isinstance(row, dict)
        },
        "performance_ms": report.get("performance_ms"),
    }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(redact(summary), indent=2, sort_keys=True), encoding="utf-8")
    capability_payload = {
        "observed_at": report.get("observed_at"),
        "capability_matrix": report.get("capability_matrix", []),
        "entitlement": report.get("entitlement"),
        "freshness": report.get("freshness"),
        "registry_manifest": report.get("registry_manifest"),
    }
    args.capability_output.write_text(
        json.dumps(redact(capability_payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "output": str(args.output),
                "summary": str(args.summary_output),
                "capability_evidence": str(args.capability_output),
            },
            indent=2,
        )
    )
    return 0 if report.get("status") == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
