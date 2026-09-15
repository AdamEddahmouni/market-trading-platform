"""Phase 5 Lane D — MATLABRuntime governed export round-trip + fixture parity."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_platform_foundation.research.export_v1 import PROFILE_MARKET_TECHNICAL  # noqa: E402
from market_platform_foundation.strategy.source_runtime import (  # noqa: E402
    MATLAB_RUNTIME_UNAVAILABLE,
    MATLAB_STRATEGY_RUNTIME_READY,
    MATLABRuntime,
    PythonRuntime,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyExecutionMode,
    StrategyParameterRef,
    StrategySourceRef,
)
from tools.research.matlab_runtime import probe_matlab_runtime  # noqa: E402


def _empty_dataset() -> StrategyDatasetRef:
    return StrategyDatasetRef(events=())


class MatlabStrategyRuntimeTests(unittest.TestCase):
    def test_fixture_roundtrip_unavailable_without_host_matlab(self) -> None:
        probe = probe_matlab_runtime()
        runtime = MATLABRuntime()
        source = StrategySourceRef(
            kind="research_export_v1",
            body={"profile": PROFILE_MARKET_TECHNICAL},
        )
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-15T00:00:00.000000000Z",
        )
        result = runtime.execute(source, _empty_dataset(), StrategyParameterRef(body={}), context)
        if probe["status"] == "AVAILABLE":
            self.assertEqual(result.foundation_gate, MATLAB_STRATEGY_RUNTIME_READY)
            self.assertTrue(result.metrics["matlab_runtime_used"])
            self.assertEqual(result.metrics["analysis_source"], "matlab_smoke")
        else:
            self.assertEqual(result.foundation_gate, MATLAB_RUNTIME_UNAVAILABLE)
            self.assertFalse(result.metrics["matlab_runtime_used"])
            self.assertIn("MATLAB_RUNTIME_NOT_AVAILABLE", result.warnings)
        self.assertTrue(result.metrics["parity_reference_statistics_match"])
    def test_parity_mode_prefers_host_matlab_when_available(self) -> None:
        probe = probe_matlab_runtime()
        if probe["status"] != "AVAILABLE":
            self.skipTest("MATLAB runtime not available on host")
        runtime = MATLABRuntime()
        source = StrategySourceRef(
            kind="research_export_v1",
            body={"profile": PROFILE_MARKET_TECHNICAL},
        )
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.PARITY,
            generated_at="2026-09-15T00:00:00.000000000Z",
        )
        result = runtime.execute(source, _empty_dataset(), StrategyParameterRef(body={}), context)
        self.assertEqual(result.foundation_gate, MATLAB_STRATEGY_RUNTIME_READY)
        self.assertTrue(result.metrics["parity_reference_statistics_match"])

    def test_parity_python_reference_vs_matlab_runtime_fixture_path(self) -> None:
        runtime = MATLABRuntime()
        source = StrategySourceRef(
            kind="research_export_v1",
            body={"profile": PROFILE_MARKET_TECHNICAL},
        )
        parameters = StrategyParameterRef(body={"prefer_matlab": False})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-15T00:00:00.000000000Z",
        )
        matlab_result = runtime.execute(source, _empty_dataset(), parameters, context)
        self.assertTrue(matlab_result.metrics["parity_reference_statistics_match"])
        self.assertEqual(matlab_result.foundation_gate, MATLAB_RUNTIME_UNAVAILABLE)
        self.assertEqual(matlab_result.metrics["analysis_source"], "python_reference")

    def test_python_strategy_runtime_still_independent(self) -> None:
        from tests.phase4.test_strategy_source_runtime import (  # noqa: PLC0415
            _synthetic_events,
        )
        from market_platform_foundation.strategy.evaluation import (  # noqa: E402
            default_forecast_momentum_spec,
        )

        events = _synthetic_events(4)
        py = PythonRuntime()
        source = StrategySourceRef(kind="strategy_spec", body=default_forecast_momentum_spec())
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-15T00:00:00.000000000Z",
        )
        py_result = py.execute(
            source,
            StrategyDatasetRef(events=tuple(events)),
            StrategyParameterRef(body={}),
            context,
        )
        self.assertGreater(py_result.metrics["signal_count"], 0)


if __name__ == "__main__":
    unittest.main()
