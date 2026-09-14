"""CLI — Item 7 read-only US.AAPL SNAPSHOT_BBO diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import importlib.util

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_ITEM7_PATH = _ROOT / "tools" / "moomoo" / "item7_bbo_snapshot.py"
_spec = importlib.util.spec_from_file_location("imp_item7_bbo_snapshot", _ITEM7_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load Item 7 module from {_ITEM7_PATH}")
_item7 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _item7
_spec.loader.exec_module(_item7)
DEFAULT_SYMBOL = _item7.DEFAULT_SYMBOL
run_live_probe = _item7.run_live_probe


def _default_host() -> str:
    return (os.environ.get("IMP_MOOMOO_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def _default_port() -> int:
    raw = (os.environ.get("IMP_MOOMOO_PORT") or "11111").strip()
    try:
        return int(raw)
    except ValueError:
        return 11111


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Item 7 OpenD market-snapshot BBO probe (read-only).")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Provider code, default US.AAPL")
    parser.add_argument("--host", default=_default_host())
    parser.add_argument("--port", type=int, default=_default_port())
    parser.add_argument(
        "--require-rth",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When true, refuse probe outside US cash RTH (honest block).",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args(argv)

    diagnostic = run_live_probe(
        symbol=args.symbol,
        host=args.host,
        port=args.port,
        require_rth=args.require_rth,
    )
    payload = json.dumps(diagnostic.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if diagnostic.probe_status == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
