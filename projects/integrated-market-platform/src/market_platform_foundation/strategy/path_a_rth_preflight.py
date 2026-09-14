"""Monday OpenD Path A / G7 / ForecastV1 preflight — software only.

Never runs a MATCHED hop, never mints PRODUCTION JSON, never starts Live.
Reports aggregate disposition: READY | BLOCKED | STALE | MISSING | MARKET_CLOSED.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..intelligence.opportunity.freshness import (
    CLOCK_UTC_NS,
    DEFAULT_STALE_AFTER_NS,
    OpportunityFreshnessPolicy,
)
from ..intelligence.paper_forward_bridge.session_policy import (
    CALENDAR_US_EQUITY_RTH,
    is_within_us_equity_rth,
)
from ..local_state.paths import REPO_ROOT, persistence_enabled
from ..market_data.live_config import (
    live_internal_simulation_enabled,
    live_observational_enabled,
    moomoo_host,
    moomoo_live_enabled,
    moomoo_port,
    probe_report_path,
    probe_staleness_seconds,
)
from ..providers.adapters.moomoo_opend_equity_quote import MOOMOO_OPEND_PROVIDER_ID
from ..providers.adapters.yahoo_delayed_equity_quote import YAHOO_PROVIDER_ID
from ..providers.equity_quote_discovery import discover_equity_quote_stack
from ..providers.equity_quote_selection import opend_readiness

_PREFLIGHT_DISPOSITIONS = frozenset(
    {"READY", "BLOCKED", "STALE", "MISSING", "MARKET_CLOSED"}
)
_PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_SCHEMA_VERSION = "1.0.0"
_ARTIFACT_KIND = "path_a_rth_preflight"

G7_FRESHNESS_AXES = (
    "status",
    "policy",
    "reason_code",
    "source",
    "actionable",
    "clock",
    "timeliness",
    "entitlement",
)


@dataclass(frozen=True, slots=True)
class PathARthPreflightOptions:
    symbol: str = "AAPL"
    forecast_path: str | None = None
    contributor_path: str | None = None
    calibration_path: str | None = None
    preregistration_path: str | None = None
    probe_local_opend: bool = True
    now_ns: int | None = None


def _now_ns(explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    return time.time_ns()


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in _PLACEHOLDERS


def _live_gates_on(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = environ if environ is not None else os.environ
    blockers: list[str] = []
    if env.get("IMP_LIVE_OBSERVATIONAL", "").strip() == "1":
        blockers.append("IMP_LIVE_OBSERVATIONAL")
    if env.get("IMP_MOOMOO_LIVE", "").strip() == "1":
        blockers.append("IMP_MOOMOO_LIVE")
    if env.get("IMP_LIVE_INTERNAL_SIMULATION", "").strip() == "1":
        blockers.append("IMP_LIVE_INTERNAL_SIMULATION")
    if env.get("IMP_PAPER_EXECUTION", "").strip().lower() in {"1", "true", "yes"}:
        blockers.append("IMP_PAPER_EXECUTION")
    if env.get("IMP_FINVIZ_LIVE", "").strip().lower() in {"1", "true", "yes"}:
        blockers.append("IMP_FINVIZ_LIVE")
    return tuple(blockers)


def _invalid_moomoo_config_keys(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Env keys present but unusable (placeholder or bad port)."""

    env = environ if environ is not None else os.environ
    bad: list[str] = []
    host_raw = env.get("IMP_MOOMOO_HOST")
    if host_raw is not None and not _present(host_raw):
        bad.append("IMP_MOOMOO_HOST")
    port_raw = env.get("IMP_MOOMOO_PORT")
    if port_raw is not None:
        if not _present(port_raw):
            bad.append("IMP_MOOMOO_PORT")
        else:
            try:
                int(port_raw.strip())
            except ValueError:
                bad.append("IMP_MOOMOO_PORT")
    return tuple(bad)


