from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.credential_audit import SECRET_SCAN_RULES, scan_redacted_bytes
from market_platform_foundation.finra.auth import FinraAuthError, FinraTokenManager
from market_platform_foundation.finra.client_config import (
    FinraCredentials,
    credential_health,
    rotation_alert,
)
from market_platform_foundation.finra.publication_calendar import cycle_for_settlement
from market_platform_foundation.finra.short_interest import normalize_short_interest_row
from market_platform_foundation.finra.short_sale_volume import (
    aggregate_short_sale_rows,
    normalize_short_sale_row,
)
from market_platform_foundation.finra.transport import FinraTransport
from market_platform_foundation.market_data.lifecycle import ObservationLifecycle, next_lifecycle_state
from market_platform_foundation.nasdaq_regsho.threshold import normalize_threshold_file, parse_threshold_file
from market_platform_foundation.nasdaq_regsho.transport import NasdaqTransport
from market_platform_foundation.short_intelligence.clocks import ny_wall_to_utc_iso, visible_at
from market_platform_foundation.short_intelligence.contracts import (
    CredentialHealthState,
    ObservationFamily,
    ShortInterestObservation,
    ShortSaleVolumeObservation,
)
from market_platform_foundation.short_intelligence.features import (
    cross_source_features,
    short_interest_pct_float,
    threshold_duration,
)
from market_platform_foundation.short_intelligence.identity import SymbolMap
from market_platform_foundation.short_intelligence.pressure import pressure_state
from market_platform_foundation.short_intelligence.quality import quality_from_failure
from market_platform_foundation.short_intelligence.redaction import redact_mapping
from market_platform_foundation.short_intelligence.store import ShortIntelligenceStore
from market_platform_foundation.short_intelligence.squeeze import fuse_regulatory_and_short, rank_candidates

FIXTURES = ROOT / "tests" / "fixtures" / "short_intelligence"


class FakeHttpError(HTTPError):
    def __init__(self, code: int) -> None:
        super().__init__("https://api.finra.org/x", code, "err", {}, BytesIO(b""))


def _creds() -> FinraCredentials:
    return FinraCredentials("id", "secret", "2026-08-01", "2027-08-01")


def _map() -> SymbolMap:
    return SymbolMap.from_path(FIXTURES / "symbol_map.json")


class SemanticSeparationTests(unittest.TestCase):
    def test_families_cannot_masquerade(self) -> None:
        si_fields = set(ShortInterestObservation.__dataclass_fields__)
        ssv_fields = set(ShortSaleVolumeObservation.__dataclass_fields__)
        self.assertEqual(ObservationFamily.SHORT_INTEREST.value, "SHORT_INTEREST")
        self.assertEqual(ObservationFamily.SHORT_SALE_VOLUME.value, "SHORT_SALE_VOLUME")
        self.assertNotEqual(ObservationFamily.SHORT_INTEREST, ObservationFamily.SHORT_SALE_VOLUME)
        self.assertIn("current_short_position_quantity", si_fields)
        self.assertNotIn("current_short_position_quantity", ssv_fields)
        self.assertIn("short_sale_volume", ssv_fields)
        self.assertNotIn("short_sale_volume", si_fields)
        self.assertNotIn("finra_reported_total_volume", si_fields)


