"""Bounded operator-local verification for IBKR historical TRADE pagination.

Does not enable subscriptions or purchase market data. Writes a JSON receipt
under evidence/market_data/ibkr/ when run; otherwise records PROVIDER_UNVERIFIED.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes  # noqa: E402


def _loopback_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _build_receipt(status: str, **fields: object) -> dict[str, object]:
    body: dict[str, object] = {
        "verification_kind": "IBKR_HISTORICAL_TRADES_BOUNDED",
        "status": status,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "not_prospective_evidence": True,
    }
    body.update(fields)
    body["receipt_sha256"] = sha256_bytes(canonical_bytes(body))
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "market_data" / "ibkr" / "historical-trades-verification.json",
    )
    parser.add_argument("--symbol", default="AAPL")
    args = parser.parse_args()

    live = os.environ.get("IMP_IBKR_LIVE", "").strip() == "1"
    transport = os.environ.get("IMP_IBKR_TRANSPORT", "rest").strip().lower()
    host = os.environ.get("IMP_IBKR_TWS_HOST", "127.0.0.1").strip()
    try:
        port = int(os.environ.get("IMP_IBKR_TWS_PORT", "4001"))
    except ValueError:
        port = 0

    if not live:
        receipt = _build_receipt(
            "PROVIDER_UNVERIFIED",
            reason="IMP_IBKR_LIVE_NOT_ENABLED",
            transport=transport,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_bytes(receipt))
        print(json.dumps(receipt, indent=2))
        return 0

    if transport != "tws" or not _loopback_reachable(host, port):
        receipt = _build_receipt(
            "PROVIDER_UNVERIFIED",
            reason="TWS_LOOPBACK_UNAVAILABLE",
            transport=transport,
            host=host,
            port=port,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_bytes(receipt))
        print(json.dumps(receipt, indent=2))
        return 0

    try:
        if __package__:
            from .config import IbkrConfig
            from .query_provider import build_query_provider
        else:
            from tools.ibkr.config import IbkrConfig
            from tools.ibkr.query_provider import build_query_provider
        from market_platform_foundation.providers.ibkr_observational.query_provider import (
            IbkrObservationalQueryService,
        )
    except Exception as exc:  # pragma: no cover - operator path
        receipt = _build_receipt(
            "PROVIDER_UNVERIFIED",
            reason=f"IMPORT_FAILED:{exc}",
            transport=transport,
        )
        args.output.write_bytes(canonical_bytes(receipt))
        print(json.dumps(receipt, indent=2))
        return 0

    end = datetime.now(timezone.utc) - timedelta(days=3)
    start = end - timedelta(minutes=5)
    start_ns = int(start.timestamp() * 1_000_000_000)
    end_ns = int(end.timestamp() * 1_000_000_000)
    request_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    try:
        config = IbkrConfig.from_environment()
        provider = build_query_provider(config)
        service = IbkrObservationalQueryService(provider=provider)
        result = service.fetch_historical_trades(
            args.symbol,
            start_time_ns=start_ns,
            end_time_ns=end_ns,
            request_time_ns=request_ns,
            terminal_window_end_ns=end_ns,
            ticks_per_page=100,
            max_pages=2,
            min_inter_page_interval_ns=0,
        )
        provider.shutdown()
    except Exception as exc:  # pragma: no cover - operator path
        receipt = _build_receipt(
            "PROVIDER_UNVERIFIED",
            reason=f"SESSION_FAILED:{exc}",
            transport=transport,
        )
        args.output.write_bytes(canonical_bytes(receipt))
        print(json.dumps(receipt, indent=2))
        return 0

    status = "VERIFIED_BOUNDED" if result.accepted else "PROVIDER_UNVERIFIED"
    receipt = _build_receipt(
        status,
        transport=transport,
        symbol=args.symbol.upper(),
        accepted=result.accepted,
        reason=result.reason,
        trade_count=len(result.trades),
        complete=result.complete,
        provenance=result.provenance.as_dict() if result.provenance else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(receipt))
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