def _probe_loopback(host: str, port: int, *, timeout: float = 0.35) -> bool:
    if host not in _LOOPBACK_HOSTS:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _moomoo_probe_report_stale(*, now_ns: int) -> tuple[bool, dict[str, Any]]:
    path = probe_report_path()
    body: dict[str, Any] = {"path": str(path), "present": path.is_file()}
    if not path.is_file():
        body["status"] = "ABSENT"
        return False, body
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        body["status"] = "UNREADABLE"
        body["error"] = type(exc).__name__
        return True, body
    observed_raw = payload.get("observed_at_ns") or payload.get("generated_at_ns")
    try:
        observed_ns = int(observed_raw) if observed_raw is not None else None
    except (TypeError, ValueError):
        observed_ns = None
    body["observed_at_ns"] = observed_ns
    limit_sec = probe_staleness_seconds()
    body["staleness_limit_sec"] = limit_sec
    if observed_ns is None:
        body["status"] = "STALE_NO_TIMESTAMP"
        return True, body
    age_sec = max(0, (now_ns - observed_ns) / 1_000_000_000)
    body["age_sec"] = age_sec
    stale = age_sec > limit_sec
    body["status"] = "STALE" if stale else "FRESH"
    return stale, body


def _committed_production_forecast_paths() -> tuple[str, ...]:
    """Lawful operator PRODUCTION ForecastV1 JSON checked into the repo (usually none)."""

    roots = (REPO_ROOT / "artifacts", REPO_ROOT / "evidence")
    hits: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            if "fixture" in path.parts or "test" in path.name.casefold():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            stage = payload.get("forecast_stage") or payload.get("stage")
            role = payload.get("contributor_role")
            if stage in {"PRODUCTION_RAW", "PRODUCTION"} or role == "PRODUCTION":
                hits.append(str(path.relative_to(REPO_ROOT)))
    return tuple(sorted(set(hits)))


def _operator_path_status(label: str, raw: str | None) -> dict[str, Any]:
    if raw is None or not str(raw).strip():
        return {"label": label, "configured": False, "exists": None, "status": "NOT_REQUESTED"}
    path = Path(raw).expanduser()
    exists = path.exists()
    return {
        "label": label,
        "configured": True,
        "exists": exists,
        "path": str(path),
        "status": "PRESENT" if exists else "MISSING",
    }


def hop_cli_refuses_live_mode() -> bool:
    """True when Path A hop CLI argparse excludes ``live``."""

    hop_cli = REPO_ROOT / "tools" / "path_a_prospective_run.py"
    try:
        text = hop_cli.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'choices=("paper", "demo")' in text and '"live"' not in text.split("choices=")[1].split(")")[0]


def _pip_importable(python: Path, runner: Callable[..., Any]) -> tuple[bool, str | None]:
    probe = runner(
        [str(python), "-c", "import pip"],
        check=False,
        capture_output=True,
        text=True,
    )
    ok = int(getattr(probe, "returncode", 1) or 0) == 0
    return ok, None if ok else "PIP_MISSING"


def _aggregate_disposition(
    *,
    rth_open: bool,
    blockers: Sequence[str],
    missing: Sequence[str],
    stale: bool,
) -> str:
    if blockers:
        return "BLOCKED"
    if missing:
        return "MISSING"
    if stale:
        return "STALE"
    if not rth_open:
        return "MARKET_CLOSED"
    return "READY"


