"""Deterministic tests for the multi-source provider foundation."""

from __future__ import annotations

import unittest

from market_platform_foundation.providers.registry import (
    CapabilityDescriptor,
    ProviderDescriptor,
    ProviderRegistry,
    ProviderRegistryError,
)
from market_platform_foundation.providers.identity import (
    InstrumentIdentity,
    MappingConflictResolution,
    ProviderIdentifierMapping,
    resolve_mapping_conflict,
)
from market_platform_foundation.providers.observations import (
    Observation,
    ObservationClocks,
    build_observation_envelope,
)
from market_platform_foundation.providers.raw_records import (
    NormalizedObservation,
    RawRecord,
    RawRecordStore,
)
from market_platform_foundation.providers.planner import (
    ProviderPolicy,
    QueryRequest,
    QueryPlanner,
)
from market_platform_foundation.providers.reconciliation import (
    CandidateObservation,
    QualityScore,
    ReconciliationPolicy,
    reconcile_candidates,
)
from market_platform_foundation.providers.testing import DeterministicQuoteProvider
from market_platform_foundation.providers.storage import InMemoryObservationStore


def provider(provider_id: str, *, priority: int, capability: str) -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=provider_id,
        display_name=provider_id.title(),
        capabilities=(
            CapabilityDescriptor(
                capability_id=capability,
                asset_classes=("equity",),
                venues=("US_EQUITY",),
                interfaces=("EquityQuoteProvider",),
                supports_history=True,
                supports_pit=True,
                freshness_sla_ns=1_000_000_000,
                license_class="RESEARCH_ONLY",
                rate_policy_id="test",
                normalizer_version="test/1",
            ),
        ),
        health_state="HEALTHY",
        credential_refs=(),
        schema_versions=("1.0",),
        priority=priority,
    )


class RegistryTests(unittest.TestCase):
    def test_registry_orders_providers_deterministically_and_validates_capabilities(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("zeta", priority=20, capability="quote"))
        registry.register(provider("alpha", priority=10, capability="quote"))

        self.assertEqual(
            [item.provider_id for item in registry.providers_for("quote")],
            ["alpha", "zeta"],
        )
        self.assertEqual(registry.manifest()["schema_version"], "1.0")

    def test_registry_rejects_duplicate_provider_ids(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("alpha", priority=1, capability="quote"))

        with self.assertRaisesRegex(ProviderRegistryError, "PROVIDER_ID_DUPLICATE"):
            registry.register(provider("alpha", priority=2, capability="quote"))

    def test_registry_validate_returns_a_stable_manifest(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("alpha", priority=1, capability="quote"))
        self.assertEqual(registry.validate()["provider_count"], 1)

    def test_registry_rejects_unscoped_credential_refs_and_unknown_licenses(self) -> None:
        unsafe = provider("unsafe", priority=1, capability="quote")
        unsafe = unsafe.__class__(
            unsafe.provider_id,
            unsafe.display_name,
            unsafe.capabilities,
            unsafe.health_state,
            ("raw-secret",),
            unsafe.schema_versions,
            unsafe.priority,
        )
        with self.assertRaisesRegex(ProviderRegistryError, "CREDENTIAL_REF_INVALID"):
            ProviderRegistry().register(unsafe)

        capability = CapabilityDescriptor(
            "quote", ("equity",), ("US_EQUITY",), ("Quote",), True, True,
            1, "UNLICENSED", "test", "test/1",
        )
        invalid_license = unsafe.__class__(
            "license",
            "License",
            (capability,),
            "HEALTHY",
            (),
            ("1.0",),
            1,
        )
        with self.assertRaisesRegex(ProviderRegistryError, "CAPABILITY_LICENSE_INVALID"):
            ProviderRegistry().register(invalid_license)


