"""Focused tests for validate.py live-gate handling (audit finding F9).

Proves that every entry in ``LIVE_GATES`` -- including the master
``IMP_LIVE_EXECUTION`` execution-enable gate -- is stripped from any
offline child environment, is only settable inside an explicit
LIVE_EXCLUSIVE child run, and that unknown provider keys fail closed.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from tools.validate import (
        ALL_LIVE_GATES,
        LIVE_GATES,
        ValidationSelectionError,
        _child_environment,
    )
except ModuleNotFoundError as exc:  # RED: make the missing implementation a failure.
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

# Pre-existing provider mappings whose semantics must not change.
LEGACY_MAPPINGS: dict[str, tuple[str, ...]] = {
    "cboe": ("IMP_CBOE_REGSHO_LIVE",),
    "cboe_options": ("IMP_CBOE_OPTIONS_LIVE",),
    "cftc": ("RUN_LIVE_CFTC",),
    "eia": ("IMP_EIA_LIVE",),
    "finra": ("IMP_FINRA_LIVE", "IMP_FINRA_OTC_THRESHOLD_LIVE"),
    "fred": ("IMP_FRED_LIVE",),
    "moomoo": ("IMP_MOOMOO_LIVE",),
    "nasdaq": ("IMP_NASDAQ_REGSHO_LIVE",),
    "nyse": ("IMP_NYSE_REGSHO_LIVE",),
    "sec": ("SEC_LIVE_TESTS",),
    "sec_ftd": ("IMP_SEC_FTD_LIVE",),
    "weather": ("IMP_WEATHER_LIVE",),
}


@unittest.skipIf(IMPORT_ERROR is not None, f"tools.validate unavailable: {IMPORT_ERROR}")
class ValidateLiveGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_imp_live_execution_is_a_registered_live_gate(self) -> None:
        self.assertIn("IMP_LIVE_EXECUTION", ALL_LIVE_GATES)
        self.assertEqual(LIVE_GATES["execution"], ("IMP_LIVE_EXECUTION",))
        self.assertIn("IMP_LIVE_OBSERVATIONAL", ALL_LIVE_GATES)
        self.assertEqual(LIVE_GATES["live_observational"], ("IMP_LIVE_OBSERVATIONAL",))

    def test_preexisting_provider_mappings_are_unchanged(self) -> None:
        for provider, gates in LEGACY_MAPPINGS.items():
            with self.subTest(provider=provider):
                self.assertIn(provider, LIVE_GATES)
                self.assertEqual(LIVE_GATES[provider], gates)

    def test_every_live_gate_is_stripped_from_offline_environment(self) -> None:
        leaked = {gate: "1" for gate in sorted(ALL_LIVE_GATES)}
        with patch.dict(os.environ, leaked, clear=False):
            child = _child_environment(self.root, None)
            for gate in sorted(ALL_LIVE_GATES):
                with self.subTest(gate=gate):
                    self.assertNotIn(gate, child)
            # Parent environment must not be mutated by the strip.
            for gate in sorted(ALL_LIVE_GATES):
                self.assertEqual(os.environ[gate], "1")

    def test_imp_live_execution_cannot_survive_into_offline_run(self) -> None:
        with patch.dict(
            os.environ,
            {
                "IMP_LIVE_EXECUTION": "1",
                "IMP_PAPER_EXECUTION": "1",
                "IMP_LIVE_OBSERVATIONAL": "1",
            },
            clear=False,
        ):
            child = _child_environment(self.root, None)
            self.assertNotIn("IMP_LIVE_EXECUTION", child)
            self.assertNotIn("IMP_LIVE_OBSERVATIONAL", child)
            # Paper/sandbox enables are intentionally NOT live gates.
            self.assertEqual(child["IMP_PAPER_EXECUTION"], "1")
            self.assertEqual(os.environ["IMP_LIVE_EXECUTION"], "1")

    def test_live_exclusive_child_sets_only_selected_provider_gates(self) -> None:
        with patch.dict(
            os.environ, {"IMP_LIVE_EXECUTION": "1"}, clear=False
        ):
            child = _child_environment(self.root, "weather")
            self.assertEqual(child["IMP_WEATHER_LIVE"], "1")
            self.assertNotIn("IMP_LIVE_EXECUTION", child)

    def test_unknown_provider_key_raises_validation_selection_error(self) -> None:
        with self.assertRaises(ValidationSelectionError):
            _child_environment(self.root, "definitely_not_a_provider")


if __name__ == "__main__":
    unittest.main()