def run_path_a_rth_preflight(
    *,
    options: PathARthPreflightOptions | None = None,
    python: Path | None = None,
    pip_runner: Callable[..., Any] | None = None,
    opend_diagnose: Callable[..., dict[str, Any]] | None = None,
    hop_interpreter: Callable[[], dict[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a secret-free Path A RTH preflight report."""

    opts = options or PathARthPreflightOptions()
    now = _now_ns(opts.now_ns)
    rth_open = is_within_us_equity_rth(now)
    blockers: list[str] = []
    missing: list[str] = []

    if python is None:
        try:
            from tools.environment import effective_python_executable

            python = Path(effective_python_executable(REPO_ROOT))
        except Exception:  # noqa: BLE001 — fail-closed preflight only
            python = Path(os.environ.get("IMP_PYTHON") or sys.executable)

    runner = pip_runner
    if runner is None:
        import subprocess

        runner = subprocess.run
    pip_ok, pip_reason = _pip_importable(python, runner)
    pip_check = {"ready": pip_ok, "reason_code": pip_reason, "python": str(python)}

    if opend_diagnose is None:
        from ..local_state.opend import diagnose_opend

        opend_diagnose = lambda **_: diagnose_opend(start=False)  # noqa: E731
    opend_report = opend_diagnose(start=False)
    host = moomoo_host()
    port = moomoo_port()
    loopback = host in _LOOPBACK_HOSTS
    reachable = (
        _probe_loopback(host, port)
        if opts.probe_local_opend and loopback
        else False
    )
    opend_loopback = {
        "host": host,
        "port": port,
        "loopback_only": loopback,
        "reachable": reachable,
        "diagnose_status": opend_report.get("status"),
        "ready_for_live_observational": bool(opend_report.get("ready_for_live_observational")),
    }
    if not loopback:
        blockers.append("OPEND_NON_LOOPBACK_BLOCKED")

    if hop_interpreter is None:
        from tools.moomoo.opend_hop_interpreter import diagnose_hop_interpreter

        hop_interpreter = diagnose_hop_interpreter
    hop = hop_interpreter()
    if hop.get("mixed_foreign_venv"):
        blockers.append("HOP_MIXED_FOREIGN_VENV")
    if not pip_ok and pip_reason:
        missing.append(pip_reason)
    if not hop.get("sklearn"):
        missing.append("HOP_SKLEARN_MISSING")
    if not hop.get("vendor_sdk"):
        missing.append("MOOMOO_SDK_MISSING")

    invalid_keys = _invalid_moomoo_config_keys(environ)
    if invalid_keys:
        missing.extend(f"CONFIG_KEY_INVALID:{key}" for key in invalid_keys)

    live_blockers = _live_gates_on(environ)
    blockers.extend(live_blockers)

    provider, discovery = discover_equity_quote_stack()
    yahoo_never_l1 = {
        "primary_provider_id": provider.provider_id,
        "overlay_provider_id": discovery.overlay_provider_id,
        "yahoo_is_primary": provider.provider_id == YAHOO_PROVIDER_ID,
        "yahoo_is_overlay_only": discovery.overlay_provider_id == YAHOO_PROVIDER_ID,
        "moomoo_is_primary": provider.provider_id == MOOMOO_OPEND_PROVIDER_ID,
        "ok": provider.provider_id == MOOMOO_OPEND_PROVIDER_ID
        and discovery.overlay_provider_id == YAHOO_PROVIDER_ID,
    }
    if not yahoo_never_l1["ok"]:
        blockers.append("YAHOO_HOP_L1_POLICY_VIOLATION")

    finviz_overlay = {
        "finviz_token_names_present": list(discovery.finviz_token_names_present),
        "classification": discovery.classification,
        "overlay_only": provider.provider_id != "finviz.elite",
    }

    policy = OpportunityFreshnessPolicy()
    g7_axes = {
        "policy_name": policy.name,
        "stale_after_ns": policy.stale_after_ns,
        "realtime_required": policy.realtime_required,
        "clock": CLOCK_UTC_NS,
        "default_stale_after_ns": DEFAULT_STALE_AFTER_NS,
        "report_axes": list(G7_FRESHNESS_AXES),
    }

    persist = {
        "persistence_enabled": persistence_enabled(),
        "default_off": not persistence_enabled(),
    }
    if persistence_enabled():
        blockers.append("PERSISTENCE_ENABLED")

    stale_probe, probe_body = _moomoo_probe_report_stale(now_ns=now)
    if not rth_open:
        stale_probe = False
    committed = _committed_production_forecast_paths()
    production = {
        "repository_committed_paths": list(committed),
        "repository_committed_present": bool(committed),
        "operator_forecast": _operator_path_status("forecast", opts.forecast_path),
        "operator_contributor": _operator_path_status("contributor", opts.contributor_path),
        "operator_calibration": _operator_path_status("calibration", opts.calibration_path),
        "operator_preregistration": _operator_path_status("preregistration", opts.preregistration_path),
    }
    for key in ("operator_forecast", "operator_contributor", "operator_calibration", "operator_preregistration"):
        row = production[key]
        if row.get("status") == "MISSING":
            missing.append(f"{row['label'].upper()}_PATH_MISSING")

    mode_live = {"hop_cli_refuses_live_mode": hop_cli_refuses_live_mode()}

    readiness = opend_readiness()
    disposition = _aggregate_disposition(
        rth_open=rth_open,
        blockers=tuple(dict.fromkeys(blockers)),
        missing=tuple(dict.fromkeys(missing)),
        stale=stale_probe,
    )

    reason_codes = list(dict.fromkeys([*blockers, *missing]))
    if stale_probe and rth_open:
        reason_codes.append("MOOMOO_PROBE_STALE")
    if not rth_open:
        reason_codes.append("US_EQUITY_RTH_CLOSED")

    return {
        "artifact_kind": _ARTIFACT_KIND,
        "schema_version": _SCHEMA_VERSION,
        "secrets_included": False,
        "symbol": opts.symbol,
        "calendar_scope": CALENDAR_US_EQUITY_RTH,
        "us_equity_rth_open": rth_open,
        "observed_at_ns": now,
        "disposition": disposition,
        "reason_codes": reason_codes,
        "checks": {
            "interpreter": {
                "python": str(python),
                "hop_interpreter": hop,
            },
            "pip": pip_check,
            "install_opend_fail_closed": {
                "pip_required_before_install": True,
                "pip_ready": pip_ok,
                "reason_code": pip_reason,
            },
            "opend_loopback": opend_loopback,
            "opend_readiness": {
                "host": readiness.host,
                "port": readiness.port,
                "loopback": readiness.loopback,
                "reachable": readiness.reachable,
            },
            "g7_freshness_axes": g7_axes,
            "yahoo_never_l1": yahoo_never_l1,
            "finviz_overlay_only": finviz_overlay,
            "mode_live_argparse": mode_live,
            "persist_default_off": persist,
            "forecast_production_json": production,
            "paper_vs_live_gates": {
                "live_gates_on": list(live_blockers),
                "live_observational_enabled": live_observational_enabled(),
                "moomoo_live_enabled": moomoo_live_enabled(),
                "live_internal_simulation_enabled": live_internal_simulation_enabled(),
            },
            "moomoo_capability_probe": probe_body,
            "discovery": {
                "provider_id": discovery.provider_id,
                "classification": discovery.classification,
                "reason_code": discovery.reason_code,
                "opend_reachable": discovery.opend_reachable,
            },
        },
    }


def build_path_a_rth_preflight_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Software-only preflight for Monday OpenD Path A / G7 / ForecastV1. "
            "Never runs a hop or mints PRODUCTION JSON."
        ),
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--forecast-path", default=None)
    parser.add_argument("--contributor-path", default=None)
    parser.add_argument("--calibration-path", default=None)
    parser.add_argument("--preregistration-path", default=None)
    parser.add_argument(
        "--no-probe-opend",
        action="store_true",
        help="Skip loopback TCP probe (still reports configured host/port).",
    )
    parser.add_argument("--now-ns", type=int, default=None, help="Test-only wall clock override.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_path_a_rth_preflight_parser().parse_args(argv)
    report = run_path_a_rth_preflight(
        options=PathARthPreflightOptions(
            symbol=args.symbol,
            forecast_path=args.forecast_path,
            contributor_path=args.contributor_path,
            calibration_path=args.calibration_path,
            preregistration_path=args.preregistration_path,
            probe_local_opend=not args.no_probe_opend,
            now_ns=args.now_ns,
        ),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    disposition = report["disposition"]
    if disposition == "READY":
        return 0
    if disposition == "MARKET_CLOSED":
        return 0
    return 1


__all__ = [
    "G7_FRESHNESS_AXES",
    "PathARthPreflightOptions",
    "build_path_a_rth_preflight_parser",
    "hop_cli_refuses_live_mode",
    "main",
    "run_path_a_rth_preflight",
]
