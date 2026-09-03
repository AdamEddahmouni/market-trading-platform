from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from io import BytesIO

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.market_data.lifecycle import ObservationLifecycle, next_lifecycle_state
from market_platform_foundation.sec_edgar.dilution import dilution_from_filing
from market_platform_foundation.sec_edgar.discovery import parse_latest_filings_atom
from market_platform_foundation.sec_edgar.documents import DocumentRetrievalPolicy, hash_document, select_exhibits
from market_platform_foundation.sec_edgar.evidence import catalyst_from_filing, participant_hints_from_filing
from market_platform_foundation.sec_edgar.filing import submissions_to_filings
from market_platform_foundation.sec_edgar.forms import classify_form, eight_k_item_labels, is_amendment_form
from market_platform_foundation.sec_edgar.identity import EntityMap, normalize_accession, pad_cik
from market_platform_foundation.sec_edgar.monitoring import filing_to_allocation_hint
from market_platform_foundation.sec_edgar.quality import quality_from_failure
from market_platform_foundation.sec_edgar.replay import replay_captured_filings
from market_platform_foundation.sec_edgar.store import FilingStore
from market_platform_foundation.sec_edgar.timestamps import clocks_from_submission_row
from market_platform_foundation.sec_edgar.transport import SecTransport, require_user_agent
from market_platform_foundation.sec_edgar.xbrl import facts_as_of

FIXTURES = ROOT / "tests" / "fixtures" / "sec_edgar"


class FakeHttpError(HTTPError):
    def __init__(self, code: int) -> None:
        super().__init__("https://data.sec.gov/x", code, "err", {}, BytesIO(b""))


class IdentityTests(unittest.TestCase):
    def test_accession_normalization_is_stable(self) -> None:
        self.assertEqual(normalize_accession("000104581025000010"), "0001045810-25-000010")
        self.assertEqual(normalize_accession("0001045810-25-000010"), "0001045810-25-000010")
        self.assertEqual(pad_cik("1045810"), "0001045810")

    def test_cik_to_instrument_fails_closed_when_unmapped(self) -> None:
        mapping = EntityMap.from_path(FIXTURES / "entity_map_slice.json")
        hit = mapping.resolve(cik="1045810", as_of="2025-01-15T00:00:00Z")
        self.assertEqual(hit.instrument_id, "NVDA")
        miss = mapping.resolve(cik="0000999999", as_of="2025-01-15T00:00:00Z")
        self.assertEqual(miss.instrument_id, "")
        self.assertIn("UNKNOWN_ENTITY", miss.quality_flags)


class TransportTests(unittest.TestCase):
    def test_missing_user_agent_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            require_user_agent("")
        self.assertIn("SEC_USER_AGENT", str(ctx.exception))
        with self.assertRaises(ValueError):
            require_user_agent("python-urllib/3.11")

    def test_rate_limiter_caps_concurrent_callers(self) -> None:
        stamps: list[float] = []
        lock = threading.Lock()

        def requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
            with lock:
                stamps.append(time.monotonic())
            return b"{}"

        transport = SecTransport(
            user_agent="IntegratedMarketPlatform research test@example.com",
            requester=requester,
            min_interval_s=0.2,
        )

        def worker() -> None:
            transport.get("https://data.sec.gov/submissions/CIK0001045810.json")

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stamps.sort()
        gaps = [stamps[i] - stamps[i - 1] for i in range(1, len(stamps))]
        self.assertTrue(all(gap >= 0.15 for gap in gaps))

    def test_cache_avoids_repeat_fetch_of_immutable_url(self) -> None:
        calls = {"n": 0}

        def requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
            calls["n"] += 1
            return b'{"ok": true}'

        transport = SecTransport(
            user_agent="IntegratedMarketPlatform research test@example.com",
            requester=requester,
            min_interval_s=0.0,
        )
        url = "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000010/nvda-8k.htm"
        first = transport.get(url, immutable=True)
        second = transport.get(url, immutable=True)
        self.assertEqual(first, second)
        self.assertEqual(calls["n"], 1)

    def test_http_error_is_source_unavailable_not_empty_filings(self) -> None:
        def requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
            raise FakeHttpError(503)

        transport = SecTransport(
            user_agent="IntegratedMarketPlatform research test@example.com",
            requester=requester,
            min_interval_s=0.0,
        )
        with self.assertRaises(OSError) as ctx:
            transport.get("https://data.sec.gov/submissions/CIK0001045810.json")
        flags = quality_from_failure(ctx.exception)
        self.assertIn("SOURCE_UNAVAILABLE", flags)
        self.assertNotIn("NO_FILINGS", flags)