class AuthTests(unittest.TestCase):
    def test_initial_request_and_cache_hit(self) -> None:
        calls = {"n": 0}

        def requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
            calls["n"] += 1
            self.assertNotIn("Bearer", str(headers.get("Authorization")))
            return 200, b'{"access_token":"tok-1","token_type":"Bearer","expires_in":"43170"}'

        manager = FinraTokenManager(_creds(), requester=requester, safety_margin_s=120)
        self.assertEqual(manager.get_token(), "tok-1")
        self.assertEqual(manager.get_token(), "tok-1")
        self.assertEqual(calls["n"], 1)

    def test_refresh_before_expiry(self) -> None:
        clock = {"t": 0.0}
        calls = {"n": 0}

        def requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
            calls["n"] += 1
            return 200, b'{"access_token":"tok-%d","token_type":"Bearer","expires_in":200}' % calls["n"]

        manager = FinraTokenManager(
            _creds(), requester=requester, safety_margin_s=50, clock=lambda: clock["t"]
        )
        self.assertEqual(manager.get_token(), "tok-1")
        clock["t"] = 160
        self.assertEqual(manager.get_token(), "tok-2")
        self.assertEqual(calls["n"], 2)

    def test_invalid_secret_fails_closed(self) -> None:
        def requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
            raise FakeHttpError(401)

        manager = FinraTokenManager(_creds(), requester=requester)
        with self.assertRaises(FinraAuthError) as ctx:
            manager.get_token()
        self.assertIn("AUTH_FAILED", str(ctx.exception))
        flags = quality_from_failure(ctx.exception)
        self.assertIn("AUTH_FAILED", flags)
        self.assertNotIn("NO_RECORD", flags)

    def test_token_endpoint_unavailable(self) -> None:
        def requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
            raise OSError("offline")

        manager = FinraTokenManager(_creds(), requester=requester)
        with self.assertRaises(FinraAuthError) as ctx:
            manager.get_token()
        self.assertIn("SOURCE_UNAVAILABLE", str(ctx.exception))

    def test_missing_secret(self) -> None:
        with self.assertRaises(FinraAuthError):
            FinraTokenManager(FinraCredentials("", "", "", ""))

    def test_concurrent_refresh_is_single_flight(self) -> None:
        calls = {"n": 0}
        started = threading.Event()
        release = threading.Event()

        def requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
            calls["n"] += 1
            started.set()
            release.wait(timeout=2)
            return 200, b'{"access_token":"shared","token_type":"Bearer","expires_in":1800}'

        manager = FinraTokenManager(_creds(), requester=requester)
        results: list[str] = []

        def worker() -> None:
            results.append(manager.get_token())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        started.wait(timeout=2)
        time.sleep(0.05)
        release.set()
        for thread in threads:
            thread.join()
        self.assertEqual(calls["n"], 1)
        self.assertEqual(set(results), {"shared"})

    def test_401_recovery_refreshes_once(self) -> None:
        tokens = {"v": "old"}
        api_calls = {"n": 0}

        def token_requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
            return 200, json.dumps({"access_token": tokens["v"], "expires_in": 1800}).encode()

        def api_requester(method, url, headers, body, timeout):
            api_calls["n"] += 1
            if "old" in headers.get("Authorization", ""):
                raise FakeHttpError(401)
            return 200, {"FINRA-api-request-id": "req-1"}, b"[]"

        manager = FinraTokenManager(_creds(), requester=token_requester)
        manager.get_token()
        tokens["v"] = "new"
        transport = FinraTransport(manager, requester=api_requester, min_interval_s=0.0)
        response = transport.get("/data/group/otcMarket/name/regShoDaily")
        self.assertEqual(response.request_id, "req-1")
        self.assertGreaterEqual(api_calls["n"], 2)


class CredentialHealthTests(unittest.TestCase):
    def test_states(self) -> None:
        today = date(2026, 8, 20)
        healthy = FinraCredentials("id", "secret", "2026-08-01", "2027-08-01")
        due = FinraCredentials("id", "secret", "2025-09-01", "2026-09-10")
        urgent = FinraCredentials("id", "secret", "2025-08-25", "2026-08-25")
        expired = FinraCredentials("id", "secret", "2025-01-01", "2026-08-01")
        unknown = FinraCredentials("id", "secret", "", "")
        self.assertEqual(credential_health(healthy, today=today), CredentialHealthState.HEALTHY)
        self.assertEqual(credential_health(due, today=today), CredentialHealthState.ROTATION_DUE)
        self.assertEqual(credential_health(urgent, today=today), CredentialHealthState.ROTATION_URGENT)
        self.assertEqual(credential_health(expired, today=today), CredentialHealthState.EXPIRED)
        self.assertEqual(credential_health(unknown, today=today), CredentialHealthState.UNKNOWN)
        self.assertEqual(credential_health(healthy, today=today, auth_failed=True), CredentialHealthState.AUTH_FAILED)
        self.assertEqual(rotation_alert(CredentialHealthState.ROTATION_DUE, days_remaining=20), "FINRA credential expires in 30 days")
        self.assertEqual(rotation_alert(CredentialHealthState.EXPIRED, days_remaining=-1), "FINRA credential expired")


