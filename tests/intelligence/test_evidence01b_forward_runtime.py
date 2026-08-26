"""EVIDENCE-01B real-provider runtime and operational control tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from market_platform_foundation.intelligence.contracts.common import ForecastEstimate
from market_platform_foundation.intelligence.forward_qualification.evidence01.continuity import (
    is_trading_day,
    maximum_qualifying_gap_ns,
    qualifying_gap_ns,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01a import (
    CampaignEvidenceOrigin,
    CampaignService,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01a.types import (
    MIN_QUALIFYING_SESSION_DURATION_NS,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01b import (
    CampaignRuntime,
    CampaignRuntimeService,
    FakeProviderAdapter,
    PreflightDisposition,
    ProviderEventV1,
    SettlementWorker,
    ShakedownStatus,
    build_configuration_snapshot,
    classify_gap,
    is_semantic_config_compatible,
    map_runtime_admission_to_quality,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01b.config import (
    PREDICTOR_ID,
    derive_configuration_fingerprint,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01b.health import (
    CampaignHealthState,
    assess_campaign_health,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01b.provider_bridge import (
    build_provider_provenance,
    ingest_runtime_record,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01b.types import (
    ContinuityGapCategory,
    HealthSeverity,
)
from market_platform_foundation.intelligence.outcomes.service import OutcomeSettlementService
from market_platform_foundation.intelligence.outcomes.types import SettlementMode
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.outcome_fixtures import HORIZON_5M, ONE_MIN, T
from tests.intelligence.test_evidence01_forward_qualification import DAY_NS

_ET = ZoneInfo("America/New_York")
_HOUR_NS = 60 * 60 * 1_000_000_000


def _et_ns(year: int, month: int, day: int, hour: int, minute: int = 0) -> int:
    dt = datetime(year, month, day, hour, minute, tzinfo=_ET)
    return int(dt.timestamp() * 1_000_000_000)


class ContinuityCalendarTests(unittest.TestCase):
    def test_weekday_is_trading_day(self) -> None:
        self.assertTrue(is_trading_day(date(2025, 6, 3)))

    def test_weekend_not_trading_day(self) -> None:
        self.assertFalse(is_trading_day(date(2025, 6, 7)))
        self.assertFalse(is_trading_day(date(2025, 6, 8)))

    def test_holiday_not_trading_day(self) -> None:
        self.assertFalse(is_trading_day(date(2025, 12, 25)))

    def test_overnight_closure_not_qualifying_gap(self) -> None:
        fri_close = _et_ns(2025, 6, 6, 15, 59)
        mon_open = _et_ns(2025, 6, 9, 9, 31)
        gap = qualifying_gap_ns(fri_close, mon_open)
        self.assertLess(gap, 24 * _HOUR_NS)

    def test_weekend_not_qualifying_gap(self) -> None:
        fri = _et_ns(2025, 6, 6, 14, 0)
        mon = _et_ns(2025, 6, 9, 10, 0)
        gap = qualifying_gap_ns(fri, mon)
        self.assertLess(gap, 24 * _HOUR_NS)
        raw = mon - fri
        self.assertGreater(raw, 48 * _HOUR_NS)

    def test_intraday_gap_counts(self) -> None:
        t1 = _et_ns(2025, 6, 3, 10, 0)
        t2 = _et_ns(2025, 6, 3, 14, 0)
        gap = qualifying_gap_ns(t1, t2)
        self.assertGreater(gap, 3 * _HOUR_NS)

    def test_exact_24h_boundary_within_session(self) -> None:
        t1 = _et_ns(2025, 6, 3, 10, 0)
        t2 = _et_ns(2025, 6, 3, 14, 0)
        gap = qualifying_gap_ns(t1, t2)
        self.assertEqual(gap, 4 * _HOUR_NS)

    def test_provider_disconnect_gap_classified(self) -> None:
        t1 = _et_ns(2025, 6, 3, 10, 0)
        t2 = _et_ns(2025, 6, 3, 12, 0)
        record = classify_gap(t1, t2, provider_disconnected=True)
        self.assertIn(
            record.category,
            {ContinuityGapCategory.PROVIDER_DISCONNECT, ContinuityGapCategory.UNKNOWN},
        )
        self.assertGreater(record.qualifying_gap_ns, 0)

    def test_expected_closure_classified(self) -> None:
        fri = _et_ns(2025, 6, 6, 15, 0)
        mon = _et_ns(2025, 6, 9, 10, 0)
        record = classify_gap(fri, mon)
        self.assertEqual(record.category, ContinuityGapCategory.EXPECTED_MARKET_CLOSURE)
        self.assertLess(record.qualifying_gap_ns, 24 * _HOUR_NS)

    def test_maximum_qualifying_gap_ignores_weekend(self) -> None:
        fri = _et_ns(2025, 6, 6, 14, 0)
        mon = _et_ns(2025, 6, 9, 10, 0)
        tue = _et_ns(2025, 6, 10, 10, 0)
        max_gap = maximum_qualifying_gap_ns([fri, mon, tue])
        self.assertLess(max_gap, 24 * _HOUR_NS)


class ProviderIntegrationTests(unittest.TestCase):
    def test_fake_provider_deduplication(self) -> None:
        adapter = FakeProviderAdapter()
        event = ProviderEventV1(
            instrument_id="AAPL",
            quality_state="GOOD",
            provider_connected=True,
            event_time_ns=T,
            received_time_ns=T,
            provider_id="FAKE",
            provider_capability="QUOTE",
            provider_event_id="evt-1",
        )
        self.assertTrue(adapter.ingest_event(event))
        self.assertFalse(adapter.ingest_event(event))
        self.assertEqual(adapter.duplicate_events, 1)

    def test_disconnect_changes_acceptance(self) -> None:
        adapter = FakeProviderAdapter()
        adapter.disconnect()
        event = ProviderEventV1(
            instrument_id="AAPL",
            quality_state="GOOD",
            provider_connected=False,
            event_time_ns=T,
            received_time_ns=T,
            provider_id="FAKE",
            provider_capability="QUOTE",
        )
        self.assertFalse(adapter.ingest_event(event))

    def test_reconnect_restores_acceptance(self) -> None:
        adapter = FakeProviderAdapter()
        adapter.disconnect()
        adapter.reconnect()
        event = ProviderEventV1(
            instrument_id="AAPL",
            quality_state="GOOD",
            provider_connected=True,
            event_time_ns=T,
            received_time_ns=T,
            provider_id="FAKE",
            provider_capability="QUOTE",
            provider_event_id="evt-2",
        )
        self.assertTrue(adapter.ingest_event(event))

    def test_admission_maps_clock_drift(self) -> None:
        quality, connected = map_runtime_admission_to_quality({
            "admission": {"display": "BLOCKED"},
            "quality": {"state": "CLOCK_DRIFT", "blocking_reasons": ["CLOCK_DRIFT"]},
        })
        self.assertEqual(quality, "CLOCK_DRIFT")
        self.assertFalse(connected)

    def test_ingest_runtime_record(self) -> None:
        record = {
            "instrument_id": "AAPL",
            "capability": "QUOTE",
            "clocks": {"event_time_ns": T, "received_time_ns": T + 1000},
        }
        event = ingest_runtime_record(record, {"admission": {"display": "DISPLAY_ADMITTED"}, "quality": {"state": "GOOD"}})
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.instrument_id, "AAPL")

    def test_provider_provenance_fields(self) -> None:
        event = ProviderEventV1(
            instrument_id="AAPL",
            quality_state="GOOD",
            provider_connected=True,
            event_time_ns=T,
            received_time_ns=T + 1000,
            provider_id="MOOMOO",
            provider_capability="QUOTE",
            provider_event_id="evt-prov-1",
        )
        prov = build_provider_provenance(
            event,
            campaign_id="camp-1",
            session_id="sess-1",
            evidence_origin=CampaignEvidenceOrigin.LIVE_FORWARD,
        )
        self.assertEqual(prov["provider_id"], "MOOMOO")
        self.assertEqual(prov["campaign_id"], "camp-1")
        self.assertEqual(prov["evidence_origin"], "LIVE_FORWARD")


class ConfigurationFreezeTests(unittest.TestCase):
    def test_deterministic_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="cfg-test",
                source_commit_sha="abc123",
            )
            spec = service.store.read_spec()
            a = build_configuration_snapshot(spec)
            b = build_configuration_snapshot(spec)
            self.assertEqual(a.campaign_configuration_fingerprint, b.campaign_configuration_fingerprint)
            self.assertTrue(a.campaign_configuration_fingerprint.startswith("CFGFP-"))

    def test_predictor_change_blocks_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(campaign_root=Path(tmp), campaign_name="drift")
            frozen = build_configuration_snapshot(service.store.read_spec())
            current = build_configuration_snapshot(service.store.read_spec())
            from dataclasses import replace
            changed = replace(current, predictor_id="different_predictor")
            compatible, reasons = is_semantic_config_compatible(frozen, changed)
            self.assertFalse(compatible)
            self.assertIn("predictor_id changed", reasons)


class PreflightTests(unittest.TestCase):
    def test_preflight_ready_for_new_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="preflight-test",
            )
            result = service.preflight()
            self.assertIn(result.disposition, {PreflightDisposition.READY, PreflightDisposition.READY_WITH_LIMITATIONS})
            self.assertEqual(len(result.blockers), 0)

    def test_execution_disabled_in_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="exec-check",
            )
            spec = service.store.read_spec()
            self.assertEqual(spec.execution_authority, "BLOCKED")


class RuntimeRecoveryTests(unittest.TestCase):
    def _forecast(self, repo, forecast_id: str, decision_time_ns: int):
        from market_platform_foundation.intelligence.baselines import direction_up_down_target
        from market_platform_foundation.intelligence.contracts import ForecastV1, SnapshotV1
        from market_platform_foundation.intelligence.contracts.common import ContractKind, ContractReference, TimeHorizonNs
        from tests.intelligence.outcome_fixtures import INSTRUMENT, QUALITY, SCOPE, seed_anchor_trade

        snapshot = SnapshotV1(
            snapshot_id=f"snap-{forecast_id}",
            schema_version="1",
            decision_time_ns=decision_time_ns,
            scope=SCOPE,
            quality=QUALITY,
            source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id=f"a-{forecast_id}"),),
        )
        seed_anchor_trade(repo, event_id=f"a-{forecast_id}", event_time_ns=decision_time_ns - ONE_MIN)
        repo.put_snapshot(snapshot)
        forecast = ForecastV1(
            forecast_id=forecast_id,
            schema_version="1",
            scope=SCOPE,
            decision_time_ns=decision_time_ns,
            snapshot_id=snapshot.snapshot_id,
            target=direction_up_down_target(INSTRUMENT),
            horizon=TimeHorizonNs(duration_ns=HORIZON_5M),
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=0.7,
                calibrated_probability=0.7,
            ),
            quality=QUALITY,
            metadata={"predicted_direction": "UP"},
        )
        repo.put_forecast(forecast)
        return forecast

    def test_restart_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="restart-01b",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            campaign_dir = runtime.store.root
            runtime.service.start_campaign()
            runtime.runtime.start_session(now_ns=T)
            forecast = self._forecast(runtime.service.repository, "fc-r1", T)
            runtime.service.record_observation(forecast=forecast, now_ns=T)
            runtime.runtime.stop_runtime(now_ns=T + MIN_QUALIFYING_SESSION_DURATION_NS)
            reloaded = CampaignRuntimeService.open(campaign_dir)
            self.assertEqual(len(reloaded.store.list_observation_refs()), 1)
            reloaded.runtime.recover()
            metrics = reloaded.store.read_metrics()
            self.assertGreaterEqual(metrics.runtime_restarts, 1)

    def test_pause_resume_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="pause-test",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            runtime.service.start_campaign()
            runtime.runtime.start_runtime(now_ns=T)
            runtime.runtime.start_session(now_ns=T)
            runtime.pause()
            runtime.resume()
            self.assertEqual(len(runtime.store.list_observation_refs()), 0)

    def test_abort_preserves_prior_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="abort-01b",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            runtime.service.start_campaign()
            runtime.runtime.start_session(now_ns=T)
            forecast = self._forecast(runtime.service.repository, "fc-abort", T)
            runtime.service.record_observation(forecast=forecast, now_ns=T)
            runtime.service.abort_campaign()
            self.assertEqual(len(runtime.store.list_observation_refs()), 1)


class SettlementWorkerTests(unittest.TestCase):
    def test_immature_predictions_skipped(self) -> None:
        repo = InMemoryIntelligenceRepository()
        worker = SettlementWorker(repo)
        result = worker.run_settlement_batch(now_ns=T)
        self.assertEqual(result.settled, 0)

    def test_settlement_backlog_count(self) -> None:
        repo = InMemoryIntelligenceRepository()
        worker = SettlementWorker(repo)
        self.assertEqual(worker.settlement_backlog(now_ns=T), 0)


class SessionGamingTests(unittest.TestCase):
    def test_empty_restart_session_not_qualifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="gaming",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            service.start_campaign()
            for i in range(5):
                service.start_session(now_ns=T + i * 1000)
                service.stop_session(now_ns=T + i * 1000 + 1000)
            self.assertEqual(service.qualifying_session_count(), 0)


class HealthTests(unittest.TestCase):
    def test_market_closed_is_info_not_blocking(self) -> None:
        from market_platform_foundation.intelligence.forward_qualification.evidence01a.types import (
            ForwardObservationCampaignState,
        )

        sunday_ns = _et_ns(2025, 6, 8, 12, 0)
        health = assess_campaign_health(
            campaign_state=ForwardObservationCampaignState.ACTIVE,
            provider_connected=True,
            provider_degraded=False,
            settlement_backlog=0,
            qualifying_continuity_gap_ns=0,
            clock_drift_exclusions=0,
            eligible_predictions=0,
            now_ns=sunday_ns,
        )
        self.assertEqual(health.health_state, CampaignHealthState.WAITING_FOR_MARKET)
        self.assertEqual(health.severity, HealthSeverity.INFO)

    def test_provider_disconnect_degraded(self) -> None:
        from market_platform_foundation.intelligence.forward_qualification.evidence01a.types import (
            ForwardObservationCampaignState,
        )

        health = assess_campaign_health(
            campaign_state=ForwardObservationCampaignState.ACTIVE,
            provider_connected=False,
            provider_degraded=False,
            settlement_backlog=0,
            qualifying_continuity_gap_ns=0,
            clock_drift_exclusions=0,
            eligible_predictions=5,
            now_ns=_et_ns(2025, 6, 3, 11, 0),
        )
        self.assertEqual(health.health_state, CampaignHealthState.PROVIDER_DISCONNECTED)


class ShakedownTests(unittest.TestCase):
    def test_shakedown_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="shakedown",
            )
            status = runtime.shakedown_start()
            self.assertEqual(status, ShakedownStatus.SHAKEDOWN_ACTIVE)
            final = runtime.runtime.complete_shakedown(passed=True)
            self.assertEqual(final, ShakedownStatus.SHAKEDOWN_PASSED)


class AuthoritySeparationTests(unittest.TestCase):
    def test_no_broker_submit_in_runtime_modules(self) -> None:
        root = Path("src/market_platform_foundation/intelligence/forward_qualification/evidence01b")
        forbidden = ("submit_order", "place_order", "authorize_live_session")
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for term in forbidden:
                self.assertNotIn(term, source, msg=f"{term} found in {path.name}")

    def test_fixture_origin_excluded_from_real_cohort(self) -> None:
        from market_platform_foundation.intelligence.forward_qualification.evidence01a.observations import (
            origin_qualifies_for_real_evidence,
        )

        self.assertFalse(origin_qualifies_for_real_evidence(CampaignEvidenceOrigin.FIXTURE))
        self.assertFalse(origin_qualifies_for_real_evidence(CampaignEvidenceOrigin.REPLAY))
        self.assertFalse(origin_qualifies_for_real_evidence(CampaignEvidenceOrigin.SYNTHETIC))


class EndToEndSyntheticRuntimeTests(unittest.TestCase):
    def test_provider_to_checkpoint_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_svc = CampaignRuntimeService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="e2e",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            runtime_svc.service.start_campaign()
            runtime_svc.runtime.start_runtime(now_ns=T)
            runtime_svc.runtime.start_session(now_ns=T)

            event = ProviderEventV1(
                instrument_id="AAPL",
                quality_state="GOOD",
                provider_connected=True,
                event_time_ns=T,
                received_time_ns=T,
                provider_id="FAKE",
                provider_capability="QUOTE",
                provider_event_id="e2e-evt-1",
            )
            self.assertTrue(runtime_svc.runtime.ingest_provider_event(event))
            runtime_svc.runtime.record_decision_time(T)
            runtime_svc.runtime.run_settlement_cycle(now_ns=T + DAY_NS)
            runtime_svc.runtime.run_checkpoint_cycle(now_ns=T + DAY_NS, force=True)
            runtime_svc.runtime.stop_runtime(now_ns=T + MIN_QUALIFYING_SESSION_DURATION_NS)

            events = runtime_svc.store.list_operational_events()
            event_types = {e.event_type.value for e in events}
            self.assertIn("CAMPAIGN_STARTED", event_types)
            self.assertIn("SESSION_STARTED", event_types)
            self.assertIn("CHECKPOINT_CREATED", event_types)

            reloaded = CampaignRuntimeService.open(runtime_svc.store.root)
            reloaded.runtime.recover()
            metrics = reloaded.store.read_metrics()
            self.assertGreaterEqual(metrics.provider_events_accepted, 1)


class CheckpointAutomationTests(unittest.TestCase):
    def test_explicit_checkpoint_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="ckpt",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            service.start_campaign()
            cp1 = service.generate_checkpoint(observation_cutoff_ns=T, settlement_cutoff_ns=T)
            checkpoints = service.store.list_checkpoints()
            matching = [c for c in checkpoints if c.checkpoint_id == cp1.checkpoint_id]
            self.assertEqual(len(matching), 1)


if __name__ == "__main__":
    unittest.main()
