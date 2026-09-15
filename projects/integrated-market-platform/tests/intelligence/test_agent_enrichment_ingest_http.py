"""HTTP-level Lane G ingest guards (body cap, repository, opportunity)."""

from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.common import (  # noqa: E402
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1  # noqa: E402
from market_platform_foundation.intelligence.ingest.boundary import (  # noqa: E402
    AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402


def _payload(opportunity_id: str = "opp-http") -> dict:
    return {
        "record_id": "aer-http-1",
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
        "claim_body": {"summary": "http test"},
    }


class _MiniStore:
    def __init__(self, strategy_repository) -> None:
        self.strategy_repository = strategy_repository


class AgentEnrichmentIngestHttpTests(unittest.TestCase):
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
        self.repo = InMemoryIntelligenceRepository()
        self.repo.put_opportunity(
            OpportunityV1(
                opportunity_id="opp-http",
                schema_version="1",
                scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
                created_at_ns=10_000,
                quality=QualitySummary(state=QualityState.GOOD),
                side=OpportunitySide.LONG,
                reason_summary="HTTP test opportunity",
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

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes,
        content_length: int | None = None,
    ) -> http.client.HTTPResponse:
        conn = http.client.HTTPConnection("127.0.0.1", self.__class__._port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if content_length is not None:
            headers["Content-Length"] = str(content_length)
        else:
            headers["Content-Length"] = str(len(body))
        conn.request(method, path, body=body, headers=headers)
        return conn.getresponse()

    @patch.object(UiApiHandler, "_authorize_request", return_value=True)
    def test_http_post_rejects_oversized_content_length_before_read(self, _auth) -> None:
        over = AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES + 1
        response = self._request(
            "POST",
            "/intelligence/ingest/enrichment",
            body=b"{}",
            content_length=over,
        )
        self.assertEqual(response.status, 413)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertIn("AGENT_ENRICHMENT_BODY_TOO_LARGE", payload.get("reason_code", ""))

    @patch.object(UiApiHandler, "_authorize_request", return_value=True)
    def test_http_put_rejects_oversized_content_length(self, _auth) -> None:
        over = AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES + 1
        response = self._request(
            "PUT",
            "/intelligence/ingest/enrichment/aer-http-1",
            body=b"{}",
            content_length=over,
        )
        self.assertEqual(response.status, 413)

    @patch.object(UiApiHandler, "_authorize_request", return_value=True)
    def test_http_post_fails_closed_when_repository_unsupported(self, _auth) -> None:
        class _ForeignRepository:
            def get_opportunity(self, opportunity_id: str) -> None:
                return None

        UiApiHandler.store = _MiniStore(_ForeignRepository())
        body = json.dumps(_payload()).encode("utf-8")
        response = self._request("POST", "/intelligence/ingest/enrichment", body=body)
        self.assertEqual(response.status, 503)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertIn("AGENT_ENRICHMENT_REPOSITORY_UNSUPPORTED", payload.get("reason_code", ""))

    @patch.object(UiApiHandler, "_authorize_request", return_value=True)
    def test_http_post_rejects_unknown_opportunity(self, _auth) -> None:
        body = json.dumps(_payload(opportunity_id="opp-missing")).encode("utf-8")
        response = self._request("POST", "/intelligence/ingest/enrichment", body=body)
        self.assertEqual(response.status, 404)
        payload = json.loads(response.read().decode("utf-8"))
        self.assertIn("OPPORTUNITY_NOT_FOUND", payload.get("reason_code", ""))


if __name__ == "__main__":
    unittest.main()
