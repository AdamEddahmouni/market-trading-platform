"""OCT1-08: local timing of the stop core, its persistence, the cycle overhead and the replay run.

Operational measurements on this machine only; not a market or profitability metric.
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from market_platform_foundation.local_state.connection import LocalStateConnection  # noqa: E402
from market_platform_foundation.local_state.sma_trailing_stop import SmaStopRepository  # noqa: E402
from market_platform_foundation.research.sma_stop_evaluation import corpus_bars, load_corpus, run_frozen_evaluation  # noqa: E402
from market_platform_foundation.risk.sma_trailing_stop import REFERENCE_TEST_CONFIG, advance, build_policy, initial_state  # noqa: E402


def _ms(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {"mean_ms": round(statistics.fmean(samples) * 1000, 4), "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1] * 1000, 4), "samples": len(samples)}


def main() -> int:
    policy = build_policy(**REFERENCE_TEST_CONFIG)
    bars = corpus_bars(load_corpus(ROOT)["rows"])[:390]
    state = initial_state(account_id="perf", session_id="perf", instrument_id="PERF", position_epoch_id="PE-perf", epoch_basis="PERF", side="LONG",
                          quantity=1, policy=policy, activated_at=0, activation_reason="POSITION_OPENED")
    updates = []
    for count in range(1, len(bars) + 1):
        started = time.perf_counter()
        state, _ = advance(state, bars[:count], policy)
        updates.append(time.perf_counter() - started)

    with tempfile.TemporaryDirectory() as directory:
        connection = LocalStateConnection(Path(directory) / "imp-state.sqlite3")
        repository = SmaStopRepository(connection)
        writes, reads = [], []
        for index in range(200):
            started = time.perf_counter()
            repository.put("state", state["stop_state_id"], dict(state, last_evaluated_at=index), updated_at=index)
            writes.append(time.perf_counter() - started)
            started = time.perf_counter()
            repository.latest_state("perf", "PERF")
            reads.append(time.perf_counter() - started)
        connection.close()

    from tests.intelligence.test_reevaluation import Harness
    from tests.intelligence.test_sma_stop_decision import StopHarness

    def cycles(harness, configure):
        harness.hold(10)
        configure(harness)
        samples = []
        for _ in range(40):
            started = time.perf_counter()
            harness.tick()
            samples.append(time.perf_counter() - started)
        return samples

    with patch("market_platform_foundation.operating_modes.paper_execution_env_enabled", return_value=True):
        plain = cycles(Harness(), lambda h: h.configure())

        def with_stop(h):
            h.stops.configure(dict(enabled=True))
            h.closes = [14000] * 400  # revealed one per tick by the clock; steady, so no transition noise
            h.configure()
        stopped = cycles(StopHarness(), with_stop)

    started = time.perf_counter()
    result = run_frozen_evaluation(ROOT)
    elapsed = time.perf_counter() - started
    report = {
        "schema_version": "oct1-08-performance/1.0.0", "classification": "SOFTWARE_CONTROLLED", "scope": "local timing only",
        "stop_calculation": {"bars_processed": len(bars), "sma_window_bars": policy["sma_window_bars"], **_ms(updates)},
        "persistence": {"durability": "SQLITE_LOCAL_STATE", "state_write": _ms(writes), "state_read": _ms(reads)},
        "reevaluation_cycle": {"without_stop": _ms(plain), "with_stop": _ms(stopped),
                               "added_mean_ms": round((statistics.fmean(stopped) - statistics.fmean(plain)) * 1000, 4), "extra_model_calls": 0},
        "replay": {"episodes": result["counts"]["episodes"], "bars": result["corpus"]["bars"], "seconds": round(elapsed, 3),
                   "episodes_per_second": round(result["counts"]["episodes"] / elapsed, 1), "result_hash": result["result_hash"]},
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