class IdentityTests(unittest.TestCase):
    def test_provider_aliases_share_canonical_identity_without_ticker_collision(self) -> None:
        nasdaq = InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")
        nyse = InstrumentIdentity("venue", "AAPL", "equity", "NYSE", "USD")
        mapping = ProviderIdentifierMapping(
            provider_id="alpha",
            source_instance_id="alpha-live",
            provider_identifier="US.AAPL",
            canonical_instrument=nasdaq,
            mapping_version="1",
        )

        self.assertNotEqual(nasdaq.qualified_id(), nyse.qualified_id())
        self.assertEqual(mapping.canonical_instrument, nasdaq)
        self.assertEqual(mapping.to_dict()["provider_identifier"], "US.AAPL")

    def test_mapping_rejects_empty_provider_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "PROVIDER_IDENTIFIER_REQUIRED"):
            ProviderIdentifierMapping(
                provider_id="alpha",
                source_instance_id="alpha-live",
                provider_identifier="",
                canonical_instrument=InstrumentIdentity(
                    "venue", "AAPL", "equity", "NASDAQ", "USD"
                ),
                mapping_version="1",
            )

    def test_mapping_conflicts_fail_closed_and_resolution_is_auditable(self) -> None:
        first = InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")
        second = InstrumentIdentity("venue", "AAPL", "equity", "NYSE", "USD")
        with self.assertRaisesRegex(ValueError, "MAPPING_CONFLICT_STATE_INVALID"):
            ProviderIdentifierMapping("alpha", "alpha-live", "AAPL", first, "1", "CONFLICT")

        resolution = resolve_mapping_conflict(
            (
                ProviderIdentifierMapping("alpha", "alpha-live", "AAPL", first, "1"),
                ProviderIdentifierMapping("alpha", "alpha-live", "AAPL", second, "1"),
            )
        )
        self.assertIsInstance(resolution, MappingConflictResolution)
        self.assertIsNone(resolution.selected)
        self.assertEqual(resolution.decision, "FAIL_CLOSED_CONFLICT")
        self.assertEqual(len(resolution.candidates), 2)
        self.assertEqual(resolution.to_dict()["decision"], "FAIL_CLOSED_CONFLICT")


