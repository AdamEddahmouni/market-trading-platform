from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of03.canonical import definition_hash_from_obj
from market_platform_foundation.of03.errors import OF03Error, OF03ErrorCode
from market_platform_foundation.of03.loader import load_registry, snapshot_payload

from tests.of03.support import REPO, sample_capability, sample_sop, sample_workflow, write_registry


class HashAndSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reg"

    def test_definition_hash_stable_and_excludes_hash_field(self) -> None:
        a = sample_capability()
        b = dict(a)
        b["definition_hash"] = "DEADBEEF"
        self.assertEqual(definition_hash_from_obj(a), definition_hash_from_obj(b))

    def test_semantic_change_changes_hash(self) -> None:
        a = sample_capability()
        b = sample_capability(title="other")
        self.assertNotEqual(definition_hash_from_obj(a), definition_hash_from_obj(b))

    def test_same_id_version_conflict(self) -> None:
        write_registry(
            self.root,
            capabilities=[sample_capability(), sample_capability(title="dup")],
            sops=[sample_sop()],
            workflows=[sample_workflow()],
        )
        with self.assertRaises(OF03Error) as ctx:
            load_registry(self.root, repository_root=REPO, fail_closed=True)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.REGISTRY_INVALID)

    def test_snapshot_ignores_file_and_key_order(self) -> None:
        caps = [sample_capability(), sample_capability(capability_id="TEST.OP.OTHER", sop_refs=[{"sop_id": "SOP-OF03-001", "sop_version": 1}])]
        sops = [sample_sop(related_capability_refs=[{"capability_id": "TEST.OP.READ", "capability_version": 1}, {"capability_id": "TEST.OP.OTHER", "capability_version": 1}])]
        wfs = [sample_workflow(capability_refs=[{"capability_id": "TEST.OP.READ", "capability_version": 1}, {"capability_id": "TEST.OP.OTHER", "capability_version": 1}])]
        write_registry(self.root, capabilities=caps, sops=sops, workflows=wfs)
        first = load_registry(self.root, repository_root=REPO)
        write_registry(self.root, capabilities=list(reversed(caps)), sops=sops, workflows=wfs)
        second = load_registry(self.root, repository_root=REPO)
        self.assertEqual(first.snapshot_hash, second.snapshot_hash)
        payload = snapshot_payload(first)
        self.assertEqual(payload["capabilities"], sorted(payload["capabilities"], key=lambda x: (x["capability_id"], x["definition_version"])))

    def test_active_pointer_changes_snapshot(self) -> None:
        v1 = sample_capability()
        v2 = sample_capability(definition_version=2, title="v2")
        write_registry(self.root, capabilities=[v1, v2], sops=[sample_sop()], workflows=[sample_workflow()], active_capabilities={"TEST.OP.READ": 1})
        a = load_registry(self.root, repository_root=REPO)
        write_registry(self.root, capabilities=[v1, v2], sops=[sample_sop()], workflows=[sample_workflow()], active_capabilities={"TEST.OP.READ": 2})
        b = load_registry(self.root, repository_root=REPO)
        self.assertNotEqual(a.snapshot_hash, b.snapshot_hash)
        old = a.capability("TEST.OP.READ", 1)
        self.assertEqual(old.title, "Read")
        self.assertEqual(b.capability("TEST.OP.READ", 1).definition_hash, old.definition_hash)

    def test_implicit_latest_prohibited(self) -> None:
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[sample_workflow()])
        registry = load_registry(self.root, repository_root=REPO)
        with self.assertRaises(OF03Error) as ctx:
            registry.resolve_capability("TEST.OP.READ", None)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED)

    def test_windows_path_nonsemantic_in_snapshot(self) -> None:
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[sample_workflow()])
        registry = load_registry(self.root, repository_root=REPO)
        self.assertNotIn("\\", json.dumps(snapshot_payload(registry)))
        self.assertNotIn(str(self.root), registry.snapshot_hash)


class CanonicalRegistryTests(unittest.TestCase):
    def test_canonical_registry_loads(self) -> None:
        registry = load_registry(fail_closed=True)
        self.assertTrue(registry.is_valid())
        self.assertGreaterEqual(len(registry.capabilities), 84)
        self.assertEqual(len(registry.sops), 40)
        self.assertEqual(len(registry.workflows), 30)
        self.assertEqual(registry.capability("OF01.OP.RESTORE_ACTIVATE", 1).binding.binding_kind.value, "UNBOUND")
        smoke = registry.capability("OF02.ADAPTER.provider_smoke", 1)
        self.assertEqual(smoke.availability_probe if False else smoke.raw.get("availability_probe"), "LIVE_PROVIDER")
        eval_cap = registry.capability("OF02.ADAPTER.evaluation", 1)
        self.assertGreaterEqual(len(eval_cap.domain_reference_requirements), 2)


if __name__ == "__main__":
    unittest.main()
