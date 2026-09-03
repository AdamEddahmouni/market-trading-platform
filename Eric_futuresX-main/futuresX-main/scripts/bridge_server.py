"""Read-only HTTP bridge for IMP futures lane integration (stdlib only)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1] / "src_client" / "workspace"
sys.path.insert(0, str(WORKSPACE))

from utils import get_latest_index_futures_expiry  # noqa: E402

DEFAULT_PORT = 8788
MODE = "FIXTURE_BRIDGE"


def _is_rth() -> bool:
    import pytz

    now = datetime.now(pytz.timezone("America/New_York")).time()
    return (
        now >= datetime.strptime("09:30", "%H:%M").time()
        and now <= datetime.strptime("16:00", "%H:%M").time()
    )


def _latest_fixture_snapshot() -> dict[str, Any]:
    """Return latest depth from smoke CSV when bundled data is unavailable."""
    smoke_csv = Path(__file__).resolve().parents[1] / ".smoke_data" / "es_level2_data.csv"
    if not smoke_csv.is_file():
        return {
            "asks": [{"price": 6002.0, "size": 10}],
            "bids": [{"price": 6000.0, "size": 50}],
            "event_time": datetime.utcnow().isoformat() + "Z",
            "source": "bridge_default",
        }
    import pandas as pd

    frame = pd.read_csv(smoke_csv)
    if frame.empty:
        return {"asks": [], "bids": [], "event_time": datetime.utcnow().isoformat() + "Z"}
    row = frame.iloc[-1]
    bids = _parse_ladder(str(row.get("bids", "")))
    asks = _parse_ladder(str(row.get("asks", "")))
    ts = datetime.utcfromtimestamp(int(row["timestamp"])).isoformat() + "Z"
    return {"asks": asks, "bids": bids, "event_time": ts, "source": "smoke_csv"}


def _parse_ladder(raw: str) -> list[dict[str, float]]:
    levels: list[dict[str, float]] = []
    for part in raw.split(";"):
        if not part.strip() or ":" not in part:
            continue
        price, size = part.split(":", 1)
        levels.append({"price": float(price), "size": float(size)})
    return levels


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                {
                    "available": True,
                    "contract_month": get_latest_index_futures_expiry("ES"),
                    "mode": MODE,
                    "status": "OK",
                    "symbol": "ES",
                }
            )
            return
        if self.path == "/api/session":
            rth = _is_rth()
            self._send_json(
                {
                    "available": True,
                    "rth": rth,
                    "session_state": "RTH" if rth else "OUTSIDE_RTH",
                    "symbol": "ES",
                }
            )
            return
        if self.path == "/api/depth/latest":
            snap = _latest_fixture_snapshot()
            self._send_json(
                {
                    "available": True,
                    "contract_month": get_latest_index_futures_expiry("ES"),
                    "exchange": "CME",
                    "provenance": "donor_bridge",
                    "research_only": True,
                    "snapshot": snap,
                    "symbol": "ES",
                }
            )
            return
        self._send_json({"available": False, "error": "NOT_FOUND"}, status=404)


def main() -> int:
    parser = argparse.ArgumentParser(description="FuturesX read-only bridge for IMP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    print(f"FuturesX bridge listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Bridge stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
