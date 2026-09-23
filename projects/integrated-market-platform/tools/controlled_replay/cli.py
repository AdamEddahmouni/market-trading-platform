"""Operator CLI for CONTROLLED REPLAY golden path."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

from tools.controlled_replay import CONTROLLED_REPLAY_OPERATOR_URL_PATH
from tools.controlled_replay.env import (
    build_controlled_replay_environment,
    controlled_replay_state_dir,
)
from tools.controlled_replay.reset import reset_controlled_replay_state
from tools.controlled_replay.scenarios import list_scenario_catalog, load_scenarios
from tools.platform.local_launcher import (
    API_URL,
    UI_URL,
    PlatformController,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "CONTROLLED REPLAY operator golden path: start the real stack with "
            "FIXTURE_REPLAY posture, load deterministic scenarios through real "
            "ingest, and reset only namespaced demo state. Not Live."
        )
    )
    sub = parser.add_subparsers(dest="action", required=True)

    start = sub.add_parser(
        "start",
        help="Start API+UI in controlled-replay mode and load scenario pack",
    )
    start.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="Open Radar in the browser after readiness",
    )
    start.add_argument(
        "--skip-load",
        action="store_true",
        help="Start stack only; do not POST scenario pack",
    )
    start.add_argument("--json", action="store_true")

    sub.add_parser("stop", help="Stop launcher-owned controlled-replay stack")
    sub.add_parser("status", help="Show controlled-replay stack readiness")
    reset = sub.add_parser(
        "reset",
        help="Delete only .local/controlled-replay/ durable state (never empirical)",
    )
    reset.add_argument("--json", action="store_true")

    load = sub.add_parser(
        "load",
        help="POST scenario pack into a running controlled-replay API",
    )
    load.add_argument("--json", action="store_true")

    catalog = sub.add_parser("scenarios", help="List controlled-replay scenarios")
    catalog.add_argument("--json", action="store_true")
    return parser


def _controller(root: Path) -> PlatformController:
    env = build_controlled_replay_environment(dict(**__import__("os").environ), root=root)
    return PlatformController(root=root, environ=env, profile="controlled_replay")


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def verify_controlled_replay_context(*, api_base: str = API_URL) -> dict[str, Any]:
    """Fail closed unless the running API advertises CONTROLLED REPLAY posture.

    Prevents loading fixture news into a Live / default stack that already
    owns :8766 (shared launcher idempotency short-circuit).
    """

    base = api_base.rstrip("/")
    # local_launcher.API_URL is the readiness probe (.../context). Accept either
    # a base origin or that probe URL without double-appending /context.
    if base.endswith("/context"):
        base = base[: -len("/context")]
    try:
        request = urllib.request.Request(
            f"{base}/context",
            method="GET",
            headers={"User-Agent": "imp-controlled-replay/1.0"},
        )
        with urllib.request.urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "reason": "CONTEXT_UNAVAILABLE",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "CONTEXT_INVALID", "payload": payload}
    as_of = payload.get("as_of_context") if isinstance(payload.get("as_of_context"), dict) else {}
    controlled = bool(payload.get("controlled_replay")) or bool(as_of.get("controlled_replay"))
    evidence = str(as_of.get("evidence_class") or payload.get("evidence_class") or "").upper()
    data_mode = str(as_of.get("data_mode") or "").upper()
    authority = str(as_of.get("execution_authority") or "").upper()
    if data_mode == "LIVE_OBSERVATIONAL":
        return {
            "ok": False,
            "reason": "LIVE_OBSERVATIONAL_REFUSED",
            "data_mode": data_mode,
            "execution_authority": authority,
        }
    if not controlled and evidence != "CONTROLLED_REPLAY":
        return {
            "ok": False,
            "reason": "NOT_CONTROLLED_REPLAY",
            "data_mode": data_mode,
            "execution_authority": authority,
            "evidence_class": evidence or None,
        }
    if authority and authority not in {"BLOCKED", "NONE", ""}:
        # Controlled replay must never advertise Live/paper execution authority.
        if authority in {"LIVE", "AUTHORIZED", "BROKER_LIVE"}:
            return {
                "ok": False,
                "reason": "EXECUTION_AUTHORITY_NOT_BLOCKED",
                "execution_authority": authority,
            }
    return {
        "ok": True,
        "data_mode": data_mode or None,
        "execution_authority": authority or "BLOCKED",
        "evidence_class": evidence or "CONTROLLED_REPLAY",
        "controlled_replay": True,
    }


def run_controlled_replay(root: Path, argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    state_dir = controlled_replay_state_dir(root)

    if args.action == "scenarios":
        catalog = list_scenario_catalog()
        if args.json:
            _print_json({"scenarios": catalog, "evidence_class": "CONTROLLED_REPLAY"})
        else:
            print("CONTROLLED REPLAY scenarios (not Live market data):")
            for row in catalog:
                print(f"  - {row['scenario_id']}: {row['title']} — {row['description']}")
        return 0

    if args.action == "reset":
        result = reset_controlled_replay_state(root)
        if args.json:
            _print_json(result)
        else:
            if result.get("ok"):
                print(f"Controlled-replay state reset: {result['path']}")
            else:
                print(f"ERROR: reset refused ({result.get('reason')}): {result.get('path')}")
        return 0 if result.get("ok") else 1

    if args.action == "load":
        gate = verify_controlled_replay_context()
        if not gate.get("ok"):
            print(
                f"ERROR: refuse load — API is not CONTROLLED REPLAY "
                f"({gate.get('reason')}): {gate}"
            )
            return 1
        payload = load_scenarios()
        if args.json:
            _print_json(payload)
        else:
            if payload.get("ok"):
                print(
                    f"Loaded controlled-replay pack: "
                    f"{payload.get('summary_item_count')} opportunities visible "
                    f"(zero-qualifying scenario retained as empty-valid)."
                )
            else:
                print(f"ERROR: scenario load failed at {payload.get('stage')}: {payload.get('payload')}")
        return 0 if payload.get("ok") else 1

    controller = _controller(root)

    if args.action == "stop":
        return controller.stop()

    if args.action == "status":
        code = controller.status()
        print(f"controlled_replay_state_dir={state_dir}")
        print("evidence_class=CONTROLLED_REPLAY")
        print("live_authority=BLOCKED")
        gate = verify_controlled_replay_context()
        print(f"context_gate_ok={bool(gate.get('ok'))} reason={gate.get('reason') or 'OK'}")
        return code if gate.get("ok") else 1

    if args.action == "start":
        # Always stop first so we never attach to a healthy non-CR stack that
        # already owns shared ports (launcher idempotency is profile-blind).
        controller.stop()
        reset_result = reset_controlled_replay_state(root)
        if not reset_result.get("ok"):
            print(
                f"ERROR: controlled-replay reset refused "
                f"({reset_result.get('reason')}): {reset_result.get('path')}"
            )
            return 1
        state_dir.mkdir(parents=True, exist_ok=True)
        code = controller.start(open_browser=False)
        if code != 0:
            return code
        gate = verify_controlled_replay_context()
        if not gate.get("ok"):
            print(
                f"ERROR: stack is up but not CONTROLLED REPLAY "
                f"({gate.get('reason')}) — refusing scenario load. "
                f"Stop foreign processes on :8766/:5173 and retry."
            )
            if args.json:
                _print_json({"ok": False, "gate": gate, "state_dir": str(state_dir)})
            return 1
        load_payload: dict | None = None
        if not args.skip_load:
            load_payload = load_scenarios()
            if not load_payload.get("ok"):
                print(
                    f"ERROR: scenario load failed at "
                    f"{load_payload.get('stage')}: {load_payload.get('payload')}"
                )
                if args.json:
                    _print_json(
                        {
                            "ok": False,
                            "gate": gate,
                            "load": load_payload,
                            "state_dir": str(state_dir),
                        }
                    )
                return 1
        operator_url = UI_URL.rstrip("/") + CONTROLLED_REPLAY_OPERATOR_URL_PATH
        print("CONTROLLED REPLAY ready (NOT LIVE MARKET DATA).")
        print(f"Operator UI: {operator_url}")
        print(f"API:         {API_URL}")
        print(f"State dir:   {state_dir}")
        print("execution_authority=BLOCKED · evidence_class=CONTROLLED_REPLAY")
        if load_payload and load_payload.get("ok"):
            print(
                f"Scenarios loaded; summary items={load_payload.get('summary_item_count')}"
            )
        if args.open_browser:
            controller.system.open_browser(operator_url)
        if args.json:
            _print_json(
                {
                    "ok": True,
                    "operator_url": operator_url,
                    "api_url": API_URL,
                    "state_dir": str(state_dir),
                    "evidence_class": "CONTROLLED_REPLAY",
                    "gate": gate,
                    "load": load_payload,
                }
            )
        return 0

    print(f"unknown controlled-replay action: {args.action}", file=sys.stderr)
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    return run_controlled_replay(root, argv)


if __name__ == "__main__":
    raise SystemExit(main())
