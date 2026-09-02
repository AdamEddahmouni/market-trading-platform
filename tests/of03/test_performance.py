from __future__ import annotations

import time
import unittest

from market_platform_foundation.of03.loader import load_registry
from market_platform_foundation.of03.operations import execute


class PerformanceTests(unittest.TestCase):
    def test_informational_timings(self) -> None:
        started = time.perf_counter()
        registry = load_registry(fail_closed=True)
        load_s = time.perf_counter() - started
        started = time.perf_counter()
        execute("OF03.OP.VALIDATE", registry=registry)
        validate_s = time.perf_counter() - started
        started = time.perf_counter()
        execute("OF03.OP.SNAPSHOT", registry=registry)
        snap_s = time.perf_counter() - started
        started = time.perf_counter()
        execute("OF03.OP.VERIFY_BINDINGS", registry=registry)
        bind_s = time.perf_counter() - started
        started = time.perf_counter()
        registry.capability("OF03.OP.STATUS", 1)
        lookup_s = time.perf_counter() - started
        self.assertGreaterEqual(load_s, 0.0)
        self.assertGreaterEqual(validate_s, 0.0)
        self.assertGreaterEqual(snap_s, 0.0)
        self.assertGreaterEqual(bind_s, 0.0)
        self.assertGreaterEqual(lookup_s, 0.0)
        print(
            f"of03 timings load={load_s:.4f}s validate={validate_s:.4f}s snapshot={snap_s:.4f}s "
            f"bindings={bind_s:.4f}s lookup={lookup_s:.6f}s"
        )


if __name__ == "__main__":
    unittest.main()