class RawObservationTests(unittest.TestCase):
    def test_raw_payload_is_deduplicated_and_reprocessing_is_versioned(self) -> None:
        store = RawRecordStore(max_records=2, max_bytes=10_000)
        record = RawRecord.create(
            request_identity={"instrument": "venue:equity:NASDAQ:AAPL", "page": 1},
            provider_id="alpha",
            source_instance_id="alpha-test",
            received_time_ns=20,
            payload={"price": 100.0},
            schema_version="quote/1",
            ingestion_version="capture/1",
            license_class="RESEARCH_ONLY",
            storage_ref="memory://raw/1",
            request_metadata={"api_key": "REDACTED", "url": "https://example.test"},
        )
        duplicate = store.put(record)
        self.assertEqual(duplicate.raw_record_id, record.raw_record_id)
        self.assertEqual(store.get(record.raw_record_id).payload_hash, record.payload_hash)

        normalized = store.reprocess(
            record.raw_record_id,
            "quote-normalizer/2",
            lambda payload: {"mid": payload["price"]},
        )
        self.assertIsInstance(normalized, NormalizedObservation)
        self.assertEqual(normalized.normalizer_version, "quote-normalizer/2")
        self.assertEqual(store.get(record.raw_record_id).payload, {"price": 100.0})
        self.assertEqual(
            store.get(record.raw_record_id).redacted_request["api_key"],
            "***REDACTED***",
        )

    def test_raw_record_is_deeply_immutable_and_reprocessing_is_idempotent(self) -> None:
        record = RawRecord.create(
            request_identity={"query": "https://example.test?api_key=secret"},
            provider_id="alpha",
            source_instance_id="alpha-test",
            received_time_ns=20,
            payload={"nested": {"price": 100.0}},
            schema_version="quote/1",
            ingestion_version="capture/1",
            license_class="RESEARCH_ONLY",
            storage_ref="memory://raw/1",
            request_metadata={},
        )
        with self.assertRaises(TypeError):
            record.payload["nested"]["price"] = 101.0
        self.assertNotIn("secret", repr(record.request_identity))

        store = RawRecordStore()
        store.put(record)
        first = store.reprocess(record.raw_record_id, "quote/1", lambda _: {"mid": 100.0})
        second = store.reprocess(record.raw_record_id, "quote/1", lambda _: {"mid": 100.0})
        self.assertEqual(first.observation_id, second.observation_id)
        self.assertEqual(store.manifest()["normalization_count"], 1)
        with self.assertRaisesRegex(ValueError, "NORMALIZATION_IMMUTABILITY_CONFLICT"):
            store.reprocess(record.raw_record_id, "quote/1", lambda _: {"mid": 101.0})

    def test_raw_identity_isolated_by_provider_and_source_instance(self) -> None:
        common = dict(
            request_identity={"instrument": "AAPL"},
            received_time_ns=20,
            payload={"price": 100.0},
            schema_version="quote/1",
            ingestion_version="capture/1",
            license_class="RESEARCH_ONLY",
            storage_ref="memory://raw",
            request_metadata={"url": "https://example.test"},
        )
        alpha = RawRecord.create(provider_id="alpha", source_instance_id="alpha-live", **common)
        beta = RawRecord.create(provider_id="beta", source_instance_id="beta-live", **common)
        self.assertNotEqual(alpha.raw_record_id, beta.raw_record_id)

    def test_observation_preserves_all_pit_clocks_and_lineage(self) -> None:
        observation = Observation(
            observation_id="obs-1",
            instrument=InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            capability_id="quote",
            provider_id="alpha",
            source_instance_id="alpha-test",
            clocks=ObservationClocks(
                event_time_ns=10,
                source_publish_time_ns=11,
                effective_time_ns=12,
                available_time_ns=13,
                received_time_ns=14,
                ingested_time_ns=15,
                normalized_time_ns=16,
                published_time_ns=17,
                validity_start_ns=12,
                validity_end_ns=None,
            ),
            value={"bid": 99.0, "ask": 101.0},
            raw_record_id="raw-1",
            quality=("COMPLETE",),
            confidence=0.9,
            revision_id="r2",
            adjustment_state="UNADJUSTED",
            license_class="RESEARCH_ONLY",
            normalizer_version="quote/1",
        )
        self.assertEqual(observation.clocks.available_time_ns, 13)
        envelope = build_observation_envelope(observation)
        self.assertEqual(envelope["raw_reference"], "raw-1")
        self.assertEqual(envelope["source_revision_id"], "r2")
        self.assertEqual(envelope["received_time"], 14)
        self.assertEqual(envelope["normalized_time"], 16)
        self.assertEqual(envelope["published_time"], 17)

    def test_live_envelope_preserves_live_semantics_and_supersedes_revision(self) -> None:
        observation = Observation(
            "obs-r3",
            InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            "quote",
            "alpha",
            "alpha-live",
            ObservationClocks(10, 11, 12, 13, 14, 15, 16, 17, 12, None),
            {"bid": 99.0},
            "raw-r3",
            ("COMPLETE",),
            0.9,
            "r3",
            "UNADJUSTED",
            "RESEARCH_ONLY",
            "quote/3",
            "live",
            "obs-r2",
        )
        envelope = observation.to_envelope()
        self.assertEqual(envelope["live_received_time"], 14)
        self.assertIsNone(envelope["historical_ingested_time"])
        self.assertEqual(envelope["supersedes_event_id"], "obs-r2")
        self.assertEqual(envelope["acquisition_mode"], "live")

    def test_observation_values_are_deeply_immutable(self) -> None:
        observation = Observation(
            "immutable",
            InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            "quote",
            "alpha",
            "alpha-test",
            ObservationClocks(1, 1, 1, 2, 3, 4, 5, None, 1, None),
            {"nested": {"price": 100.0}},
            "raw-immutable",
            ("COMPLETE",),
            1.0,
            "r1",
            "UNADJUSTED",
            "RESEARCH_ONLY",
            "quote/1",
        )
        with self.assertRaises(TypeError):
            observation.value["nested"]["price"] = 101.0

    def test_extensions_are_frozen_preserved_and_secret_safe(self) -> None:
        observation = Observation(
            "with-extensions",
            InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            "quote",
            "alpha",
            "alpha-test",
            ObservationClocks(1, 1, 1, 2, 3, 4, 5, None, 1, None),
            {"price": 100.0},
            "raw-extensions",
            ("COMPLETE",),
            1.0,
            "r1",
            "UNADJUSTED",
            "RESEARCH_ONLY",
            "quote/1",
            extensions={"vendor_flag": {"venue_code": "XNAS"}},
        )
        self.assertEqual(observation.to_envelope()["extensions"]["vendor_flag"]["venue_code"], "XNAS")
        with self.assertRaises(TypeError):
            observation.extensions["vendor_flag"]["venue_code"] = "XNYS"
        raw = RawRecord.create(
            request_identity={"instrument": "AAPL"},
            provider_id="alpha",
            source_instance_id="alpha-test",
            received_time_ns=1,
            payload={"price": 100.0},
            schema_version="quote/1",
            ingestion_version="capture/1",
            license_class="RESEARCH_ONLY",
            storage_ref="memory://raw",
            request_metadata={},
        )
        normalized = RawRecordStore()
        normalized.put(raw)
        output = normalized.reprocess(
            raw.raw_record_id,
            "quote/1",
            lambda _: {"price": 100.0, "extensions": {"vendor_flag": {"venue_code": "XNAS"}}},
        )
        self.assertEqual(output.extensions["vendor_flag"]["venue_code"], "XNAS")
        with self.assertRaises(TypeError):
            output.extensions["vendor_flag"]["venue_code"] = "XNYS"
        with self.assertRaisesRegex(ValueError, "OBSERVATION_EXTENSIONS_SECRET"):
            Observation(
                "secret-extension",
                observation.instrument,
                "quote",
                "alpha",
                "alpha-test",
                observation.clocks,
                observation.value,
                "raw-secret-extension",
                ("COMPLETE",),
                1.0,
                "r1",
                "UNADJUSTED",
                "RESEARCH_ONLY",
                "quote/1",
                extensions={"api_key": "do-not-store"},
            )


