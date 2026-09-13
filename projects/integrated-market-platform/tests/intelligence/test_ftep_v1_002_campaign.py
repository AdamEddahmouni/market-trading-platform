"""FTEP-V1-002 US equity news-catalyst pivot tests (section 24)."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    ActivationManifestStatus,
    compute_manifest_fingerprint,
    load_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.campaign_readiness import (  # noqa: E402
    CampaignReadinessDisposition,
    evaluate_campaign_readiness,
)
from market_platform_foundation.intelligence.paper_forward_bridge.frozen_manifest_verifier import (  # noqa: E402
    FrozenProspectiveDisposition,
    verify_ftep_v1_001_frozen_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_profile_refs import (  # noqa: E402
    load_ftep_v1_002_profile_stack,
)
from market_platform_foundation.intelligence.paper_forward_bridge.preflight import (  # noqa: E402
    PreflightDisposition,
    run_forward_test_preflight,
)
from market_platform_foundation.providers.capability_requirements import (  # noqa: E402
    FTEP_V1_002_US_EQUITY_NEWS_PROFILE,
    get_campaign_requirement_profile,
)
from market_platform_foundation.providers.moomoo_prospective_market_evidence import (  # noqa: E402
    ProspectiveMarketEvidenceDisposition,
    assess_moomoo_prospective_market_evidence,
)

_EXPECTED_V1_001_FINGERPRINT = (
    "69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C"
)


class FtepV1001FrozenInvariantTests(unittest.TestCase):
    def test_v1_001_fingerprint_unchanged(self) -> None:
        path = ROOT / "artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw["fingerprint"], _EXPECTED_V1_001_FINGERPRINT)
        self.assertEqual(raw["manifest_fingerprint"], _EXPECTED_V1_001_FINGERPRINT)
        manifest = load_activation_manifest("FTEP-V1-001")
        self.assertEqual(manifest.status, ActivationManifestStatus.FROZEN)
        self.assertEqual(compute_manifest_fingerprint(manifest.raw), _EXPECTED_V1_001_FINGERPRINT)

    def test_v1_001_frozen_verifier_external_entitlement_block(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"
        try:
            result = verify_ftep_v1_001_frozen_manifest(
                ROOT,
                readiness_report={"providers": []},
            )
        finally:
            os.environ.pop("IMP_PERSIST_STATE", None)
        self.assertTrue(result.fingerprint_verified)
        self.assertEqual(
            result.prospective_disposition,
            FrozenProspectiveDisposition.FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT,
        )
        self.assertIn("CAP-REQ-futures.es_quote.moomoo", result.coverage_gap_blockers)


class FtepV1002ProfileTests(unittest.TestCase):
    def test_v1_002_requirement_profile_equity_not_futures(self) -> None:
        profile = get_campaign_requirement_profile("FTEP-V1-002")
        self.assertEqual(profile.profile_id, FTEP_V1_002_US_EQUITY_NEWS_PROFILE.profile_id)
        req_ids = {row.requirement_id for row in profile.capability_requirements}
        self.assertIn("equity.us_l1.moomoo", req_ids)
        self.assertNotIn("futures.es_quote.moomoo", req_ids)

    def test_v1_002_profile_stack_loads(self) -> None:
        stack = load_ftep_v1_002_profile_stack(repo_root=ROOT)
        ids = {row.profile_version_id for row in stack}
        self.assertIn("US_EQUITY_PROFILE_V1", ids)
        self.assertIn("CATALYST_TAXONOMY_CONTRACT_V1", ids)

    def test_v1_002_manifest_frozen_with_owner_universe(self) -> None:
        manifest = load_activation_manifest("FTEP-V1-002")
        self.assertEqual(manifest.status, ActivationManifestStatus.FROZEN)
        self.assertEqual(manifest.binding["universe"]["asset_class"], "US_EQUITY")
        symbols = set(manifest.binding["universe"]["symbols"])
        self.assertEqual(symbols, {"AAPL", "MSFT", "NVDA", "AMZN", "META"})
        benchmark = manifest.binding["universe"].get("benchmark_symbols") or []
        self.assertEqual(list(benchmark), ["SPY"])
        self.assertFalse(manifest.owner_decisions_pending)

    def test_v1_002_preflight_ready_when_frozen(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"
        try:
            preflight = run_forward_test_preflight(campaign_slug="FTEP-V1-002", mode="PAPER")
        finally:
            os.environ.pop("IMP_PERSIST_STATE", None)
        self.assertEqual(preflight.disposition, PreflightDisposition.READY)
        manifest = load_activation_manifest("FTEP-V1-002")
        self.assertEqual(
            manifest.paper_account_id,
            "7CBA5536EED17C4A6246327EE7ABF223C58627660B93A642D8A99C2AEC10A579",
        )

    def test_moomoo_equity_market_evidence_sample_verified(self) -> None:
        assessment = assess_moomoo_prospective_market_evidence("FTEP-V1-002", repository_root=ROOT)
        self.assertEqual(assessment.capability_id, "US_EQUITY_L1")
        self.assertEqual(assessment.disposition, ProspectiveMarketEvidenceDisposition.SAMPLE_VERIFIED)

    def test_v1_002_campaign_readiness_includes_market_evidence_metadata(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"
        try:
            result = evaluate_campaign_readiness(
                "FTEP-V1-002",
                repository_root=ROOT,
                readiness_report={"providers": []},
            )
        finally:
            os.environ.pop("IMP_PERSIST_STATE", None)
        self.assertIn("prospective_market_evidence", result.metadata)
        self.assertEqual(
            result.metadata["prospective_market_evidence"]["disposition"],
            "SAMPLE_VERIFIED",
        )
        self.assertNotIn("COVERAGE_GAP:WAVE-A-002", result.blockers)
        self.assertEqual(result.disposition, CampaignReadinessDisposition.READY)


if __name__ == "__main__":
    unittest.main()
