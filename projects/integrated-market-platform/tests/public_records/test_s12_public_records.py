"""S12 official public records: USAspending award transactions, LDA lobbying filings, bounded HTTP.

Fixtures are real API responses (Lockheed Martin, 2026) trimmed to the fields the
adapters read; individual lobbyists are not part of the fixture.
"""

from __future__ import annotations

import json
import sys
import threading
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.public_records import lobbying, usaspending  # noqa: E402
from market_platform_foundation.public_records.http import (  # noqa: E402
    PublicRecordsError, PublicRecordsHttp, live_state,
)

FIXTURES = ROOT / "tests" / "fixtures" / "public_records"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeRequester:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append((url, json.loads(body) if body else None, headers))
        status, payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return status, payload if isinstance(payload, bytes) else json.dumps(payload).encode()


def http(responses) -> tuple[PublicRecordsHttp, FakeRequester]:
    fake = FakeRequester(responses)
    return PublicRecordsHttp(requester=fake, min_interval_s=0.0), fake


class UsaSpendingTests(unittest.TestCase):
    def test_transactions_are_signed_actions_with_their_recipient(self):
        rows = usaspending.parse_transactions(load("usaspending_transactions_contracts.json"), family="CONTRACT")
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0].recipient_name, "SIKORSKY AIRCRAFT CORPORATION")  # parent-linked recipient, as named
        self.assertEqual(rows[0].obligation_amount, 0.0)  # a no-cost modification is not an award of money
        self.assertTrue(all(row.award_url.startswith("https://www.usaspending.gov/award/") for row in rows))
        as_dict = rows[3].to_dict()
        self.assertEqual(as_dict["obligation_currency"], "USD")
        self.assertIn("not revenue", as_dict["obligation_note"])

    def test_families_are_separate_and_dedupe(self):
        grants = usaspending.parse_transactions(load("usaspending_transactions_grants.json"), family="GRANT")
        self.assertEqual({row.family for row in grants}, {"GRANT"})
        duplicated = usaspending.dedupe_transactions(grants + grants)
        self.assertEqual(len(duplicated), len(grants))

    def test_negative_obligation_is_kept(self):
        payload = {"results": [{"Award ID": "X1", "Mod": "P0002", "Transaction Amount": -125000.5,
                                "Action Date": "2026-09-01", "generated_internal_id": "CONT_AWD_X1"}]}
        row = usaspending.parse_transactions(payload, family="CONTRACT")[0]
        self.assertEqual(row.obligation_amount, -125000.5)

    def test_malformed(self):
        with self.assertRaises(ValueError):
            usaspending.parse_transactions({"rows": []}, family="CONTRACT")
        self.assertEqual(usaspending.parse_transactions({"results": [{"Award ID": ""}, "x"]}, family="GRANT"), [])

    def test_client_reports_truncation_and_publication_clock(self):
        client_http, fake = http([(200, load("usaspending_transactions_contracts.json")),
                                  (200, load("usaspending_transactions_grants.json")),
                                  (200, load("usaspending_last_updated.json"))])
        client = usaspending.UsaSpendingClient(client_http)
        families = client.recipient_transactions("Lockheed Martin", today=date(2026, 9, 28), window_days=90)
        self.assertTrue(families["CONTRACT"]["has_more"])
        self.assertFalse(families["GRANT"]["has_more"])
        body = fake.calls[0][1]
        self.assertEqual(body["filters"]["award_type_codes"], ["A", "B", "C", "D"])
        self.assertEqual(body["filters"]["time_period"], [{"start_date": "2026-06-30", "end_date": "2026-09-28"}])
        self.assertEqual(fake.calls[1][1]["filters"]["award_type_codes"], ["02", "03", "04", "05"])
        self.assertEqual(client.last_updated(), "2026-09-28")
        self.assertIsNone(usaspending.parse_last_updated({"last_updated": "yesterday"}))


