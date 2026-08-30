"""XA-04 backward compatibility with XA-01/02/03 semantics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa02.fixtures import admit_fixture as admit_xa02_fixture  # noqa: E402
from market_platform_foundation.xa02.registry import AdmissionRegistry  # noqa: E402
from market_platform_foundation.xa01.registry import InstrumentRegistry  # noqa: E402
from market_platform_foundation.xa03.registry import PositioningAdmissionRegistry  # noqa: E402
from tests.xa04.test_xa04_fixtures import reset_all_registries  # noqa: E402


class Xa04BackwardCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_all_registries()

    def test_xa02_admission_semantics_unchanged_without_repository(self) -> None:
        xa01 = InstrumentRegistry()
        xa02 = AdmissionRegistry(xa_registry=xa01)
        xa02.bootstrap_catalog()
        first = admit_xa02_fixture(fixture_name="rates_reference_vertical.json", registry=xa02)
        second = admit_xa02_fixture(fixture_name="rates_reference_vertical.json", registry=xa02)
        self.assertEqual(first["observation_ids"], second["observation_ids"])

    def test_xa03_admission_semantics_unchanged_without_repository(self) -> None:
        xa01 = InstrumentRegistry()
        xa03 = PositioningAdmissionRegistry(xa_registry=xa01)
        xa03.bootstrap_catalog()
        from market_platform_foundation.xa03.fixtures import admit_fixture as admit_xa03_fixture

        first = admit_xa03_fixture(fixture_name="legacy_futures_only_gc.json", registry=xa03)
        second = admit_xa03_fixture(fixture_name="legacy_futures_only_gc.json", registry=xa03)
        self.assertEqual(first["observation_ids"], second["observation_ids"])


if __name__ == "__main__":
    unittest.main()