class PublicationAndPitTests(unittest.TestCase):
    def test_publication_lag_is_mandatory(self) -> None:
        rows = json.loads((FIXTURES / "consolidated_short_interest_slice.json").read_text(encoding="utf-8"))
        observed = "2026-08-11T20:45:00Z"
        si = normalize_short_interest_row(rows[0], symbol_map=_map(), observed_time=observed, retrieved_time=observed)
        store = ShortIntelligenceStore()
        store.add_short_interest(si)
        cycle = cycle_for_settlement("2026-07-31")
        self.assertIsNotNone(cycle)
        assert cycle is not None
        self.assertEqual(cycle.publication_date, "2026-08-11")
        self.assertEqual(si.clocks["available_time"], ny_wall_to_utc_iso("2026-08-11", 16, 40))
        self.assertIsNone(store.short_interest_as_of("BIYA", "2026-08-01T00:00:00Z"))
        self.assertIsNotNone(store.short_interest_as_of("BIYA", cycle.provider_available_time))
        self.assertFalse(visible_at(si.clocks, "2026-08-01T12:00:00Z"))

    def test_revision_pit(self) -> None:
        rows = json.loads((FIXTURES / "consolidated_short_interest_slice.json").read_text(encoding="utf-8"))
        map_ = _map()
        v1 = normalize_short_interest_row(rows[0], symbol_map=map_, observed_time="2026-08-11T20:45:00Z", retrieved_time="2026-08-11T20:45:00Z")
        v2 = normalize_short_interest_row(rows[1], symbol_map=map_, observed_time="2026-08-12T15:00:00Z", retrieved_time="2026-08-12T15:00:00Z")
        clocks = dict(v2.clocks)
        clocks["available_time"] = "2026-08-12T15:00:00Z"
        clocks["observed_time"] = "2026-08-12T15:00:00Z"
        from dataclasses import replace

        v2 = replace(v2, clocks=clocks, record_version=2)
        store = ShortIntelligenceStore()
        store.add_short_interest(v1)
        store.add_short_interest(v2)
        mid = store.short_interest_as_of("BIYA", "2026-08-12T00:00:00Z")
        later = store.short_interest_as_of("BIYA", "2026-08-12T16:00:00Z")
        self.assertIsNotNone(mid)
        self.assertIsNotNone(later)
        assert mid is not None and later is not None
        self.assertEqual(mid.current_short_position_quantity, 1500000)
        self.assertEqual(later.current_short_position_quantity, 1600000)
        self.assertIn("REVISED", later.quality_flags)

    def test_zero_is_not_missing(self) -> None:
        rows = json.loads((FIXTURES / "consolidated_short_interest_slice.json").read_text(encoding="utf-8"))
        row = normalize_short_interest_row(rows[2], symbol_map=_map(), observed_time="2026-08-11T20:45:00Z", retrieved_time="2026-08-11T20:45:00Z")
        self.assertEqual(row.current_short_position_quantity, 0)
        store = ShortIntelligenceStore()
        store.add_short_interest(row)
        hit = store.short_interest_as_of("AAPL", row.clocks["available_time"])
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.current_short_position_quantity, 0)
        self.assertIsNone(store.short_interest_as_of("NVDA", row.clocks["available_time"]))

    def test_historical_backfill_marks_revision_unknown(self) -> None:
        rows = json.loads((FIXTURES / "consolidated_short_interest_slice.json").read_text(encoding="utf-8"))
        row = normalize_short_interest_row(rows[0], symbol_map=_map(), observed_time="2026-08-11T20:45:00Z", retrieved_time="2026-08-11T20:45:00Z")
        store = ShortIntelligenceStore()
        store.add_short_interest(row, historical_backfill=True)
        hit = store.short_interest_as_of("BIYA", row.clocks["available_time"])
        assert hit is not None
        self.assertIn("ORIGINAL_VERSION_UNAVAILABLE", hit.quality_flags)


class ShortSaleTests(unittest.TestCase):
    def test_facility_provenance_and_aggregation(self) -> None:
        rows = json.loads((FIXTURES / "reg_sho_daily_slice.json").read_text(encoding="utf-8"))
        observed = "2026-07-29T12:00:00Z"
        map_ = _map()
        observations = [
            normalize_short_sale_row(row, symbol_map=map_, observed_time=observed, retrieved_time=observed)
            for row in rows
        ]
        day = [item for item in observations if item.trade_report_date == "2026-07-28"]
        self.assertEqual(len(day), 2)
        aggregate = aggregate_short_sale_rows(day)
        self.assertEqual(aggregate["short_sale_volume"], 500)
        self.assertEqual(aggregate["finra_reported_total_volume"], 1500)
        self.assertAlmostEqual(aggregate["finra_reported_short_sale_ratio"], 500 / 1500)
        self.assertEqual(len(aggregate["reporting_facilities"]), 2)
        self.assertTrue(all(item.reporting_facility_code for item in day))
        self.assertNotEqual(day[0].observation_family, ObservationFamily.SHORT_INTEREST)


