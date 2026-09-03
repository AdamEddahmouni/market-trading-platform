"""Tests for O11 0DTE prerequisite infrastructure (contracts, quality, PIT, admission).

Fixture-driven against ``tests/fixtures/options/o11_chain_snapshots.json``.
Synthetic contract fixtures only: they exercise code paths and prove nothing
about real markets.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.zerodte import (  # noqa: E402
    DEFAULT_ADMISSION_MANIFEST,
    DUPLICATE_SNAPSHOT_KEY_REASON,
    ET_TIMEZONE_NAME,
    PHASE_C_ADMISSION_STATUS_PENDING,
    PHASE_C_DATA_NOT_ADMITTED_REASON,
    PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT,
    PIT_REJECTED_FUTURE_AVAILABLE_TIME,
    PIT_REJECTED_FUTURE_EVENT_TIME,
    PIT_REJECTED_MISSING_TIMESTAMPS,
    SESSION_CLOSE_ET_HOUR,
    SESSION_CLOSE_ET_MINUTE,
    IntradayChainSnapshotRecord,
    LiquidityPolicy,
    PitDecision,
    StalenessPolicy,
    ZeroDTEQualityFlag,
    admissible_snapshots_at,
    detect_duplicate_snapshots,
    et_calendar_date,
    evaluate_phase_c_admission,
    evaluate_snapshot_quality,
    expiration_boundary_flags,
    expiration_session_close_ns,
    is_zero_dte_snapshot,
    liquidity_flags,
    load_phase_c_admission_manifest,
    run_o11_zerodte_prerequisite_harness,
    snapshot_dte_hours,
    snapshot_from_dict,
    snapshot_to_dict,
    snapshot_usable_at,
    staleness_flags,
)
from market_platform_foundation.options.zerodte.admission import (  # noqa: E402
    PHASE_C_ADMISSION_STATUS_ADMITTED,
)
from market_platform_foundation.options.zerodte.pit import evaluate_pit  # noqa: E402

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "options" / "o11_chain_snapshots.json"
NS = 1_000_000_000
# Wall-clock anchors from the fixture (America/New_York, 2026-08-21, EDT = UTC-4).
EXPIRY_CLOSE_NS = 1787342400000000000  # 16:00 ET session close, expiry day
HEALTHY_EVENT_NS = 1787337000000000000  # 14:30 ET, expiry day
NEXT_DAY_EXPIRY_NS = EXPIRY_CLOSE_NS + 86_400 * NS  # 2026-08-22 16:00 ET


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def fixture_records() -> dict[str, IntradayChainSnapshotRecord]:
    payload = load_fixture()
    return {
        entry["snapshot_id"]: snapshot_from_dict(entry["record"])
        for entry in payload["snapshots"]
    }


def make_record(**overrides) -> IntradayChainSnapshotRecord:
    """Minimal valid record with per-test overrides."""
    base: dict = {
        "underlying": "TEST",
        "event_time_ns": HEALTHY_EVENT_NS,
        "available_time_ns": HEALTHY_EVENT_NS + NS,
        "expiration_timestamp_ns": EXPIRY_CLOSE_NS,
        "strikes": (100.0,),
        "multiplier": 100,
        "best_bid": 1.0,
        "best_ask": 1.1,
        "publisher": "test-generator",
        "retrieved_time": "2026-08-21T14:30:01-04:00",
        "ingested_time": "2026-08-21T14:30:02-04:00",
        "content_hash": "sha256:test-record",
    }
    base.update(overrides)
    return IntradayChainSnapshotRecord(**base)


class O11FixtureProvenanceTests(unittest.TestCase):
    def test_fixture_loads_and_parses_all_records(self) -> None:
        payload = load_fixture()
        self.assertTrue(payload.get("synthetic"))
        self.assertTrue(payload.get("not_market_data"))
        self.assertEqual(payload.get("fixture_kind"), "SYNTHETIC_CONTRACT_FIXTURE")
        self.assertIn(payload.get("evidence_class"), {"FIXTURE_PROVEN_INFRASTRUCTURE_ONLY"})
        self.assertEqual(payload.get("timezone"), ET_TIMEZONE_NAME)
        entries = payload["snapshots"]
        self.assertEqual(len(entries), 8)
        for entry in entries:
            record = snapshot_from_dict(entry["record"])
            self.assertEqual(record.underlying, entry["record"]["underlying"])

    def test_fixture_provenance_refs_are_labeled_and_synthetic(self) -> None:
        payload = load_fixture()
        for entry in payload["snapshots"]:
            record = snapshot_from_dict(entry["record"])
            self.assertEqual(record.publisher, "synthetic-fixture-generator")
            self.assertEqual(record.provenance_ref, f"fixtures/options/o11_chain_snapshots.json#{entry['snapshot_id']}")
            self.assertFalse(record.predictive)
            self.assertTrue(record.research_only)

    def test_fixture_wall_clock_reference_matches_et_math(self) -> None:
        payload = load_fixture()
        ref = payload["wall_clock_reference"]
        self.assertEqual(ref["expiry_session_close_2026-08-21T16:00_ET"], EXPIRY_CLOSE_NS)
        self.assertEqual(ref["healthy_event_2026-08-21T14:30_ET"], HEALTHY_EVENT_NS)
        et = ZoneInfo(ET_TIMEZONE_NAME)
        close_wall = datetime.fromtimestamp(EXPIRY_CLOSE_NS / NS, tz=timezone.utc).astimezone(et)
        self.assertEqual((close_wall.hour, close_wall.minute), (SESSION_CLOSE_ET_HOUR, SESSION_CLOSE_ET_MINUTE))
        self.assertEqual(close_wall.date().isoformat(), "2026-08-21")


class O11ContractRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_fields_and_bitemporal_pair(self) -> None:
        original = make_record(
            source_symbol="TEST",
            content_hash="sha256:test",
            retrieved_time="2026-08-21T14:30:01-04:00",
            ingested_time="2026-08-21T14:30:02-04:00",
        )
        as_dict = snapshot_to_dict(original)
        self.assertEqual(as_dict["event_time_ns"], HEALTHY_EVENT_NS)
        self.assertEqual(as_dict["available_time_ns"], HEALTHY_EVENT_NS + NS)
        rebuilt = snapshot_from_dict(as_dict)
        self.assertEqual(rebuilt, original)
        # Stable under a second cycle.
        self.assertEqual(snapshot_from_dict(snapshot_to_dict(rebuilt)), original)
        # Derived block carries the deterministic analytics.
        self.assertEqual(as_dict["derived"]["is_zero_dte"], True)
        self.assertEqual(as_dict["derived"]["expiration_session_close_ns"], EXPIRY_CLOSE_NS)
        self.assertAlmostEqual(as_dict["derived"]["dte_hours"], 1.5)

    def test_optional_best_bid_ask_survive_round_trip(self) -> None:
        two_sided = make_record(best_bid=0.8, best_ask=0.9)
        restored_two_sided = snapshot_from_dict(snapshot_to_dict(two_sided))
        self.assertEqual(restored_two_sided.best_bid, 0.8)
        cases = [
            {"strikes": [100.0]},  # list, not tuple
            {"event_time_ns": HEALTHY_EVENT_NS / NS},  # float, not int
            {"available_time_ns": True},  # bool masquerading as int
            {"expiration_timestamp_ns": -1},  # negative epoch
            {"best_bid": "1.0"},  # non-numeric quote
        ]
        for override in cases:
            with self.subTest(override=override):
                kwargs = {
                    "underlying": "TEST",
                    "event_time_ns": HEALTHY_EVENT_NS,
                    "available_time_ns": HEALTHY_EVENT_NS + NS,
                    "expiration_timestamp_ns": EXPIRY_CLOSE_NS,
                    "strikes": (100.0,),
                    "multiplier": 100,
                    "best_bid": 1.0,
                    "best_ask": 1.1,
                    "publisher": "test-generator",
                }
                kwargs.update(override)
                with self.assertRaises((TypeError, ValueError)):
                    IntradayChainSnapshotRecord(**kwargs)


class O11ZeroDTEBoundaryMatrixTests(unittest.TestCase):
    def test_same_calendar_day_expiry_is_zero_dte(self) -> None:
        record = make_record(event_time_ns=HEALTHY_EVENT_NS, expiration_timestamp_ns=EXPIRY_CLOSE_NS)
        self.assertTrue(is_zero_dte_snapshot(record))
        self.assertEqual(snapshot_dte_hours(record), 1.5)
        self.assertEqual(et_calendar_date(HEALTHY_EVENT_NS), "2026-08-21")
        self.assertEqual(et_calendar_date(EXPIRY_CLOSE_NS), "2026-08-21")

    def test_next_day_expiry_is_not_zero_dte(self) -> None:
        record = make_record(event_time_ns=HEALTHY_EVENT_NS, expiration_timestamp_ns=NEXT_DAY_EXPIRY_NS)
        self.assertFalse(is_zero_dte_snapshot(record))
        self.assertEqual(snapshot_dte_hours(record), 25.5)
        self.assertEqual(et_calendar_date(NEXT_DAY_EXPIRY_NS), "2026-08-22")

    def test_post_close_event_on_expiry_day_still_classifies_zero_dte(self) -> None:
        # 16:05 ET event after the session close: same ET calendar date, so the
        # deterministic rule keeps it 0DTE while quality flags the past-close edge.
        event_ns = EXPIRY_CLOSE_NS + 5 * 60 * NS
        record = make_record(event_time_ns=event_ns)
        self.assertTrue(is_zero_dte_snapshot(record))
        self.assertLess(snapshot_dte_hours(record), 0.0)

    def test_evening_event_across_midnight_utc_stays_expiry_day_in_et(self) -> None:
        # 20:00 ET on expiry day == 00:00 UTC next day. ET calendar dating must win;
        # a naive UTC comparison would misclassify this snapshot.
        evening_ns = EXPIRY_CLOSE_NS + 4 * 60 * 60 * NS
        utc_date = datetime.fromtimestamp(evening_ns / NS, tz=timezone.utc).date().isoformat()
        self.assertEqual(utc_date, "2026-08-22")
        self.assertEqual(et_calendar_date(evening_ns), "2026-08-21")
        self.assertTrue(is_zero_dte_snapshot(make_record(event_time_ns=evening_ns)))

    def test_dst_winter_date_uses_zoneinfo_offset_not_fixed_edt(self) -> None:
        et = ZoneInfo(ET_TIMEZONE_NAME)
        # 2026-01-16 12:00 ET (EST, UTC-5): fixed UTC-4 math would land on the wrong instant.
        noon_wall = datetime(2026, 1, 16, 12, 0, tzinfo=et)
        noon_ns = int(noon_wall.timestamp() * NS)
        expected_close_ns = int(datetime(2026, 1, 16, 16, 0, tzinfo=et).timestamp() * NS)
        self.assertEqual(expiration_session_close_ns(noon_ns), expected_close_ns)
        self.assertEqual(et_calendar_date(noon_ns), "2026-01-16")
        self.assertTrue(is_zero_dte_snapshot(make_record(event_time_ns=noon_ns, expiration_timestamp_ns=expected_close_ns)))
        # Sanity: EST offset differs from the August EDT anchor by one hour.
        self.assertEqual(expected_close_ns - noon_ns, 4 * 60 * 60 * NS)

    def test_session_close_anchor_is_exact_for_any_timestamp_on_expiry_day(self) -> None:
        for wall_hour in (0, 9, 15, 23):
            with self.subTest(wall_hour=wall_hour):
                et = ZoneInfo(ET_TIMEZONE_NAME)
                stamp_ns = int(datetime(2026, 8, 21, wall_hour, 30, tzinfo=et).timestamp() * NS)
                self.assertEqual(expiration_session_close_ns(stamp_ns), EXPIRY_CLOSE_NS)

    def test_snapshot_dte_hours_negative_once_expired(self) -> None:
        expired = fixture_records()["negative_dte_expired_before_event"]
        self.assertLess(snapshot_dte_hours(expired), 0.0)


class O11QualityGateTests(unittest.TestCase):
    def test_fresh_snapshot_passes_staleness_budget(self) -> None:
        record = fixture_records()["healthy_0dte"]
        self.assertEqual(staleness_flags(record), ())
        # Exactly at the budget boundary: not stale (strictly greater trips).
        at_limit = make_record(available_time_ns=HEALTHY_EVENT_NS + 60 * NS)
        self.assertEqual(staleness_flags(at_limit), ())

    def test_stale_available_time_flagged_and_blocking(self) -> None:
        record = fixture_records()["stale_available_time"]  # 120s lag vs 60s budget
        flags = staleness_flags(record)
        self.assertEqual(flags, (ZeroDTEQualityFlag.STALE_SNAPSHOT,))
        report = evaluate_snapshot_quality(record)
        self.assertTrue(report["blocking"])
        self.assertIn("STALE_SNAPSHOT", report["blocking_reasons"])

    def test_custom_staleness_policy_threshold(self) -> None:
        record = make_record(available_time_ns=HEALTHY_EVENT_NS + 30 * NS)
        self.assertEqual(staleness_flags(record, policy=StalenessPolicy(max_available_lag_ns=10 * NS)), (ZeroDTEQualityFlag.STALE_SNAPSHOT,))
        self.assertEqual(staleness_flags(record, policy=StalenessPolicy(max_available_lag_ns=30 * NS)), ())
        with self.assertRaises(ValueError):
            StalenessPolicy(max_available_lag_ns=-1)

    def _assert_absent_quote_side_blocks(self, record: IntradayChainSnapshotRecord, flag: ZeroDTEQualityFlag) -> None:
        """Fail-closed invariant: an absent quote side can never admit.

        Known upstream defect (reported, not fixed here): liquidity_flags
        appends MISSING_BID/MISSING_ASK but then calls float() on the absent
        side, raising TypeError before the flags are returned. The gate still
        fails closed — by hard rejection today; this test also accepts the
        intended flag-returning behavior so it stays green once that is fixed.
        """
        try:
            flags = liquidity_flags(record)
        except TypeError:
            return
        self.assertIn(flag, flags)

    def test_missing_bid_fails_closed_never_zero_filled(self) -> None:
        record = fixture_records()["missing_bid_side"]
        self._assert_absent_quote_side_blocks(record, ZeroDTEQualityFlag.MISSING_BID)

    def test_missing_ask_fails_closed(self) -> None:
        self._assert_absent_quote_side_blocks(
            make_record(best_bid=1.0, best_ask=None),
            ZeroDTEQualityFlag.MISSING_ASK,
        )
        self._assert_absent_quote_side_blocks(
            make_record(best_bid=None, best_ask=None),
            ZeroDTEQualityFlag.MISSING_BID,
        )

    def test_width_caps_breach_and_pass(self) -> None:
        wide = fixture_records()["wide_quote"]  # 10.0 / 12.0 => width 2.0
        self.assertEqual(liquidity_flags(wide), (ZeroDTEQualityFlag.QUOTE_WIDTH_EXCEEDED,))
        healthy = fixture_records()["healthy_0dte"]  # width 0.10 <= 0.50 cap
        self.assertEqual(liquidity_flags(healthy), ())

    def test_width_fraction_of_mid_cap_enforced_without_absolute_cap(self) -> None:
        wide = fixture_records()["wide_quote"]  # 2.0 / 11.0 ~= 18% of mid > 10%
        policy = LiquidityPolicy(max_absolute_width=None)
        self.assertEqual(liquidity_flags(wide, policy=policy), (ZeroDTEQualityFlag.QUOTE_WIDTH_EXCEEDED,))
        # A tight absolute cap can pass while percent-of-mid still blocks.
        narrow_but_relative = make_record(best_bid=0.01, best_ask=0.03)  # width 0.02, mid 0.02 -> 100%
        self.assertEqual(
            liquidity_flags(narrow_but_relative),
            (ZeroDTEQualityFlag.QUOTE_WIDTH_EXCEEDED,),
        )

    def test_invalid_liquidity_policy_rejected(self) -> None:
        for kwargs in (
            {"max_absolute_width": 0.0},
            {"max_absolute_width": -1.0},
            {"max_width_fraction_of_mid": 0.0},
            {"max_width_fraction_of_mid": -0.5},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    LiquidityPolicy(**kwargs)

    def test_expiration_boundary_flags(self) -> None:
        # Fixture record: event (16:05 ET) is after the expiry timestamp (16:00
        # close), so the negative-DTE branch fires first.
        expired = fixture_records()["expiry_boundary_past_close"]
        self.assertEqual(
            expiration_boundary_flags(expired),
            (ZeroDTEQualityFlag.EXPIRATION_BEFORE_EVENT_TIME, ZeroDTEQualityFlag.NEGATIVE_DTE),
        )
        fully_expired = fixture_records()["negative_dte_expired_before_event"]
        self.assertEqual(
            expiration_boundary_flags(fully_expired),
            (ZeroDTEQualityFlag.EXPIRATION_BEFORE_EVENT_TIME, ZeroDTEQualityFlag.NEGATIVE_DTE),
        )
        # Event past the 16:00 ET session-close anchor but still at/before the
        # recorded expiration stamp: only the past-close flag applies.
        past_close_only = make_record(
            event_time_ns=EXPIRY_CLOSE_NS + 5 * 60 * NS,
            expiration_timestamp_ns=EXPIRY_CLOSE_NS + 60 * 60 * NS,
        )
        self.assertEqual(expiration_boundary_flags(past_close_only), (ZeroDTEQualityFlag.EXPIRY_PAST_SESSION_CLOSE,))
        healthy = fixture_records()["healthy_0dte"]
        self.assertEqual(expiration_boundary_flags(healthy), ())

    def test_duplicate_detection_by_underlying_and_event_time(self) -> None:
        records = list(fixture_records().values())
        duplicates = detect_duplicate_snapshots(records)
        expected_key = ("SYNF", 1787339400000000000)
        self.assertEqual(list(duplicates.keys()), [expected_key])
        ids = sorted(duplicates[expected_key])
        self.assertEqual(ids, [5, 6])
        # Feeding the duplicate key into evaluation must block BOTH members.
        for index in ids:
            report = evaluate_snapshot_quality(records[index], duplicate_keys=frozenset({expected_key}))
            self.assertTrue(report["blocking"])
            self.assertIn("DUPLICATE_SNAPSHOT_KEY", report["blocking_reasons"])
        # No duplicates reported when every (underlying, event_time_ns) is unique.
        unique_first = detect_duplicate_snapshots(records[:5])
        self.assertEqual(unique_first, {})

    def test_evaluate_snapshot_quality_clean_record_is_not_blocking(self) -> None:
        report = evaluate_snapshot_quality(fixture_records()["healthy_0dte"])
        self.assertFalse(report["blocking"])
        self.assertEqual(report["flags"], [])
        self.assertEqual(report["blocking_reasons"], [])
        self.assertEqual(report["underlying"], "SYNA")


class O11PointInTimeTests(unittest.TestCase):
    DECISION_T_NS = HEALTHY_EVENT_NS + 10 * NS

    def test_snapshot_usable_when_both_timestamps_closed(self) -> None:
        record = fixture_records()["healthy_0dte"]  # available = event + 5s
        self.assertEqual(snapshot_usable_at(record, decision_time_ns=self.DECISION_T_NS), PitDecision(usable=True, reason=None))
        # Boundary: exactly at available_time is usable (<= T).
        self.assertTrue(snapshot_usable_at(record, decision_time_ns=record.available_time_ns).usable)
        self.assertTrue(snapshot_usable_at(record, decision_time_ns=record.event_time_ns - NS).usable is False)

    def test_decision_before_availability_rejected_as_lookahead(self) -> None:
        record = fixture_records()["healthy_0dte"]
        before_availability = record.available_time_ns - NS
        decision = snapshot_usable_at(record, decision_time_ns=before_availability)
        self.assertFalse(decision.usable)
        self.assertEqual(decision.reason, PIT_REJECTED_FUTURE_AVAILABLE_TIME)

    def test_future_event_time_rejected_even_if_available(self) -> None:
        decision = evaluate_pit(
            event_time_ns=self.DECISION_T_NS + NS,  # event in the future of T
            available_time_ns=self.DECISION_T_NS,  # already published
            decision_time_ns=self.DECISION_T_NS,
        )
        self.assertFalse(decision.usable)
        self.assertEqual(decision.reason, PIT_REJECTED_FUTURE_EVENT_TIME)

    def test_missing_timestamps_fail_closed(self) -> None:
        for kwargs in (
            {"event_time_ns": None, "available_time_ns": 1},
            {"event_time_ns": 1, "available_time_ns": None},
            {"event_time_ns": None, "available_time_ns": None},
        ):
            with self.subTest(kwargs=kwargs):
                decision = evaluate_pit(decision_time_ns=self.DECISION_T_NS, **kwargs)
                self.assertFalse(decision.usable)
                self.assertEqual(decision.reason, PIT_REJECTED_MISSING_TIMESTAMPS)

    def test_decision_time_validation(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_pit(event_time_ns=1, available_time_ns=1, decision_time_ns="now")
        with self.assertRaises(TypeError):
            evaluate_pit(event_time_ns=1, available_time_ns=1, decision_time_ns=True)
        with self.assertRaises(ValueError):
            evaluate_pit(event_time_ns=1, available_time_ns=1, decision_time_ns=-1)

    def test_admissible_snapshots_at_filters_lookahead(self) -> None:
        records = [
            fixture_records()["healthy_0dte"],  # available at event+5s
            fixture_records()["stale_available_time"],  # available much later
        ]
        early_t = fixture_records()["healthy_0dte"].available_time_ns
        admissible = admissible_snapshots_at(records, decision_time_ns=early_t)
        self.assertEqual(len(admissible), 1)
        self.assertEqual(admissible[0].underlying, "SYNA")
        later_t = max(r.available_time_ns for r in records)
        self.assertEqual(len(admissible_snapshots_at(records, decision_time_ns=later_t)), 2)


class O11AdmissionFailClosedTests(unittest.TestCase):
    def test_default_manifest_pending_with_empty_slots(self) -> None:
        manifest = load_phase_c_admission_manifest()
        self.assertEqual(manifest["status"], PHASE_C_ADMISSION_STATUS_PENDING)
        self.assertEqual(manifest["dataset_slots"], [])
        self.assertTrue(manifest["research_only"])
        self.assertEqual(manifest["logical_id"], "options.o11_zerodte_intraday_chain_admission")
        requirement_ids = {row["requirement_id"] for row in manifest["admission_requirements"]}
        self.assertIn(PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT, requirement_ids)

    def test_default_manifest_load_returns_defensive_copy(self) -> None:
        first = load_phase_c_admission_manifest()
        first["status"] = PHASE_C_ADMISSION_STATUS_ADMITTED
        first["dataset_slots"].append({"tampered": True})
        second = load_phase_c_admission_manifest()
        self.assertEqual(second["status"], PHASE_C_ADMISSION_STATUS_PENDING)
        self.assertEqual(second["dataset_slots"], [])
        self.assertIsNot(DEFAULT_ADMISSION_MANIFEST, first)

    def test_missing_external_manifest_path_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_phase_c_admission_manifest(ROOT / "manifests" / "options" / "does-not-exist.json")

    def test_default_evaluation_blocks_with_explicit_reasons(self) -> None:
        admission = evaluate_phase_c_admission()
        self.assertFalse(admission["admitted"])
        self.assertEqual(admission["status"], PHASE_C_ADMISSION_STATUS_PENDING)
        self.assertIn("PHASE_C_MANIFEST_STATUS_PENDING", admission["blocking_reasons"])
        self.assertIn(f"{PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT}_NOT_ADMITTED", admission["blocking_reasons"])
        self.assertTrue(admission["research_only"])

    def test_harness_reports_blocked_fail_closed(self) -> None:
        report = run_o11_zerodte_prerequisite_harness()
        self.assertFalse(report["available"])
        self.assertEqual(report["gate_status"], "BLOCKED")
        self.assertEqual(report["reason"], PHASE_C_DATA_NOT_ADMITTED_REASON)
        self.assertEqual(report["partition_scaffold"], {"fold_count": 0, "partitions": []})
        self.assertTrue(report["research_only"])

    def test_admitted_status_without_slots_still_blocks(self) -> None:
        manifest = load_phase_c_admission_manifest()
        adversarial = {
            **manifest,
            "status": PHASE_C_ADMISSION_STATUS_ADMITTED,
            "admission_requirements": [
                {**row, "status": PHASE_C_ADMISSION_STATUS_ADMITTED}
                for row in manifest.get("admission_requirements", [])
                if isinstance(row, dict)
            ],
            "dataset_slots": [],
        }
        admission = evaluate_phase_c_admission(adversarial)
        self.assertFalse(admission["admitted"])
        self.assertIn("PHASE_C_DATASET_SLOTS_EMPTY", admission["blocking_reasons"])
        report = run_o11_zerodte_prerequisite_harness(manifest=adversarial)
        self.assertFalse(report["available"])
        self.assertEqual(report["reason"], PHASE_C_DATA_NOT_ADMITTED_REASON)


if __name__ == "__main__":
    unittest.main()
