"""CFTC COT institutional positioning — unit and acceptance tests."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.contracts import (
    CotParticipantCategory,
    CotPositionScope,
    CotReportFamily,
)
from market_platform_foundation.cftc.datasets import CotDataset, dataset_spec, require_position_scope
from market_platform_foundation.cftc.derived import compute_net, compute_net_pct_oi, derive_features
from market_platform_foundation.cftc.mapping import CotProductMapper, load_mapper_from_fixture
from market_platform_foundation.cftc.normalize import (
    filter_scope_rows,
    normalize_api_rows,
    to_futures_positioning_report,
)
from market_platform_foundation.cftc.parser import parse_cot_row
from market_platform_foundation.cftc.quality import CotQualityFlag, quality_blocks_positioning
from market_platform_foundation.cftc.release_schedule import (
    HOLIDAY_FIXTURE_POSITION,
    HOLIDAY_FIXTURE_PUBLICATION,
    PIT_FIXTURE_POSITION,
    PIT_FIXTURE_PUBLICATION,
    is_visible_at,
    publication_time_utc,
    release_for_position_date,
)
from market_platform_foundation.cftc.store import CotStore
from market_platform_foundation.cftc.sync import CotSync
from market_platform_foundation.cftc.transport import CotTransportError
from market_platform_foundation.contracts.futures import cot_point_in_time_valid
from market_platform_foundation.contracts.reference import ReferenceKind

FIXTURES = ROOT / "tests" / "fixtures" / "cftc"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class CotDatasetTests(unittest.TestCase):
    def test_official_dataset_ids(self) -> None:
        self.assertEqual(CotDataset.TFF_FUTURES_ONLY.value, "gpe5-46if")
        self.assertEqual(CotDataset.TFF_COMBINED.value, "yw9f-hn96")
        self.assertEqual(CotDataset.DISAGGREGATED_FUTURES_ONLY.value, "72hh-3qpy")
        self.assertEqual(CotDataset.LEGACY_FUTURES_ONLY.value, "6dca-aqww")
        self.assertEqual(CotDataset.PRODUCT_HIERARCHY.value, "rj6x-va3z")

    def test_require_scope_raises_on_ambiguity(self) -> None:
        with self.assertRaises(ValueError):
            require_position_scope(None)


class CotParserTests(unittest.TestCase):
    def test_tff_categories_preserved(self) -> None:
        payload = _load_fixture("tff_futures_only_es.json")
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        parsed = parse_cot_row(payload["rows"][0], spec=spec)
        categories = {row.participant_category for row in parsed.categories}
        self.assertIn(CotParticipantCategory.LEVERAGED_FUNDS, categories)
        self.assertIn(CotParticipantCategory.ASSET_MANAGER_INSTITUTIONAL, categories)
        self.assertIn(CotParticipantCategory.DEALER_INTERMEDIARY, categories)

    def test_disaggregated_managed_money_distinct_from_tff_leveraged(self) -> None:
        payload = _load_fixture("disaggregated_futures_only_cl.json")
        spec = dataset_spec(CotDataset.DISAGGREGATED_FUTURES_ONLY)
        parsed = parse_cot_row(payload["rows"][0], spec=spec)
        categories = {row.participant_category for row in parsed.categories}
        self.assertIn(CotParticipantCategory.MANAGED_MONEY, categories)
        self.assertNotIn(CotParticipantCategory.LEVERAGED_FUNDS, categories)


class CotNormalizeTests(unittest.TestCase):
    def test_tff_futures_only_normalization(self) -> None:
        payload = _load_fixture("tff_futures_only_es.json")
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        mapper = CotProductMapper()
        observations = normalize_api_rows(
            payload["rows"],
            spec=spec,
            mapper=mapper,
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        self.assertGreater(len(observations), 0)
        lev = next(
            obs
            for obs in observations
            if obs.participant_category == CotParticipantCategory.LEVERAGED_FUNDS
        )
        self.assertEqual(lev.contract_family_id, "ES")
        self.assertEqual(lev.position_scope, CotPositionScope.FUTURES_ONLY)
        self.assertEqual(lev.report_family, CotReportFamily.TFF)
        self.assertFalse(lev.predictive)

    def test_unresolved_mapping_flagged(self) -> None:
        payload = _load_fixture("unresolved_mapping.json")
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        observations = normalize_api_rows(
            payload["rows"],
            spec=spec,
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        self.assertTrue(
            any(CotQualityFlag.PRODUCT_MAPPING_UNRESOLVED.value in obs.quality_flags for obs in observations)
        )

    def test_contract_family_not_specific_expiration(self) -> None:
        payload = _load_fixture("tff_futures_only_es.json")
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        observations = normalize_api_rows(
            payload["rows"],
            spec=spec,
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        report = to_futures_positioning_report(observations[0])
        self.assertTrue(report["is_contract_family_level"])
        self.assertFalse(report["is_specific_expiration"])


class CotScopeTests(unittest.TestCase):
    def test_double_count_protection_requires_scope_filter(self) -> None:
        payload = _load_fixture("scope_double_count.json")
        fo_rows = filter_scope_rows(payload["rows"], CotPositionScope.FUTURES_ONLY)
        combined_rows = filter_scope_rows(payload["rows"], CotPositionScope.FUTURES_AND_OPTIONS_COMBINED)
        self.assertEqual(len(fo_rows), 1)
        self.assertEqual(len(combined_rows), 1)
        self.assertNotEqual(
            fo_rows[0].get("open_interest_all"),
            combined_rows[0].get("open_interest_all"),
        )

    def test_unfiltered_all_rows_not_both_in_canonical_aggregate(self) -> None:
        payload = _load_fixture("scope_double_count.json")
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        mapper = CotProductMapper()
        # Without scope filter on All-shaped data, both rows would normalize
        unfiltered = normalize_api_rows(
            payload["rows"],
            spec=spec,
            mapper=mapper,
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        fo_only = normalize_api_rows(
            filter_scope_rows(payload["rows"], CotPositionScope.FUTURES_ONLY),
            spec=spec,
            mapper=mapper,
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        self.assertGreater(len(unfiltered), len(fo_only))


class CotPitTests(unittest.TestCase):
    def test_tuesday_friday_release_lag(self) -> None:
        release = release_for_position_date(PIT_FIXTURE_POSITION)
        assert release is not None
        self.assertEqual(release.publication_date, PIT_FIXTURE_PUBLICATION)
        pub_time = publication_time_utc(PIT_FIXTURE_PUBLICATION)

        thursday = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        self.assertFalse(is_visible_at(PIT_FIXTURE_PUBLICATION, thursday))
        self.assertFalse(
            cot_point_in_time_valid(
                "2026-08-18T00:00:00Z",
                pub_time,
                "2026-08-20T16:00:00.000000000Z",
            )
        )

        from zoneinfo import ZoneInfo

        friday_1529_et = datetime(2026, 8, 21, 15, 29, tzinfo=ZoneInfo("America/New_York"))
        self.assertFalse(is_visible_at(PIT_FIXTURE_PUBLICATION, friday_1529_et))
        self.assertFalse(
            cot_point_in_time_valid(
                "2026-08-18T00:00:00Z",
                pub_time,
                friday_1529_et.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
            )
        )

        friday_1530_et = datetime(2026, 8, 21, 15, 30, tzinfo=ZoneInfo("America/New_York"))
        self.assertTrue(is_visible_at(PIT_FIXTURE_PUBLICATION, friday_1530_et))
        self.assertTrue(
            cot_point_in_time_valid(
                "2026-08-18T00:00:00Z",
                pub_time,
                friday_1530_et.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
            )
        )

    def test_holiday_delayed_release_not_friday(self) -> None:
        release = release_for_position_date(HOLIDAY_FIXTURE_POSITION)
        assert release is not None
        self.assertEqual(release.publication_date, HOLIDAY_FIXTURE_PUBLICATION)
        self.assertTrue(release.delayed)
        # Friday Nov 27 2026 is Thanksgiving — report NOT visible on that Friday
        from zoneinfo import ZoneInfo

        thanksgiving_friday = datetime(2026, 11, 27, 16, 0, tzinfo=ZoneInfo("America/New_York"))
        self.assertFalse(is_visible_at(HOLIDAY_FIXTURE_PUBLICATION, thanksgiving_friday))
        pub_time = publication_time_utc(HOLIDAY_FIXTURE_PUBLICATION)
        monday_delayed = datetime(2026, 11, 30, 15, 30, tzinfo=ZoneInfo("America/New_York"))
        self.assertTrue(is_visible_at(HOLIDAY_FIXTURE_PUBLICATION, monday_delayed))
        self.assertTrue(
            cot_point_in_time_valid(
                "2026-11-24T00:00:00Z",
                pub_time,
                monday_delayed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
            )
        )


class CotCategorySeparationTests(unittest.TestCase):
    def test_categories_remain_distinct(self) -> None:
        tff = _load_fixture("tff_futures_only_es.json")
        disagg = _load_fixture("disaggregated_futures_only_cl.json")
        legacy = _load_fixture("legacy_futures_only_gc.json")
        tff_obs = normalize_api_rows(
            tff["rows"],
            spec=dataset_spec(CotDataset.TFF_FUTURES_ONLY),
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        disagg_obs = normalize_api_rows(
            disagg["rows"],
            spec=dataset_spec(CotDataset.DISAGGREGATED_FUTURES_ONLY),
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        legacy_obs = normalize_api_rows(
            legacy["rows"],
            spec=dataset_spec(CotDataset.LEGACY_FUTURES_ONLY),
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        tff_cats = {obs.participant_category for obs in tff_obs}
        disagg_cats = {obs.participant_category for obs in disagg_obs}
        legacy_cats = {obs.participant_category for obs in legacy_obs}
        self.assertIn(CotParticipantCategory.ASSET_MANAGER_INSTITUTIONAL, tff_cats)
        self.assertIn(CotParticipantCategory.LEVERAGED_FUNDS, tff_cats)
        self.assertIn(CotParticipantCategory.MANAGED_MONEY, disagg_cats)
        self.assertIn(CotParticipantCategory.NON_COMMERCIAL, legacy_cats)
        self.assertNotIn(CotParticipantCategory.MANAGED_MONEY, tff_cats)


class CotDerivedTests(unittest.TestCase):
    def test_net_and_pct_oi_from_compatible_oi(self) -> None:
        payload = _load_fixture("tff_futures_only_es.json")
        observations = normalize_api_rows(
            payload["rows"],
            spec=dataset_spec(CotDataset.TFF_FUTURES_ONLY),
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        lev = next(
            obs
            for obs in observations
            if obs.participant_category == CotParticipantCategory.LEVERAGED_FUNDS
        )
        net = compute_net(lev)
        assert net is not None
        self.assertEqual(net, 30000)
        pct = compute_net_pct_oi(lev)
        assert pct is not None
        self.assertAlmostEqual(pct, 30000 / 2500000, places=6)
        features = derive_features(lev, [])
        self.assertFalse(features.predictive)

    def test_weekly_change_is_not_trade_flow(self) -> None:
        features = derive_features(
            __import__("market_platform_foundation.cftc.contracts", fromlist=["InstitutionalPositioningObservation"]).InstitutionalPositioningObservation(
                market_id="x",
                contract_family_id="ES",
                cftc_contract_market_code="13874+",
                cftc_commodity_code="138",
                market_and_exchange_names="ES",
                report_family=CotReportFamily.TFF,
                position_scope=CotPositionScope.FUTURES_ONLY,
                participant_category=CotParticipantCategory.LEVERAGED_FUNDS,
                position_date="2026-08-11T00:00:00Z",
                publication_time="2026-08-14T19:30:00Z",
                available_time="2026-08-14T19:30:00Z",
                observed_time="2026-08-14T20:00:00Z",
                long_positions=320000,
                short_positions=280000,
                open_interest=2500000,
            ),
            [],
        )
        self.assertIn("trade flow", features.disclaimer)


class CotStoreTests(unittest.TestCase):
    def test_pit_query_excludes_unreleased(self) -> None:
        store = CotStore()
        payload = _load_fixture("tff_futures_only_es.json")
        observations = normalize_api_rows(
            payload["rows"],
            spec=dataset_spec(CotDataset.TFF_FUTURES_ONLY),
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        store.add_observations(observations)
        pub_time = observations[0].publication_time
        before_pub = (
            datetime.fromisoformat(pub_time.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.000000000Z"
            )
        )
        # Query before publication
        visible, flags = store.latest_visible_or_flags(
            contract_family_id="ES",
            decision_time="2026-08-13T12:00:00.000000000Z",
            position_scope=CotPositionScope.FUTURES_ONLY,
        )
        self.assertIsNone(visible)
        self.assertIn(CotQualityFlag.REPORT_NOT_YET_RELEASED.value, flags)

    def test_bitemporal_reference_kind(self) -> None:
        store = CotStore()
        payload = _load_fixture("tff_futures_only_es.json")
        observations = normalize_api_rows(
            payload["rows"],
            spec=dataset_spec(CotDataset.TFF_FUTURES_ONLY),
            mapper=CotProductMapper(),
            observed_time="2026-08-14T20:00:00Z",
            retrieved_time="2026-08-14T20:00:00Z",
        )
        store.add_observations(observations)
        record = store.bitemporal.as_of(
            ReferenceKind.COT_POSITIONING,
            CotStore._entity_key(observations[0]),
            observations[0].position_date,
            observations[0].available_time,
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.payload.get("contract_family_id"), "ES")


class CotSourceOutageTests(unittest.TestCase):
    def test_source_unavailable_not_zero_positions(self) -> None:
        from market_platform_foundation.cftc.transport import CotTransport

        class FailingTransport(CotTransport):
            def query_dataset(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                raise CotTransportError("SOURCE_UNAVAILABLE")

        sync = CotSync(store=CotStore(), transport=FailingTransport())
        result = sync.sync_cot(position_dates=("2026-08-11",))
        self.assertTrue(any(r.get("status") == "source_unavailable" for r in result["results"]))
        self.assertEqual(sync.store.stats()["observation_count"], 0)

    def test_quality_blocks_empty_as_not_zero(self) -> None:
        self.assertTrue(quality_blocks_positioning((CotQualityFlag.SOURCE_UNAVAILABLE.value,)))


class CotProductMappingTests(unittest.TestCase):
    def test_hierarchy_fixture_extends_mapper(self) -> None:
        mapper = load_mapper_from_fixture(FIXTURES / "product_hierarchy_slice.json")
        mapping = mapper.resolve(cftc_contract_market_code="13874+", market_and_exchange_names="ES")
        self.assertEqual(mapping.contract_family_id, "ES")
        self.assertTrue(mapping.resolved)


class CotRevisionTests(unittest.TestCase):
    def test_source_revision_preserves_versions(self) -> None:
        payload = _load_fixture("source_revision.json")
        base_row = {
            "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
            "report_date_as_yyyy_mm_dd": payload["position_date"],
            "cftc_contract_market_code": "13874+",
            "cftc_commodity_code": "138",
            "open_interest_all": "2500000",
            "dealer_positions_long_all": "120000",
            "dealer_positions_short": "95000",
            "asset_mgr_positions_long": "450000",
            "asset_mgr_positions_short": "380000",
            "other_rept_positions_long": "85000",
            "other_rept_positions_short": "72000",
            "nonrept_positions_long_all": "95000",
            "nonrept_positions_short_all": "110000",
        }
        store = CotStore()
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        mapper = CotProductMapper()
        for version in payload["versions"]:
            row = dict(base_row)
            row["lev_money_positions_long"] = version["lev_money_positions_long"]
            row["lev_money_positions_short"] = version["lev_money_positions_short"]
            observations = normalize_api_rows(
                [row],
                spec=spec,
                mapper=mapper,
                observed_time=version["observed_time"],
                retrieved_time=version["observed_time"],
            )
            store.add_observations(observations)
        lev_versions = [
            obs
            for obs in store.observations
            if obs.participant_category == CotParticipantCategory.LEVERAGED_FUNDS
        ]
        self.assertEqual(len(lev_versions), 2)
        self.assertNotEqual(lev_versions[0].content_hash, lev_versions[1].content_hash)


if __name__ == "__main__":
    unittest.main()
