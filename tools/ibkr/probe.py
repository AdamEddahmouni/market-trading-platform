"""Bounded, redacted capability probe for the local IBKR gateway."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if __package__:
    from .capture import redact, redact_text
    from .client import IbkrClient
    from .config import IbkrConfig
    from .tws_client import TwsIbkrClient
else:  # Support the documented ``python tools/ibkr/probe.py`` entry point.
    sys.path.insert(0, str(ROOT))
    from tools.ibkr.capture import redact, redact_text
    from tools.ibkr.client import IbkrClient
    from tools.ibkr.config import IbkrConfig
    from tools.ibkr.tws_client import TwsIbkrClient


DEFAULT_OUTPUT = ROOT / "evidence" / "market_data" / "ibkr" / "capability-report.json"
_NON_SESSION_CAPABILITIES = (
    "contract_search",
    "delayed_snapshot",
    "historical_bars",
    "option_definitions",
    "scanner_parameters",
    "portfolio_accounts",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _summary(payload: object) -> dict[str, object]:
    """Characterize payload shape without copying sensitive provider values."""

    if isinstance(payload, list):
        keys: list[str] = []
        if payload and isinstance(payload[0], Mapping):
            keys = sorted(str(key) for key in payload[0])
        return {"payload_type": "array", "item_count": len(payload), "item_keys": keys}
    if isinstance(payload, Mapping):
        return {"payload_type": "object", "keys": sorted(str(key) for key in payload)}
    if payload is None:
        return {"payload_type": "null"}
    return {"payload_type": type(payload).__name__}


def _conid(payload: object) -> int | None:
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = row.get("conid")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit() and int(value) > 0:
            return int(value)
    return None


def _untested(reason: str) -> dict[str, object]:
    return {"evidence_class": "UNTESTED", "status": "UNTESTED", "reason": reason}


def build_client(config: IbkrConfig) -> Any:
    """Construct the explicitly selected observational transport."""

    if config.transport == "tws":
        return TwsIbkrClient(config)
    return IbkrClient(config)


class CapabilityProbe:
    """Probe each observational surface independently through a restricted client."""

    def __init__(self, client: Any, *, observed_at: Callable[[], str] = _now) -> None:
        self._client = client
        self._observed_at = observed_at

    def _observe(self, operation: Callable[[], object]) -> tuple[dict[str, object], object | None]:
        try:
            payload = operation()
        except Exception as exc:  # Boundary report records a sanitized observed failure.
            return (
                {
                    "evidence_class": "OBSERVED",
                    "status": "ERROR",
                    "diagnostic": redact_text(str(exc)),
                },
                None,
            )
        return (
            {"evidence_class": "OBSERVED", "status": "AVAILABLE", "shape": _summary(payload)},
            payload,
        )

    def run(self, symbol: str = "AAPL") -> dict[str, object]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or not normalized_symbol.replace(".", "").isalnum():
            raise ValueError("symbol must be alphanumeric with optional dots")
        capabilities: dict[str, dict[str, object]] = {}
        session_row, session_payload = self._observe(
            lambda: self._client.request_json("GET", "/iserver/auth/status")
        )
        if isinstance(session_payload, Mapping):
            connected = session_payload.get("connected") is True
            authenticated = session_payload.get("authenticated") is True
            session_row["connected"] = connected
            session_row["authenticated"] = authenticated
            if not (connected and authenticated):
                session_row["status"] = "UNAVAILABLE"
        else:
            connected = authenticated = False
        capabilities["session"] = session_row
        report: dict[str, object] = {
            "schema_version": "1.0",
            "adr_id": "ADR-LIVE-002",
            "provider": getattr(self._client, "provider", "IBKR_CLIENT_PORTAL_GATEWAY"),
            "transport": getattr(self._client, "transport", "client_portal"),
            "classification": "OBSERVED_CAPABILITY_REPORT_NOT_ADMITTED",
            "observed_at": self._observed_at(),
            "symbol": normalized_symbol,
            "resolved_contract": {"symbol": normalized_symbol, "conid": None},
            "capabilities": capabilities,
        }
        if not (connected and authenticated):
            for name in _NON_SESSION_CAPABILITIES:
                capabilities[name] = _untested("AUTHENTICATED_GATEWAY_SESSION_REQUIRED")
            return report

        search_row, search_payload = self._observe(
            lambda: self._client.request_json(
                "GET", "/iserver/secdef/search", params={"symbol": normalized_symbol}
            )
        )
        capabilities["contract_search"] = search_row
        conid = _conid(search_payload)
        report["resolved_contract"] = {"symbol": normalized_symbol, "conid": conid}
        if conid is None:
            capabilities["delayed_snapshot"] = _untested("CONTRACT_ID_NOT_OBSERVED")
            capabilities["historical_bars"] = _untested("CONTRACT_ID_NOT_OBSERVED")
        else:
            snapshot_params = {"conids": str(conid), "fields": "31,84,86,87,88"}
            snapshot_row, _ = self._observe(
                lambda: (
                    self._client.request_json(
                        "GET", "/iserver/marketdata/snapshot", params=snapshot_params
                    ),
                    self._client.request_json(
                        "GET", "/iserver/marketdata/snapshot", params=snapshot_params
                    ),
                )[1]
            )
            capabilities["delayed_snapshot"] = snapshot_row
            history_row, _ = self._observe(
                lambda: self._client.request_json(
                    "GET",
                    "/hmds/history",
                    params={"conid": str(conid), "period": "1d", "bar": "1h"},
                )
            )
            capabilities["historical_bars"] = history_row

        option_row, _ = self._observe(
            lambda: self._client.request_json(
                "GET", "/trsrv/secdef", params={"symbols": normalized_symbol}
            )
        )
        capabilities["option_definitions"] = option_row
        scanner_row, _ = self._observe(
            lambda: self._client.request_json("GET", "/iserver/scanner/params")
        )
        capabilities["scanner_parameters"] = scanner_row
        portfolio_row, _ = self._observe(
            lambda: self._client.request_json("GET", "/portfolio/accounts")
        )
        capabilities["portfolio_accounts"] = portfolio_row
        return report


def write_report(path: Path, report: Mapping[str, object]) -> None:
    """Write a redacted capability report; no raw account payload is retained."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(redact(dict(report)), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    client_factory: Callable[[IbkrConfig], Any] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Probe read-only IBKR Gateway capabilities")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--symbol", default="AAPL")
    arguments = parser.parse_args(argv)
    config = IbkrConfig.from_env(dict(os.environ) if env is None else env, root=ROOT)
    if not config.live_enabled:
        print("IMP_IBKR_LIVE=1 is required; no gateway request was made", file=sys.stderr)
        return 2
    client = (client_factory or build_client)(config)
    try:
        report = CapabilityProbe(client).run(arguments.symbol)
        write_report(arguments.output, report)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(f"Wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["CapabilityProbe", "DEFAULT_OUTPUT", "build_client", "main", "write_report"]
