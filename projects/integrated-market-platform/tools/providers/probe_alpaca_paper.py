#!/usr/bin/env python3
"""Alpaca Paper wire probe — credential-gated, read-only first.

Exercises GET /v2/account against https://paper-api.alpaca.markets only.
Standard library only. Never imports the Alpaca SDK. Never contacts
api.alpaca.markets.

Without paper keys the probe prints COMPARATOR_NOT_CONFIGURED and exits
nonzero BEFORE any network activity. Live host URLs are LIVE_FORBIDDEN.

Token resolution order:
  1. env APCA_API_KEY_ID / APCA_API_SECRET_KEY
  2. .private/providers.env lines with those names

Secrets are never printed.
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
    AlpacaPaperHttpTransport,
    alpaca_http_fetch_account,
    assert_alpaca_paper_url,
)

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


def _load_private_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not PROVIDERS_ENV_PATH.is_file():
        return values
    for raw_line in PROVIDERS_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw = line.split("=", 1)
        values[name.strip()] = raw.strip().strip('"').strip("'")
    return values


def load_keys() -> tuple[str, str]:
    private = _load_private_env()
    key_id = os.environ.get("APCA_API_KEY_ID") or private.get("APCA_API_KEY_ID") or ""
    secret = os.environ.get("APCA_API_SECRET_KEY") or private.get("APCA_API_SECRET_KEY") or ""
    return key_id.strip(), secret.strip()


def resolve_origin(endpoint_arg: str | None) -> str:
    origin = (
        endpoint_arg
        or os.environ.get("APCA_API_BASE_URL")
        or os.environ.get("ALPACA_BASE_URL")
        or ALPACA_PAPER_ORIGIN
    )
    try:
        assert_alpaca_paper_url(origin)
    except AlpacaPaperHttpError as exc:
        code = str(exc)
        if code == "LIVE_FORBIDDEN":
            raise SystemExit(
                f"[fail] LIVE_FORBIDDEN: origin {origin!r} is not the Paper host; refusing to probe"
            ) from exc
        raise SystemExit(f"[fail] {code}: origin {origin!r} refused") from exc
    return origin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Credential-gated Alpaca Paper probe (read-only GET /v2/account)."
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="override APCA_API_BASE_URL (must be the Paper origin)",
    )
    args = parser.parse_args(argv)
    key_id, secret = load_keys()
    if not key_id or not secret:
        print("[fail] COMPARATOR_NOT_CONFIGURED: APCA_API_KEY_ID / APCA_API_SECRET_KEY absent")
        print("orders_placed=false")
        print("fabricated_fills=false")
        return EXIT_NOT_CONFIGURED
    try:
        origin = resolve_origin(args.endpoint)
    except SystemExit as exc:
        detail = str(exc)
        if "LIVE_FORBIDDEN" in detail:
            print(detail)
            return EXIT_LIVE_FORBIDDEN
        print(detail)
        return EXIT_NOT_CONFIGURED
    transport = AlpacaPaperHttpTransport()
    try:
        account = alpaca_http_fetch_account(
            transport, origin=origin, key_id=key_id, secret_key=secret
        )
    except AlpacaPaperHttpError as exc:
        code = str(exc)
        print(f"[fail] {code}")
        if code.startswith("ALPACA_PAPER_NETWORK") or code == "ALPACA_PAPER_AUTH_REJECTED":
            return EXIT_NETWORK
        if code == "LIVE_FORBIDDEN":
            return EXIT_LIVE_FORBIDDEN
        return EXIT_NOT_CONFIGURED
    if account is None:
        print("[fail] BROKER_RESPONSE_INVALID: GET /v2/account did not return an account object")
        return EXIT_NETWORK
    print(f"[gate] Paper origin {origin}; GET /v2/account")
    print(f"response-body: {json.dumps(_scrub(account), indent=2, sort_keys=True)[:4000]}")
    print("[done] PROBE_PASSED")
    print("orders_placed=false")
    print("fabricated_fills=false")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
