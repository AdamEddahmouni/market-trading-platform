"""EIA physical energy fundamentals — unit and acceptance tests."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.contracts import (
    CotParticipantCategory,
    CotPositionScope,
    CotReportFamily,
    InstitutionalPositioningObservation,
)
from market_platform_foundation.cftc.store import CotStore
from market_platform_foundation.contracts.reference import ReferenceKind
from market_platform_foundation.eia.capture import capture_envelope
from market_platform_foundation.eia.contracts import (
    EnergyCommodity,
    EnergyMetricClass,
    EnergyReleaseFamily,
)
from market_platform_foundation.eia.cross_asset import build_energy_market_context
from market_platform_foundation.eia.derived import build_energy_fundamentals_state, derive_balance_change
from market_platform_foundation.eia.health import capability_report
from market_platform_foundation.eia.normalize import (
    assert_metric_class,
    assert_no_commercial_spr_mix,
    assert_region_distinct,
    normalize_api_row,
    normalize_api_rows,
    parse_eia_value,
)
from market_platform_foundation.eia.pit import energy_as_of, observation_visible, query_visible
from market_platform_foundation.eia.quality import EiaQualityFlag, quality_blocks_fundamentals
from market_platform_foundation.eia.redaction import redact_text, sanitize_response_payload
from market_platform_foundation.eia.registry import FULL_REGISTRY, lookup_canonical
from market_platform_foundation.eia.release_schedule import (
    PIT_FIXTURE_WNGSR_PERIOD_END,
    PIT_FIXTURE_WPSR_PERIOD_END,
    WNGSR_HOLIDAY_FIXTURE_PERIOD_END,
    WPSR_HOLIDAY_FIXTURE_PERIOD_END,
    is_visible_at,
    naive_wednesday_would_leak,
    publication_time_utc,
    release_for_period_end,
)
from market_platform_foundation.eia.store import EiaStore
from market_platform_foundation.eia.transport import EiaTransport, EiaTransportError, MAX_JSON_ROWS
from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.registry import lookup_canonical as lookup_macro

FIXTURES = ROOT / "tests" / "fixtures" / "eia"
FAKE_KEY = "FAKE_EIA_SECRET"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class EiaRedactionTests(unittest.TestCase):
    def test_url_api_key_redacted(self) -> None:
        dirty = f"https://api.eia.gov/v2/petroleum/sum/sndw/data?api_key={FAKE_KEY}&frequency=weekly"
        clean = redact_text(dirty)
        self.assertNotIn(FAKE_KEY, clean)
        self.assertIn("REDACTED", clean)

    def test_response_echo_api_key_sanitized(self) -> None:
        for fixture in ("request_echo_redaction.json", "request_echo_redaction_nested.json"):
            payload = _load(fixture)
            sanitized = sanitize_response_payload(payload)
            serialized = json.dumps(sanitized)
            self.assertNotIn(FAKE_KEY, serialized)
            self.assertIn("REDACTED", serialized)


class EiaRegistryTests(unittest.TestCase):
    def test_bounded_registry(self) -> None:
        self.assertGreaterEqual(len(FULL_REGISTRY), 20)
        self.assertLessEqual(len(FULL_REGISTRY), 30)

    def test_commercial_and_spr_separate(self) -> None:
        commercial = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        spr = lookup_canonical("SPR_CRUDE_STOCKS")
        assert commercial and spr
        self.assertNotEqual(commercial.series, spr.series)
        self.assertNotEqual(commercial.product, spr.product)


class EiaNormalizeTests(unittest.TestCase):
    def test_petroleum_rows_normalize(self) -> None:
        payload = _load("petroleum_weekly_rows.json")
        observations = normalize_api_rows(
            payload["rows"],
            observed_time=payload["observed_time"],
            retrieved_time=payload["retrieved_time"],
            api_first_observed_time=payload["api_first_observed_time"],
        )
        self.assertGreaterEqual(len(observations), 5)
        commercial = next(o for o in observations if o.canonical_indicator_id == "COMMERCIAL_CRUDE_STOCKS")
        self.assertEqual(commercial.metric_class, EnergyMetricClass.STOCK)
        self.assertEqual(commercial.unit, "Thousand Barrels")
        self.assertFalse(commercial.predictive)

    def test_withheld_value_not_zero(self) -> None:
        raw, normalized, flags = parse_eia_value("W")
        self.assertIsNone(normalized)
        self.assertIn(EiaQualityFlag.WITHHELD.value, flags)

    def test_stock_flow_semantics(self) -> None:
        commercial = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        production = lookup_canonical("CRUDE_OIL_PRODUCTION")
        assert commercial and production
        self.assertTrue(assert_metric_class(commercial, EnergyMetricClass.STOCK))
        self.assertTrue(assert_metric_class(production, EnergyMetricClass.FLOW_RATE))
        self.assertNotEqual(commercial.metric_class, production.metric_class)

    def test_commercial_spr_not_mixed(self) -> None:
        payload = _load("petroleum_weekly_rows.json")
        observations = normalize_api_rows(
            payload["rows"],
            observed_time=payload["observed_time"],
            retrieved_time=payload["retrieved_time"],
            api_first_observed_time=payload["api_first_observed_time"],
        )
        self.assertTrue(assert_no_commercial_spr_mix(observations))

    def test_region_distinct(self) -> None:
        self.assertTrue(assert_region_distinct("CUSHING_OK", "PADD_2"))
        self.assertTrue(assert_region_distinct("CUSHING_OK", "US_TOTAL"))


class EiaNaturalGasTests(unittest.TestCase):
    def test_working_gas_is_stock(self) -> None:
        entry = lookup_canonical("LOWER48_WORKING_GAS_STORAGE")
        assert entry
        self.assertEqual(entry.metric_class, EnergyMetricClass.STOCK)
        self.assertEqual(entry.commodity, EnergyCommodity.NATURAL_GAS)

    def test_storage_change_is_balance_change(self) -> None:
        payload = _load("natural_gas_weekly_rows.json")
        observations = normalize_api_rows(
            payload["rows"][:2],
            observed_time=payload["observed_time"],
            retrieved_time=payload["retrieved_time"],
            api_first_observed_time=payload["api_first_observed_time"],
        )
        derived = derive_balance_change(
            observations,
            canonical_indicator_id="LOWER48_WORKING_GAS_STORAGE",
            decision_time="2026-08-20T15:00:00Z",
        )
        self.assertEqual(derived.weekly_balance_change, 71.0)
        self.assertFalse(derived.predictive)


class EiaPitTests(unittest.TestCase):
    def _obs(self, *, available_time: str, period_end: str = "2026-08-08") -> object:
        entry = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        assert entry
        return normalize_api_row(
            {"period": period_end, "series": entry.series, "value": 100},
            entry=entry,
            observed_time=available_time,
            retrieved_time=available_time,
            api_first_observed_time=available_time,
        )

    def test_wpsr_pre_release_not_visible(self) -> None:
        release = release_for_period_end(PIT_FIXTURE_WPSR_PERIOD_END, EnergyReleaseFamily.WPSR)
        assert release
        pub = publication_time_utc(release)
        obs = self._obs(available_time=pub)
        assert obs
        self.assertFalse(observation_visible(obs, "2026-08-19T14:29:00Z"))
        self.assertTrue(observation_visible(obs, "2026-08-19T15:00:00Z"))

    def test_wngsr_pre_release_not_visible(self) -> None:
        release = release_for_period_end(PIT_FIXTURE_WNGSR_PERIOD_END, EnergyReleaseFamily.WNGSR)
        assert release
        pub = publication_time_utc(release)
        entry = lookup_canonical("LOWER48_WORKING_GAS_STORAGE")
        assert entry
        obs = normalize_api_row(
            {"period": str(PIT_FIXTURE_WNGSR_PERIOD_END), "series": entry.series, "value": 3000},
            entry=entry,
            observed_time=pub,
            retrieved_time=pub,
            api_first_observed_time=pub,
        )
        assert obs
        self.assertFalse(observation_visible(obs, "2026-08-20T14:29:00Z"))
        self.assertTrue(observation_visible(obs, "2026-08-20T15:00:00Z"))

    def test_wpsr_holiday_not_naive_wednesday(self) -> None:
        release = release_for_period_end(WPSR_HOLIDAY_FIXTURE_PERIOD_END, EnergyReleaseFamily.WPSR)
        assert release
        self.assertTrue(release.holiday_adjusted)
        self.assertTrue(naive_wednesday_would_leak(release))
        from market_platform_foundation.eia.release_schedule import ET

        wed_1030 = datetime(2026, 11, 18, 10, 30, tzinfo=ET)
        self.assertFalse(is_visible_at(release, wed_1030.astimezone(timezone.utc)))

    def test_wngsr_holiday_wednesday_noon(self) -> None:
        release = release_for_period_end(WNGSR_HOLIDAY_FIXTURE_PERIOD_END, EnergyReleaseFamily.WNGSR)
        assert release
        self.assertEqual(release.publication_date, date(2026, 11, 25))
        self.assertEqual(release.publication_hour_et, 12)


class EiaRevisionTests(unittest.TestCase):
    def test_correction_preserves_versions(self) -> None:
        fixture = _load("wpsr_correction.json")
        entry = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        assert entry
        store = EiaStore()
        for version in fixture["versions"]:
            obs = normalize_api_row(
                {"period": fixture["period_end"], "series": fixture["series"], "value": version["value"]},
                entry=entry,
                observed_time=version["observed_time"],
                retrieved_time=version["observed_time"],
                api_first_observed_time=version["available_time"],
                revision_status=f"v{version['version']}",
            )
            assert obs
            store.add_observation(obs)
        v1 = energy_as_of(
            store.observations,
            decision_time="2026-08-15T12:00:00Z",
            canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS",
        )
        v2 = energy_as_of(
            store.observations,
            decision_time="2026-08-21T12:00:00Z",
            canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS",
        )
        assert v1 and v2
        self.assertEqual(v1.normalized_value, 100.0)
        self.assertEqual(v2.normalized_value, 102.0)
        self.assertEqual(store.bitemporal._records[-1].kind, ReferenceKind.ENERGY_FUNDAMENTAL)


class EiaPaginationTests(unittest.TestCase):
    def test_pagination_no_duplicates_or_gaps(self) -> None:
        fixture = _load("api_pagination.json")
        transport = EiaTransport(api_key=FAKE_KEY)
        rows: list[dict] = []
        with patch.object(transport, "query_data") as mock_query:
            def _side_effect(route, params=None, length=5000, offset=0):
                for page in fixture["pages"]:
                    if page["offset"] == offset:
                        return {"response": {"total": fixture["total"], "data": page["data"]}}
                return {"response": {"total": fixture["total"], "data": []}}

            mock_query.side_effect = _side_effect
            rows, meta = transport.query_data_paginated(
                "/v2/petroleum/sum/sndw/data",
                params={"frequency": "weekly"},
                length=fixture["page_length"],
            )
        periods = [row["period"] for row in rows]
        self.assertEqual(len(periods), fixture["total"])
        self.assertEqual(len(set(periods)), len(periods))
        self.assertEqual(int(meta.get("total", 0)), fixture["total"])


class EiaOutageTests(unittest.TestCase):
    def test_source_unavailable_not_zero(self) -> None:
        flags = (EiaQualityFlag.SOURCE_UNAVAILABLE.value,)
        self.assertTrue(quality_blocks_fundamentals(flags))
        state = build_energy_fundamentals_state([], decision_time="2026-08-20T15:00:00Z")
        self.assertIsNone(state.petroleum.commercial_crude)
        self.assertIsNone(state.natural_gas.lower48_storage)

    def test_not_yet_released_flag(self) -> None:
        entry = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        assert entry
        release = release_for_period_end(PIT_FIXTURE_WPSR_PERIOD_END, EnergyReleaseFamily.WPSR)
        assert release
        pub = publication_time_utc(release)
        obs = normalize_api_row(
            {"period": str(PIT_FIXTURE_WPSR_PERIOD_END), "series": entry.series, "value": 100},
            entry=entry,
            observed_time=pub,
            retrieved_time=pub,
            api_first_observed_time=pub,
        )
        assert obs
        store = EiaStore()
        store.add_observation(obs)
        latest, flags = store.latest_visible_or_flags(
            decision_time="2026-08-19T14:00:00Z",
            canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS",
        )
        self.assertIsNone(latest)
        self.assertIn(EiaQualityFlag.REPORT_NOT_YET_RELEASED.value, flags)


class EiaCrossAssetTests(unittest.TestCase):
    def _macro_obs(self) -> MacroObservation:
        entry = lookup_macro("US_REAL_GDP")
        assert entry
        return MacroObservation(
            canonical_indicator_id="US_REAL_GDP",
            series_id=entry.fred_series_id,
            observation_date="2026-07-01",
            raw_value="2.1",
            normalized_value=2.1,
            frequency=entry.frequency,
            units=entry.units,
            seasonal_adjustment=entry.seasonal_adjustment,
            source_agency="BEA",
            fred_release_id=None,
            realtime_start="2026-07-01",
            realtime_end="2026-07-01",
            vintage_date="2026-07-01",
            available_time="2026-08-13T13:30:00Z",
            availability_precision="TIMESTAMP",
        )

    def _cot_obs(self, *, publication_time: str, position_date: str) -> InstitutionalPositioningObservation:
        return InstitutionalPositioningObservation(
            market_id="CL",
            contract_family_id="CL",
            cftc_contract_market_code="067651",
            cftc_commodity_code="067651",
            market_and_exchange_names="CRUDE OIL",
            report_family=CotReportFamily.DISAGGREGATED,
            position_scope=CotPositionScope.FUTURES_ONLY,
            participant_category=CotParticipantCategory.MANAGED_MONEY,
            position_date=position_date,
            publication_time=publication_time,
            available_time=publication_time,
            observed_time=publication_time,
            long_positions=100,
            short_positions=120,
        )

    def test_cftc_eia_independent_clocks(self) -> None:
        payload = _load("cftc_eia_independent_clocks.json")
        petroleum = _load("petroleum_weekly_rows.json")
        gas = _load("natural_gas_weekly_rows.json")
        eia_store = EiaStore()
        for row in petroleum["rows"]:
            obs = normalize_api_row(
                row,
                observed_time=petroleum["observed_time"],
                retrieved_time=petroleum["retrieved_time"],
                api_first_observed_time=payload["wpsr_publication"],
            )
            if obs:
                eia_store.add_observation(obs)
        for row in gas["rows"][:8]:
            obs = normalize_api_row(
                row,
                observed_time=gas["observed_time"],
                retrieved_time=gas["retrieved_time"],
                api_first_observed_time=payload["wngsr_publication"],
            )
            if obs:
                eia_store.add_observation(obs)

        cot_store = CotStore()
        cot_store.add_observation(
            self._cot_obs(
                publication_time=payload["cot_publication"],
                position_date="2026-08-18",
            )
        )

        for step in payload["timeline"]:
            ctx = build_energy_market_context(
                macro_observations=[self._macro_obs()],
                cot_store=cot_store,
                eia_store=eia_store,
                decision_time=step["decision_time"],
                contract_family_id="CL",
            )
            wpsr_visible = ctx.physical_fundamentals_state.petroleum.commercial_crude is not None
            wngsr_visible = ctx.physical_fundamentals_state.natural_gas.lower48_storage is not None
            cot_visible = ctx.institutional_positioning_state is not None
            self.assertEqual(wpsr_visible, step["wpsr_visible"], step["label"])
            self.assertEqual(wngsr_visible, step["wngsr_visible"], step["label"])
            self.assertEqual(cot_visible, step["cot_visible"], step["label"])


class EiaCaptureTests(unittest.TestCase):
    def test_capture_hash_excludes_api_key(self) -> None:
        payload = _load("request_echo_redaction.json")
        envelope = capture_envelope(
            route="/v2/petroleum/sum/sndw/data",
            params={"frequency": "weekly", "api_key": FAKE_KEY},
            response=payload,
        )
        serialized = json.dumps(envelope)
        self.assertNotIn(FAKE_KEY, serialized)


class EiaCapabilityTests(unittest.TestCase):
    def test_offline_capability_report(self) -> None:
        report = capability_report(live=False)
        self.assertEqual(report["source"], "eia")
        self.assertIn("api_v2", report)
        self.assertNotIn("api_key", json.dumps(report))


class EiaTransportPolicyTests(unittest.TestCase):
    def test_max_json_rows_respected(self) -> None:
        self.assertEqual(MAX_JSON_ROWS, 5000)


if __name__ == "__main__":
    unittest.main()
