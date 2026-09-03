"""Operator diagnostic for the local Moomoo OpenD observational environment."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.capability_registry import VerifiedCapabilityRegistry  # noqa: E402
from market_platform_foundation.market_data.live_config import (  # noqa: E402
    moomoo_host,
    moomoo_live_enabled,
    moomoo_port,
    probe_report_path,
    probe_staleness_seconds,
)

STATUS_OPEN_D_NOT_INSTALLED = "OPEN_D_NOT_INSTALLED"
STATUS_OPEN_D_NOT_RUNNING = "OPEN_D_NOT_RUNNING"
STATUS_PORT_UNREACHABLE = "PORT_UNREACHABLE"
STATUS_SDK_MISSING = "SDK_MISSING"
STATUS_SDK_INCOMPATIBLE = "SDK_INCOMPATIBLE"
STATUS_SDK_VERSION_MISMATCH = STATUS_SDK_INCOMPATIBLE
STATUS_QUOTE_CONTEXT_FAILED = "QUOTE_CONTEXT_FAILED"
STATUS_READY = "READY"

EXPECTED_SDK_PREFIX = "10.10"


def opend_executable_path() -> Path:
    appdata = os.environ.get("APPDATA") or ""
    return Path(appdata) / "moomoo_OpenD" / "moomoo_OpenD.exe"


def opend_config_dir() -> Path:
    appdata = os.environ.get("APPDATA") or ""
    return Path(appdata) / "com.moomoo.OpenD"


def _opend_file_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Item -LiteralPath '{path}').VersionInfo.ProductVersion",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        text = (completed.stdout or "").strip()
        return text or None
    except OSError:
        return None


def _opend_process_running() -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq moomoo_OpenD.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        out = (completed.stdout or "").lower()
        return "moomoo_opend.exe" in out
    except OSError:
        return False


def _check_sdk() -> dict[str, Any]:
    try:
        import moomoo as ft  # type: ignore

        version = str(getattr(ft, "__version__", "unknown"))
        mismatch = not version.startswith(EXPECTED_SDK_PREFIX)
        return {
            "installed": True,
            "mismatch": mismatch,
            "open_quote_context": hasattr(ft, "OpenQuoteContext"),
            "version": version,
        }
    except ImportError as exc:
        return {"installed": False, "error": str(exc), "mismatch": False}


def _check_port(host: str, port: int) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return {"reachable": False, "error": "OPEND_MUST_REMAIN_LOCALHOST"}
    try:
        sock = socket.create_connection((host, port), timeout=3)
        peer = sock.getpeername()
        sock.close()
        return {"host": host, "peer": list(peer), "port": port, "reachable": True}
    except OSError as exc:
        return {"host": host, "port": port, "reachable": False, "error": str(exc)}


def _quote_context_check(host: str, port: int) -> dict[str, Any]:
    try:
        import moomoo as ft  # type: ignore
    except ImportError as exc:
        return {"ok": False, "error": str(exc)}
    ctx = ft.OpenQuoteContext(host=host, port=port)
    try:
        ret, state = ctx.get_global_state()
        return {
            "ok": ret == ft.RET_OK,
            "ret": ret,
            "qot_logined": None if ret != ft.RET_OK else str(state.get("qot_logined")),
            "server_ver": None if ret != ft.RET_OK else state.get("server_ver"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    finally:
        ctx.close()


def start_opend() -> dict[str, Any]:
    exe = opend_executable_path()
    if not exe.is_file():
        return {"started": False, "error": STATUS_OPEN_D_NOT_INSTALLED, "path": str(exe)}
    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True)
        return {"started": True, "path": str(exe)}
    except OSError as exc:
        return {"started": False, "error": str(exc), "path": str(exe)}


def run_check(
    *,
    host: str | None = None,
    port: int | None = None,
    json_output: Path | None = None,
    start: bool = False,
) -> dict[str, Any]:
    target_host = host or moomoo_host()
    target_port = port or moomoo_port()
    exe = opend_executable_path()
    installed = exe.is_file()
    running = _opend_process_running()
    if start and installed and not running:
        start_opend()
        running = _opend_process_running()
    sdk = _check_sdk()
    port_state = _check_port(target_host, target_port)
    quote = {"ok": False}
    if sdk.get("installed") and port_state.get("reachable"):
        quote = _quote_context_check(target_host, target_port)
    registry = VerifiedCapabilityRegistry.from_probe_file(
        probe_report_path(),
        max_staleness_seconds=probe_staleness_seconds(),
        moomoo_configured=moomoo_live_enabled(),
        runtime_connected=bool(port_state.get("reachable")),
    )
    status = STATUS_READY
    if not installed:
        status = STATUS_OPEN_D_NOT_INSTALLED
    elif not running and not port_state.get("reachable"):
        status = STATUS_OPEN_D_NOT_RUNNING
    elif not port_state.get("reachable"):
        status = STATUS_PORT_UNREACHABLE
    elif not sdk.get("installed"):
        status = STATUS_SDK_MISSING
    elif sdk.get("mismatch"):
        status = STATUS_SDK_INCOMPATIBLE
    elif not quote.get("ok"):
        status = STATUS_QUOTE_CONTEXT_FAILED
    ready = status == STATUS_READY
    report: dict[str, Any] = {
        "config_dir": str(opend_config_dir()),
        "connection": "CONNECTED" if port_state.get("reachable") else "DISCONNECTED",
        "imp_moomoo_live": moomoo_live_enabled(),
        "opend": {
            **port_state,
            "executable": str(exe),
            "file_version": _opend_file_version(exe),
            "installed": installed,
            "running": running,
        },
        "probe_report": str(probe_report_path()),
        "probe_stale": registry.is_stale,
        "provider": "MOOMOO",
        "quote_context": quote,
        "ready_for_live_observational": ready,
        "sdk": sdk,
        "status": status,
        "verified_at": registry.verified_at,
        "verified_capabilities": registry.summary_rows(),
    }
    lines = [
        "MOOMOO LIVE ENVIRONMENT",
        f"OpenD installed     {'YES' if installed else 'NO'}  ({exe})",
        f"OpenD running       {'YES' if running else 'NO'}",
        f"{target_host}:{target_port}     {'REACHABLE' if port_state.get('reachable') else 'UNREACHABLE'}",
        f"SDK                  {sdk.get('version') or 'MISSING'}",
        f"Quote context        {'PASS' if quote.get('ok') else 'FAIL'}",
        status,
    ]
    report["operator_message"] = "\n".join(lines)
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local Moomoo live observational prerequisites")
    parser.add_argument("--host", default=moomoo_host())
    parser.add_argument("--port", type=int, default=moomoo_port())
    parser.add_argument("--json", dest="json_output", default="")
    parser.add_argument(
        "--start-opend",
        action="store_true",
        help="Start %APPDATA%\\moomoo_OpenD\\moomoo_OpenD.exe if installed and not running",
    )
    args = parser.parse_args()
    report = run_check(
        host=args.host,
        port=args.port,
        json_output=Path(args.json_output) if args.json_output else None,
        start=args.start_opend,
    )
    print(str(report.get("operator_message")))
    return 0 if report.get("ready_for_live_observational") else 1


if __name__ == "__main__":
    raise SystemExit(main())
