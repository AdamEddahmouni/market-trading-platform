"""Tests for Wave B provider capability-matrix foundation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.providers.capability_contract import (
    CapabilityAccessState,
    CapabilityContractError,
    CapabilityMatrixSnapshot,
    CapabilitySupportLevel,
    CampaignRole,
    ProviderCapabilityEntry,
    ProviderCapabilityRecord,
    redact_mapping,
    validate_provider_record,
    validate_snapshot,
)
from market_platform_foundation.providers.capability_snapshot import (
    build_capability_matrix_snapshot,
    serialize_snapshot,
)


class CapabilityContractTests(unittest.TestCase):
    def test_promoted_without_evidence_fails(self) -> None:
        record = ProviderCapabilityRecord(
            provider_id="example",
            access_state=CapabilityAccessState.PROMOTED,
            campaign_role=CampaignRole.UNASSIGNED,
            support_level=CapabilitySupportLevel.KNOWN_SUPPORTED,
            capabilities=(
                ProviderCapabilityEntry("US_EQUITY_L1", CapabilitySupportLevel.KNOWN_SUPPORTED),
            ),
            verification_evidence=(),
        )
        with self.assertRaises(CapabilityContractError):
            validate_provider_record(record)

    def test_unknown_support_cannot_be_promoted_at_capability_level(self) -> None:
        record = ProviderCapabilityRecord(
            provider_id="example",
            access_state=CapabilityAccessState.SAMPLE_VERIFIED,
            campaign_role=CampaignRole.UNASSIGNED,
            support_level=CapabilitySupportLevel.KNOWN_SUPPORTED,
            capabilities=(
                ProviderCapabilityEntry(
                    "US_FUTURES_QUOTE",
                    CapabilitySupportLevel.UNKNOWN,
                    access_state=CapabilityAccessState.PROMOTED,
                ),
            ),
            verification_evidence=("evidence/fixture.json",),
        )
        with self.assertRaises(CapabilityContractError):
            validate_provider_record(record)

    def test_unsupported_vs_unknown_semantics(self) -> None:
        unsupported = ProviderCapabilityEntry(
            "OPTIONS_EXECUTION_DATA",
            CapabilitySupportLevel.KNOWN_UNSUPPORTED,
            access_state=CapabilityAccessState.CATALOGED,
        )
        unknown = ProviderCapabilityEntry(
            "US_FUTURES_QUOTE",
            CapabilitySupportLevel.UNKNOWN,
        )
        self.assertEqual(unsupported.support_level, CapabilitySupportLevel.KNOWN_UNSUPPORTED)
        self.assertEqual(unknown.support_level, CapabilitySupportLevel.UNKNOWN)

    def test_secret_redaction(self) -> None:
        payload = {
            "api_key": "sk-abcdefghijklmnopqrstuvwxyz",
            "notes": "token=AKIAIOSFODNN7EXAMPLE",
        }
        redacted = redact_mapping(payload)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", json.dumps(redacted))
        self.assertEqual(redacted["api_key"], "[REDACTED]")


class CapabilitySnapshotTests(unittest.TestCase):
    def test_build_snapshot_is_deterministic_for_provider_order(self) -> None:
        root = Path(__file__).resolve().parents[2]
        first = build_capability_matrix_snapshot(
            repository_root=root,
            observed_at="2026-09-11T23:00:00Z",
            readiness_report={"providers": []},
        )
        second = build_capability_matrix_snapshot(
            repository_root=root,
            observed_at="2026-09-11T23:00:00Z",
            readiness_report={"providers": []},
        )
        self.assertEqual(serialize_snapshot(first), serialize_snapshot(second))
        ids = [row.provider_id for row in first.providers]
        self.assertEqual(ids, sorted(ids))
        self.assertFalse(first.secrets_included)

    def test_snapshot_serializes_without_secrets_from_readiness(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            env_root = Path(tmp)
            (env_root / ".env").write_text("IMP_TRADIER_TOKEN=super-secret-token-value\n", encoding="utf-8")
            from tools.provider_readiness import collect_readiness

            readiness = collect_readiness(
                {"IMP_TRADIER_PAPER": "1", "IMP_BROKER_PAPER_EXECUTION": "1"},
                repository_root=env_root,
            )
            snapshot = build_capability_matrix_snapshot(
                repository_root=root,
                readiness_report=readiness,
                observed_at="2026-09-11T23:00:00Z",
            )
            serialized = serialize_snapshot(snapshot)
            self.assertNotIn("super-secret-token-value", serialized)
            validate_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
