from __future__ import annotations

import os
import unittest


@unittest.skipUnless(os.environ.get("SEC_LIVE_TESTS") == "1", "opt-in live SEC tests")
class LiveSecSmokeTests(unittest.TestCase):
    def test_submissions_and_companyfacts_smoke(self) -> None:
        from datetime import datetime, timezone

        from market_platform_foundation.sec_edgar.documents import hash_document
        from market_platform_foundation.sec_edgar.live import (
            fetch_companyfacts,
            fetch_primary_document,
            fetch_submissions,
            transport_from_env,
        )

        transport = transport_from_env()
        filings = fetch_submissions(transport, "0000320193")
        self.assertGreater(len(filings), 0)
        self.assertEqual(filings[0].cik, "0000320193")
        as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        facts = fetch_companyfacts(transport, "0000320193", as_of=as_of, tag="Assets")
        self.assertGreaterEqual(len(facts), 0)
        compact = next((row for row in filings if row.form_type in {"4", "8-K", "3"} and row.primary_document), None)
        if compact is not None:
            body = fetch_primary_document(transport, compact)
            self.assertGreater(len(hash_document(body)), 0)
