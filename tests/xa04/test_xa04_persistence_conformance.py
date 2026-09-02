"""Repository conformance tests for XA catalog persistence (IMP-XA-04)."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa04 import (  # noqa: E402
    InMemoryCrossAssetCatalogRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from tests.xa04.test_xa04_fixtures import populate_vertical_slice_repository  # noqa: E402


class CatalogRepositoryConformanceTests(unittest.TestCase):
    backend_name = "in_memory"

    def setUp(self) -> None:
        self.repo, self.state = populate_vertical_slice_repository(
            InMemoryCrossAssetCatalogRepository()
        )

    def test_round_trip_vertical_slice_records(self) -> None:
        gc_id = str(self.state["gc_canonical_id"])
        stored = self.repo.get_instrument(gc_id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.descriptor.identity.canonical_id, gc_id)
        fred_ids = self.state["fred"]["observation_ids"]  # type: ignore[index]
        self.assertTrue(fred_ids)
        obs = self.repo.get_scalar_observation(fred_ids[0])
        self.assertIsNotNone(obs)
        cftc_ids = self.state["cftc"]["observation_ids"]  # type: ignore[index]
        self.assertTrue(cftc_ids)
        envelope = self.repo.get_admission_envelope(cftc_ids[0])
        self.assertIsNotNone(envelope)

    def test_idempotent_write_same_content(self) -> None:
        gc_id = str(self.state["gc_canonical_id"])
        record = self.repo.get_instrument(gc_id)
        assert record is not None
        self.assertEqual(self.repo.put_instrument(record), RepositoryPutResult.ALREADY_PRESENT)

    def test_conflict_same_id_different_content(self) -> None:
        gc_id = str(self.state["gc_canonical_id"])
        record = self.repo.get_instrument(gc_id)
        assert record is not None
        mutated = copy.deepcopy(record)
        mutated = type(record)(
            descriptor=type(record.descriptor)(
                identity=record.descriptor.identity,
                display_name="MUTATED",
                venue_id=record.descriptor.venue_id,
                exchange=record.descriptor.exchange,
                denomination=record.descriptor.denomination,
                sovereign_issuer=record.descriptor.sovereign_issuer,
                security_type=record.descriptor.security_type,
                issue_date=record.descriptor.issue_date,
                maturity_date=record.descriptor.maturity_date,
                coupon=record.descriptor.coupon,
                commodity_code=record.descriptor.commodity_code,
                contract_month=record.descriptor.contract_month,
                expiration=record.descriptor.expiration,
                strike=record.descriptor.strike,
                call_put=record.descriptor.call_put,
                base_currency=record.descriptor.base_currency,
                quote_currency=record.descriptor.quote_currency,
                schema_version=record.descriptor.schema_version,
            ),
            analytical_domains=record.analytical_domains,
            aliases=record.aliases,
            relationships=record.relationships,
        )
        with self.assertRaises(RepositoryConflictError):
            self.repo.put_instrument(mutated)
        unchanged = self.repo.get_instrument(gc_id)
        assert unchanged is not None
        self.assertNotEqual(unchanged.descriptor.display_name, "MUTATED")

    def test_not_found_returns_none(self) -> None:
        self.assertIsNone(self.repo.get_instrument("missing"))

    def test_health(self) -> None:
        health = self.repo.check_health()
        self.assertTrue(health["available"])
        self.assertEqual(health["backend"], self.backend_name)


if __name__ == "__main__":
    unittest.main()
