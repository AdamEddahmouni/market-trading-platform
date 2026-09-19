"""Backend runtime / provider resilience snapshot for operator diagnostics (Lane B).

Does not start collectors, auto-restart empirical processes, or mutate receipts.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from ..git_ref import read_git_head
from ..paper.calibration.bar_ohlcv_prospective_proof import (
    DEFAULT_RECEIPT_DIR,
    resolve_runtime_git_sha,
)
from ..paper.calibration.item9_next_rth_preflight import (
    FROZEN_COLLECTOR_AUTHORITY_SHA,
    Item9NextRthPreflightOptions,
    detect_active_item9_prospective_collector,
    resolve_frozen_collector_imp_root,
    run_item9_next_rth_preflight,
)
from ..platform.artifact_path_resolver import (
    analyze_item9_collect_log_gaps,
    analyze_item9_receipt_directory,
    read_item9_collector_log_text,
)
from ..providers.equity_quote_selection import opend_readiness

_ARTIFACT_KIND = "imp_runtime_resilience_diagnostic"
_SCHEMA_VERSION = "1.0.0"


def _list_process_command_lines() -> list[str]:
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return []

    lines: list[str] = []
    for proc in psutil.process_iter(attrs=["cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
        except (OSError, AttributeError):
            continue
        if not cmdline:
            continue
        lines.append(" ".join(str(part) for part in cmdline))
    return lines


def build_runtime_resilience_diagnostic(
    imp_root: Path,
    *,
    receipt_dir: Path | None = None,
    collector_log_text: str | None = None,
    env: Mapping[str, str] | None = None,
    now_ns: int | None = None,
    active_collector_probe: Callable[[], tuple[bool, list[str]]] | None = None,
) -> dict[str, Any]:
    imp_root = imp_root.resolve()
    mapping = env if env is not None else os.environ
    observed_ns = now_ns if now_ns is not None else time.time_ns()

    if receipt_dir is None:
        receipt_dir = imp_root / DEFAULT_RECEIPT_DIR
    elif not receipt_dir.is_absolute():
        receipt_dir = imp_root / receipt_dir

    runtime_sha = resolve_runtime_git_sha(start=imp_root)
    frozen_imp = resolve_frozen_collector_imp_root(imp_root)
    frozen_sha = read_git_head(start=frozen_imp) if frozen_imp is not None else None

    probe = active_collector_probe
    if probe is None:
        command_lines = _list_process_command_lines()
        probe = lambda lines=command_lines: detect_active_item9_prospective_collector(  # noqa: E731
            command_lines=lines
        )

    item9_preflight = run_item9_next_rth_preflight(
        imp_root,
        options=Item9NextRthPreflightOptions(receipt_dir=receipt_dir, now_ns=observed_ns),
        env=mapping,
        active_collector_probe=probe,
    )
    opend = opend_readiness()

    log_source: dict[str, object] = {"availability": "NOT_OBSERVED"}
    if collector_log_text is None:
        collector_log_text, log_source = read_item9_collector_log_text(imp_root, mapping)
    else:
        log_source = {"availability": "CALLER_SUPPLIED"}

    log_gaps: dict[str, object] | None = None
    if collector_log_text:
        log_gaps = analyze_item9_collect_log_gaps(collector_log_text)

    receipt_inventory = analyze_item9_receipt_directory(receipt_dir)

    provider_state = "REACHABLE" if opend.loopback and opend.reachable else "UNAVAILABLE"
    if opend.loopback and not opend.reachable:
        provider_failure_class = "PROVIDER_UNREACHABLE"
    elif not opend.loopback:
        provider_failure_class = "PROVIDER_NOT_LOOPBACK"
    else:
        provider_failure_class = "NONE"

    return {
        "artifact_kind": _ARTIFACT_KIND,
        "schema_version": _SCHEMA_VERSION,
        "observed_at_ns": observed_ns,
        "evidence_class": "SOFTWARE",
        "runtime_identity": {
            "runtime_git_sha": runtime_sha,
            "frozen_collector_authority_sha": FROZEN_COLLECTOR_AUTHORITY_SHA,
            "frozen_collector_worktree_sha": frozen_sha,
            "frozen_collector_imp_root": str(frozen_imp) if frozen_imp else None,
            "runtime_matches_frozen_authority": item9_preflight.get("runtime", {}).get(
                "runtime_matches_frozen_authority"
            ),
        },
        "provider_connectivity": {
            "provider_id": "moomoo.opend",
            "state": provider_state,
            "failure_class": provider_failure_class,
            "host": opend.host,
            "port": opend.port,
            "loopback": opend.loopback,
            "reachable": opend.reachable,
        },
        "collector_process": {
            "active_collector_detected": bool(item9_preflight.get("active_collector", {}).get("detected")),
            "active_collector_matches": list(
                item9_preflight.get("active_collector", {}).get("matching_command_lines") or []
            ),
            "probe_status": item9_preflight.get("active_collector", {}).get("process_probe_status"),
        },
        "item9_next_rth_preflight": {
            "disposition": item9_preflight.get("disposition"),
            "blockers": list(item9_preflight.get("blockers") or []),
            "reason_codes": list(item9_preflight.get("reason_codes") or []),
        },
        "expected_cycle": {
            "receipt_dir": str(receipt_dir),
            "receipt_inventory": receipt_inventory,
            "collector_log_gaps": log_gaps,
            "collector_log_source": log_source,
        },
        "readiness_vs_liveness": {
            "readiness": item9_preflight.get("readiness"),
            "liveness": {
                "provider_reachable": opend.reachable,
                "collector_process_running": bool(
                    item9_preflight.get("active_collector", {}).get("detected")
                ),
            },
        },
    }


__all__ = ["build_runtime_resilience_diagnostic"]
