from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.ibkr.capture import JsonlJournal, ObservationCapture, redact, redact_text
from tools.ibkr.client import IbkrClient, RateLimitError, TransportResponse
from tools.ibkr.config import IbkrConfig


SECRETS = (
    "user-ada",
    "hunter-2",
    "totp-123456",
    "bearer-abcdef",
    "cookie-session-xyz",
    "api-key-qwerty",
)


class RedactionTests(unittest.TestCase):
    def test_recursive_redaction_covers_nested_and_mixed_case_secret_keys(self) -> None:
        payload = {
            "instrument": "AAPL",
            "Username": SECRETS[0],
            "nested": {
                "password": SECRETS[1],
                "IBKR_TOTP_SECRET": SECRETS[2],
                "Authorization": f"Bearer {SECRETS[3]}",
                "rows": [{"set-cookie": SECRETS[4]}, {"api_key": SECRETS[5]}],
            },
        }
        cleaned = redact(payload)
        encoded = json.dumps(cleaned, sort_keys=True)
        self.assertEqual(cleaned["instrument"], "AAPL")
        self.assertTrue(all(secret not in encoded for secret in SECRETS))
        self.assertIn("<REDACTED>", encoded)

    def test_free_form_text_redacts_json_header_kv_and_query_shapes(self) -> None:
        dirty = (
            f'{{"password":"{SECRETS[1]}"}} '
            f"Authorization: Bearer {SECRETS[3]} "
            f"Cookie={SECRETS[4]}&api_key={SECRETS[5]} username={SECRETS[0]}"
        )
        cleaned = redact_text(dirty)
        self.assertTrue(all(secret not in cleaned for secret in SECRETS))
        self.assertIn("<REDACTED>", cleaned)


class JsonlCaptureTests(unittest.TestCase):
    def test_jsonl_journal_appends_one_parseable_redacted_object_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.jsonl"
            journal = JsonlJournal(path)
            journal.append({"event": "one", "token": SECRETS[3]})
            journal.append({"event": "two", "plain": "visible"})
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["event"] for line in lines], ["one", "two"])
        self.assertTrue(all(secret not in "\n".join(lines) for secret in SECRETS))

    def test_observation_capture_is_explicitly_not_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observations.jsonl"
            capture = ObservationCapture(path)
            capture.record(
                method="GET",
                path="/iserver/auth/status",
                params={"username": SECRETS[0]},
                request_body=None,
                status=200,
                headers={"set-cookie": SECRETS[4]},
                response_payload={"authenticated": True, "access_token": SECRETS[3]},
            )
            record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["classification"], "CAPTURED_NOT_ADMITTED")
        self.assertEqual(record["provider"], "IBKR_CLIENT_PORTAL_GATEWAY")
        encoded = json.dumps(record)
        self.assertTrue(all(secret not in encoded for secret in SECRETS))

    def test_observation_capture_accepts_tws_provider_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observations.jsonl"
            capture = ObservationCapture(path)
            capture.record(
                method="GET",
                path="/iserver/auth/status",
                params=None,
                request_body=None,
                status=200,
                headers={},
                response_payload={"connected": True},
                provider="IBKR_TWS_GATEWAY",
            )
            record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["provider"], "IBKR_TWS_GATEWAY")

    def test_client_writes_redacted_capture_and_penalty_journal_by_default(self) -> None:
        responses = [
            TransportResponse(
                200,
                {"set-cookie": SECRETS[4]},
                json.dumps({"authenticated": True, "token": SECRETS[3]}).encode("utf-8"),
            ),
            TransportResponse(429, {}, json.dumps({"password": SECRETS[1]}).encode("utf-8")),
        ]

        def transport(request, *, ssl_context, timeout: float) -> TransportResponse:
            return responses.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = IbkrConfig.from_env({"IMP_IBKR_LIVE": "1"}, root=root)
            client = IbkrClient(config, transport=transport)
            client.request_json("GET", "/iserver/auth/status")
            with self.assertRaises(RateLimitError):
                client.request_json("GET", "/iserver/auth/status")
            captures = (config.capture_root / "observations.jsonl").read_text(encoding="utf-8")
            penalties = (config.capture_root / "penalty-box.jsonl").read_text(encoding="utf-8")
        self.assertEqual(len(captures.splitlines()), 2)
        self.assertEqual(len(penalties.splitlines()), 1)
        self.assertTrue(all(secret not in captures + penalties for secret in SECRETS))
        self.assertEqual(json.loads(penalties)["event"], "IBKR_429_PENALTY_BOX_ENTERED")


if __name__ == "__main__":
    unittest.main()
