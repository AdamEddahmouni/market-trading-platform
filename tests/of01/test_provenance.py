from __future__ import annotations

import unittest

from market_platform_foundation.of01.commands import AttachProvenanceReference
from market_platform_foundation.of01.errors import OF01Error
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.records import ProvenanceReferenceRecord, ReferenceKind
from market_platform_foundation.of01.source_attribution import validate_attach_provenance_reference


class TestProvenanceValidation(unittest.TestCase):
    def test_valid_configuration_reference(self) -> None:
        ref = ProvenanceReferenceRecord(
            provenance_ref_id=new_uuid(),
            run_id=new_uuid(),
            attempt_id=None,
            reference_kind=ReferenceKind.CONFIGURATION,
            canonical_identity="config://runtime/profile",
            canonical_version="1",
            canonical_hash=None,
            available_at_ns=None,
            coverage_start_ns=None,
            coverage_end_ns=None,
            artifact_id=None,
            limitations=None,
        )
        validate_attach_provenance_reference(AttachProvenanceReference(provenance_reference=ref))

    def test_rejects_inverted_coverage(self) -> None:
        ref = ProvenanceReferenceRecord(
            provenance_ref_id=new_uuid(),
            run_id=new_uuid(),
            attempt_id=None,
            reference_kind=ReferenceKind.DATA,
            canonical_identity="dataset://prices",
            canonical_version=None,
            canonical_hash=None,
            available_at_ns=None,
            coverage_start_ns=200,
            coverage_end_ns=100,
            artifact_id=None,
            limitations=None,
        )
        with self.assertRaises(OF01Error):
            validate_attach_provenance_reference(AttachProvenanceReference(provenance_reference=ref))


if __name__ == "__main__":
    unittest.main()
