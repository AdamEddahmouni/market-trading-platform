"""FRED / ALFRED dual-API macro evidence — unit and acceptance tests."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.reference import ReferenceKind
from market_platform_foundation.cftc.contracts import (
    CotParticipantCategory,
    CotPositionScope,
    CotReportFamily,
    InstitutionalPositioningObservation,
)
from market_platform_foundation.cftc.release_schedule import publication_time_utc, release_for_position_date
from market_platform_foundation.cftc.store import CotStore
from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.cross_asset import build_cross_asset_regime_context
from market_platform_foundation.fred.derived import derive_us_2s10s, derive_us_3m10y
from market_platform_foundation.fred.availability import AvailabilityPrecision
from market_platform_foundation.fred.normalize import normalize_v1_observation_row, normalize_v2_observation_row, parse_fred_value
from market_platform_foundation.fred.pit import (
    DEFAULT_REVISION_FIXTURE,
    macro_as_of,
    macro_state_as_of,
    observations_from_v1_realtime_rows,
)
from market_platform_foundation.fred.quality import FredQualityFlag
from market_platform_foundation.fred.reconcile import (
    detect_mixed_release_update,
    reconcile_current_values,
)
from market_platform_foundation.fred.redaction import redact_text, sanitize_v1_request_semantics
from market_platform_foundation.fred.registry import TIER1_REGISTRY, lookup_canonical
from market_platform_foundation.fred.store import FredStore
from market_platform_foundation.fred.v2_client import FredV2Client, V2ReleasePage, V2ReleaseSnapshot, _flatten_v2_observations
from market_platform_foundation.fred.transport import FredTransportError

FIXTURES = ROOT / "tests" / "fixtures" / "fred"
FAKE_KEY = "test_fred_key_not_real_abc123"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _obs(
    *,
    canonical: str,
    series_id: str,
    observation_date: str,
    raw_value: str,
    available_time: str,
    knowledge_end: str = "9999-12-31",
    revision_number: int = 0,
    availability_precision: str = "",
) -> MacroObservation:
    entry = lookup_canonical(canonical)
    assert entry is not None
    normalized = float(raw_value) if raw_value != "." else None
    precision = availability_precision or (
        AvailabilityPrecision.DATE_ONLY.value
        if len(available_time) == 10
        else AvailabilityPrecision.TIMESTAMP.value
    )
    return MacroObservation(
        canonical_indicator_id=canonical,
        series_id=series_id,
        observation_date=observation_date,
        raw_value=None if raw_value == "." else raw_value,
        normalized_value=normalized,
        frequency=entry.frequency,
        units=entry.units,
        seasonal_adjustment=entry.seasonal_adjustment,
        source_agency=entry.original_source,
        fred_release_id=entry.fred_release_id,
        realtime_start=available_time[:10] if precision == AvailabilityPrecision.DATE_ONLY.value else available_time,
        realtime_end=knowledge_end,
        knowledge_start_date=available_time[:10] if precision == AvailabilityPrecision.DATE_ONLY.value else available_time,
        knowledge_end_date=knowledge_end if knowledge_end not in {"9999-12-31", ""} else "",
        vintage_date=observation_date,
        revision_number=revision_number,
        available_time=available_time[:10] if precision == AvailabilityPrecision.DATE_ONLY.value else available_time,
        availability_precision=precision,
        observed_time=available_time,
        retrieved_time=available_time,
    )


class FredRedactionTests(unittest.TestCase):
    def test_v1_api_key_redacted_from_url(self) -> None:
        dirty = "https://api.stlouisfed.org/fred/series?api_key=SECRET123&series_id=DFF"
        self.assertNotIn("SECRET123", redact_text(dirty))
        self.assertIn("REDACTED", redact_text(dirty))

    def test_v2_bearer_redacted(self) -> None:
        dirty = "Authorization: Bearer SECRET123"
        self.assertNotIn("SECRET123", redact_text(dirty))

    def test_sanitize_v1_request_semantics(self) -> None:
        semantics = sanitize_v1_request_semantics(
            endpoint="/fred/series/observations",
            params={"api_key": FAKE_KEY, "series_id": "CPIAUCSL"},
        )
        self.assertNotIn("api_key", semantics)
        self.assertEqual(semantics["series_id"], "CPIAUCSL")

    def test_transport_error_redacted(self) -> None:
        exc = FredTransportError(f"failed api_key={FAKE_KEY}")
        self.assertNotIn(FAKE_KEY, str(exc))


class FredNormalizeTests(unittest.TestCase):
    def test_missing_dot_is_unknown_not_zero(self) -> None:
        raw, normalized, flags = parse_fred_value(".")
        self.assertIsNone(raw)
        self.assertIsNone(normalized)
        self.assertIn(FredQualityFlag.MISSING_VALUE.value, flags)

    def test_v1_missing_value_fixture(self) -> None:
        payload = _load("v1_missing_value.json")
        entry = lookup_canonical("US_CORE_CPI")
        assert entry is not None
        obs = normalize_v1_observation_row(
            payload["observations"][0],
            entry=entry,
            retrieved_time="2026-01-01T00:00:00Z",
            observed_time="",
        )
        self.assertIsNone(obs.normalized_value)
        self.assertIn(FredQualityFlag.MISSING_VALUE.value, obs.quality_flags)
        self.assertEqual(obs.available_time, "2020-01-01")
        self.assertNotEqual(obs.available_time, obs.realtime_end)

    def test_v1_available_time_from_realtime_start_not_end(self) -> None:
        entry = lookup_canonical("US_CORE_CPI")
        assert entry is not None
        obs = normalize_v1_observation_row(
            {
                "date": "2024-01-01",
                "value": "100",
                "realtime_start": "2024-04-25",
                "realtime_end": "2024-05-29",
            },
            entry=entry,
            retrieved_time="2026-01-01T00:00:00Z",
            observed_time="",
        )
        self.assertEqual(obs.available_time, "2024-04-25")
        self.assertEqual(obs.knowledge_end_date, "2024-05-29")
        self.assertEqual(obs.availability_precision, AvailabilityPrecision.DATE_ONLY.value)
        self.assertNotEqual(obs.available_time, obs.realtime_end)

    def test_v1_live_first_observed_overrides_date_only_start(self) -> None:
        entry = lookup_canonical("US_CORE_CPI")
        assert entry is not None
        obs = normalize_v1_observation_row(
            {
                "date": "2024-01-01",
                "value": "100",
                "realtime_start": "2024-04-25",
                "realtime_end": "2024-05-29",
            },
            entry=entry,
            retrieved_time="2024-04-25T13:31:00Z",
            observed_time="2024-04-25T13:31:00Z",
        )
        self.assertEqual(obs.available_time, "2024-04-25T13:31:00Z")
        self.assertEqual(obs.provider_first_observed_time, "2024-04-25T13:31:00Z")
        self.assertEqual(obs.availability_precision, AvailabilityPrecision.TIMESTAMP.value)


class FredRevisionTests(unittest.TestCase):
    def test_revision_sequence_as_of(self) -> None:
        fixture = DEFAULT_REVISION_FIXTURE
        before, _, flags = fixture.as_of("2020-01-10T00:00:00Z")
        self.assertIsNone(before)
        self.assertIn(FredQualityFlag.PIT_UNAVAILABLE.value, flags)

        v1, _, _ = fixture.as_of("2020-01-15T13:30:00Z")
        self.assertEqual(v1, 100.0)
        v2, _, _ = fixture.as_of("2020-02-14T13:30:00Z")
        self.assertEqual(v2, 98.0)
        v3, _, _ = fixture.as_of("2026-01-01T00:00:00Z")
        self.assertEqual(v3, 99.0)

    def test_no_lookahead_current_revision(self) -> None:
        payload = _load("v1_revision_sequence.json")
        entry = lookup_canonical("US_CORE_CPI")
        assert entry is not None
        observations = observations_from_v1_realtime_rows(
            payload["observations"],
            canonical_indicator_id="US_CORE_CPI",
            series_id="CPIAUCSL",
            retrieved_time="2026-01-01T00:00:00Z",
        )
        as_t1 = macro_as_of(observations, canonical_indicator_id="US_CORE_CPI", decision_time="2020-01-20T00:00:00Z")
        self.assertEqual(as_t1.value, 100.0)
        as_t3 = macro_as_of(observations, canonical_indicator_id="US_CORE_CPI", decision_time="2020-03-20T00:00:00Z")
        self.assertEqual(as_t3.value, 99.0)
        self.assertNotEqual(as_t1.value, as_t3.value)

    def test_realtime_end_not_used_as_available_time_regression(self) -> None:
        """Mandatory regression: decision during initial knowledge interval must see initial value."""
        payload = _load("v1_knowledge_interval_sequence.json")
        observations = observations_from_v1_realtime_rows(
            payload["observations"],
            canonical_indicator_id="US_CORE_CPI",
            series_id="CPIAUCSL",
            retrieved_time="2026-01-01T00:00:00Z",
        )
        initial = observations[0]
        self.assertEqual(initial.available_time, "2024-04-25")
        self.assertEqual(initial.realtime_end, "2024-05-29")
        self.assertNotEqual(initial.available_time, initial.realtime_end)
        during_initial = macro_as_of(
            observations,
            canonical_indicator_id="US_CORE_CPI",
            decision_time="2024-05-10T12:00:00Z",
        )
        self.assertEqual(during_initial.value, 100.0)

    def test_knowledge_interval_sequence(self) -> None:
        payload = _load("v1_knowledge_interval_sequence.json")
        observations = observations_from_v1_realtime_rows(
            payload["observations"],
            canonical_indicator_id="US_CORE_CPI",
            series_id="CPIAUCSL",
            retrieved_time="2026-01-01T00:00:00Z",
        )
        self.assertEqual(observations[0].knowledge_start_date, "2024-04-25")
        self.assertEqual(observations[0].knowledge_end_date, "2024-05-29")
        self.assertEqual(observations[1].knowledge_start_date, "2024-05-30")
        self.assertEqual(observations[2].knowledge_end_date, "")
        before = macro_as_of(observations, canonical_indicator_id="US_CORE_CPI", decision_time="2024-04-24T23:59:00Z")
        self.assertIsNone(before.value)
        v1 = macro_as_of(observations, canonical_indicator_id="US_CORE_CPI", decision_time="2024-05-10T12:00:00Z")
        self.assertEqual(v1.value, 100.0)
        v2 = macro_as_of(observations, canonical_indicator_id="US_CORE_CPI", decision_time="2024-06-01T12:00:00Z")
        self.assertEqual(v2.value, 98.0)
        v3 = macro_as_of(observations, canonical_indicator_id="US_CORE_CPI", decision_time="2026-01-01T00:00:00Z")
        self.assertEqual(v3.value, 99.0)

    def test_date_only_intraday_on_start_date_is_conservative(self) -> None:
        payload = _load("v1_knowledge_interval_sequence.json")
        observations = observations_from_v1_realtime_rows(
            payload["observations"],
            canonical_indicator_id="US_CORE_CPI",
            series_id="CPIAUCSL",
            retrieved_time="2026-01-01T00:00:00Z",
        )
        same_day_intraday = macro_as_of(
            observations,
            canonical_indicator_id="US_CORE_CPI",
            decision_time="2024-04-25T08:00:00Z",
        )
        self.assertIsNone(same_day_intraday.value)
        next_day = macro_as_of(
            observations,
            canonical_indicator_id="US_CORE_CPI",
            decision_time="2024-04-26T00:00:00Z",
        )
        self.assertEqual(next_day.value, 100.0)

    def test_v2_pit_fallback_forbidden(self) -> None:
        v2_only = [
            MacroObservation(
                canonical_indicator_id="US_CORE_CPI",
                series_id="CPIAUCSL",
                observation_date="2020-01-01",
                raw_value="999",
                normalized_value=999.0,
                frequency="Monthly",
                units="Index",
                seasonal_adjustment="SA",
                source_agency="BLS",
                fred_release_id=10,
                realtime_start="",
                realtime_end="",
                vintage_date="",
                series_last_updated="2026-01-01T00:00:00Z",
                snapshot_observed_time="2026-01-01T00:00:00Z",
                available_time="2026-01-01T00:00:00Z",
                availability_precision=AvailabilityPrecision.SNAPSHOT.value,
                observed_time="2026-01-01T00:00:00Z",
                retrieved_time="2026-01-01T00:00:00Z",
                api_version="v2",
            )
        ]
        result = macro_as_of(
            v2_only,
            canonical_indicator_id="US_CORE_CPI",
            decision_time="2020-06-01T00:00:00Z",
            pit_available=False,
        )
        self.assertIsNone(result.value)
        self.assertIn(FredQualityFlag.PIT_UNAVAILABLE.value, result.quality_flags)

    def test_v2_last_updated_not_historical_availability(self) -> None:
        entry = lookup_canonical("US_CORE_CPI")
        assert entry is not None
        rows = [
            normalize_v2_observation_row(
                {"series_id": "CPIAUCSL", "date": "2025-01-01", "value": "1", "last_updated": "2026-08-12T14:09:55Z"},
                retrieved_time="2026-08-20T12:00:00Z",
                observed_time="2026-08-20T12:00:00Z",
            ),
            normalize_v2_observation_row(
                {"series_id": "CPIAUCSL", "date": "2026-07-01", "value": "2", "last_updated": "2026-08-12T14:09:55Z"},
                retrieved_time="2026-08-20T12:00:00Z",
                observed_time="2026-08-20T12:00:00Z",
            ),
        ]
        observations = [row for row in rows if row is not None]
        self.assertTrue(all(obs.series_last_updated == "2026-08-12T14:09:55Z" for obs in observations))
        self.assertTrue(all(obs.available_time == "2026-08-20T12:00:00Z" for obs in observations))
        self.assertTrue(all(obs.availability_precision == AvailabilityPrecision.SNAPSHOT.value for obs in observations))
        historical = macro_as_of(
            observations,
            canonical_indicator_id="US_CORE_CPI",
            decision_time="2025-06-01T00:00:00Z",
        )
        self.assertIsNone(historical.value)


class FredStoreTests(unittest.TestCase):
    def test_bitemporal_reference_kind(self) -> None:
        store = FredStore()
        store.add_observation(
            _obs(
                canonical="US_10Y_TREASURY_YIELD",
                series_id="DGS10",
                observation_date="2026-02-10",
                raw_value="4.25",
                available_time="2026-02-10T22:00:00Z",
            )
        )
        record = store.bitemporal.as_of(
            ReferenceKind.MACRO_OBSERVATION,
            "US_10Y_TREASURY_YIELD:2026-02-10",
            market_time="2026-02-10",
            knowledge_time="2026-02-11T00:00:00Z",
        )
        self.assertIsNotNone(record)


class FredReconciliationTests(unittest.TestCase):
    def _build_pair(self, payload: dict) -> tuple[MacroObservation | None, MacroObservation | None]:
        entry = lookup_canonical("US_10Y_TREASURY_YIELD")
        assert entry is not None
        v1 = normalize_v1_observation_row(
            {
                "date": payload["v1"]["date"],
                "value": payload["v1"]["value"],
                "realtime_start": "2026-02-10",
                "realtime_end": "2026-02-10T22:00:00Z",
            },
            entry=entry,
            retrieved_time="2026-02-11T00:00:00Z",
            observed_time="2026-02-10T22:00:00Z",
        )
        v2 = normalize_v1_observation_row(
            {
                "date": payload["v2"]["date"],
                "value": payload["v2"]["value"],
                "realtime_start": "2026-02-10",
                "realtime_end": "2026-02-10T22:00:00Z",
            },
            entry=entry,
            retrieved_time="2026-02-11T00:00:00Z",
            observed_time="2026-02-10T22:00:00Z",
        )
        return v1, v2

    def test_reconciliation_pass(self) -> None:
        pair = self._build_pair(_load("reconciliation_pass.json"))
        result = reconcile_current_values(v1_observation=pair[0], v2_observation=pair[1])
        self.assertTrue(result.match)

    def test_reconciliation_mismatch(self) -> None:
        pair = self._build_pair(_load("reconciliation_mismatch.json"))
        result = reconcile_current_values(v1_observation=pair[0], v2_observation=pair[1])
        self.assertFalse(result.match)
        self.assertIn(FredQualityFlag.V1_V2_RECONCILIATION_MISMATCH.value, result.quality_flags)


class FredV2NestedPayloadTests(unittest.TestCase):
    def test_flatten_production_series_blocks(self) -> None:
        payload = {
            "has_more": False,
            "series": [
                {
                    "series_id": "CPILFESL",
                    "last_updated": "2026-08-12T14:09:56Z",
                    "copyright_id": "public domain: citation requested",
                    "observations": [{"date": "2026-07-01", "value": "336.789"}],
                }
            ],
        }
        rows = _flatten_v2_observations(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["series_id"], "CPILFESL")
        self.assertEqual(rows[0]["value"], "336.789")


class FredV2PaginationTests(unittest.TestCase):
    def _snapshot_from_fixture(self, name: str) -> V2ReleaseSnapshot:
        payload = _load(name)
        snapshot = V2ReleaseSnapshot(release_id=10)
        for index, page_data in enumerate(payload["pages"]):
            snapshot.pages.append(
                V2ReleasePage(
                    observations=page_data.get("observations", []),
                    has_more=bool(page_data.get("has_more")),
                    next_cursor=page_data.get("next_cursor"),
                    page_index=index,
                    raw=page_data,
                )
            )
            for row in page_data.get("observations", []):
                sid = str(row.get("series_id", ""))
                if sid:
                    snapshot.series_last_updated[sid] = str(row.get("last_updated", ""))
        snapshot.consistency_result = "COMPLETE" if not snapshot.pages[-1].has_more else "PARTIAL"
        return snapshot

    def test_multipage_complete(self) -> None:
        snap = self._snapshot_from_fixture("v2_multipage_release.json")
        self.assertEqual(len(snap.pages), 2)
        self.assertFalse(snap.pages[-1].has_more)

    def test_cursor_missing(self) -> None:
        snap = self._snapshot_from_fixture("v2_cursor_missing.json")
        self.assertTrue(snap.pages[0].has_more)
        self.assertIsNone(snap.pages[0].next_cursor)

    def test_mixed_release_update(self) -> None:
        payload = _load("v2_mixed_release_update.json")
        snap = self._snapshot_from_fixture("v2_mixed_release_update.json")
        state, flags = detect_mixed_release_update(
            snap,
            configured_series={"CPIAUCSL", "CPILFESL"},
            retrieval_started=payload["retrieval_started"],
        )
        self.assertEqual(state, "MIXED_RELEASE_UPDATE")
        self.assertIn(FredQualityFlag.MIXED_RELEASE_UPDATE.value, flags)

    def test_fetch_detects_cursor_loop(self) -> None:
        transport = MagicMock()
        client = FredV2Client(api_key=FAKE_KEY, transport=transport)

        def side_effect(release_id: int, *, limit: int = 500000, cursor: str | None = None):
            return V2ReleasePage(
                observations=[{"series_id": "CPIAUCSL", "date": "2026-01-01", "value": "1", "last_updated": "2026-01-01"}],
                has_more=True,
                next_cursor="loop",
                page_index=0,
                raw={},
            )

        transport.request_json.side_effect = lambda **kwargs: {}
        with patch.object(client, "release_observations_page", side_effect=side_effect):
            snap = client.fetch_release_observations(10, max_pages=3)
        self.assertIn(FredQualityFlag.CURSOR_LOOP.value, snap.quality_flags)


class FredCrossFrequencyPitTests(unittest.TestCase):
    def test_cross_frequency_join(self) -> None:
        payload = _load("cross_frequency_pit.json")
        observations = [
            _obs(
                canonical=row["canonical_indicator_id"],
                series_id=row["series_id"],
                observation_date=row["observation_date"],
                raw_value=row["value"],
                available_time=row["available_time"],
            )
            for row in payload["series"]
        ]
        early = "2026-02-13T12:00:00Z"
        state = macro_state_as_of(observations, decision_time=early)
        self.assertIsNotNone(state.yield_curve["US_10Y_TREASURY_YIELD"].value)
        self.assertIsNone(state.labor["US_INITIAL_CLAIMS"].value)
        later = "2026-02-13T14:00:00Z"
        state2 = macro_state_as_of(observations, decision_time=later)
        self.assertIsNotNone(state2.labor["US_INITIAL_CLAIMS"].value)
        self.assertIsNotNone(state2.inflation["US_CORE_CPI"].value)
        self.assertIsNotNone(state2.growth["US_REAL_GDP"].value)


class FredDerivedTests(unittest.TestCase):
    def test_derive_2s10s_pit_compatible(self) -> None:
        observations = [
            _obs(
                canonical="US_10Y_TREASURY_YIELD",
                series_id="DGS10",
                observation_date="2026-02-10",
                raw_value="4.50",
                available_time="2026-02-10T22:00:00Z",
            ),
            _obs(
                canonical="US_2Y_TREASURY_YIELD",
                series_id="DGS2",
                observation_date="2026-02-10",
                raw_value="4.10",
                available_time="2026-02-10T22:00:00Z",
            ),
        ]
        spread = derive_us_2s10s(observations, decision_time="2026-02-11T00:00:00Z")
        self.assertAlmostEqual(spread.value or 0, 0.40, places=2)

    def test_derive_3m10y(self) -> None:
        observations = [
            _obs(
                canonical="US_10Y_TREASURY_YIELD",
                series_id="DGS10",
                observation_date="2026-02-10",
                raw_value="4.50",
                available_time="2026-02-10T22:00:00Z",
            ),
            _obs(
                canonical="US_3M_TREASURY_YIELD",
                series_id="DGS3MO",
                observation_date="2026-02-10",
                raw_value="4.30",
                available_time="2026-02-10T22:00:00Z",
            ),
        ]
        spread = derive_us_3m10y(observations, decision_time="2026-02-11T00:00:00Z")
        self.assertAlmostEqual(spread.value or 0, 0.20, places=2)


class FredReleaseAvailabilityTests(unittest.TestCase):
    def test_scheduled_release_before_fred_availability(self) -> None:
        payload = _load("release_availability_gap.json")
        query_time = "2026-02-12T10:00:00Z"
        self.assertLess(query_time, payload["first_observed_availability"])
        obs_before = _obs(
            canonical="US_CORE_CPI",
            series_id="CPIAUCSL",
            observation_date=payload["observation_date"],
            raw_value=str(payload["value_after_availability"]),
            available_time=payload["first_observed_availability"],
        )
        result = macro_as_of([obs_before], canonical_indicator_id="US_CORE_CPI", decision_time=query_time)
        self.assertIsNone(result.value)


class FredCftcInteropTests(unittest.TestCase):
    def _cot_obs(self, *, position_date: str, publication_time: str) -> InstitutionalPositioningObservation:
        return InstitutionalPositioningObservation(
            market_id="ES",
            contract_family_id="ES",
            cftc_contract_market_code="13874",
            cftc_commodity_code="13874",
            market_and_exchange_names="E-MINI S&P 500",
            report_family=CotReportFamily.TFF,
            position_scope=CotPositionScope.FUTURES_ONLY,
            participant_category=CotParticipantCategory.LEVERAGED_FUNDS,
            position_date=position_date,
            publication_time=publication_time,
            available_time=publication_time,
            observed_time=publication_time,
            long_positions=100,
            short_positions=80,
        )

    def test_independent_source_clocks(self) -> None:
        payload = _load("cftc_fred_independent_clocks.json")
        macro_obs = [
            _obs(
                canonical="US_CORE_CPI",
                series_id="CPIAUCSL",
                observation_date="2026-01-01",
                raw_value="320",
                available_time=payload["macro_observation"]["available_time"],
            )
        ]
        cot_store = CotStore()
        prior_release = release_for_position_date(date(2026, 8, 4))
        assert prior_release is not None
        prior_pub = publication_time_utc(prior_release.publication_date)
        cot_store.add_observation(
            self._cot_obs(
                position_date=str(prior_release.position_date),
                publication_time=prior_pub,
            )
        )
        new_release = release_for_position_date(date(2026, 8, 11))
        assert new_release is not None
        new_pub = publication_time_utc(new_release.publication_date)
        cot_store.add_observation(
            self._cot_obs(
                position_date=str(new_release.position_date),
                publication_time=new_pub,
            )
        )

        for step in payload["timeline"]:
            decision = step["decision_time"]
            ctx = build_cross_asset_regime_context(
                macro_observations=macro_obs,
                cot_store=cot_store,
                decision_time=decision,
            )
            macro_visible = ctx.macro_state.inflation["US_CORE_CPI"].value is not None
            new_visible = ctx.positioning_available_time == new_pub
            prior_visible = ctx.positioning_available_time == prior_pub
            if step["macro_visible"]:
                self.assertTrue(macro_visible, step["label"])
            if step["new_cot_visible"]:
                self.assertTrue(new_visible, step["label"])
            else:
                self.assertFalse(new_visible, step["label"])
            if step["prior_cot_visible"]:
                self.assertTrue(prior_visible or new_visible, step["label"])


class FredRegistryTests(unittest.TestCase):
    def test_tier1_bounded_registry(self) -> None:
        self.assertGreaterEqual(len(TIER1_REGISTRY), 20)
        self.assertLessEqual(len(TIER1_REGISTRY), 50)

    def test_no_composite_macro_score_in_contracts(self) -> None:
        from market_platform_foundation.fred.contracts import MacroRegimeState
        fields = MacroRegimeState.__dataclass_fields__
        self.assertNotIn("macro_score", fields)


if __name__ == "__main__":
    unittest.main()