class PlannerTests(unittest.TestCase):
    def test_planner_selects_healthy_licensed_provider_and_fallback(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("alpha", priority=10, capability="quote"))
        registry.register(provider("beta", priority=20, capability="quote"))
        planner = QueryPlanner(
            registry,
            {
                "alpha": ProviderPolicy(allowed_license_classes=("RESEARCH_ONLY",)),
                "beta": ProviderPolicy(allowed_license_classes=("RESEARCH_ONLY",)),
            },
            clock_ns=lambda: 100,
        )

        plan = planner.plan(
            QueryRequest(
                capability_id="quote",
                instrument=InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
                as_of_time_ns=50,
                freshness_max_age_ns=2_000_000_000,
                license_purpose="RESEARCH_ONLY",
            )
        )
        self.assertEqual(plan.selected_provider_ids, ("alpha",))
        self.assertEqual(plan.fallback_provider_ids, ("beta",))
        self.assertTrue(plan.cache_key.startswith("query-"))

    def test_planner_filters_disabled_unhealthy_and_unlicensed_providers(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("alpha", priority=1, capability="quote"))
        registry.register(provider("beta", priority=2, capability="quote"))
        planner = QueryPlanner(
            registry,
            {
                "alpha": ProviderPolicy(enabled=False),
                "beta": ProviderPolicy(allowed_license_classes=("COMMERCIAL",)),
            },
        )
        plan = planner.plan(
            QueryRequest(
                capability_id="quote",
                instrument=InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
                as_of_time_ns=50,
                freshness_max_age_ns=None,
                license_purpose="RESEARCH_ONLY",
            )
        )
        self.assertEqual(plan.selected_provider_ids, ())
        self.assertIn("NO_ELIGIBLE_PROVIDER", plan.diagnostics)

    def test_planner_rejects_provider_that_cannot_meet_requested_freshness(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("slow", priority=1, capability="quote"))
        planner = QueryPlanner(registry, {"slow": ProviderPolicy()})
        plan = planner.plan(
            QueryRequest(
                capability_id="quote",
                instrument=InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
                as_of_time_ns=None,
                freshness_max_age_ns=100,
                license_purpose="RESEARCH_ONLY",
            )
        )
        self.assertEqual(plan.selected_provider_ids, ())
        self.assertIn("FRESHNESS_UNAVAILABLE:slow", plan.diagnostics)

    def test_planner_supports_mode_scope_retry_cache_and_bounded_rate(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("alpha", priority=10, capability="quote"))
        planner = QueryPlanner(
            registry,
            {
                "alpha": ProviderPolicy(
                    priority=3,
                    max_retries=4,
                    base_backoff_ns=25,
                    cache_ttl_ns=100,
                    serve_stale=True,
                    rate_budget=1,
                )
            },
            clock_ns=lambda: 1_000,
        )
        request = QueryRequest(
            "quote",
            InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            900,
            None,
            "RESEARCH_ONLY",
            mode="research",
            source_instance_id="alpha-live",
            account_id="acct-1",
        )
        plan = planner.plan(request)
        self.assertEqual(plan.retry_max_retries, 4)
        self.assertEqual(plan.retry_backoff_ns, 25)
        self.assertEqual(plan.cache_ttl_ns, 100)
        self.assertTrue(plan.serve_stale)
        planner.cache_put(
            plan.cache_key,
            {"value": 1},
            now_ns=1_000,
            ttl_ns=plan.cache_ttl_ns,
            serve_stale=plan.serve_stale,
        )
        self.assertEqual(planner.cache_get(plan.cache_key, now_ns=1_050), {"value": 1})
        self.assertEqual(planner.cache_get(plan.cache_key, now_ns=1_200), {"value": 1})
        planner.record_result("alpha", True)
        self.assertIn("RATE_BUDGET_EXHAUSTED:alpha", planner.plan(request).diagnostics)
        with self.assertRaisesRegex(ValueError, "LIVE_AS_OF_UNSUPPORTED"):
            QueryRequest(
                "quote",
                request.instrument,
                900,
                None,
                "RESEARCH_ONLY",
                mode="live",
            )

    def test_planner_can_pin_provider_scope_without_cross_source_cache_reuse(self) -> None:
        registry = ProviderRegistry()
        registry.register(provider("alpha", priority=10, capability="quote"))
        registry.register(provider("beta", priority=20, capability="quote"))
        planner = QueryPlanner(registry, {})
        base = dict(
            capability_id="quote",
            instrument=InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            as_of_time_ns=50,
            freshness_max_age_ns=None,
            license_purpose="RESEARCH_ONLY",
            source_instance_id="alpha-live",
            account_id="acct-1",
        )
        alpha = planner.plan(QueryRequest(**base, provider_id="alpha"))
        beta = planner.plan(QueryRequest(**base, provider_id="beta"))
        self.assertEqual(alpha.selected_provider_ids, ("alpha",))
        self.assertEqual(beta.selected_provider_ids, ("beta",))
        self.assertNotEqual(alpha.cache_key, beta.cache_key)


