"""Operator CLI for CONTROLLED REPLAY golden path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

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
        return code

    if args.action == "start":
        # Deterministic demo: wipe only the namespaced controlled-replay root
        # before spawn so re-ingest cannot hit EVENT_PERSIST_CONFLICT on the
        # required ingress.store consumer. Never touches empirical / RTH state.
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
        load_payload: dict | None = None
        if not args.skip_load:
            load_payload = load_scenarios()
            if not load_payload.get("ok"):
                print(
                    f"WARNING: stack is up but scenario load failed at "
                    f"{load_payload.get('stage')}: {load_payload.get('payload')}"
                )
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
                    "ok": code == 0,
                    "operator_url": operator_url,
                    "api_url": API_URL,
                    "state_dir": str(state_dir),
                    "evidence_class": "CONTROLLED_REPLAY",
                    "load": load_payload,
                }
            )
        return code

    print(f"unknown controlled-replay action: {args.action}", file=sys.stderr)
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    return run_controlled_replay(root, argv)


if __name__ == "__main__":
    raise SystemExit(main())