class ThresholdTests(unittest.TestCase):
    def test_publication_time_not_backdated(self) -> None:
        raw = (FIXTURES / "nasdaq_threshold_biya_20260728.txt").read_bytes()
        parsed = parse_threshold_file(raw, trade_date="2026-07-28")
        observations = normalize_threshold_file(
            parsed,
            symbol_map=_map(),
            observed_time="2026-07-29T04:00:00Z",
            retrieved_time="2026-07-29T04:00:00Z",
            requested_symbols=("BIYA",),
        )
        store = ShortIntelligenceStore()
        store.add_threshold(observations[0])
        self.assertIsNone(store.latest_threshold("BIYA", "2026-07-28T12:00:00Z"))
        later = store.latest_threshold("BIYA", observations[0].clocks["available_time"])
        self.assertIsNotNone(later)
        assert later is not None
        self.assertTrue(later.currently_threshold)
        self.assertEqual(later.listing_coverage, "NASDAQ")
        self.assertIn("FTD_QUANTITY_UNKNOWN", later.quality_flags)

    def test_duration_resets(self) -> None:
        payload = json.loads((FIXTURES / "nasdaq_threshold_run.json").read_text(encoding="utf-8"))
        map_ = SymbolMap(({"provider_symbol": "TEST", "instrument_id": "TEST", "venue_id": "US_EQUITY", "aliases": ["TEST"], "valid_from": "2020-01-01"},))
        store = ShortIntelligenceStore()
        dates = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04"]
        for key, trade_date in zip(("day1", "day2", "day3", "day4"), dates):
            parsed = parse_threshold_file(payload[key], trade_date=trade_date)
            for row in normalize_threshold_file(
                parsed,
                symbol_map=map_,
                observed_time="2026-07-05T00:00:00Z",
                retrieved_time="2026-07-05T00:00:00Z",
                requested_symbols=("TEST",),
            ):
                store.add_threshold(row)
        stats = threshold_duration(store.threshold_as_of("TEST", "2026-07-05T00:00:00Z"))
        self.assertFalse(stats["currently_threshold"])
        self.assertEqual(stats["consecutive_observed_threshold_days"], 0)
        self.assertEqual(stats["days_since_exited"], 1)
        early = threshold_duration(store.threshold_as_of("TEST", "2026-07-03T16:00:00Z"))
        self.assertTrue(early["currently_threshold"])
        self.assertEqual(early["consecutive_observed_threshold_days"], 3)

    def test_unknown_instrument(self) -> None:
        raw = (FIXTURES / "nasdaq_threshold_synthetic.txt").read_bytes()
        parsed = parse_threshold_file(raw, trade_date="2026-07-24")
        rows = normalize_threshold_file(
            parsed,
            symbol_map=_map(),
            observed_time="2026-07-24T16:00:00Z",
            retrieved_time="2026-07-24T16:00:00Z",
        )
        unknown = next(row for row in rows if row.provider_symbol == "ZZZZ")
        self.assertIn("IDENTITY_UNRESOLVED", unknown.quality_flags)
        self.assertEqual(unknown.instrument_id, "")


class OutageAndIdentityTests(unittest.TestCase):
    def test_source_outage_is_not_zero(self) -> None:
        def requester(method, url, headers, body, timeout):
            raise FakeHttpError(500)

        manager = FinraTokenManager(
            _creds(),
            requester=lambda url, headers, timeout: (200, b'{"access_token":"x","expires_in":1800}'),
        )
        transport = FinraTransport(manager, requester=requester, min_interval_s=0.0)
        with self.assertRaises(OSError) as ctx:
            transport.post("/data/group/otcMarket/name/consolidatedShortInterest", {"limit": 1})
        flags = quality_from_failure(ctx.exception)
        self.assertIn("SOURCE_UNAVAILABLE", flags)
        self.assertNotIn("0", flags)

    def test_nasdaq_outage(self) -> None:
        def requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
            raise FakeHttpError(503)

        transport = NasdaqTransport(requester=requester, min_interval_s=0.0)
        with self.assertRaises(OSError) as ctx:
            transport.fetch_threshold_file("2026-07-28")
        self.assertIn("SOURCE_UNAVAILABLE", str(ctx.exception))

    def test_symbol_reuse_is_temporal(self) -> None:
        map_ = _map()
        old = map_.resolve("OLDX", as_of="2023-06-01")
        new = map_.resolve("OLDX", as_of="2025-06-01")
        self.assertEqual(old.instrument_id, "REUSED")
        self.assertEqual(new.instrument_id, "NEWCO")

    def test_float_denominator_refuses_lookahead(self) -> None:
        self.assertIsNone(
            short_interest_pct_float(
                current_short_position=100,
                pit_shares_outstanding=1000,
                denominator_known_from="2026-08-12T00:00:00Z",
                observation_available_time="2026-08-11T20:40:00Z",
            )
        )
        self.assertEqual(
            short_interest_pct_float(
                current_short_position=100,
                pit_shares_outstanding=1000,
                denominator_known_from="2026-08-11T20:40:00Z",
                observation_available_time="2026-08-11T20:40:00Z",
            ),
            0.1,
        )


