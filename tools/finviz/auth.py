"""Finviz Elite authentication operator tooling — never prints credentials."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.finviz.credential_manager import (  # noqa: E402
    get_finviz_credential_manager,
    reset_finviz_credential_manager,
)
from market_platform_foundation.finviz.request_manager import reset_finviz_request_manager  # noqa: E402
from market_platform_foundation.finviz.secure_store import (  # noqa: E402
    write_login_credentials,
)


def _print_status() -> int:
    manager = get_finviz_credential_manager()
    health = manager.health()
    print("FINVIZ ELITE AUTH")
    print()
    print(f"Credential source       {health.source.value}")
    print(f"Credential present      {'YES' if health.credential_present else 'NO'}")
    print(f"Authentication          {health.state.value}")
    print(f"Credential generation   {health.finviz_credential_generation}")
    print(f"Last validated          {health.last_validated or '—'}")
    print(f"Last rotation           {health.last_rotation or '—'}")
    print(f"Recovery mode           {health.recovery_mode.value}")
    print(f"Automatic recovery      {health.automatic_recovery}")
    print(f"Last auth error         {health.last_auth_error or 'NONE'}")
    if health.state.value == "HEALTHY":
        print("READY")
        return 0
    if health.state.value == "UNCONFIGURED":
        print("NOT CONFIGURED — run: python tools/finviz/auth.py configure")
        return 2
    return 1


def _configure(*, token: str | None, username: str | None, password: str | None) -> int:
    manager = get_finviz_credential_manager()
    token_value = token or getpass.getpass("Finviz Elite API token: ")
    if not token_value.strip():
        print("ERROR: token required")
        return 2
    if not manager.configure_token(token_value.strip(), validate=False):
        print("ERROR: failed to store credential")
        return 2
    if username and password:
        if not write_login_credentials(username, password):
            print("WARNING: login credentials not stored — automatic recovery may be limited")
    if manager.validate_token(token_value.strip()):
        print("Validation              PASS")
        print("READY")
        return 0
    print("Validation              FAIL")
    print("Token stored but validation failed — check Elite subscription")
    return 1


def _validate() -> int:
    manager = get_finviz_credential_manager()
    token = manager.get_token()
    if not token:
        print("NOT CONFIGURED")
        return 2
    if manager.validate_token(token):
        print("Validation              PASS")
        return 0
    print("Validation              FAIL")
    return 1


def _repair() -> int:
    manager = get_finviz_credential_manager()
    if manager.attempt_recovery():
        print("Recovery                SUCCESS")
        return 0
    health = manager.health()
    print(f"Recovery                FAILED ({health.state.value})")
    if health.state.value == "AUTH_OPERATOR_ACTION_REQUIRED":
        print("Operator action required — complete Finviz MFA/CAPTCHA in browser, then retry.")
    return 1


def _clear() -> int:
    manager = get_finviz_credential_manager()
    manager.clear_credentials()
    reset_finviz_credential_manager()
    reset_finviz_request_manager()
    print("Finviz credentials cleared")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finviz Elite authentication maintenance")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show sanitized auth status")
    configure = sub.add_parser("configure", help="Store and validate API token")
    configure.add_argument("--token", help="API token (omit to prompt securely)")
    configure.add_argument("--username", help="Optional Finviz login for automatic recovery")
    configure.add_argument("--password", help="Optional Finviz password (omit to prompt)")
    sub.add_parser("validate", help="Validate stored credential")
    sub.add_parser("repair", help="Attempt automatic credential recovery")
    sub.add_parser("clear", help="Remove stored Finviz credentials")

    args = parser.parse_args(argv)
    if args.command == "status":
        return _print_status()
    if args.command == "configure":
        password = args.password
        if args.username and not password:
            password = getpass.getpass("Finviz password: ")
        return _configure(token=args.token, username=args.username, password=password)
    if args.command == "validate":
        return _validate()
    if args.command == "repair":
        return _repair()
    if args.command == "clear":
        return _clear()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
