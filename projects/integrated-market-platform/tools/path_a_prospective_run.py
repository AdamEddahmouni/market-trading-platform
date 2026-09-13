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
)
from market_platform_foundation.providers.equity_quote_discovery import discover_equity_quote_stack
from market_platform_foundation.providers.equity_quote_selection import primary_equity_quote_provider


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
    parser.add_argument(
        "--preregistration-path",
        default=None,
        help=(
            "Previously persisted Phase-6 preregistration JSON file or "
            "directory. Create is a separate operator step that stamps "
            "registered_at before any hop; this hop only loads. Load "
            "requires identity match and registered_at before quote "
            "event_time_ns. Paper/Demo only."
        ),
    )
    parser.add_argument(
        "--forecast-path",
        default=None,
        help=(
            "Previously persisted PRODUCTION forecast JSON file or directory. "
            "This hop only loads; it does not mint a probability. Load "
            "requires identity, PIT, champion, horizon, account, and mode "
            "to match Opportunity Engine hop policy; otherwise "
            "FORECAST_UNAVAILABLE. Paper/Demo only."
        ),
    )
    args = parser.parse_args(argv)
    _, discovery = discover_equity_quote_stack()
    provider = primary_equity_quote_provider()
    persist_context = build_cli_persist_context(args)
    # Composer fetches once, then auto-builds the invoke with that quote so
    # the catalog is not stuck on FCAST_NO_QUOTE_OBSERVATION. G7 remains
    # freshness authority over the same admitted event.
    result = PathAProspectiveComposer(
        quote_provider=provider,
        persist=persist_context,
        preregistration_path=args.preregistration_path,
        forecast_path=args.forecast_path,
    ).run(args.symbol, mode=args.mode)
    payload = {
        "discovery": {
            "classification": discovery.classification,
            "config_names_present": list(discovery.config_names_present),
            "finviz_token_names_present": list(discovery.finviz_token_names_present),
            "opend_reachable": discovery.opend_reachable,
            "overlay_provider_id": discovery.overlay_provider_id,
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
