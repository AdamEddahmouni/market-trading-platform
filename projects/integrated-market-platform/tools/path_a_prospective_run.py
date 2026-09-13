"""One-shot Paper/Demo Path A prospective runner. Never submits Live orders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.strategy.path_a_prospective import (
    PathAPersistContext,
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)
from market_platform_foundation.providers.equity_quote_discovery import discover_equity_quote_stack


def _local_forward_test_service():
    """Build a ForwardTestService bound to durable local state, or None.

    Only meaningful when the existing IMP_STATE_DIR / IMP_PERSIST_STATE
    persist-on switch is already set; callers must check
    ``persistence_enabled()`` first. Fails closed (returns ``None``) rather
    than raising if local state cannot be opened, so a persist-context
    request never crashes the honesty hop.
    """

    from market_platform_foundation.intelligence.paper_forward_bridge import (
        ForwardTestService,
        create_forward_test_repository,
    )
    from market_platform_foundation.local_state.startup import open_local_state

    local = open_local_state()
    if local is None:
        return None
    return ForwardTestService(create_forward_test_repository(connection=local.connection))


def build_cli_persist_context(args: argparse.Namespace) -> PathAPersistContext | None:
    """Optional PD-09 v6 persist wiring for the Paper/Demo CLI hop.

    Stays ``None`` (persist unreachable, same as before) unless the operator
    supplies every identifier for an *existing* governed Forward-Test
    session (created out-of-band, e.g. via ``tools/ftep_session_start.py``)
    AND the existing persist-on switch (``IMP_STATE_DIR`` /
    ``IMP_PERSIST_STATE=1``) is already set. This never creates, freezes, or
    activates a campaign, and never runs for Live -- ``--mode`` only accepts
    ``paper``/``demo``. Demo stays ``INTENTIONAL_EPHEMERAL`` regardless
    (``PathAProspectiveComposer`` only writes through for Paper).
    """

    if args.mode not in ("paper", "demo"):
        return None
    if not (
        args.persist_account_id
        and args.persist_session_id
        and args.persist_strategy_id
        and args.persist_strategy_version
    ):
        return None
    from market_platform_foundation.local_state.paths import persistence_enabled

    if not persistence_enabled():
        return None
    service = _local_forward_test_service()
    if service is None:
        return None
    return PathAPersistContext(
        service=service,
        account_id=args.persist_account_id,
        session_id=args.persist_session_id,
        strategy_id=args.persist_strategy_id,
        strategy_version=args.persist_strategy_version,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot Path A prospective hop (Paper/Demo).")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--mode", default="paper", choices=("paper", "demo"))
    parser.add_argument(
        "--persist-account-id",
        default=None,
        help=(
            "Existing Paper Forward-Test account id for optional PD-09 v6 "
            "write-through. Ignored unless IMP_STATE_DIR/IMP_PERSIST_STATE "
            "is already set and every --persist-* value is supplied."
        ),
    )
    parser.add_argument(
        "--persist-session-id",
        default=None,
        help=(
            "Existing governed Forward-Test session id (e.g. created via "
            "tools/ftep_session_start.py). Required to reach "
            "ForwardTestService.create_decision; no session is created here."
        ),
    )
    parser.add_argument("--persist-strategy-id", default=None)
    parser.add_argument("--persist-strategy-version", default=None)
    args = parser.parse_args(argv)
    provider, discovery = discover_equity_quote_stack()
    invoke = build_paper_demo_path_a_invoke(args.symbol, mode=args.mode)
    persist_context = build_cli_persist_context(args)
    result = PathAProspectiveComposer(
        quote_provider=provider,
        path_a_caller=invoke.caller,
        persist=persist_context,
    ).run(args.symbol, mode=args.mode, scan_request=invoke.scan_request)
    payload = {
        "discovery": {
            "classification": discovery.classification,
            "config_names_present": list(discovery.config_names_present),
            "finviz_token_names_present": list(discovery.finviz_token_names_present),
            "opend_reachable": discovery.opend_reachable,
            "provider_id": discovery.provider_id,
            "reason_code": discovery.reason_code,
            "timeliness": discovery.timeliness,
        },
        "persist_context_injected": persist_context is not None,
        "result": result.to_dict(),
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.status not in {"LIVE_FORBIDDEN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
