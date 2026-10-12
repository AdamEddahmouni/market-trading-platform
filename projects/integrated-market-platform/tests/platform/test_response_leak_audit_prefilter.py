"""The secret-leak audit is a fail-closed control; optimization must not weaken it.

Two changes made this path much cheaper on every API response:

* ``is_secret_key`` memoizes a pure name-shape classification;
* ``scan_snapshot`` builds a path only when a finding can actually be reported;
* ``audit_text`` retains every governed regex evaluation; the unsafe prefilter was removed.

The first two must return exactly what the straightforward implementation
returns. The third must only ever *skip* a rule that provably cannot match --
never one that can. These tests pin both properties against reimplementations of
the original behaviour written directly from the documented contract, plus a
differential test over adversarial text.
"""
from __future__ import annotations

import json
import random
import re
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.credential_audit import SECRET_SCAN_RULES
from market_platform_foundation.platform.security import leak_audit
from market_platform_foundation.platform.security.redaction import (
    SECRET_KEY_MARKERS,
    is_secret_key,
    normalize_key,
)


# ------------------------------------------------------------------- references

def reference_is_secret_key(name: str) -> bool:
    """Name-based, value-blind, deliberately over-broad -- straight from the contract."""

    if not isinstance(name, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", "", name.lower())
    return any(marker in normalized for marker in SECRET_KEY_MARKERS)


def reference_scan(snapshot: Any, *, path: str = "", _segments: tuple | None = None) -> tuple:
    """The straightforward recursive scan, written independently of the optimized one."""

    findings = []
    segments = (() if not path else (path,)) if _segments is None else _segments
    if isinstance(snapshot, Mapping):
        for key, value in snapshot.items():
            child_path = f"{path}.{key}" if path else str(key)
            child_segments = (*segments, str(key))
            matrix = leak_audit._is_finviz_matrix_authority_path(child_segments)
            if is_secret_key(str(key)) and not leak_audit._structural_secret_key_is_benign(
                    child_path, str(key), value, segments=child_segments):
                if matrix:
                    findings.append(leak_audit.SecretFinding(
                        path=child_path, reason="UNSUPPORTED_PUBLIC_AUTHORITY_ASSIGNMENT",
                        fingerprint=leak_audit._fingerprint(str(value))))
                elif isinstance(value, str) and value.strip().upper() not in leak_audit.PLACEHOLDER_VALUES:
                    findings.append(leak_audit.SecretFinding(
                        path=child_path, reason="SECRET_SHAPED_KEY_WITH_LIVE_VALUE",
                        fingerprint=leak_audit._fingerprint(value)))
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    findings.append(leak_audit.SecretFinding(
                        path=child_path, reason="SECRET_SHAPED_KEY_WITH_NON_STRING_VALUE",
                        fingerprint=leak_audit._fingerprint(str(value))))
            findings.extend(reference_scan(value, path=child_path, _segments=child_segments))
    elif isinstance(snapshot, (list, tuple)):
        for index, item in enumerate(snapshot):
            findings.extend(reference_scan(item, path=f"{path}[{index}]", _segments=(*segments, index)))
    return tuple(findings)


def reference_audit_text(text: str) -> tuple[str, ...]:
    return tuple(sorted(rule_id for rule_id, pattern in SECRET_SCAN_RULES.items()
                        if re.search(pattern, text)))


# --------------------------------------------------------------------- corpus

def _payloads() -> list[Any]:
    corpus: list[Any] = [
        {},
        {"price": 10.0, "symbol": "AAPL", "as_of": "2026-10-02T15:00:00Z"},
        {"api_key": "sk-live-abcdef0123456789"},
        {"api_key": "CHANGEME"},
        {"api_key": "EXAMPLE"},
        {"api_key": ""},
        {"api_key": "   "},
        {"api_key": None},
        {"token": 1234},
        {"token": True},
        {"token": 1.25},
        {"nested": {"secret": "value"}, "list": [{"auth": "Bearer x"}, {"safe": 1}]},
        {"rows": [{"fields": {"price": {"value": 1, "auth_key": "zz"}}}]},
        {"tokens_input": 1200, "max_tokens": 4000, "output_tokens": 10, "actual_tokens": 7},
        {"status_token": "OPEND_UNAVAILABLE", "boundary_token": "FALLBACK_BLOCKED",
         "provider_status_token": "HEALTHY", "token_status": "READY"},
        {"authority": {"matrix": {"finviz": {"authority": "PUBLIC_FINVIZ"}}}},
        {"authority": {"matrix": {"finviz": {"authority": "ROGUE_MATRIX_AUTHORITY"}}}},
        {"fields": [{"key": "ANTHROPIC_API_KEY"}]},
        {"fields": [{"key": "an anthropic api key"}]},
        {"backend_authority": "market_platform_foundation.ui_api.server"},
        {"monkey": 1, "hockey": 2, "turkey": "x", "keyword": "y"},
        {"credentials": {}},
        [(1, 2, 3)],
        {"t": ({"api_key": "inside-a-tuple"},)},
        {1: "integer key", 2.5: "float key"},
        {"a" * 120: {"b" * 60: "c"}},
        {"empty_list": [], "empty_dict": {}, "none": None, "false": False, "zero": 0},
        {"deep": {"deeper": {"deepest": [{"api_key": "buried"}]}}},
    ]
    rows = [{"symbol": f"S{index:05d}",
             "fields": {name: {"value": index + offset, "source": "TEST", "state": "SNAPSHOT",
                               "as_of": "2026-10-02T15:00:00Z"}
                        for offset, name in enumerate(("price", "volume", "rsi_14"))}}
            for index in range(60)]
    corpus.append({"market_session": "REGULAR", "result_count": len(rows), "rows": rows})
    return corpus


class KeyShapeTests(unittest.TestCase):
    def test_memoized_classification_matches_the_reference(self) -> None:
        for name in ["api_key", "API-KEY", "Client Secret", "authorization", "monkey", "symbol",
                     "price", "x", "", "cookieJar", "credential_store", "session_token", "totally_clean"]:
            with self.subTest(name=name):
                self.assertEqual(is_secret_key(name), reference_is_secret_key(name))

    def test_repeated_answers_are_stable_after_the_cache_is_warm(self) -> None:
        first = [is_secret_key(name) for name in ("api_key", "symbol", "token", "price")]
        for _ in range(50):
            self.assertEqual([is_secret_key(name) for name in ("api_key", "symbol", "token", "price")], first)

    def test_non_string_names_are_not_secret(self) -> None:
        for value in (None, 1, 2.5, True, b"key", [], {}):
            self.assertFalse(is_secret_key(value))

    def test_normalize_key_is_unchanged(self) -> None:
        self.assertEqual(normalize_key("Client-Secret"), "clientsecret")
        self.assertEqual(normalize_key("API_KEY"), "apikey")


class StructuralScanParityTests(unittest.TestCase):
    def test_scan_matches_the_reference_on_every_payload(self) -> None:
        for index, payload in enumerate(_payloads()):
            with self.subTest(payload=index):
                self.assertEqual(leak_audit.scan_snapshot(payload), reference_scan(payload))

    def test_real_findings_are_still_reported(self) -> None:
        findings = leak_audit.scan_snapshot({"a": {"api_key": "live-value"}, "rows": [{"token": "t"}]})
        self.assertTrue(findings)
        self.assertEqual({finding.reason for finding in findings},
                         {"SECRET_SHAPED_KEY_WITH_LIVE_VALUE"})
        self.assertTrue(all(finding.path for finding in findings))
        self.assertTrue(all(re.fullmatch(r"[0-9A-F]+", finding.fingerprint) for finding in findings))

    def test_findings_never_carry_the_secret_value(self) -> None:
        secret = "sk-live-do-not-disclose-0123456789"
        rendered = json.dumps([finding.__dict__ if hasattr(finding, "__dict__") else
                               {"path": finding.path, "reason": finding.reason,
                                "fingerprint": finding.fingerprint}
                               for finding in leak_audit.scan_snapshot({"api_key": secret})])
        self.assertNotIn(secret, rendered)

    def test_scalar_and_container_paths_are_identical(self) -> None:
        # The optimized walk branches on value type; a finding must carry the same path either way.
        scalar = leak_audit.scan_snapshot({"outer": {"api_key": "v"}})
        container = leak_audit.scan_snapshot({"outer": {"inner": {"api_key": "v"}}})
        self.assertEqual([f.path for f in scalar], ["outer.api_key"])
        self.assertEqual([f.path for f in container], ["outer.inner.api_key"])
        self.assertEqual([f.reason for f in scalar], [f.reason for f in container])

    def test_list_indices_render_as_bracketed_paths(self) -> None:
        findings = leak_audit.scan_snapshot({"rows": [{"api_key": "v"}]})
        self.assertEqual([f.path for f in findings], ["rows[0].api_key"])

    def test_deeply_nested_payload_matches_the_reference(self) -> None:
        payload: Any = {"api_key": "root"}
        for _ in range(12):
            payload = {"level": payload}
        self.assertEqual(leak_audit.scan_snapshot(payload), reference_scan(payload))


class AuditTextPrefilterTests(unittest.TestCase):
    def test_prefilter_never_skips_a_rule_that_would_match(self) -> None:
        samples: list[str] = [
            "", "clean", '{"access_token":"eyJhbGciOi"}', '{"access_token":"REDACTED"}',
            "FINVIZ_API_KEY=abc", "finviz_api_key: abc", "FINVIZ_API_KEY=CHANGEME", "FINVIZ_API_KEY=",
            "Authorization: Bearer token", "Authorization: Basic dXNlcjpwYXNz", "Authorization: Digest x",
            "?auth=0123456789abcdef0123456789abcdef0123", "&auth=zzz", "?auth=",
            "api_key=abc", "api_key=", "FRED_API_KEY=1", "EIA_API_KEY=2",
            "FINRA_CLIENT_ID=3", "FINRA_CLIENT_SECRET=4",
            'access_token: "x"', '"access_token"  :  "y"',
        ]
        seeds = list(samples)
        random.seed(20261012)
        alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=.:/?& \"'{}[]")
        for _ in range(3000):
            samples.append("".join(random.choice(alphabet) for _ in range(random.randint(0, 120))))
        for _ in range(400):
            base = random.choice(seeds)
            index = random.randrange(max(1, len(base)))
            samples.append(base[:index] + random.choice(alphabet) + base[index + 1:])
        for text in samples:
            with self.subTest(text=text[:60]):
                self.assertEqual(leak_audit.audit_text(text), reference_audit_text(text))

    def test_each_governed_rule_remains_reachable(self) -> None:
        for rule_id, sample in {
            "FINRA_CLIENT_ID": "FINRA_CLIENT_ID=abc123",
            "FINRA_CLIENT_SECRET": "finra_client_secret: s3cr3t",
            "ACCESS_TOKEN": '{"access_token":"eyJhbGciOi"}',
            "AUTHORIZATION_HEADER": "Authorization: Bearer eyJhbGciOi",
            "FRED_API_KEY": "FRED_API_KEY=abcdef",
            "FRED_V1_API_KEY_PARAM": "https://x/y?api_key=abcdef",
            "EIA_API_KEY": "EIA_API_KEY=abcdef",
            "FINVIZ_API_KEY": "FINVIZ_API_KEY=abcdef",
            "FINVIZ_AUTH_QUERY": "?auth=0123456789abcdef0123456789abcdef0123",
        }.items():
            with self.subTest(rule=rule_id):
                self.assertIn(rule_id, reference_audit_text(sample))
                self.assertIn(rule_id, leak_audit.audit_text(sample))



