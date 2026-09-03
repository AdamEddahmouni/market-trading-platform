"""One-command launcher: ``python -m apps.research_screener``."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

from . import APP_TITLE, DISCLAIMER
from .deployment import DeploymentMode, RuntimeConfig, deployment_mode, resolve_runtime
from .credentials import default_private_path
from .config import resolve_application_config
from .paths import FrozenLayout
from .live_providers import configure_application
from .providers import provider_health
from .server import DEFAULT_PORT, HOST, build_server, default_export_dir, find_free_port


def _bootstrap_live_data(session, *, sec_user_agent: str | None = None) -> None:
    """Bootstrap live data flow immediately on boot, then start auto-refresh.

    Runs in a daemon thread so the HTTP server is already serving before the
    first provider probe.  A bootstrap failure **never** prevents the server
    from starting; auto-refresh is still started so the background loop retries
    continuously and data flows as soon as a provider becomes available.

    Order matters: one-shot discovery → bounded refresh → start_auto_refresh.
    Never call refresh_all after the loop has started (avoids concurrent
    _cursor / pacing burn). Seed last_scan after bootstrap discovery so the
    loop does not immediately rediscover.
    """
    discovery_ok = False
    try:
        result = session.refresh_discovery()
        discovered = result.get("discovered", 0)
        ibkr = result.get("ibkr", 0)
        finviz = result.get("finviz", 0)
        discovery_ok = True
        print(
            f"  Bootstrap: discovered {discovered} candidate(s) "
            f"(IBKR scanner: {ibkr}, Finviz screener: {finviz})"
        )
    except Exception as exc:  # noqa: BLE001 - bootstrap must never block the server
        print(
            f"  Bootstrap: discovery failed ({type(exc).__name__}: {exc}) "
            "- auto-refresh will retry"
        )

    if discovery_ok and hasattr(session, "note_discovery_scan"):
        session.note_discovery_scan()

    # Bounded warm cycles (pacing-aware batch sizes). Must complete before
    # start_auto_refresh so refresh_all never overlaps the loop.
    try:
        total = len(session.states)
        if total > 0:
            warm_cycles = int(os.environ.get("BOOTSTRAP_WARM_CYCLES", "4"))
            refreshed = 0
            for _ in range(max(1, warm_cycles)):
                result = session.refresh_all()
                refreshed += int(result.get("refreshed", 0))
            print(
                f"  Bootstrap: warmed {refreshed} symbol refresh(es) across "
                f"{warm_cycles} cycle(s) ({total} on screen); "
                "auto-refresh continues with squeeze priority"
            )
        else:
            print("  Bootstrap: no candidates yet - auto-refresh will discover them")
    except Exception as exc:  # noqa: BLE001
        print(
            f"  Bootstrap: initial refresh failed ({type(exc).__name__}: {exc}) "
            "- auto-refresh will retry"
        )

    try:
        session.start_auto_refresh()
        print("  Bootstrap: auto-refresh started - data flowing continuously")
    except Exception as exc:  # noqa: BLE001
        print(
            f"  Bootstrap: auto-refresh start failed ({type(exc).__name__}: {exc})"
        )

    try:
        from .collector_session import start_collectors_for_session

        start_collectors_for_session(session, sec_user_agent=sec_user_agent)
        print("  Bootstrap: evidence collectors started (gap-driven scheduler)")
    except Exception as exc:  # noqa: BLE001
        print(
            f"  Bootstrap: collectors start failed ({type(exc).__name__}: {exc})"
        )


def _preflight(runtime_config: RuntimeConfig) -> tuple[bool, list[str]]:
    """Report what is available before the browser opens. Never blocks startup."""
    lines: list[str] = []
    if runtime_config.use_frozen_demo:
        from .frozen_demo import load_frozen_demo

        frozen_ok = bool(load_frozen_demo()["rows"])
        source_label = "sanitized frozen demo"
    else:
        layout = FrozenLayout()
        frozen_ok = layout.available
        source_label = "private canonical freeze"
    lines.append(
        f"  Frozen Research artifacts : {'FOUND' if frozen_ok else 'NOT FOUND'}"
        f"  ({source_label})"
    )
    if runtime_config.enable_local_ibkr:
        for entry in provider_health(frozen_available=frozen_ok):
            lines.append(f"  {entry['name']:<26}: {entry['state']}")
    else:
        lines.extend([
            "  IB Gateway                : UNAVAILABLE (cloud/frozen mode; not probed)",
            "  Market Data               : UNAVAILABLE",
            "  Historical Bars           : UNAVAILABLE",
        ])
    return frozen_ok, lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apps.research_screener",
        description=f"{APP_TITLE} — {DISCLAIMER}",
    )
    parser.add_argument("--port", type=int, default=None, help="preferred port")
    parser.add_argument(
        "--mode",
        choices=[str(mode) for mode in DeploymentMode],
        default=None,
        help="deployment mode (default: SQUEEZE_APP_MODE or LOCAL_FULL)",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument(
        "--export-dir", type=Path, default=None, help="where research snapshots are written"
    )
    parser.add_argument("--verbose", action="store_true", help="log every HTTP request")
    parser.add_argument(
        "--provider-config", type=Path, default=None,
        dest="provider_config",
        help="explicit private provider configuration path (production opt-in)",
    )
    parser.add_argument(
        "--private-path", type=Path, default=None,
        dest="provider_config",
        help="alias for --provider-config",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="explicit non-secret application configuration file",
    )
    parser.add_argument(
        "--check", action="store_true", help="print availability and exit without serving"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    private_file = args.provider_config or default_private_path()

    # Preload private provider credentials into os.environ so provider init
    # code (which reads from env vars) sees the keys before the config
    # pipeline processes them. Only preload in LOCAL_FULL mode.
    selected_mode = deployment_mode(args.mode or os.environ.get("SQUEEZE_APP_MODE"))
    if (
        private_file
        and private_file.is_file()
        and selected_mode is DeploymentMode.LOCAL_FULL
    ):
        from .config import load_private_env
        load_private_env(private_file, verbose=True)

    application_config = resolve_application_config(
        cli={
            "SQUEEZE_APP_MODE": args.mode,
            "PORT": str(args.port) if args.port is not None else None,
        },
        config_file=args.config,
        private_file=private_file,
    )
    runtime_config = RuntimeConfig(
        mode=application_config.deployment.mode,
        host=application_config.deployment.host,
        port=application_config.deployment.port,
        load_private=application_config.deployment.mode is DeploymentMode.LOCAL_FULL,
        enable_local_ibkr=application_config.providers.ibkr.enabled,
        use_frozen_demo=application_config.deployment.mode is not DeploymentMode.LOCAL_FULL,
    )
    runtime = configure_application(application_config)
    from .sentiment_live import get_sentiment_analyzer

    sa = get_sentiment_analyzer()
    if application_config.providers.sentiment.enabled:
        if sa.model_loaded:
            print(f"  FinBERT sentiment          : LOADED ({sa.model_id})")
        elif sa.enabled:
            err = sa.load_error or "model not loaded"
            print(f"  FinBERT sentiment          : NOT READY ({err})")
        else:
            print("  FinBERT sentiment          : DISABLED")
    if runtime_config.enable_local_ibkr:
        from .provider_session import LiveProvider, ibkr_endpoint_from_config
        from .session_state import ScreenerSession, reset_session

        reset_session(ScreenerSession(
            provider=LiveProvider(
                ibkr_endpoint=ibkr_endpoint_from_config(
                    application_config.providers.ibkr,
                ),
            ),
            external_providers=runtime,
        ))
    else:
        from .provider_session import CloudUnavailableProvider
        from .session_state import ScreenerSession, reset_session

        reset_session(ScreenerSession(
            provider=CloudUnavailableProvider(), external_providers=runtime,
        ))

    print(f"\n{APP_TITLE}")
    print(DISCLAIMER)
    print("\nAvailability:")
    frozen_ok, lines = _preflight(runtime_config)
    for line in lines:
        print(line)

    if not frozen_ok:
        print(
            "\n  Frozen Research mode is unavailable on this machine. The application "
            "will still start; it will report the artifacts as missing rather than "
            "showing anything in their place."
        )
    if args.check:
        print(
            "\n  For a detailed credential and provider report, run:"
            "\n"
            "    python -m apps.research_screener.config doctor"
        )
        return 0

    port = (
        find_free_port(runtime_config.port)
        if runtime_config.mode is DeploymentMode.LOCAL_FULL
        else runtime_config.port
    )
    export_dir = args.export_dir or default_export_dir()
    server = build_server(
        port,
        export_dir=export_dir,
        verbose=args.verbose,
        host=runtime_config.host,
        deployment_mode=runtime_config.mode,
    )
    display_host = HOST if runtime_config.host == "0.0.0.0" else runtime_config.host
    url = f"http://{display_host}:{port}/"

    print(f"\n  Exports        : {export_dir}")
    print(f"\n  Screener ready : {url}")
    print("  Press Ctrl+C to stop.\n")

    if not args.no_browser and runtime_config.mode is DeploymentMode.LOCAL_FULL:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    # ── Auto-bootstrap live data flow ─────────────────────────────────
    # Runs in a daemon thread so the server is already serving requests
    # before the first provider probe. This makes the dashboard show live
    # data on the very first page load instead of an empty screen, and
    # starts the auto-refresh loop so providers keep feeding data through
    # without any manual interaction — essential for demonstrations.
    if not args.check:
        from . import session_state as _ss
        _session = _ss.get_session()
        _boot = threading.Thread(
            target=_bootstrap_live_data,
            args=(_session,),
            kwargs={"sec_user_agent": application_config.providers.sec.user_agent},
            name="screener-bootstrap",
            daemon=True,
        )
        _boot.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
