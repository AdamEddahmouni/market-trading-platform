"""Controlled OpenD process reconnect smoke. Quote-only. Requires operator intent.

Set IMP_RECONNECT_SMOKE=1 before running. Stops only the local moomoo_OpenD process
and restarts %APPDATA%\\moomoo_OpenD\\moomoo_OpenD.exe.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

from check_live_environment import opend_executable_path, run_check, start_opend
from market_platform_foundation.market_data.connectivity import opend_reachable
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState
from market_platform_foundation.market_data.subscription_manager import SubscriptionPriority


def _stop_opend() -> None:
    subprocess.run(["taskkill", "/IM", "moomoo_OpenD.exe", "/F"], capture_output=True, check=False)


def main() -> int:
    if os.environ.get("IMP_RECONNECT_SMOKE") != "1":
        print("Set IMP_RECONNECT_SMOKE=1 to run the OpenD process reconnect smoke.")
        return 2
    os.environ.setdefault("IMP_LIVE_OBSERVATIONAL", "1")
    os.environ.setdefault("IMP_MOOMOO_LIVE", "1")
    reset_live_runtime()
    runtime = LiveObservationalRuntime()
    runtime.configure()
    runtime.subscribe(
        instrument_id="AAPL",
        capabilities=["BASIC_QUOTE", "TRADES"],
        consumer_id="reconnect-smoke",
        priority=SubscriptionPriority.ACTIVE_WORKSPACE,
    )
    deadline = time.time() + 8
    while time.time() < deadline and runtime._fresh_event_count < 1:
        time.sleep(0.25)
    before = runtime.lifecycle.connection_state.value
    print(f"before_stop={before} events={runtime._fresh_event_count}")
    _stop_opend()
    disconnected_at = None
    deadline = time.time() + 20
    while time.time() < deadline:
        if runtime.lifecycle.connection_state in {
            ProviderConnectionState.DISCONNECTED,
            ProviderConnectionState.RECONNECTING,
        } or not opend_reachable():
            disconnected_at = time.time()
            break
        time.sleep(0.25)
    print(f"after_stop={runtime.lifecycle.connection_state.value} reachable={opend_reachable()}")
    start_opend()
    restored = False
    deadline = time.time() + 40
    while time.time() < deadline:
        if runtime.lifecycle.connection_state == ProviderConnectionState.CONNECTED and runtime._fresh_event_count > 0:
            restored = True
            break
        time.sleep(0.5)
    after = runtime.lifecycle.connection_state.value
    runtime.unsubscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE", "TRADES"], consumer_id="reconnect-smoke")
    runtime.stop()
    print(f"after_restart={after} restored_healthy={restored} generation={runtime.lifecycle.provider_generation_id}")
    report = run_check()
    print(report.get("status"))
    return 0 if restored or after in {"CONNECTED", "CONNECTED_DEGRADED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
