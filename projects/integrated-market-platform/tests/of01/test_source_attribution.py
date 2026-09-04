from __future__ import annotations

import unittest

from market_platform_foundation.of01.commands import AttachSourceAttribution
from market_platform_foundation.of01.errors import OF01Error
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.records import SourceAttributionRecord, SourceState
from market_platform_foundation.of01.source_attribution import (
    normalize_repository_identity,
    validate_attach_source_attribution,
    validate_stable_identity,
)


class TestSourceAttributionValidation(unittest.TestCase):
    def test_clean_committed_requires_no_capsule(self) -> None:
        source = SourceAttributionRecord(
            source_attribution_id=new_uuid(),
            run_id=new_uuid(),
            repository_identity="github.com/org/repo",
            root_identity="main",
            base_revision="abc123",
            source_state=SourceState.CLEAN_COMMITTED,
            scope_manifest_artifact_id=None,
            capsule_artifact_id=None,
            outside_scope_proof_artifact_id=None,
            limitations=None,
        )
        command = AttachSourceAttribution(source_attribution=source)
        validate_attach_source_attribution(command, {})

    def test_dirty_attributable_requires_capsule(self) -> None:
        source = SourceAttributionRecord(
            source_attribution_id=new_uuid(),
            run_id=new_uuid(),
            repository_identity="github.com/org/repo",
            root_identity="feature/x",
            base_revision=None,
            source_state=SourceState.DIRTY_ATTRIBUTABLE,
            scope_manifest_artifact_id=None,
            capsule_artifact_id=new_uuid(),
            outside_scope_proof_artifact_id=None,
            limitations=None,
        )
        command = AttachSourceAttribution(source_attribution=source)
        with self.assertRaises(OF01Error):
            validate_attach_source_attribution(command, {})

    def test_rejects_absolute_path(self) -> None:
        with self.assertRaises(OF01Error):
            validate_stable_identity("C:\\secrets\\repo", field="repository_identity")

    def test_rejects_secret_marker(self) -> None:
        with self.assertRaises(OF01Error):
            validate_stable_identity("api_key=deadbeef", field="root_identity")

    def test_normalizes_repository_identity(self) -> None:
        self.assertEqual(
            normalize_repository_identity("github.com/org/repo"),
            "github.com/org/repo",
        )


if __name__ == "__main__":
    unittest.main()
