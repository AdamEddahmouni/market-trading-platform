"""CLI entry for Item 9 next-RTH prospective collection preflight."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.item9_next_rth_preflight import (  # noqa: E402
    DISPOSITION_NOT_RTH,
    DISPOSITION_READY_TO_COLLECT,
    Item9NextRthPreflightOptions,
    detect_active_item9_prospective_collector,
    imp_package_root,
    run_item9_next_rth_preflight,
)


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


def _active_collector_probe() -> tuple[bool, list[str]]:
    return detect_active_item9_prospective_collector(command_lines=_iter_process_command_lines())


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] == "next-rth-preflight":
        args = args[1:]
    instrument_id = "AAPL"
    receipt_dir: Path | None = None
    now_ns: int | None = None
    emit_json = False
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--instrument-id" and index + 1 < len(args):
            instrument_id = args[index + 1]
            index += 2
            continue
        if token == "--receipt-dir" and index + 1 < len(args):
            receipt_dir = Path(args[index + 1])
            index += 2
            continue
        if token == "--now-ns" and index + 1 < len(args):
            now_ns = int(args[index + 1])
            index += 2
            continue
        if token == "--json":
            emit_json = True
            index += 1
            continue
        index += 1
    report = run_item9_next_rth_preflight(
        imp_package_root(),
        options=Item9NextRthPreflightOptions(
            instrument_id=instrument_id,
            receipt_dir=receipt_dir,
            now_ns=now_ns,
        ),
        active_collector_probe=_active_collector_probe,
    )
    if emit_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"disposition={report['disposition']} blockers={report['blockers']}")
        print(f"reason_codes={report['reason_codes']}")
    disposition = report["disposition"]
    if disposition in {DISPOSITION_READY_TO_COLLECT, DISPOSITION_NOT_RTH}:
        return 0
    return 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0] == "next-rth-preflight" or argv[0].startswith("-"):
        if argv and argv[0] == "next-rth-preflight":
            argv = argv[1:]
        argv = ["next-rth-preflight", *argv]
    raise SystemExit(main(argv))