class SqueezeAndLifecycleTests(unittest.TestCase):
    def test_biya_case_and_ranking(self) -> None:
        map_ = _map()
        store = ShortIntelligenceStore()
        observed = "2026-08-11T20:45:00Z"
        si_rows = json.loads((FIXTURES / "consolidated_short_interest_slice.json").read_text(encoding="utf-8"))
        store.add_short_interest(
            normalize_short_interest_row(si_rows[0], symbol_map=map_, observed_time=observed, retrieved_time=observed)
        )
        flow_rows = json.loads((FIXTURES / "reg_sho_daily_slice.json").read_text(encoding="utf-8"))
        for row in flow_rows:
            store.add_short_sale(
                normalize_short_sale_row(row, symbol_map=map_, observed_time="2026-07-30T12:00:00Z", retrieved_time="2026-07-30T12:00:00Z")
            )
        for name, trade_date in (
            ("nasdaq_threshold_biya_20260724.txt", "2026-07-24"),
            ("nasdaq_threshold_biya_20260727.txt", "2026-07-27"),
            ("nasdaq_threshold_biya_20260728.txt", "2026-07-28"),
            ("nasdaq_threshold_biya_20260729.txt", "2026-07-29"),
        ):
            parsed = parse_threshold_file((FIXTURES / name).read_bytes(), trade_date=trade_date)
            for observation in normalize_threshold_file(
                parsed,
                symbol_map=map_,
                observed_time="2026-07-30T12:00:00Z",
                retrieved_time="2026-07-30T12:00:00Z",
                requested_symbols=("BIYA",),
            ):
                store.add_threshold(observation)
        as_of = "2026-08-11T21:00:00Z"
        state = pressure_state(store, "BIYA", as_of)
        self.assertEqual(state.threshold_status, "ACTIVE")
        self.assertEqual(state.borrow_state, "UNKNOWN")
        self.assertNotIn("squeeze_score", state.__dataclass_fields__)
        ranked = rank_candidates(store, ["BIYA"], as_of)
        self.assertEqual(ranked[0]["instrument_id"], "BIYA")
        fused = fuse_regulatory_and_short(
            regulatory_state={"fresh_8k": True, "dilution_terms_known": True},
            pressure=state,
        )
        self.assertIsNone(fused["squeeze_probability"])
        self.assertIn("DILUTION_VS_SHORT_CROWDING", fused["contradictions"])
        features = cross_source_features(store, "BIYA", as_of)
        self.assertFalse(features["predictive"])
        self.assertTrue(features["short_interest_rising_and_threshold"])

    def test_admission_still_requires_adr(self) -> None:
        with self.assertRaises(ValueError):
            next_lifecycle_state(ObservationLifecycle.QUALITY_CHARACTERIZED, ObservationLifecycle.ADMITTED)


class RedactionTests(unittest.TestCase):
    def test_tokens_are_redacted_and_scan_rules_match(self) -> None:
        cleaned = redact_mapping(
            {
                "access_token": "abc",
                "Authorization": "Bearer abc",
                "dataset": "regShoDaily",
                "token_refresh_success": True,
            }
        )
        self.assertEqual(cleaned["access_token"], "REDACTED")
        self.assertEqual(cleaned["Authorization"], "REDACTED")
        self.assertEqual(cleaned["dataset"], "regShoDaily")
        self.assertEqual(cleaned["token_refresh_success"], True)
        findings = scan_redacted_bytes(
            b'Authorization: Bearer abc\nFINRA_CLIENT_SECRET=realvalue\n',
            "PATH-1",
            "WORKTREE",
            SECRET_SCAN_RULES,
        )
        self.assertGreaterEqual(len(findings), 2)
        empty = scan_redacted_bytes(b"FINRA_CLIENT_SECRET=\n", "PATH-1", "WORKTREE", SECRET_SCAN_RULES)
        self.assertEqual(empty, [])
        self.assertNotIn("abc", json.dumps(findings))