class LobbyingTests(unittest.TestCase):
    def setUp(self):
        self.filings = lobbying.parse_filings(load("lda_filings.json"))

    def test_income_and_expenses_are_never_combined(self):
        self_filed, outside = self.filings[0], self.filings[1]
        self.assertTrue(self_filed.self_filed)
        self.assertEqual((self_filed.income, self_filed.expenses), (None, 4_180_000.0))
        self.assertIn("includes payments to outside firms", self_filed.to_dict()["amount_note"])
        self.assertFalse(outside.self_filed)
        self.assertEqual((outside.income, outside.expenses), (80_000.0, None))
        self.assertIn("income", outside.to_dict()["amount_note"])
        self.assertIn("No amount reported", self.filings[-1].to_dict()["amount_note"])

    def test_issues_and_entities_are_as_filed_and_no_lobbyist_names(self):
        data = self.filings[0].to_dict()
        self.assertTrue(data["issues"])
        self.assertTrue(all(set(issue) == {"code", "label"} for issue in data["issues"]))
        self.assertNotIn("lobbyists", json.dumps(data))

    def test_url_and_client(self):
        url = lobbying.filings_url("Lockheed Martin", year=2026)
        self.assertIn("client_name=Lockheed+Martin", url)
        self.assertIn("ordering=-dt_posted", url)
        client_http, fake = http([(200, load("lda_filings.json")), (200, {"count": 0, "results": []})])
        filings, total = lobbying.LobbyingClient(client_http).client_filings("Lockheed Martin", today=date(2026, 9, 28))
        self.assertEqual((len(filings), total), (4, 34))
        self.assertIn("filing_year=2025", fake.calls[1][0])

    def test_malformed(self):
        with self.assertRaises(ValueError):
            lobbying.parse_filings({"count": 1})


class HttpTests(unittest.TestCase):
    def test_live_gate(self):
        self.assertEqual(live_state(lambda name: None), ("LIVE_DISABLED", "IMP_PUBLIC_RECORDS_LIVE_NOT_SET"))
        self.assertEqual(live_state(lambda name: "1"), ("CURRENT", None))

    def test_stable_error_codes(self):
        for status, code in ((429, "HTTP_429"), (403, "HTTP_403"), (500, "HTTP_500")):
            client, _ = http([(status, b"")])
            with self.assertRaises(PublicRecordsError) as caught:
                client.get_json("https://api.example.test/x")
            self.assertEqual(str(caught.exception), code)
        client, _ = http([(200, b"<html>")])
        with self.assertRaisesRegex(PublicRecordsError, "MALFORMED_JSON"):
            client.get_json("https://api.example.test/x")
        client, _ = http([(0, OSError("boom"))])
        with self.assertRaisesRegex(PublicRecordsError, "NETWORK_ERROR"):
            client.get_bytes("https://api.example.test/x")

    def test_identifying_user_agent_and_no_credentials(self):
        client, fake = http([(200, {"ok": True})])
        client.post_json("https://api.example.test/x", {"a": 1})
        headers = fake.calls[0][2]
        self.assertTrue(headers["User-Agent"].startswith("integrated-market-platform"))
        self.assertFalse({"Authorization", "Cookie"} & set(headers))

    def test_per_host_throttle(self):
        waits = []
        fake = FakeRequester([(200, {}), (200, {}), (200, {})])
        client = PublicRecordsHttp(requester=fake, min_interval_s=5.0, sleeper=waits.append)
        client.get_json("https://a.test/1")
        client.get_json("https://b.test/1")
        client.get_json("https://a.test/2")
        self.assertEqual(len(waits), 1)

    def test_throttle_wait_never_blocks_other_hosts(self):
        other_done = threading.Event()

        def sleeper(_seconds):
            # While a.test waits for its slot, a request to b.test must go straight through.
            worker = threading.Thread(target=lambda: (client.get_json("https://b.test/1"), other_done.set()))
            worker.start()
            worker.join(timeout=2.0)

        fake = FakeRequester([(200, {}), (200, {}), (200, {})])
        client = PublicRecordsHttp(requester=fake, min_interval_s=5.0, sleeper=sleeper)
        client.get_json("https://a.test/1")
        client.get_json("https://a.test/2")
        self.assertTrue(other_done.is_set())
        self.assertEqual([call[0] for call in fake.calls], ["https://a.test/1", "https://b.test/1", "https://a.test/2"])


if __name__ == "__main__":
    unittest.main()
