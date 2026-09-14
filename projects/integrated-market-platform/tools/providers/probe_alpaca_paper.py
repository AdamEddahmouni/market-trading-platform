#!/usr/bin/env python3
"""Alpaca Paper wire probe — credential-gated, read-only first.

Exercises GET /v2/account, GET /v2/clock, and GET /v2/positions against
https://paper-api.alpaca.markets only. Standard library only. Never imports
the Alpaca SDK. Never contacts api.alpaca.markets. ``/v2`` is a path, not
an origin. Uses the GET-only Paper transport so POST/DELETE order paths are
refused before the socket is opened.

Without paper keys the probe prints COMPARATOR_NOT_CONFIGURED and exits
nonzero BEFORE any network activity. Live host URLs are LIVE_FORBIDDEN.

Token resolution order:
  1. env APCA_API_KEY_ID / APCA_API_SECRET_KEY
  2. --env-file or IMP_ALPACA_PAPER_ENV (gitignored operator file)
  3. .private/alpaca-paper.env
  4. .private/providers.env

Secrets are never printed. Presence is names_present true/false only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.providers.adapters.alpaca_paper_http import (  # noqa: E402
    ALPACA_PAPER_ORIGIN,
    AlpacaPaperHttpError,
    AlpacaPaperReadOnlyHttpTransport,
    alpaca_http_fetch_account,
    alpaca_http_fetch_clock,
    alpaca_http_fetch_positions,
    canonicalize_alpaca_paper_origin,
    paper_api_url,
)

DEFAULT_PAPER_ENV = ROOT / ".private" / "alpaca-paper.env"
PROVIDERS_ENV_PATH = ROOT / ".private" / "providers.env"

EXIT_OK = 0
EXIT_NOT_CONFIGURED = 2
EXIT_LIVE_FORBIDDEN = 3
EXIT_NETWORK = 4

_SECRET_KEY_MARKERS = ("token", "secret", "password", "authorization", "key_id", "key")


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]"
                if any(m in str(k).lower() for m in _SECRET_KEY_MARKERS)
                else _scrub(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw = line.split("=", 1)
        values[name.strip()] = raw.strip().strip('"').strip("'")
    return values


def _candidate_env_files(explicit: str | None) -> list[Path]:
    files: list[Path] = []
    if explicit:
        files.append(Path(explicit))
    override = os.environ.get("IMP_ALPACA_PAPER_ENV", "").strip()
    if override:
        files.append(Path(override))
    files.append(DEFAULT_PAPER_ENV)
    files.append(PROVIDERS_ENV_PATH)
    return files


def load_private_values(explicit: str | None = None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in reversed(_candidate_env_files(explicit)):
        merged.update(_parse_env_file(path))
    return merged


def load_keys(explicit: str | None = None) -> tuple[str, str]:
    private = load_private_values(explicit)
    key_id = os.environ.get("APCA_API_KEY_ID") or private.get("APCA_API_KEY_ID") or ""
    secret = os.environ.get("APCA_API_SECRET_KEY") or private.get("APCA_API_SECRET_KEY") or ""
    return key_id.strip(), secret.strip()


def stamp_no_orders() -> None:
    print("orders_placed=false")
    print("fabricated_fills=false")


def presence_payload(*, key_id: str, secret: str, base_url: str) -> dict[str, bool]:
    return {
        "APCA_API_KEY_ID": bool(key_id),
        "APCA_API_SECRET_KEY": bool(secret),
        "APCA_API_BASE_URL": bool(str(base_url or "").strip()),
    }


def resolve_origin(endpoint_arg: str | None, private: dict[str, str]) -> str:
    origin = (
        endpoint_arg
        or os.environ.get("APCA_API_BASE_URL")
        or os.environ.get("ALPACA_BASE_URL")
        or private.get("APCA_API_BASE_URL")
        or private.get("ALPACA_BASE_URL")
        or ALPACA_PAPER_ORIGIN
    )
    return canonicalize_alpaca_paper_origin(origin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Credential-gated Alpaca Paper probe "
            "(read-only GET /v2/account, /v2/clock, /v2/positions)."
        )
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="override APCA_API_BASE_URL (must canonicalize to the Paper origin)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="gitignored env file with APCA_* names (values never printed)",
    )
    args = parser.parse_args(argv)
    private = load_private_values(args.env_file)
    key_id, secret = load_keys(args.env_file)
    base_url = (
        args.endpoint
        or os.environ.get("APCA_API_BASE_URL")
        or os.environ.get("ALPACA_BASE_URL")
        or private.get("APCA_API_BASE_URL")
        or private.get("ALPACA_BASE_URL")
        or ""
    )
    print("names_present " + json.dumps(presence_payload(key_id=key_id, secret=secret, base_url=base_url), sort_keys=True))
    if not key_id or not secret:
        print("[fail] COMPARATOR_NOT_CONFIGURED: APCA_API_KEY_ID / APCA_API_SECRET_KEY absent")
        stamp_no_orders()
        return EXIT_NOT_CONFIGURED
    try:
        origin = resolve_origin(args.endpoint, private)
    except AlpacaPaperHttpError as exc:
        code = str(exc)
        print(f"[fail] {code}")
        stamp_no_orders()
        if code == "LIVE_FORBIDDEN":
            return EXIT_LIVE_FORBIDDEN
        return EXIT_NOT_CONFIGURED
    account_url = paper_api_url(origin, "v2", "account")
    clock_url = paper_api_url(origin, "v2", "clock")
    positions_url = paper_api_url(origin, "v2", "positions")
    print(f"origin={origin}")
    print(f"request=GET {account_url.removeprefix(origin)}")
    print(f"request=GET {clock_url.removeprefix(origin)}")
    print(f"request=GET {positions_url.removeprefix(origin)}")
    transport = AlpacaPaperReadOnlyHttpTransport()
    try:
        account = alpaca_http_fetch_account(
            transport, origin=origin, key_id=key_id, secret_key=secret
        )
        clock = alpaca_http_fetch_clock(
            transport, origin=origin, key_id=key_id, secret_key=secret
        )
        positions = alpaca_http_fetch_positions(
            transport, origin=origin, key_id=key_id, secret_key=secret
        )
    except AlpacaPaperHttpError as exc:
        code = str(exc)
        print(f"[fail] {code}")
        stamp_no_orders()
        if code.startswith("ALPACA_PAPER_NETWORK") or code == "ALPACA_PAPER_AUTH_REJECTED":
            return EXIT_NETWORK
        if code == "LIVE_FORBIDDEN":
            return EXIT_LIVE_FORBIDDEN
        if code == "ALPACA_READONLY_FORBIDDEN":
            return EXIT_NOT_CONFIGURED
        return EXIT_NOT_CONFIGURED
    if account is None:
        print("[fail] BROKER_RESPONSE_INVALID: GET /v2/account did not return an account object")
        stamp_no_orders()
        return EXIT_NETWORK
    if clock is None:
        print("[fail] BROKER_RESPONSE_INVALID: GET /v2/clock did not return a clock object")
        stamp_no_orders()
        return EXIT_NETWORK
    if positions is None:
        print("[fail] BROKER_RESPONSE_INVALID: GET /v2/positions did not return a positions list")
        stamp_no_orders()
        return EXIT_NETWORK
    print("account_present=true")
    print(f"status_raw={account.get('status_raw') or ''}")
    print(f"clock_is_open={str(clock.get('is_open')).lower()}")
    print(f"next_open={clock.get('next_open') or ''}")
    print(f"next_close={clock.get('next_close') or ''}")
    print(f"positions_count={len(positions.get('positions') or [])}")
    print("[done] PROBE_PASSED")
    stamp_no_orders()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
