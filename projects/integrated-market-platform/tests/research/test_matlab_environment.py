"""QR-01 MATLAB toolbox honesty recorder tests (no MATLAB runtime)."""

from __future__ import annotations

import copy
import json
import unittest

from market_platform_foundation.research.matlab_environment import (
    MATLAB_TOOLBOX_MANIFEST_SCHEMA_VERSION,
    cloud_unavailable_toolbox_manifest,
    load_toolbox_manifest_example,
    toolbox_manifest_schema_path,
    validate_toolbox_manifest,
)


class MatlabEnvironmentTests(unittest.TestCase):
    def test_committed_example_is_unavailable_honest(self) -> None:
        example = load_toolbox_manifest_example()
        validate_toolbox_manifest(example)
        self.assertEqual(example["schema_version"], MATLAB_TOOLBOX_MANIFEST_SCHEMA_VERSION)
        self.assertEqual(example["matlab_release"], "UNAVAILABLE")
        self.assertIsNone(example["matlab_root"])
        self.assertEqual(example["smoke_status"], "BLOCKED_NO_MATLAB")
        self.assertFalse(example["isolation"]["production_runtime"])
        self.assertEqual(example["isolation"]["mode_authority"], "NONE")
        self.assertEqual(example["isolation"]["paper_live_broker"], "DENIED")
        self.assertEqual(cloud_unavailable_toolbox_manifest(), example)
        schema = json.loads(toolbox_manifest_schema_path().read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "imp://research/matlab-toolbox-manifest/1.0.0")
        products = {row["product"]: row for row in example["toolboxes"]}
        self.assertEqual(products["MATLAB"]["status"], "UNAVAILABLE")
        self.assertEqual(products["Datafeed Toolbox"]["status"], "PROHIBITED")
        self.assertEqual(products["Database Toolbox"]["class"], "PROHIBITED_AS_CANONICAL")

    def test_installed_claim_without_release_fails(self) -> None:
        payload = copy.deepcopy(load_toolbox_manifest_example())
        payload["toolboxes"][0]["status"] = "INSTALLED"
        with self.assertRaises(ValueError) as ctx:
            validate_toolbox_manifest(payload)
        self.assertTrue(str(ctx.exception).startswith("MATLAB_INSTALLED_WITHOUT_RELEASE"))

    def test_prohibited_toolbox_cannot_be_installed(self) -> None:
        payload = copy.deepcopy(load_toolbox_manifest_example())
        payload["matlab_release"] = "R2024b"
        for entry in payload["toolboxes"]:
            if entry["product"] == "Datafeed Toolbox":
                entry["status"] = "INSTALLED"
        with self.assertRaises(ValueError) as ctx:
            validate_toolbox_manifest(payload)
        self.assertEqual(str(ctx.exception), "MATLAB_PROHIBITED_TOOLBOX_NOT_LOCKED:Datafeed Toolbox")

    def test_production_runtime_isolation_is_required(self) -> None:
        payload = copy.deepcopy(load_toolbox_manifest_example())
        payload["isolation"]["production_runtime"] = True
        with self.assertRaises(ValueError) as ctx:
            validate_toolbox_manifest(payload)
        self.assertEqual(str(ctx.exception), "MATLAB_PRODUCTION_RUNTIME_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
