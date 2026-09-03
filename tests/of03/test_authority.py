from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of03.agent_policy import authorize_execution_from_registry, evaluate_agent_use
from market_platform_foundation.of03.enums import AgentUseDecision
from market_platform_foundation.of03.errors import OF03Error, OF03ErrorCode
from market_platform_foundation.of03.loader import load_registry

from tests.of03.support import REPO, sample_capability, sample_sop, sample_workflow, write_registry


class AuthorityNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "reg"

    def test_unknown_authority_is_error(self) -> None:
        write_registry(
            self.root,
            capabilities=[sample_capability(required_authority_refs=["NOT_A_REAL_AUTHORITY"])],
            sops=[sample_sop()],
            workflows=[sample_workflow()],
        )
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_registry_cannot_grant_promotion_or_live_authority(self) -> None:
        write_registry(
            self.root,
            capabilities=[
                sample_capability(
                    capability_id="TEST.OP.PROMOTE",
                    required_authority_refs=["MODEL_PROMOTION_AUTHORITY"],
                    automation_policy="AGENT_PROHIBITED",
                    human_approval_policy="REQUIRED",
                    effect_class="AUTHORITATIVE_MUTATION",
                    consequence_profile="C3_EVIDENCE_CRITICAL",
                    sop_refs=[{"sop_id": "SOP-OF03-001", "sop_version": 1}],
                )
            ],
            sops=[sample_sop(related_capability_refs=[{"capability_id": "TEST.OP.PROMOTE", "capability_version": 1}])],
            workflows=[
                sample_workflow(
                    capability_refs=[{"capability_id": "TEST.OP.PROMOTE", "capability_version": 1}],
                    steps=[
                        {"step_id": "a", "kind": "CAPABILITY", "capability_id": "TEST.OP.PROMOTE", "capability_version": 1, "next": ["done"]},
                        {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
                    ],
                )
            ],
        )
        registry = load_registry(self.root, repository_root=REPO)
        cap = registry.capability("TEST.OP.PROMOTE", 1)
        with self.assertRaises(OF03Error) as ctx:
            authorize_execution_from_registry(cap)
        self.assertEqual(ctx.exception.code, OF03ErrorCode.REGISTRY_DOES_NOT_GRANT_AUTHORITY)
        self.assertEqual(evaluate_agent_use(cap, intent="EXECUTE"), AgentUseDecision.DENIED_AGENT_PROHIBITED)
        live = sample_capability(
            capability_id="TEST.OP.LIVE",
            required_authority_refs=["LIVE_ORDER_AUTHORITY"],
            automation_policy="AGENT_PROHIBITED",
            human_approval_policy="REQUIRED",
            effect_class="EXTERNAL_SIDE_EFFECT",
        )
        write_registry(
            self.root,
            capabilities=[live],
            sops=[sample_sop(related_capability_refs=[{"capability_id": "TEST.OP.LIVE", "capability_version": 1}])],
            workflows=[
                sample_workflow(
                    capability_refs=[{"capability_id": "TEST.OP.LIVE", "capability_version": 1}],
                    steps=[
                        {"step_id": "a", "kind": "CAPABILITY", "capability_id": "TEST.OP.LIVE", "capability_version": 1, "next": ["done"]},
                        {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
                    ],
                )
            ],
        )
        cap2 = load_registry(self.root, repository_root=REPO).capability("TEST.OP.LIVE", 1)
        self.assertEqual(evaluate_agent_use(cap2, intent="EXECUTE"), AgentUseDecision.DENIED_AGENT_PROHIBITED)
        with self.assertRaises(OF03Error):
            authorize_execution_from_registry(cap2)

    def test_human_approval_cannot_claim_automation_allowed(self) -> None:
        write_registry(
            self.root,
            capabilities=[sample_capability(automation_policy="AUTOMATION_ALLOWED", human_approval_policy="REQUIRED")],
            sops=[sample_sop()],
            workflows=[sample_workflow()],
        )
        with self.assertRaises(OF03Error):
            load_registry(self.root, repository_root=REPO, fail_closed=True)

    def test_no_runtime_policy_mutation(self) -> None:
        write_registry(self.root, capabilities=[sample_capability()], sops=[sample_sop()], workflows=[sample_workflow()])
        registry = load_registry(self.root, repository_root=REPO)
        with self.assertRaises(AttributeError):
            registry.capabilities[0].automation_policy = "AUTOMATION_ALLOWED"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