class ReconciliationTests(unittest.TestCase):
    def test_reconciliation_retains_candidates_and_selects_best_quality(self) -> None:
        instrument = InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")
        first = Observation(
            "one", instrument, "quote", "alpha", "a", ObservationClocks(1, 1, 1, 2, 3, 4, 5, None, 1, None),
            {"price": 100.0}, "raw-1", ("COMPLETE",), 0.8, "1", "UNADJUSTED", "RESEARCH_ONLY", "quote/1",
        )
        second = Observation(
            "two", instrument, "quote", "beta", "b", ObservationClocks(1, 1, 1, 2, 3, 4, 5, None, 1, None),
            {"price": 100.2}, "raw-2", ("COMPLETE",), 0.9, "1", "UNADJUSTED", "RESEARCH_ONLY", "quote/1",
        )
        result = reconcile_candidates(
            (
                CandidateObservation(first, QualityScore(1, 1, 1, 1, 0.8, 0.8)),
                CandidateObservation(second, QualityScore(1, 1, 1, 1, 0.9, 0.9)),
            ),
            value_type="numeric",
            numeric_tolerance=0.05,
        )
        self.assertEqual(result.selected.observation_id, "two")
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.conflicts[0].code, "VALUE_OUTLIER")

    def test_reconciliation_policy_flags_stale_and_invalid_timestamps(self) -> None:
        instrument = InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")
        stale = Observation(
            "stale", instrument, "quote", "alpha", "a",
            ObservationClocks(1, 1, 1, 10, 10, 10, 10, None, 1, None),
            {"price": 100.0}, "raw-stale", ("COMPLETE",), 0.9, "1", "UNADJUSTED",
            "RESEARCH_ONLY", "quote/1",
        )
        future = Observation(
            "future", instrument, "quote", "beta", "b",
            ObservationClocks(1, 1, 1, 2_000, 2_000, 2_000, 2_000, None, 1, None),
            {"price": 100.1}, "raw-future", ("COMPLETE",), 0.9, "1", "UNADJUSTED",
            "RESEARCH_ONLY", "quote/1",
        )
        result = reconcile_candidates(
            (
                CandidateObservation(stale, QualityScore(1, 1, 1, 1, 1, 1)),
                CandidateObservation(future, QualityScore(1, 1, 1, 1, 1, 1)),
            ),
            value_type="numeric",
            policy=ReconciliationPolicy(now_time_ns=1_000, stale_after_ns=100),
        )
        codes = {conflict.code for conflict in result.conflicts}
        self.assertIn("STALE_CANDIDATE", codes)
        self.assertIn("TIMESTAMP_INVALID", codes)
        self.assertEqual(len(result.candidates), 2)

    def test_reconciliation_can_derive_quality_factors_deterministically(self) -> None:
        observation = Observation(
            "derived-quality",
            InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            "quote",
            "alpha",
            "alpha-test",
            ObservationClocks(10, 10, 10, 20, 20, 20, 20, None, 10, None),
            {"price": 100.0},
            "raw-quality",
            ("COMPLETE",),
            0.8,
            "r1",
            "UNADJUSTED",
            "RESEARCH_ONLY",
            "quote/1",
        )
        result = reconcile_candidates(
            (CandidateObservation(observation),),
            value_type="numeric",
            policy=ReconciliationPolicy(now_time_ns=100, stale_after_ns=1_000),
        )
        self.assertEqual(result.quality_summary["derived-quality"], 0.966667)


