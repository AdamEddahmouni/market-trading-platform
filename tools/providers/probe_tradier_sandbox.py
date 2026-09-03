#!/usr/bin/env python3
"""Tradier sandbox wire probe — credential-gated, read-only-first.

Exercises the documented sandbox wire contract (docs/providers/
TRADIER_PAPER.md) against https://sandbox.tradier.com/v1 and reports
sanitized request/response evidence. Standard library only.

Fail-closed gates (mirroring TradierPaperExecutionProvider, P4-SAFE-001):
  IMP_TRADIER_PAPER=1, IMP_BROKER_PAPER_EXECUTION=1, IMP_TRADIER_TOKEN set,
  and the resolved endpoint must be exactly the sandbox base URL. With any
  gate missing the probe prints a PROVIDER_NOT_CONFIGURED message and exits
  nonzero BEFORE any network activity. The production host api.tradier.com
  is never contacted.

Token resolution order:
  1. env IMP_TRADIER_TOKEN
  2. .private/providers.env line ``IMP_TRADIER_TOKEN=...``

Secrets are never printed: the Authorization header is redacted in all
evidence output, and any response key matching token/secret/password/
authorization is scrubbed recursively.

Exit codes:
  0  probe passed (all exercised contract checks OK)
  2  PROVIDER_NOT_CONFIGURED / gate missing or endpoint not sandbox
  3  CONTRACT_MISMATCH vs fixture-derived expectations
  4  NETWORK_ERROR (unreachable sandbox, non-JSON, unexpected HTTP error)

Usage:
  python tools/providers/probe_tradier_sandbox.py                 # read-only
  python tools/providers/probe_tradier_sandbox.py --submit AAPL 1 # + paper order lifecycle
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SANDBOX_ENDPOINT = "https://sandbox.tradier.com/v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_ENV_PATH = REPO_ROOT / ".private" / "providers.env"

# Documented wire vocabulary (docs.tradier.com Place Order / Orders schemas,
# retrieved 2026-08-22) — the values fixtures assume status_raw is drawn from.
DOCUMENTED_ORDER_STATUSES = {
    "pending",
    "open",
    "partially_filled",
    "filled",
    "expired",
    "canceled",
    "rejected",
    "pending_cancel",
    "error",  # guide-level status; treated as terminal failure
}
# place-order ack status per OpenAPI OrderResponse example.
DOCUMENTED_ACK_STATUSES = {"ok"}
# cancel-order ack statuses per Cancel Order schema.
DOCUMENTED_CANCEL_STATUSES = {"ok", "pending_cancel"}

TERMINAL_STATUSES = {"filled", "canceled", "rejected", "expired", "error"}

EXIT_OK = 0
EXIT_NOT_CONFIGURED = 2
EXIT_CONTRACT_MISMATCH = 3
EXIT_NETWORK = 4

_SECRET_KEY_MARKERS = ("token", "secret", "password", "authorization")


def _scrub(value: Any) -> Any:
    """Recursively redact secret-looking keys from parsed JSON evidence."""
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if any(m in str(k).lower() for m in _SECRET_KEY_MARKERS) else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: ("[REDACTED]" if k.lower() == "authorization" else v) for k, v in headers.items()}


def print_evidence(label: str, *, method: str, url: str, headers: dict[str, str], body: Any, http_status: int | None) -> None:
    print(f"--- {label} ---")
    print(f"{method} {url}")
    print(f"request-headers: {json.dumps(_redact_headers(headers), sort_keys=True)}")
    if http_status is not None:
        print(f"http-status: {http_status}")
    print(f"response-body: {json.dumps(_scrub(body), indent=2, sort_keys=True)[:4000]}")
    print()


class ProbeError(Exception):
    def __init__(self, kind: str, code: int, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.code = code
        self.detail = detail


def load_token() -> str | None:
    token = os.environ.get("IMP_TRADIER_TOKEN", "")
    if token:
        return token
    if PROVIDERS_ENV_PATH.is_file():
        for raw_line in PROVIDERS_ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("IMP_TRADIER_TOKEN="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    return None


def resolve_gates(endpoint_arg: str | None) -> tuple[dict[str, str], str]:
    """Return (env_view, endpoint) after fail-closed gate verification."""
    missing: list[str] = []
    if os.environ.get("IMP_TRADIER_PAPER") != "1":
        missing.append("IMP_TRADIER_PAPER=1")
    if os.environ.get("IMP_BROKER_PAPER_EXECUTION") != "1":
        missing.append("IMP_BROKER_PAPER_EXECUTION=1")
    token = load_token()
    if not token:
        missing.append("IMP_TRADIER_TOKEN (env or .private/providers.env)")
    endpoint = endpoint_arg or os.environ.get("IMP_TRADIER_ENDPOINT") or SANDBOX_ENDPOINT
    if endpoint != SANDBOX_ENDPOINT:
        raise ProbeError(
            "PRODUCTION_ENDPOINT_BLOCKED",
            EXIT_NOT_CONFIGURED,
            f"endpoint {endpoint!r} is not the sandbox base URL {SANDBOX_ENDPOINT}; refusing to probe",
        )
    if missing:
        raise ProbeError(
            "PROVIDER_NOT_CONFIGURED",
            EXIT_NOT_CONFIGURED,
            "gates absent: " + "; ".join(missing) + " — live wire exercise stays blocked until configured",
        )
    return {"token": token or "", "account_id": os.environ.get("IMP_TRADIER_ACCOUNT_ID", "")}, endpoint


def http_request(method: str, url: str, token: str, *, form: dict[str, str] | None = None) -> tuple[int | None, Any, dict[str, str]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    data = None
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except (urllib.error.URLError, OSError) as exc:
        raise ProbeError("NETWORK_ERROR", EXIT_NETWORK, f"{method} {url} failed: {exc}") from exc
    try:
        body: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProbeError("NETWORK_ERROR", EXIT_NETWORK, f"{method} {url} returned non-JSON body ({exc})") from exc
    return status, body, headers


def require(condition: bool, description: str) -> None:
    if not condition:
        raise ProbeError("CONTRACT_MISMATCH", EXIT_CONTRACT_MISMATCH, f"contract check failed: {description}")


def probe_readonly(env: dict[str, str], endpoint: str) -> str:
    """Minimum safe read-only workflow. Returns the resolved account id."""
    token = env["token"]
    url = f"{endpoint}/user/profile"
    status, body, headers = http_request("GET", url, token)
    print_evidence("GET user profile", method="GET", url=url, headers=headers, body=body, http_status=status)
    if status in (401, 403):
        raise ProbeError("AUTH_REJECTED", EXIT_NETWORK, f"profile fetch returned HTTP {status}: token rejected by sandbox")
    require(status == 200, f"profile fetch expected HTTP 200, got {status}")
    profile = body.get("profile") if isinstance(body, dict) else None
    require(isinstance(profile, dict), "profile payload must contain a 'profile' object")
    accounts = profile.get("account")
    require(isinstance(accounts, list) and len(accounts) >= 1, "'profile.account' must be a non-empty list")

    account_id = env["account_id"]
    if account_id:
        match = next((a for a in accounts if str(a.get("account_number")) == account_id), None)
        require(match is not None, f"configured IMP_TRADIER_ACCOUNT_ID={account_id!r} not present in profile")
    else:
        account_id = str(accounts[0].get("account_number", ""))
    require(bool(account_id), "no resolvable sandbox account_number")

    balances_url = f"{endpoint}/accounts/{urllib.parse.quote(account_id)}/balances"
    status, body, headers = http_request("GET", balances_url, token)
    print_evidence(
        f"GET account balances (account={account_id})",
        method="GET",
        url=balances_url,
        headers=headers,
        body=body,
        http_status=status,
    )
    require(status == 200, f"balances fetch expected HTTP 200, got {status}")
    require(isinstance(body, dict) and "balances" in body, "balances payload must contain a 'balances' object")
    print(f"[ok] read-only workflow verified for sandbox account {account_id}")
    return account_id


def probe_order_lifecycle(env: dict[str, str], endpoint: str, account_id: str, symbol: str, quantity: int) -> None:
    """Optional paper order lifecycle: submit -> poll -> cancel-if-still-open."""
    token = env["token"]
    submit_url = f"{endpoint}/accounts/{urllib.parse.quote(account_id)}/orders"
    form = {
        "class": "equity",
        "symbol": symbol.upper(),
        "side": "buy",
        "quantity": str(quantity),
        "type": "market",
        "duration": "day",
    }
    status, body, headers = http_request("POST", submit_url, token, form=form)
    print_evidence(
        "POST paper order (sandbox)",
        method="POST",
        url=submit_url,
        headers=headers,
        body=body,
        http_status=status,
    )
    require(status == 200, f"order submit expected HTTP 200, got {status}")
    order_ack = body.get("order") if isinstance(body, dict) else None
    require(isinstance(order_ack, dict), "submit response must contain an 'order' object")
    broker_order_id = order_ack.get("id")
    require(broker_order_id not in (None, ""), "submit ack must carry a non-empty 'order.id' (fixture expectation: broker_order_id provenance)")
    ack_status = str(order_ack.get("status", ""))
    require(
        ack_status in DOCUMENTED_ACK_STATUSES or ack_status in DOCUMENTED_ORDER_STATUSES,
        f"submit ack status {ack_status!r} outside documented vocabulary",
    )

    order_url = f"{endpoint}/accounts/{urllib.parse.quote(account_id)}/orders/{broker_order_id}"
    deadline = time.monotonic() + 30.0
    observed: list[str] = []
    final_status = ""
    while True:
        status, body, headers = http_request("GET", order_url, token)
        print_evidence(
            f"GET order {broker_order_id}",
            method="GET",
            url=order_url,
            headers=headers,
            body=body,
            http_status=status,
        )
        require(status == 200, f"order fetch expected HTTP 200, got {status}")
        orders = body.get("orders") if isinstance(body, dict) else None
        record = orders.get("order") if isinstance(orders, dict) else None
        require(isinstance(record, dict), f"order fetch payload must contain 'orders.order' for id {broker_order_id}")
        final_status = str(record.get("status", ""))
        require(final_status in DOCUMENTED_ORDER_STATUSES, f"observed order status {final_status!r} outside documented vocabulary")
        if final_status != ack_status and (not observed or observed[-1] != final_status):
            observed.append(final_status)
        if final_status in TERMINAL_STATUSES or time.monotonic() > deadline:
            break
        time.sleep(2.0)

    if final_status not in TERMINAL_STATUSES:
        print(f"[info] order {broker_order_id} still '{final_status}' after poll window; cancelling to leave no stray paper order")
        status, body, headers = http_request("DELETE", order_url, token)
        print_evidence(
            f"DELETE order {broker_order_id}",
            method="DELETE",
            url=order_url,
            headers=headers,
            body=body,
            http_status=status,
        )
        require(status == 200, f"cancel expected HTTP 200, got {status}")
        cancel_ack = body.get("order") if isinstance(body, dict) else None
        require(isinstance(cancel_ack, dict), "cancel response must contain an 'order' object")
        require(
            str(cancel_ack.get("status", "")) in DOCUMENTED_CANCEL_STATUSES,
            f"cancel ack status {cancel_ack.get('status')!r} outside documented vocabulary {{'ok','pending_cancel'}}",
        )

    print(f"[ok] order lifecycle exercised: id={broker_order_id} ack={ack_status!r} transitions={observed or ['<immediately-terminal>']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Credential-gated Tradier sandbox wire probe (read-only unless --submit).")
    parser.add_argument("--submit", nargs=2, metavar=("SYMBOL", "QTY"), default=None, help="explicitly opt in to a sandbox paper market order lifecycle")
    parser.add_argument("--endpoint", default=None, help="override IMP_TRADIER_ENDPOINT (must equal the sandbox URL)")
    args = parser.parse_args(argv)

    try:
        env, endpoint = resolve_gates(args.endpoint)
        print(f"[gate] all gates satisfied; probing sandbox endpoint {endpoint}")
        account_id = probe_readonly(env, endpoint)
        if args.submit is not None:
            symbol, qty_raw = args.submit
            try:
                quantity = int(qty_raw)
            except ValueError:
                quantity = 0
            if quantity <= 0 or not symbol.strip():
                raise ProbeError("CONTRACT_MISMATCH", EXIT_CONTRACT_MISMATCH, "--submit requires SYMBOL and positive integer QTY")
            probe_order_lifecycle(env, endpoint, account_id, symbol, quantity)
        else:
            print("[skip] no --submit given; order lifecycle not exercised (read-only run)")
        print("[done] PROBE_PASSED")
        return EXIT_OK
    except ProbeError as exc:
        print(f"[fail] {exc.kind}: {exc.detail}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
