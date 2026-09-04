from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of03.bindings import verify_binding
from market_platform_foundation.of03.contracts import CapabilityDefinition
from market_platform_foundation.of03.errors import OF03Error
from market_platform_foundation.of03.loader import inspect_capability, load_registry

from tests.of03.support import REPO, sample_capability, sample_sop, sample_workflow, write_registry


class BindingSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reg"

    def _load(self, cap: dict):
        write_registry(self.root, capabilities=[cap], sops=[sample_sop()], workflows=[sample_workflow()])
        return load_registry(self.root, repository_root=REPO, fail_closed=False)

    def test_arbitrary_import_blocked(self) -> None:
        cap = sample_capability(binding={"binding_kind": "PYTHON_API", "module": "os", "qualname": "system"})
        registry = self._load(cap)
        self.assertFalse(registry.is_valid())

    def test_path_traversal_blocked(self) -> None:
        cap = sample_capability(binding={"binding_kind": "PYTHON_API", "module": "market_platform_foundation.of03../../secrets", "qualname": "x"})
        registry = self._load(cap)
        self.assertFalse(registry.is_valid())

    def test_shell_binding_rejected(self) -> None:
        cap = sample_capability(binding={"binding_kind": "PYTHON_API", "module": "market_platform_foundation.of03.operations", "qualname": "execute", "shell": "rm -rf /"})
        with self.assertRaises(OF03Error):
            CapabilityDefinition.from_mapping(cap)

    def test_unknown_binding_kind(self) -> None:
        cap = sample_capability(binding={"binding_kind": "SHELL_COMMAND", "module": "market_platform_foundation.of03.operations", "qualname": "execute"})
        with self.assertRaises(Exception):
            CapabilityDefinition.from_mapping(cap)

    def test_missing_callable(self) -> None:
        cap = sample_capability(binding={"binding_kind": "PYTHON_API", "module": "market_platform_foundation.of03.operations", "qualname": "does_not_exist"})
        registry = self._load(cap)
        self.assertFalse(registry.is_valid())

    def test_unbound_ok(self) -> None:
        cap = sample_capability(binding={"binding_kind": "UNBOUND"})
        registry = self._load(cap)
        self.assertTrue(registry.is_valid())
        report = inspect_capability(registry, registry.capabilities[0])
        self.assertFalse(report["bound"])
        self.assertEqual(report["availability"], "UNBOUND")
        self.assertFalse(report["binding_invoked"])

    def test_feature_disabled_bound_capability(self) -> None:
        cap = sample_capability(feature_gates=[{"kind": "ENV_TRUTHY", "name": "IMP_OF03_TEST_GATE_NEVER"}])
        registry = self._load(cap)
        report = inspect_capability(registry, registry.capabilities[0])
        self.assertTrue(report["bound"])
        self.assertEqual(report["availability"], "DISABLED")

    def test_verification_does_not_call_execute(self) -> None:
        cap = CapabilityDefinition.from_mapping(sample_capability())
        report = verify_binding(cap, repository_root=REPO)
        self.assertTrue(report["ok"])
        self.assertFalse(report["invoked"])


if __name__ == "__main__":
    unittest.main()
