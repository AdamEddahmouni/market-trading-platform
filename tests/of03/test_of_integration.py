from __future__ import annotations

import unittest

from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.memory import InMemoryLedger
from market_platform_foundation.of01.records import (
    ActionCategory,
    ConsequenceProfile,
    OutcomeValidity,
    ProvenanceQualifier,
    TerminalResult,
)
from market_platform_foundation.of02.contracts import AttemptSpec, AttributionRequest, DomainIdentity
from market_platform_foundation.of02.lifecycle import attribute
from market_platform_foundation.of03.loader import load_registry
from market_platform_foundation.of03.provenance import capability_reference, registry_snapshot_extra, workflow_reference


class OfIntegrationTests(unittest.TestCase):
    def test_registry_snapshot_attributed_to_of01_not_second_ledger(self) -> None:
        registry = load_registry(fail_closed=True)
        extra = registry_snapshot_extra(registry)
        extra["capability"] = capability_reference(registry, "OF03.OP.VALIDATE", 1).to_mapping()
        extra["workflow"] = workflow_reference(registry, "WF-OF03-003", 1).to_mapping()
        ledger = InMemoryLedger(new_uuid())
        request = AttributionRequest(
            adapter_id="operational_drill",
            operation_class="OPERATIONAL_DRILL",
            objective="OF-03 registry validation acceptance",
            consequence_profile=ConsequenceProfile.C2_GOVERNED,
            provenance_qualifier=ProvenanceQualifier.NATIVE,
            domain_identities=(DomainIdentity(system="of03", id_type="snapshot", value=registry.snapshot_hash),),
            attempts=(AttemptSpec(sequence=1, terminal_result=TerminalResult.COMPLETED, reason_code="ATTEMPT_COMPLETED"),),
            outcome_type="REGISTRY_VALIDATION",
            validity=OutcomeValidity.VALID,
            disposition_action=ActionCategory.ACCEPT,
            disposition_domain_code="REGISTRY_VALID",
            extra=extra,
        )
        result = attribute(request, writer=ledger, enabled=True)
        self.assertEqual(result.status.value, "COMMITTED")
        run = ledger.get_record("RUN", result.run_id)
        self.assertEqual(run.objective, "OF-03 registry validation acceptance")
        self.assertEqual(extra["registry_snapshot_hash"], registry.snapshot_hash)
        self.assertNotEqual(result.run_id, "WF-OF03-003")


if __name__ == "__main__":
    unittest.main()
