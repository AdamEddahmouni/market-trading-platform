from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of03.errors import OF03Error
from market_platform_foundation.of03.loader import load_registry

from tests.of03.support import REPO, sample_capability, sample_sop, sample_workflow, write_registry


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reg"

    def test_cycle_rejected(self) -> None:
        wf = sample_workflow(
            steps=[
                {"step_id": "a", "kind": "PROCEDURE", "next": ["b"]},
                {"step_id": "b", "kind": "PROCEDURE", "next": ["a"]},
            ]
        )
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_missing_terminal_rejected(self) -> None:
        wf = sample_workflow(steps=[{"step_id": "a", "kind": "PROCEDURE", "next": []}])
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_unreachable_rejected(self) -> None:
        wf = sample_workflow(
            steps=[
                {"step_id": "a", "kind": "PROCEDURE", "next": ["done"]},
                {"step_id": "ghost", "kind": "PROCEDURE", "next": ["done"]},
                {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
            ]
        )
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_unknown_capability_rejected(self) -> None:
        wf = sample_workflow(
            capability_refs=[{"capability_id": "NOPE", "capability_version": 1}],
            steps=[
                {"step_id": "a", "kind": "CAPABILITY", "capability_id": "NOPE", "capability_version": 1, "next": ["done"]},
                {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
            ],
        )
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_implicit_latest_on_step_rejected(self) -> None:
        wf = sample_workflow(
            steps=[
                {"step_id": "a", "kind": "CAPABILITY", "capability_id": "TEST.OP.READ", "next": ["done"]},
                {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
            ]
        )
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_branched_acyclic(self) -> None:
        wf = sample_workflow(
            steps=[
                {"step_id": "start", "kind": "GATE", "gate": {"gate_kind": "HUMAN_APPROVAL"}, "next": ["left", "right"]},
                {"step_id": "left", "kind": "CAPABILITY", "capability_id": "TEST.OP.READ", "capability_version": 1, "next": ["done"]},
                {"step_id": "right", "kind": "SOP", "sop_id": "SOP-OF03-001", "sop_version": 1, "next": ["done"]},
                {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
            ],
            entry_step_id="start",
        )
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        registry = load_registry(self.root, repository_root=REPO)
        self.assertTrue(registry.is_valid())
        self.assertEqual(len(registry.workflows[0].domain_reference_requirements), 2)

    def test_invalid_authority_gate(self) -> None:
        wf = sample_workflow(
            steps=[
                {"step_id": "g", "kind": "GATE", "gate": {"gate_kind": "AUTHORITY", "authority_reference": "NOT_REAL"}, "next": ["done"]},
                {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
            ],
            entry_step_id="g",
        )
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[wf])
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)


if __name__ == "__main__":
    unittest.main()
