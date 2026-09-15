"""ENFORCED-mode HTTP integration tests for agent enrichment ingest (Lane G)."""

from __future__ import annotations

import http.client
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.agent_ingest import ForbiddenIngestMutation  # noqa: E402
from market_platform_foundation.intelligence.contracts.common import (  # noqa: E402
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1  # noqa: E402
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.platform.security.access_control import (  # noqa: E402
    AuthorizationFailure,
    login_principal,
    reset_principal_registry_for_tests,
)
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402

PRINCIPALS_FIXTURE = ROOT / "fixtures" / "auth" / "principals.json"


def _payload(opportunity_id: str = "opp-enforced") -> dict:
    return {
        "record_id": "aer-enforced-1",
        "schema_version": "1",
        "opportunity_id": opportunity_id,
        "retrieved_at": "2026-09-14T14:00:00+00:00",
        "agent_id": "grok.sentinel.v1",
        "bot_role": "SENTINEL",
        "skill": {"skill_id": "imp.sentinel.verify", "version": "1.0.0"},
        "claim_type": "SUPPORTING_EVIDENCE",
        "confidence": 0.5,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "provenance": {"ingest_plane": "grok", "worker_id": "http-test"},
        "operation": "ATTACH_EVIDENCE",
        "claim_body": {"summary": "enforced http test"},
    }


class _MiniStore:
    def __init__(self, strategy_repository) -> None:
        self.strategy_repository = strategy_repository


class AgentEnrichmentIngestEnforcedHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._httpd: ThreadingHTTPServer | None = None
        cls._thread: threading.Thread | None = None
        cls._port = 0

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._httpd is not None:
            cls._httpd.shutdown()
            cls._httpd.server_close()
        if cls._thread is not None:
            cls._thread.join(timeout=5)

    def setUp(self) -> None:
        reset_principal_registry_for_tests()
        self._env_backup = dict(os.environ)
        os.environ["IMP_AUTH_ENFORCEMENT_MODE"] = "ENFORCED"
        os.environ["IMP_AUTH_PRINCIPALS_PATH"] = str(PRINCIPALS_FIXTURE)
        os.environ["IMP_AUTH_SESSION_TTL_SECONDS"] = "3600"

        self.repo = InMemoryIntelligenceRepository()
        self.repo.put_opportunity(
            OpportunityV1(
                opportunity_id="opp-enforced",
                schema_version="1",
                scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
                created_at_ns=10_000,
                quality=QualitySummary(state=QualityState.GOOD),
                side=OpportunitySide.LONG,
                reason_summary="ENFORCED HTTP test opportunity",
            )
        )
        UiApiHandler.store = _MiniStore(self.repo)
        if self.__class__._httpd is None:
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
            self.__class__._httpd = httpd
            self.__class__._port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.__class__._thread = thread

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        reset_principal_registry_for_tests()

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes,
        headers: dict[str, str] | None = None,
    ) -> http.client.HTTPResponse:
        conn = http.client.HTTPConnection("127.0.0.1", self.__class__._port, timeout=10)
        request_headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        if headers:
            request_headers.update(headers)
        conn.request(method, path, body=body, headers=request_headers)
        return conn.getresponse()

    def _operator_token(self) -> str:
        login = login_principal(principal_id="paper-operator", secret="paper-operator-secret")
        self.assertNotIsInstance(login, AuthorizationFailure)
        session, _ = login
        return session.token

    def _viewer_token(self) -> str:
        login = login_principal(principal_id="canary-viewer", secret="canary-viewer-secret")
        self.assertNotIsInstance(login, AuthorizationFailure)
        session, _ = login
        return session.token

    def test_INTELLIGENCE_BOUNDARY_SECURITY_HARDENED_missing_session(self) -> None:
        body = json.dumps(_payload()).encode("utf-8")
        response = self._request("POST", "/intelligence/ingest/enrichment", body=body)
        self.assertEqual(response.status, 401)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload.get("reason_code"), "AUTH_REQUIRED")

    def test_INTELLIGENCE_BOUNDARY_SECURITY_HARDENED_viewer_denied(self) -> None:
        body = json.dumps(_payload()).encode("utf-8")
        response = self._request(
            "POST",
            "/intelligence/ingest/enrichment",
            body=body,
            headers={"Authorization": f"Bearer {self._viewer_token()}"},
        )
        self.assertEqual(response.status, 403)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload.get("reason_code"), "CAPABILITY_DENIED")

    def test_INTELLIGENCE_BOUNDARY_SECURITY_HARDENED_operator_accepted(self) -> None:
        body = json.dumps(_payload()).encode("utf-8")
        response = self._request(
            "POST",
            "/intelligence/ingest/enrichment",
            body=body,
            headers={"Authorization": f"Bearer {self._operator_token()}"},
        )
        self.assertEqual(response.status, 200)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload.get("disposition"), "INSERTED")

    def test_INTELLIGENCE_BOUNDARY_SECURITY_HARDENED_forbidden_mutation_http(self) -> None:
        body_dict = _payload()
        body_dict["requested_mutation"] = ForbiddenIngestMutation.MODE_AUTHORITY_MUTATION.value
        body = json.dumps(body_dict).encode("utf-8")
        response = self._request(
            "POST",
            "/intelligence/ingest/enrichment",
            body=body,
            headers={"Authorization": f"Bearer {self._operator_token()}"},
        )
        self.assertEqual(response.status, 403)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload.get("reason_code"), "INGEST_MUTATION_FORBIDDEN")

    def test_INTELLIGENCE_BOUNDARY_SECURITY_HARDENED_rejects_file_source_ref(self) -> None:
        body_dict = _payload()
        body_dict["source_refs"] = [
            {
                "provider_id": "finviz.news",
                "source_type": "news_article",
                "source_record_id": "src-1",
                "raw_reference": "file:///etc/passwd",
            }
        ]
        body = json.dumps(body_dict).encode("utf-8")
        response = self._request(
            "POST",
            "/intelligence/ingest/enrichment",
            body=body,
            headers={"Authorization": f"Bearer {self._operator_token()}"},
        )
        self.assertEqual(response.status, 400)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertIn("INGEST_SOURCE_REF_SCHEME_FORBIDDEN", payload.get("reason_code", ""))

    def test_ingest_cannot_route_to_paper_submit(self) -> None:
        """Ingest payload on paper order route remains capability-gated (no shadow execution)."""
        body = json.dumps(
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 1,
                "operation": "PAPER_SUBMIT",
            }
        ).encode("utf-8")
        response = self._request(
            "POST",
            "/paper/orders",
            body=body,
            headers={"Authorization": f"Bearer {self._viewer_token()}"},
        )
        self.assertEqual(response.status, 403)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload.get("reason_code"), "CAPABILITY_DENIED")


if __name__ == "__main__":
    unittest.main()
