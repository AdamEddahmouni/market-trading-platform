from __future__ import annotations

import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict, write_canonical_json
from market_platform_foundation.of03.errors import OF03Error, OF03ErrorCode
from market_platform_foundation.of03.loader import load_registry
from market_platform_foundation.of03.strategy_families import (
    ADMISSION_KIND_METADATA_ONLY,
    ADMITTED_REASON,
    CORE_CONTRACT_FIELDS,
    admit_strategy_family_fixture,
    load_strategy_family_registry,
)

from tests.of03.support import REPO

FIXTURE_ROOT = REPO / "tests" / "fixtures" / "of03" / "strategy_families"
FAMILY_IDS = ("NEWS_CATALYST", "SQUEEZE", "ORDER_FLOW", "OPTIONS", "FUTURES")
FAMILY_FIXTURES = {
    "NEWS_CATALYST": "news_catalyst.json",
    "SQUEEZE": "squeeze.json",
    "ORDER_FLOW": "order_flow.json",
    "OPTIONS": "options.json",
    "FUTURES": "futures.json",
}


def _load_fixture(name: str) -> dict:
    return copy.deepcopy(load_json_strict(FIXTURE_ROOT / name))


class StrategyFamilyRegistryTests(unittest.TestCase):
    def test_canonical_registry_loads_declared_metadata_only(self) -> None:
        registry = load_strategy_family_registry(fail_closed=True)
        self.assertEqual(registry.snapshot_hash, "BFF1C704B33C2D1CA72A8FD4FF379BAEBB07AB37B5CDCC09BD27F00D351FDD9B")
        ids = tuple(item.family_id for item in registry.families)
        self.assertEqual(ids, FAMILY_IDS)
        for family in registry.families:
            self.assertEqual(family.registration_state.value, "DECLARED")
            self.assertEqual(family.admission_kind, ADMISSION_KIND_METADATA_ONLY)
            self.assertEqual(family.binding.binding_kind.value, "UNBOUND")
            self.assertFalse(family.production_evaluator)
            self.assertFalse(family.mints_opportunity_v1)
            self.assertFalse(family.mints_forecast_v1)
            for field in CORE_CONTRACT_FIELDS:
                self.assertIn(field, family.required_contract_fields)

    def test_capability_snapshot_hash_unchanged(self) -> None:
        capabilities = load_registry(fail_closed=True)
        manifest = load_json_strict(REPO / "config" / "of03" / "manifest.json")
        self.assertEqual(capabilities.snapshot_hash, manifest["registry_snapshot_hash"])

    def test_implicit_latest_prohibited(self) -> None:
        registry = load_strategy_family_registry()
        with self.assertRaises(OF03Error) as ctx:
            registry.resolve_family("NEWS_CATALYST", None)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED)

    def test_python_api_binding_rejected(self) -> None:
        payload = load_json_strict(REPO / "config" / "of03" / "strategy_families.json")
        payload["families"][0]["binding"] = {
            "binding_kind": "PYTHON_API",
            "module": "market_platform_foundation.of03.operations",
            "qualname": "execute",
        }
        payload.pop("registry_snapshot_hash", None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_canonical_json(root / "strategy_families.json", payload)
            with self.assertRaises(OF03Error) as ctx:
                load_strategy_family_registry(root, fail_closed=True)
            self.assertEqual(ctx.exception.code, OF03ErrorCode.UNSAFE_BINDING)


class StrategyFamilyAdmissionTests(unittest.TestCase):
    def test_each_family_fixture_admits_metadata_only(self) -> None:
        registry = load_strategy_family_registry()
        for family_id, filename in FAMILY_FIXTURES.items():
            with self.subTest(family_id=family_id):
                result = admit_strategy_family_fixture(_load_fixture(filename), registry=registry)
                payload = result.to_dict()
                self.assertTrue(result.admitted)
                self.assertEqual(result.family_id, family_id)
                self.assertEqual(result.reason_code, ADMITTED_REASON)
                self.assertEqual(result.admission_kind, ADMISSION_KIND_METADATA_ONLY)
                self.assertFalse(payload["mints_opportunity_v1"])
                self.assertFalse(payload["mints_forecast_v1"])
                self.assertFalse(payload["production_evaluator"])
                self.assertNotIn("rank_score", payload)

    def test_unknown_family_fail_closed(self) -> None:
        fixture = _load_fixture("news_catalyst.json")
        fixture["strategy_family"] = "UNKNOWN_LANE"
        with self.assertRaises(OF03Error) as ctx:
            admit_strategy_family_fixture(fixture)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.UNKNOWN_STRATEGY_FAMILY)

    def test_missing_core_field_fail_closed(self) -> None:
        fixture = _load_fixture("news_catalyst.json")
        del fixture["mechanism"]
        with self.assertRaises(OF03Error) as ctx:
            admit_strategy_family_fixture(fixture)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.MISSING_CONTRACT_FIELD)
        self.assertIn("mechanism", ctx.exception.details["missing"])

    def test_missing_family_field_fail_closed(self) -> None:
        fixture = _load_fixture("news_catalyst.json")
        del fixture["catalyst_event_id"]
        with self.assertRaises(OF03Error) as ctx:
            admit_strategy_family_fixture(fixture)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.MISSING_CONTRACT_FIELD)
        self.assertIn("catalyst_event_id", ctx.exception.details["missing"])

    def test_missing_family_definition_version_fail_closed(self) -> None:
        fixture = _load_fixture("squeeze.json")
        del fixture["family_definition_version"]
        with self.assertRaises(OF03Error) as ctx:
            admit_strategy_family_fixture(fixture)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED)

    def test_admission_does_not_mint_or_scan(self) -> None:
        import market_platform_foundation.of03.strategy_families as module

        source = inspect.getsource(module)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("StrategyPaperRuntime", source)
        self.assertNotIn("import OpportunityV1", source)
        self.assertNotIn("OpportunityV1(", source)
        self.assertNotIn("ForecastV1(", source)
        self.assertNotIn("rank_score", source)
        result = admit_strategy_family_fixture(_load_fixture("order_flow.json"))
        self.assertNotIsInstance(result, dict)
        encoded = json.dumps(result.to_dict())
        self.assertNotIn("rank_score", encoded)
        self.assertNotIn("forecast_id", encoded)


if __name__ == "__main__":
    unittest.main()
