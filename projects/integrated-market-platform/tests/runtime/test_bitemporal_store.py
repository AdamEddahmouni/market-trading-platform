"""Tests for P0 bitemporal reference store."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.reference import (  # noqa: E402
    ReferenceKind,
    ReferenceRecord,
)
from market_platform_foundation.runtime.bitemporal_store import (  # noqa: E402
    BitemporalAppendError,
    BitemporalReferenceStore,
    record_is_visible,
)

T0 = "2020-01-01T00:00:00.000000000Z"
T1 = "2024-06-15T00:00:00.000000000Z"
T_BEFORE = "2024-06-14T23:59:59.000000000Z"
T_AFTER = "2024-06-16T00:00:00.000000000Z"
OPEN = ""


def _spec(version: int, known_from: str, known_to: str, spec_version: str) -> ReferenceRecord:
    return ReferenceRecord(
        kind=ReferenceKind.FUTURES_SPEC,
        entity_key="ES",
        record_id="es-spec",
        record_version=version,
        valid_from=T0,
        valid_to=OPEN,
        known_from=known_from,
        known_to=known_to,
        payload={"spec_version": spec_version, "multiplier": "50"},
    )


class BitemporalStoreTests(unittest.TestCase):
    def test_as_of_returns_visible_version(self) -> None:
        store = BitemporalReferenceStore()
        store.append(_spec(1, T0, OPEN, "es_cme_v1"))
        found = store.as_of(ReferenceKind.FUTURES_SPEC, "ES", T_AFTER, T_AFTER)
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.payload["spec_version"], "es_cme_v1")

    def test_correction_invisible_before_known_from(self) -> None:
        store = BitemporalReferenceStore()
        store.append(_spec(1, T0, T1, "es_cme_v1"))
        store.append(_spec(2, T1, OPEN, "es_cme_v1_corrected"))
        before = store.as_of(ReferenceKind.FUTURES_SPEC, "ES", T_AFTER, T_BEFORE)
        after = store.as_of(ReferenceKind.FUTURES_SPEC, "ES", T_AFTER, T_AFTER)
        self.assertEqual(before.payload["spec_version"] if before else None, "es_cme_v1")
        self.assertEqual(after.payload["spec_version"] if after else None, "es_cme_v1_corrected")

    def test_open_ended_known_to_visible(self) -> None:
        store = BitemporalReferenceStore()
        store.append(_spec(1, T0, OPEN, "es_cme_v1"))
        self.assertTrue(
            record_is_visible(store.as_of(ReferenceKind.FUTURES_SPEC, "ES", T_AFTER, T_AFTER), T_AFTER, T_AFTER)
        )

    def test_market_time_before_valid_from_is_none(self) -> None:
        store = BitemporalReferenceStore()
        store.append(_spec(1, T0, OPEN, "es_cme_v1"))
        self.assertIsNone(
            store.as_of(
                ReferenceKind.FUTURES_SPEC,
                "ES",
                "2019-12-31T00:00:00.000000000Z",
                T_AFTER,
            )
        )

    def test_overlap_append_rejected(self) -> None:
        store = BitemporalReferenceStore()
        store.append(_spec(1, T0, OPEN, "es_cme_v1"))
        with self.assertRaises(BitemporalAppendError):
            store.append(_spec(2, T0, OPEN, "es_cme_v1_corrected"))

    def test_missing_known_from_rejected(self) -> None:
        store = BitemporalReferenceStore()
        with self.assertRaises(BitemporalAppendError):
            store.append(_spec(1, "", OPEN, "es_cme_v1"))

    def test_unknown_entity_is_none(self) -> None:
        store = BitemporalReferenceStore()
        self.assertIsNone(store.as_of(ReferenceKind.FUTURES_SPEC, "NQ", T_AFTER, T_AFTER))


if __name__ == "__main__":
    unittest.main()