class FilingNormalizationTests(unittest.TestCase):
    def test_submissions_normalize_forms_and_accession_identity(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        by_form = {row.form_type: row for row in filings}
        self.assertIn("8-K", by_form)
        self.assertEqual(by_form["8-K"].normalized_accession, "0001045810-25-000010")
        self.assertEqual(by_form["8-K"].cik, "0001045810")
        self.assertEqual(classify_form("8-K").family, "CORPORATE_EVENT")
        self.assertEqual(classify_form("4").family, "OWNERSHIP")
        self.assertEqual(classify_form("10-K").family, "FUNDAMENTAL")
        self.assertEqual(classify_form("S-3").family, "CAPITAL_STRUCTURE")
        self.assertEqual(classify_form("13F-HR").family, "OWNERSHIP")
        self.assertTrue(is_amendment_form("10-K/A"))
        self.assertFalse(is_amendment_form("10-K"))
        labels = eight_k_item_labels("1.01,2.02,9.01")
        self.assertIn("1.01", labels)
        self.assertEqual(labels["2.02"], "Results of Operations and Financial Condition")

    def test_clocks_distinguish_acceptance_from_observation(self) -> None:
        clocks = clocks_from_submission_row(
            filing_date="2025-01-15",
            acceptance_datetime="2025-01-15T16:05:00.000Z",
            observed_time="2025-01-15T16:06:30Z",
            document_retrieved_time="",
        )
        self.assertLess(clocks.acceptance_time_ns, clocks.observed_time_ns)
        self.assertEqual(clocks.document_available_time_ns, 0)
        self.assertEqual(clocks.available_time_ns, clocks.observed_time_ns)


class PitStoreTests(unittest.TestCase):
    def test_amendment_is_invisible_before_its_available_time(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        store = FilingStore()
        store.extend(filings)
        original_cutoff = "2025-02-01T18:00:00Z"
        as_of_original = store.as_of(original_cutoff, cik="0001045810")
        forms = {row.form_type for row in as_of_original}
        self.assertIn("10-K", forms)
        self.assertNotIn("10-K/A", forms)
        later = store.as_of("2025-02-02T13:00:00Z", cik="0001045810")
        later_forms = {row.form_type for row in later}
        self.assertIn("10-K", later_forms)
        self.assertIn("10-K/A", later_forms)
        amendment = next(row for row in later if row.form_type == "10-K/A")
        original = next(row for row in later if row.form_type == "10-K")
        self.assertEqual(amendment.amends_accession, original.normalized_accession)


class XbrlPitTests(unittest.TestCase):
    def test_later_companyfacts_value_cannot_leak_into_earlier_as_of(self) -> None:
        payload = (FIXTURES / "companyfacts_nvda_slice.json").read_text(encoding="utf-8")
        early = facts_as_of(payload, as_of="2025-02-01T18:00:00Z", tag="Assets")
        self.assertEqual(len(early), 1)
        self.assertEqual(early[0].value, 1000000000)
        self.assertEqual(early[0].accession, "0001045810-25-000020")
        later = facts_as_of(payload, as_of="2025-02-02T18:00:00Z", tag="Assets")
        self.assertEqual(len(later), 2)
        self.assertEqual(later[-1].value, 1100000000)


class DocumentAndReplayTests(unittest.TestCase):
    def test_document_hash_and_exhibit_policy(self) -> None:
        digest = hash_document(b"<html>8-K body</html>")
        self.assertEqual(digest, sha256_bytes(b"<html>8-K body</html>"))
        selected = select_exhibits(
            form_type="8-K",
            exhibits=("EX-99.1", "EX-10.1", "GRAPHIC"),
            policy=DocumentRetrievalPolicy.HIGH_VALUE,
        )
        self.assertIn("EX-99.1", selected)
        self.assertNotIn("GRAPHIC", selected)

    def test_replay_captured_jsonl_is_deterministic(self) -> None:
        captured = ROOT / "tests" / "fixtures" / "sec_edgar" / "captured-nvda.jsonl"
        first = replay_captured_filings(captured)
        second = replay_captured_filings(captured)
        self.assertEqual([row.normalized_accession for row in first], [row.normalized_accession for row in second])
        self.assertGreaterEqual(len(first), 1)
        self.assertEqual(first[0].lifecycle, ObservationLifecycle.CAPTURED.value)


class EvidenceTests(unittest.TestCase):
    def test_eight_k_becomes_catalyst_without_direction(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        eight_k = next(row for row in filings if row.form_type == "8-K")
        catalyst = catalyst_from_filing(eight_k)
        self.assertIsNotNone(catalyst.materiality_score)
        self.assertIsNone(catalyst.semantic_sentiment)
        self.assertIn("1.01", eight_k.items)

    def test_form4_feeds_participant_hints_not_a_score(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        form4 = next(row for row in filings if row.form_type == "4")
        hints = participant_hints_from_filing(form4, transaction_code="P")
        self.assertEqual(hints["action_type"], "OPEN_MARKET_BUY")
        grant = participant_hints_from_filing(form4, transaction_code="A")
        self.assertNotEqual(grant["action_type"], "OPEN_MARKET_SELL")

    def test_shelf_and_prospectus_create_uncertain_dilution_evidence(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        shelf = next(row for row in filings if row.form_type == "S-3")
        evidence = dilution_from_filing(shelf)
        self.assertEqual(evidence.form_type, "S-3")
        self.assertIsNone(evidence.potential_new_shares)
        self.assertLess(evidence.confidence, 1.0)
        self.assertEqual(evidence.normalized_accession, shelf.normalized_accession)

    def test_sec_event_can_hint_moomoo_allocation_without_coupling(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        eight_k = next(row for row in filings if row.form_type == "8-K")
        hint = filing_to_allocation_hint(eight_k, instrument_id="NVDA")
        self.assertEqual(hint["instrument_id"], "NVDA")
        self.assertEqual(hint["capability"], "US_EQUITY_DEPTH")
        self.assertEqual(hint["lane"], "regulatory")
        self.assertNotIn("moomoo", hint)

    def test_atom_discovery_parses_accession(self) -> None:
        xml = (FIXTURES / "rss_latest_slice.xml").read_text(encoding="utf-8")
        rows = parse_latest_filings_atom(xml)
        self.assertEqual(rows[0]["normalized_accession"], "0001045810-25-000010")
        self.assertEqual(rows[0]["form_type"], "8-K")

    def test_live_observation_cannot_auto_admit(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            next_lifecycle_state(
                ObservationLifecycle.QUALITY_CHARACTERIZED,
                ObservationLifecycle.ADMITTED,
                admission_authorized=False,
            )
        self.assertIn("ADMISSION_REQUIRES_SEPARATE_ADR", str(ctx.exception))


class DuplicateAndMalformedTests(unittest.TestCase):
    def test_duplicate_accession_is_suppressed_not_amended_away(self) -> None:
        filings = submissions_to_filings(
            (FIXTURES / "submissions_nvda_slice.json").read_text(encoding="utf-8"),
            observed_time="2025-05-02T00:00:00Z",
        )
        store = FilingStore()
        store.extend(filings)
        store.extend(filings)
        as_of = store.as_of("2025-05-02T00:00:00Z", cik="0001045810")
        accessions = [row.normalized_accession for row in as_of]
        self.assertEqual(len(accessions), len(set(accessions)))

    def test_malformed_submissions_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            submissions_to_filings("{not json", observed_time="2025-01-01T00:00:00Z")


class LiveGateTests(unittest.TestCase):
    def test_live_client_is_gated_by_explicit_env(self) -> None:
        from market_platform_foundation.sec_edgar import live as live_mod

        previous = os.environ.get("SEC_LIVE_TESTS")
        previous_live = os.environ.get("IMP_EDGAR_LIVE")
        os.environ.pop("SEC_LIVE_TESTS", None)
        os.environ.pop("IMP_EDGAR_LIVE", None)
        try:
            self.assertFalse(live_mod.live_enabled())
        finally:
            if previous is not None:
                os.environ["SEC_LIVE_TESTS"] = previous
            if previous_live is not None:
                os.environ["IMP_EDGAR_LIVE"] = previous_live


if __name__ == "__main__":
    unittest.main()
