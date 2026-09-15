"""Unit tests for intelligence ingest boundary guards (Lane G)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.agent_ingest import (
    AgentBotRole,
    AgentClaimType,
    AgentEnrichmentEvidenceV1,
    AgentSkillRef,
    IngestOperation,
)
from market_platform_foundation.intelligence.ingest.boundary import (
    AGENT_ENRICHMENT_MAX_SOURCE_REFS,
    enforce_intelligence_ingest_auth_posture,
    validate_agent_enrichment_ingest_payload,
    validate_agent_enrichment_record_policy,
)
from market_platform_foundation.intelligence.ingest.outbound_policy import (
    validate_outbound_request_headers,
    validate_outbound_target_url,
)
from market_platform_foundation.platform.security.auth_config import AuthEnforcementMode


def _minimal_payload(**overrides) -> dict:
    body = {
        "record_id": "aer-boundary-1",
        "schema_version": "1",
        "opportunity_id": "opp-1",
        "retrieved_at": "2026-09-14T14:00:00+00:00",
        "agent_id": "grok.sentinel.v1",
        "bot_role": "SENTINEL",
        "skill": {"skill_id": "imp.sentinel.verify", "version": "1.0.0"},
        "claim_type": "SUPPORTING_EVIDENCE",
        "confidence": 0.5,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "provenance": {"ingest_plane": "grok", "worker_id": "worker-1"},
        "operation": "ATTACH_EVIDENCE",
    }
    body.update(overrides)
    return body


class AgentEnrichmentIngestBoundaryTests(unittest.TestCase):
    def test_rejects_file_uri_source_ref(self) -> None:
        payload = _minimal_payload(
            source_refs=[
                {
                    "provider_id": "finviz.news",
                    "source_type": "news_article",
                    "source_record_id": "src-1",
                    "raw_reference": "file:///etc/passwd",
                }
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            validate_agent_enrichment_ingest_payload(payload)
        self.assertIn("INGEST_SOURCE_REF_SCHEME_FORBIDDEN", str(ctx.exception))

    def test_rejects_path_traversal_in_source_ref(self) -> None:
        payload = _minimal_payload(
            source_refs=[
                {
                    "provider_id": "finviz.news",
                    "source_type": "news_article",
                    "source_record_id": "src-1",
                    "raw_reference": "https://example.com/../../secret",
                }
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            validate_agent_enrichment_ingest_payload(payload)
        self.assertIn("INGEST_SOURCE_REF_PATH_TRAVERSAL", str(ctx.exception))

    def test_rejects_too_many_source_refs(self) -> None:
        refs = [
            {
                "provider_id": "finviz.news",
                "source_type": "news_article",
                "source_record_id": f"src-{index}",
            }
            for index in range(AGENT_ENRICHMENT_MAX_SOURCE_REFS + 1)
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_agent_enrichment_ingest_payload(_minimal_payload(source_refs=refs))
        self.assertIn("INGEST_SOURCE_REFS_TOO_MANY", str(ctx.exception))

    def test_rejects_bot_role_claim_mismatch(self) -> None:
        record = AgentEnrichmentEvidenceV1(
            record_id="aer-role",
            schema_version="1",
            opportunity_id="opp-1",
            retrieved_at="2026-09-14T14:00:00+00:00",
            agent_id="grok.sentinel.v1",
            bot_role=AgentBotRole.CROWD_WATCH,
            skill=AgentSkillRef(skill_id="imp.sentinel.verify", version="1.0.0"),
            claim_type=AgentClaimType.SUPPORTING_EVIDENCE,
            confidence=0.5,
            expires_at="2099-01-01T00:00:00+00:00",
            provenance={"ingest_plane": "grok"},
            operation=IngestOperation.ATTACH_EVIDENCE,
        )
        with self.assertRaises(ValueError) as ctx:
            validate_agent_enrichment_record_policy(record)
        self.assertIn("INGEST_BOT_ROLE_CLAIM_MISMATCH", str(ctx.exception))

    @patch.dict(os.environ, {"IMP_INTELLIGENCE_INGEST_REQUIRE_ENFORCED": "true"}, clear=False)
    def test_require_enforced_rejects_loopback_trust(self) -> None:
        with patch(
            "market_platform_foundation.intelligence.ingest.boundary.load_auth_config"
        ) as load_config:
            load_config.return_value.enforcement_mode = AuthEnforcementMode.LOOPBACK_TRUST
            with self.assertRaises(ValueError) as ctx:
                enforce_intelligence_ingest_auth_posture()
            self.assertIn("INTELLIGENCE_INGEST_LOOPBACK_TRUST_FORBIDDEN", str(ctx.exception))


class IntelligenceOutboundPolicyTests(unittest.TestCase):
    def test_https_only_outbound(self) -> None:
        validate_outbound_target_url("https://api.example.com/v1/enrich")
        with self.assertRaises(ValueError):
            validate_outbound_target_url("http://api.example.com/v1/enrich")

    def test_rejects_secret_headers(self) -> None:
        with self.assertRaises(ValueError):
            validate_outbound_request_headers({"Authorization": "Bearer x"})


if __name__ == "__main__":
    unittest.main()