class BoundaryTests(unittest.TestCase):
    def test_observation_store_is_operational_and_as_of_aware(self) -> None:
        instrument = InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")
        observation = Observation(
            "stored", instrument, "quote", "alpha", "a",
            ObservationClocks(1, 1, 1, 20, 3, 4, 5, None, 1, None),
            {"price": 100.0}, "raw-1", ("COMPLETE",), 1.0, "1", "UNADJUSTED",
            "RESEARCH_ONLY", "quote/1",
        )
        store = InMemoryObservationStore()
        store.append(observation)
        self.assertEqual(store.query(instrument, as_of_time_ns=19), ())
        self.assertEqual(store.query(instrument, as_of_time_ns=20)[0].observation_id, "stored")

    def test_observation_store_deduplicates_ids_and_rejects_conflicts(self) -> None:
        instrument = InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")
        observation = Observation(
            "same", instrument, "quote", "alpha", "a",
            ObservationClocks(1, 1, 1, 2, 3, 4, 5, None, 1, None),
            {"price": 100.0}, "raw-1", ("COMPLETE",), 1.0, "1", "UNADJUSTED",
            "RESEARCH_ONLY", "quote/1",
        )
        conflicting = Observation(
            "same", instrument, "quote", "alpha", "a",
            ObservationClocks(1, 1, 1, 2, 3, 4, 5, None, 1, None),
            {"price": 101.0}, "raw-2", ("COMPLETE",), 1.0, "1", "UNADJUSTED",
            "RESEARCH_ONLY", "quote/1",
        )
        store = InMemoryObservationStore()
        store.append(observation)
        store.append(observation)
        with self.assertRaisesRegex(ValueError, "OBSERVATION_IMMUTABILITY_CONFLICT"):
            store.append(conflicting)

    def test_deterministic_fake_provider_returns_source_attributed_observation(self) -> None:
        provider = DeterministicQuoteProvider("fixture-alpha", price=100.0)
        observation = provider.quote(
            InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD"),
            now_ns=50,
        )
        self.assertEqual(observation.provider_id, "fixture-alpha")
        self.assertEqual(observation.value["price"], 100.0)
        self.assertEqual(observation.clocks.available_time_ns, 50)


if __name__ == "__main__":
    unittest.main()
