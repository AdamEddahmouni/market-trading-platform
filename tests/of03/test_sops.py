from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of03.contracts import SopDefinition
from market_platform_foundation.of03.errors import OF03Error
from market_platform_foundation.of03.loader import load_registry

from tests.of03.support import REPO, sample_capability, sample_sop, sample_workflow, write_registry


class SopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reg"

    def test_missing_document(self) -> None:
        write_registry(
            self.root,
            capabilities=[sample_capability()],
            sops=[sample_sop(document_path="docs/operations/missing/SOPS.md")],
            workflows=[sample_workflow()],
        )
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_missing_anchor(self) -> None:
        write_registry(
            self.root,
            capabilities=[sample_capability()],
            sops=[sample_sop(document_anchor="SOP-DOES-NOT-EXIST", sop_id="SOP-DOES-NOT-EXIST")],
            workflows=[sample_workflow(sop_refs=[{"sop_id": "SOP-DOES-NOT-EXIST", "sop_version": 1}])],
        )
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_exercised_maturity_rejected(self) -> None:
        with self.assertRaises(Exception):
            SopDefinition.from_mapping(sample_sop(maturity="EXERCISED"))

    def test_deprecated_remains_resolvable(self) -> None:
        old = sample_sop(deprecation={"deprecated": True, "superseded_by": {"id": "SOP-OF03-001", "version": 2}})
        new = sample_sop(definition_version=2, title="Inspect registry status v2")
        write_registry(
            self.root,
            capabilities=[sample_capability()],
            sops=[old, new],
            workflows=[sample_workflow(sop_refs=[{"sop_id": "SOP-OF03-001", "sop_version": 2}])],
            active_sops={"SOP-OF03-001": 2},
        )
        registry = load_registry(self.root, repository_root=REPO)
        self.assertTrue(registry.sop("SOP-OF03-001", 1).deprecation.deprecated)
        self.assertEqual(registry.sop("SOP-OF03-001", 2).title, "Inspect registry status v2")

    def test_deprecated_without_replacement(self) -> None:
        write_registry(
            self.root,
            capabilities=[sample_capability()],
            sops=[sample_sop(deprecation={"deprecated": True})],
            workflows=[sample_workflow()],
        )
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)


if __name__ == "__main__":
    unittest.main()