class LeakGateTests(unittest.TestCase):
    def test_clean_payload_passes_and_live_secret_is_blocked(self) -> None:
        leak_audit.assert_no_secrets_in_payload({"rows": [{"symbol": "AAPL", "price": 10.0}]})
        with self.assertRaises(leak_audit.SecretLeakError):
            leak_audit.assert_no_secrets_in_payload({"api_key": "sk-live-0123456789"})

    def test_error_names_the_path_and_never_the_value(self) -> None:
        secret = "sk-live-never-echo-0123456789"
        with self.assertRaises(leak_audit.SecretLeakError) as caught:
            leak_audit.assert_no_secrets_in_payload({"outer": {"api_key": secret}})
        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("api_key", str(caught.exception))

    def test_textual_rule_still_blocks_a_leaked_authorization_header(self) -> None:
        with self.assertRaises(leak_audit.SecretLeakError):
            leak_audit.assert_no_secrets_in_payload({"note": "Authorization: Bearer abc123def"})



class RecoverySecurityTests(unittest.TestCase):

    def test_dynamic_key_markers_invalidate_classification_and_redaction(self):
        from unittest.mock import patch
        from market_platform_foundation.platform.security import redaction
        self.assertFalse(redaction.is_secret_key("custom_sensitive"))
        with patch.object(redaction, "SECRET_KEY_MARKERS", (*redaction.SECRET_KEY_MARKERS, "customsensitive")):
            self.assertTrue(redaction.is_secret_key("custom_sensitive"))
            self.assertEqual(redaction.redact_mapping({"custom_sensitive": "value"}), {"custom_sensitive": redaction.REDACTED})
        self.assertFalse(redaction.is_secret_key("custom_sensitive"))

    def test_unhashable_string_subclass_keeps_baseline_key_classification(self):
        class UnhashableText(str):
            __hash__ = None
        self.assertTrue(is_secret_key(UnhashableText("api_key")))


    def test_dynamic_regex_escapes_and_alternation_use_full_regex_semantics(self):
        from unittest.mock import patch
        cases = [(r"(?i)ABCD\wEFGH", "ABCDxEFGH"),
                 (r"(?i)ABCD\)EFGH|other", "other"),
                 (r"(?i)ABCD[()]EFGH|other", "other"),
                 (r"(?i)ABCD(?:EFGH)?", "ABCD"),
                 (r"(?i)ABCD\dEFGH", "ABCD1EFGH")]
        for pattern, text in cases:
            with self.subTest(pattern=pattern), patch.dict(leak_audit.SECRET_SCAN_RULES, {"DYNAMIC": pattern}, clear=True):
                self.assertIsNotNone(re.search(pattern, text))
                self.assertEqual(leak_audit.audit_text(text), ("DYNAMIC",))

    def test_unicode_case_insensitive_matches_are_never_suppressed(self):
        from unittest.mock import patch
        for letter in ("\u017f", "\u0130", "\u0131", "\u212a"):
            pattern = r"(?i)SIKSECRET=\w+"
            sample = "SIKSECRET=value".replace({"\u017f": "S", "\u0130": "I", "\u0131": "I", "\u212a": "K"}[letter], letter)
            with self.subTest(letter=letter), patch.dict(leak_audit.SECRET_SCAN_RULES, {"UNICODE": pattern}, clear=True):
                self.assertEqual(leak_audit.audit_text(sample), ("UNICODE",))
                with self.assertRaises(leak_audit.SecretLeakError):
                    leak_audit.assert_no_secrets_in_payload({"note": sample})

    def test_dynamic_rule_replacement_and_sorted_rule_ids_are_preserved(self):
        from unittest.mock import patch
        with patch.dict(leak_audit.SECRET_SCAN_RULES, {"Z": "ABCD", "A": "ABCD"}, clear=True):
            self.assertEqual(leak_audit.audit_text("ABCD"), ("A", "Z"))
            leak_audit.SECRET_SCAN_RULES["Z"] = "EFGH"
            self.assertEqual(leak_audit.audit_text("ABCD"), ("A",))



class ActualResponseGuardTests(unittest.TestCase):
    def test_unicode_credentials_are_blocked_before_http_response_bytes(self):
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        from market_platform_foundation.ui_api.server import UiApiHandler

        samples = ["FINRA_CLIENT_" + "\u017fECRET=synthetic", "FINV" + "\u0130Z_API_KEY=synthetic",
                   "FINV" + "\u0131Z_API_KEY=synthetic", "FINVIZ_API_" + "\u212aEY=synthetic"]

        class GuardHandler(UiApiHandler):
            def do_GET(self):
                self._send_json({"note": samples[int(self.path.rsplit("/", 1)[1])]})

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), GuardHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for index, sample in enumerate(samples):
                with self.subTest(index=index):
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
                    conn.request("GET", f"/response-guard-test/{index}")
                    response = conn.getresponse()
                    body = response.read().decode("utf-8")
                    conn.close()
                    self.assertEqual(response.status, 500)
                    self.assertEqual(json.loads(body)["reason_code"], "UI_SECRET_LEAK_BLOCKED")
                    self.assertNotIn(sample, body)
                    self.assertNotIn("synthetic", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()