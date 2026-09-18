"""Item 9 next-RTH prospective collection preflight — read-only.

Never starts ``prospective --poll``, never writes receipts, never fits calibration.
Validates calendar, OpenD reachability, frozen collector authority, output path,
and duplicate collector processes before an operator-run Mode B session.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ...git_ref import main_working_tree, read_git_head
from ...intelligence.paper_forward_bridge.session_policy import (
    CALENDAR_US_EQUITY_RTH,
    is_within_us_equity_rth,
)
from ...providers.equity_quote_selection import opend_readiness
from .bar_ohlcv_prospective_proof import (
    DEFAULT_RECEIPT_DIR,
    RECEIPT_CONTRACT_VERSION,
    imp_package_root,
    item9_prospective_readiness,
    resolve_runtime_git_sha,
)
from .dual_corpus.discovery import validate_item9_prospective_receipt_output_dir

_ARTIFACT_KIND = "item9_next_rth_preflight"
_SCHEMA_VERSION = "1.0.0"

FROZEN_COLLECTOR_AUTHORITY_SHA = "fed2d9f7e183aecfcac61a7664df69aafc12ea25"
FROZEN_COLLECTOR_WORKTREE_REL = Path(".imp-actual-01-phase-d") / "projects" / "integrated-market-platform"

DEFAULT_INSTRUMENT_ID = "AAPL"
US_EQUITY_SESSION_TZ = "America/New_York"

POLL_INTERVAL_S_DEFAULT = 5.0
POLL_TIMEOUT_S_DEFAULT = 3900.0

DISPOSITION_READY_TO_COLLECT = "READY_TO_COLLECT"
DISPOSITION_NOT_RTH = "NOT_RTH"
DISPOSITION_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
DISPOSITION_WRONG_RUNTIME = "WRONG_RUNTIME"
DISPOSITION_ACTIVE_COLLECTOR_EXISTS = "ACTIVE_COLLECTOR_EXISTS"
DISPOSITION_OUTPUT_PATH_INVALID = "OUTPUT_PATH_INVALID"

_PREFLIGHT_DISPOSITIONS = frozenset(
    {
        DISPOSITION_READY_TO_COLLECT,
        DISPOSITION_NOT_RTH,
        DISPOSITION_PROVIDER_UNAVAILABLE,
        DISPOSITION_WRONG_RUNTIME,
        DISPOSITION_ACTIVE_COLLECTOR_EXISTS,
        DISPOSITION_OUTPUT_PATH_INVALID,
    }
)

_COLLECTOR_CMD_MARKERS = ("opend_bar_1m_prospective_proof.py", "prospective")


@dataclass(frozen=True, slots=True)
class Item9NextRthPreflightOptions:
    instrument_id: str = DEFAULT_INSTRUMENT_ID
    receipt_dir: Path | None = None
    now_ns: int | None = None
    frozen_collector_authority_sha: str = FROZEN_COLLECTOR_AUTHORITY_SHA


def _now_ns(explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    return time.time_ns()


def monorepo_root_from_imp(imp_root: Path) -> Path:
    """Git primary checkout root (monorepo) for sibling worktrees like ``.imp-actual-01-phase-d``."""

    main = main_working_tree(start=imp_root)
    if main is not None:
        return main
    if imp_root.name == "integrated-market-platform" and imp_root.parent.name == "projects":
        return imp_root.parent.parent
    return imp_root


def resolve_frozen_collector_imp_root(imp_root: Path) -> Path | None:
    candidate = monorepo_root_from_imp(imp_root) / FROZEN_COLLECTOR_WORKTREE_REL
    try:
        if (candidate / "phase0-dependency-lock.json").is_file():
            return candidate.resolve()
    except OSError:
        return None
    return None


def _sha_matches(sha: str, authority: str) -> bool:
    left = (sha or "").strip().lower()
    right = authority.strip().lower()
    if not left or left == "unknown":
        return False
    return left == right or left.startswith(right[:12])


def _us_equity_session_date_et(now_ns: int) -> str:
    from zoneinfo import ZoneInfo

    dt = datetime.fromtimestamp(now_ns / 1_000_000_000, tz=ZoneInfo(US_EQUITY_SESSION_TZ))
    return dt.date().isoformat()


def _receipt_dir_writable(receipt_dir: Path) -> tuple[bool, str | None]:
    gate = validate_item9_prospective_receipt_output_dir(receipt_dir)
    if not gate.get("ok"):
        return False, str(gate.get("reason_code"))
    try:
        receipt_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, type(exc).__name__
    probe = receipt_dir / ".item9-preflight-write-probe"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return False, type(exc).__name__
    return True, None


def _disk_sane(path: Path, *, min_free_mb: int = 64) -> tuple[bool, dict[str, Any]]:
    try:
        usage = shutil.disk_usage(path if path.exists() else path.parent)
    except OSError as exc:
        return False, {"error": type(exc).__name__}
    free_mb = usage.free // (1024 * 1024)
    return free_mb >= min_free_mb, {"free_mb": free_mb, "min_free_mb": min_free_mb}


def _iter_process_command_lines() -> tuple[str, ...]:
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    "name='python.exe' or name='python3.exe'",
                    "get",
                    "CommandLine",
                ],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ()
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return tuple(line for line in lines if line.lower() != "commandline")
    try:
        completed = subprocess.run(
            ["ps", "-eo", "args="],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if completed.returncode != 0:
        return ()
    return tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())


def detect_active_item9_prospective_collector(
    *,
    command_lines: Sequence[str] | None = None,
) -> tuple[bool, list[str]]:
    """True when another Item 9 Mode B prospective collector appears to be running."""

    lines = list(command_lines) if command_lines is not None else list(_iter_process_command_lines())
    matches: list[str] = []
    for line in lines:
        lowered = line.lower()
        if _COLLECTOR_CMD_MARKERS[0].lower() not in lowered:
            continue
        if _COLLECTOR_CMD_MARKERS[1] not in lowered:
            continue
        if "preflight" in lowered or "readiness" in lowered:
            continue
        matches.append(line)
    return bool(matches), matches


def _governed_prospective_invocation(
    *,
    frozen_imp_root: Path | None,
    instrument_id: str,
    receipt_dir: Path,
) -> list[str]:
    root = frozen_imp_root or imp_package_root()
    receipt_out = receipt_dir
    if frozen_imp_root is not None:
        try:
            receipt_dir.relative_to(frozen_imp_root)
        except ValueError:
            try:
                rel = receipt_dir.relative_to(imp_package_root())
                receipt_out = frozen_imp_root / rel
            except ValueError:
                receipt_out = frozen_imp_root / DEFAULT_RECEIPT_DIR
    try:
        rel_receipt = receipt_out.relative_to(root)
    except ValueError:
        rel_receipt = receipt_out
    return [
        f"cd {root}",
        (
            "python tools/moomoo/opend_bar_1m_prospective_proof.py prospective "
            f"--instrument-id {instrument_id} --poll "
            f"--poll-interval-s {POLL_INTERVAL_S_DEFAULT} "
            f"--timeout-s {POLL_TIMEOUT_S_DEFAULT} "
            f"--receipt-out {rel_receipt.as_posix()}"
        ),
    ]


def _post_run_corpus_status_command(receipt_dir: Path) -> str:
    try:
        rel = receipt_dir.relative_to(imp_package_root())
        dir_arg = rel.as_posix()
    except ValueError:
        dir_arg = str(receipt_dir)
    return f"python tools/item9_corpus_status.py corpus-status --receipt-dir {dir_arg}"


def run_item9_next_rth_preflight(
    imp_root: Path,
    *,
    options: Item9NextRthPreflightOptions | None = None,
    env: Mapping[str, str] | None = None,
    active_collector_probe: Callable[[], tuple[bool, list[str]]] | None = None,
) -> dict[str, Any]:
    opts = options or Item9NextRthPreflightOptions()
    mapping = env if env is not None else os.environ
    now = _now_ns(opts.now_ns)
    imp_root = imp_root.resolve()

    receipt_dir = opts.receipt_dir
    if receipt_dir is None:
        receipt_dir = imp_root / DEFAULT_RECEIPT_DIR
    elif not receipt_dir.is_absolute():
        receipt_dir = imp_root / receipt_dir

    runtime_sha = resolve_runtime_git_sha(start=imp_root)
    frozen_imp = resolve_frozen_collector_imp_root(imp_root)
    frozen_sha = read_git_head(start=frozen_imp) if frozen_imp is not None else None
    frozen_available = frozen_imp is not None and _sha_matches(frozen_sha or "", opts.frozen_collector_authority_sha)
    runtime_matches_frozen = _sha_matches(runtime_sha, opts.frozen_collector_authority_sha)

    readiness = item9_prospective_readiness(now_ns=now)
    rth_active = bool(readiness.get("rth_active"))
    session_date = _us_equity_session_date_et(now)

    opend = opend_readiness()
    provider_ok = opend.loopback and opend.reachable

    writable, write_reason = _receipt_dir_writable(receipt_dir)
    disk_ok, disk_report = _disk_sane(receipt_dir)

    probe = active_collector_probe or (lambda: detect_active_item9_prospective_collector())
    active_collector, active_matches = probe()

    blockers: list[str] = []
    reason_codes: list[str] = []
    operator_checks: list[str] = [
        "Confirm US/Eastern session date matches operator intent before starting --poll.",
        "Use frozen collector authority worktree when current runtime SHA differs from governed receipt semantics.",
        "Re-run readiness off-hours only for software checks; do not treat as empirical proof.",
        "After a successful prospective receipt, run corpus-status (read-only); never auto-fit calibration.",
    ]

    if not writable:
        blockers.append(DISPOSITION_OUTPUT_PATH_INVALID)
        reason_codes.append(write_reason or "receipt_dir_not_writable")
    if not disk_ok:
        blockers.append(DISPOSITION_OUTPUT_PATH_INVALID)
        reason_codes.append("disk_space_low")

    if not runtime_matches_frozen:
        blockers.append(DISPOSITION_WRONG_RUNTIME)
        if not frozen_available:
            reason_codes.append("frozen_collector_worktree_missing_or_wrong_sha")
        else:
            reason_codes.append("current_runtime_sha_not_frozen_authority")

    if active_collector:
        blockers.append(DISPOSITION_ACTIVE_COLLECTOR_EXISTS)
        reason_codes.append("item9_prospective_process_detected")

    if not provider_ok:
        blockers.append(DISPOSITION_PROVIDER_UNAVAILABLE)
        if not opend.loopback:
            reason_codes.append("opend_not_loopback")
        else:
            reason_codes.append("opend_unreachable")

    disposition: str
    if blockers:
        disposition = blockers[0]
    elif not rth_active:
        disposition = DISPOSITION_NOT_RTH
        reason_codes.append("SOFTWARE_READY_RTH_REQUIRED")
    else:
        disposition = DISPOSITION_READY_TO_COLLECT

    governed_root = frozen_imp if frozen_available else None
    invocation = _governed_prospective_invocation(
        frozen_imp_root=governed_root,
        instrument_id=opts.instrument_id,
        receipt_dir=receipt_dir,
    )

    return {
        "schema_version": _SCHEMA_VERSION,
        "artifact_kind": _ARTIFACT_KIND,
        "disposition": disposition,
        "dispositions_allowed": sorted(_PREFLIGHT_DISPOSITIONS),
        "blockers": blockers,
        "reason_codes": reason_codes,
        "operator_checks": operator_checks,
        "calendar": {
            "scope": CALENDAR_US_EQUITY_RTH,
            "timezone": US_EQUITY_SESSION_TZ,
            "session_date_et": session_date,
            "rth_active": rth_active,
        },
        "instrument_id": opts.instrument_id,
        "readiness": readiness,
        "receipt_contract_version": RECEIPT_CONTRACT_VERSION,
        "receipt_dir": str(receipt_dir),
        "output_path_gate": validate_item9_prospective_receipt_output_dir(receipt_dir),
        "receipt_dir_writable": writable,
        "disk": disk_report,
        "provider": {
            "provider_id": "moomoo.opend",
            "host": opend.host,
            "port": opend.port,
            "loopback": opend.loopback,
            "reachable": opend.reachable,
        },
        "runtime": {
            "current_imp_root": str(imp_root),
            "current_git_sha": runtime_sha,
            "frozen_collector_authority_sha": opts.frozen_collector_authority_sha,
            "frozen_collector_imp_root": str(frozen_imp) if frozen_imp else None,
            "frozen_collector_git_sha": frozen_sha,
            "frozen_collector_available": frozen_available,
            "runtime_matches_frozen_authority": runtime_matches_frozen,
        },
        "active_collector": {
            "detected": active_collector,
            "matching_command_lines": active_matches[:3],
        },
        "poll_limits": {
            "poll_interval_s": POLL_INTERVAL_S_DEFAULT,
            "timeout_s": POLL_TIMEOUT_S_DEFAULT,
            "stop_conditions": [
                "first_post_signal_bar with available_time > signal_time_ns",
                "non-retryable provider errors",
                "poll timeout (PROSPECTIVE_NO_POST_SIGNAL_BAR)",
            ],
        },
        "prospective_admission": {
            "proof_mode": "PROSPECTIVE_BAR_OHLCV_1M",
            "refuses_explicit_signal_time_ns": True,
            "raw_provenance_hash": "SHA256(sorted kline rows) on receipt",
            "corpus_evidence_authority_stamped_on_persist": True,
            "calibrated": False,
            "orders_placed": False,
            "auto_calibration_fit": False,
        },
        "governed_prospective_invocation": invocation,
        "post_run_corpus_status_command": _post_run_corpus_status_command(receipt_dir),
        "does_not_start_collector": True,
        "secrets_included": False,
        "imp_env_snapshot": {
            "IMP_MOOMOO_HOST": mapping.get("IMP_MOOMOO_HOST"),
            "IMP_MOOMOO_PORT": mapping.get("IMP_MOOMOO_PORT"),
        },
    }


def build_item9_next_rth_preflight_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Item 9 next-RTH prospective collection preflight. "
            "Never runs prospective --poll or writes receipts."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser(
        "next-rth-preflight",
        help="Validate calendar, OpenD, frozen runtime, and receipt path before Mode B --poll.",
    )
    preflight.add_argument("--instrument-id", default=DEFAULT_INSTRUMENT_ID)
    preflight.add_argument(
        "--receipt-dir",
        type=Path,
        default=None,
        help=f"Governed receipt directory (default: {DEFAULT_RECEIPT_DIR}).",
    )
    preflight.add_argument("--json", action="store_true", help="Machine-readable JSON report.")
    preflight.add_argument("--now-ns", type=int, default=None, help="Test-only wall clock override.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_item9_next_rth_preflight_parser().parse_args(argv)
    if args.command != "next-rth-preflight":
        print(f"unknown item9 command: {args.command}", file=sys.stderr)
        return 2
    imp_root = imp_package_root()
    report = run_item9_next_rth_preflight(
        imp_root,
        options=Item9NextRthPreflightOptions(
            instrument_id=str(args.instrument_id),
            receipt_dir=args.receipt_dir,
            now_ns=args.now_ns,
        ),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"disposition={report['disposition']} blockers={report['blockers']}")
        print(f"reason_codes={report['reason_codes']}")
    disposition = report["disposition"]
    if disposition in {DISPOSITION_READY_TO_COLLECT, DISPOSITION_NOT_RTH}:
        return 0
    return 1


__all__ = [
    "DISPOSITION_ACTIVE_COLLECTOR_EXISTS",
    "DISPOSITION_NOT_RTH",
    "DISPOSITION_OUTPUT_PATH_INVALID",
    "DISPOSITION_PROVIDER_UNAVAILABLE",
    "DISPOSITION_READY_TO_COLLECT",
    "DISPOSITION_WRONG_RUNTIME",
    "FROZEN_COLLECTOR_AUTHORITY_SHA",
    "Item9NextRthPreflightOptions",
    "build_item9_next_rth_preflight_parser",
    "detect_active_item9_prospective_collector",
    "main",
    "monorepo_root_from_imp",
    "resolve_frozen_collector_imp_root",
    "run_item9_next_rth_preflight",
]
