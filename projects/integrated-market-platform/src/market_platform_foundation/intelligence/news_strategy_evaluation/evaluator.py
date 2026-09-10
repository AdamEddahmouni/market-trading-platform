"""News intelligence strategy evaluation laboratory — non-executable."""

from __future__ import annotations

import time
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

from market_platform_foundation.news.config import default_pipeline_config
from market_platform_foundation.news.replay import NewsReplayHarness
from market_platform_foundation.news.timestamps import epoch_ns_from_iso, is_observable_at

from .config import EvaluationConfig, verify_evaluation_config
from .contracts import (
    EvaluationReport,
    EvaluationRunRecord,
    EvaluationSampleResult,
    PolicyClassification,
    SampleExclusionReason,
)
from .decisions import build_evaluation_decision, is_abstention
from .errors import EvaluationError, EvaluationErrorCode
from .features import build_feature_snapshot
from .fixture_loader import EvaluationFixturePack, EvaluationFixtureSample, load_fixture_pack
from .hashing import evaluation_report_hash, evaluation_run_hash
from .market_data import FixtureMarketDataProvider
from .metrics import compute_ai_incremental_delta, compute_calibration_report, compute_policy_metrics
from .observability import EvaluationObservability
from .outcomes import measure_outcome
from .policies import PolicyRegistry
from .repository import InMemoryEvaluationRunRepository
from .shadow import build_shadow_record


class NewsStrategyEvaluator:
    """Event-time-safe strategy evaluation over curated news intelligence."""

    def __init__(
        self,
        *,
        config: EvaluationConfig | None = None,
        policy_registry: PolicyRegistry | None = None,
        run_repository: InMemoryEvaluationRunRepository | None = None,
        observability: EvaluationObservability | None = None,
    ) -> None:
        self._config = config or EvaluationConfig()
        self._policies = policy_registry or PolicyRegistry()
        self._repository = run_repository or InMemoryEvaluationRunRepository()
        self._observability = observability or EvaluationObservability()

    @property
    def repository(self) -> InMemoryEvaluationRunRepository:
        return self._repository

    @property
    def observability(self) -> EvaluationObservability:
        return self._observability

    def evaluate_fixture_pack(
        self,
        pack: EvaluationFixturePack | None = None,
        *,
        fixture_path: Any = None,
    ) -> EvaluationReport:
        started = time.perf_counter()
        if pack is None:
            pack = load_fixture_pack(fixture_path)
        market_provider = FixtureMarketDataProvider.from_fixture_payload(pack.raw_payload)
        verify_evaluation_config(self._config, instrument_ids=pack.instrument_universe)

        run_identity = sha256_bytes(
            canonical_bytes(
                {
                    "fixture_schema": pack.schema_version,
                    "lane_id": pack.lane_id,
                    "config_hash": self._config.config_hash(),
                    "sample_ids": [s.sample_id for s in pack.samples],
                }
            )
        )
        run_id = f"EVRUN-{run_identity[:16]}"
        self._observability.evaluation_run_id = run_id
        self._observability.sample_count = len(pack.samples)

        baseline_policy = self._policies.get(
            self._config.baseline_policy_id,
            self._config.baseline_policy_version,
        )
        enhanced_policy = self._policies.get(
            self._config.enhanced_policy_id,
            self._config.enhanced_policy_version,
        )
        naive_policy = self._policies.get(
            self._config.naive_policy_id,
            self._config.naive_policy_version,
        )
        config_hash = self._config.config_hash()
        pipeline_config = default_pipeline_config()
        news_replay = NewsReplayHarness()

        seen_event_ids: set[str] = set()
        sample_results: list[EvaluationSampleResult] = []
        shadow_records = []

        eval_times = [epoch_ns_from_iso(s.as_of) for s in pack.samples if epoch_ns_from_iso(s.as_of)]
        eval_start = pack.samples[0].as_of if pack.samples else ""
        eval_end = pack.samples[-1].as_of if pack.samples else ""

        for sample in pack.samples:
            result = self._evaluate_sample(
                sample,
                run_id=run_id,
                config_hash=config_hash,
                market_provider=market_provider,
                baseline_policy=baseline_policy,
                enhanced_policy=enhanced_policy,
                naive_policy=naive_policy,
                news_replay=news_replay,
                pipeline_config=pipeline_config,
                seen_event_ids=seen_event_ids,
            )
            sample_results.append(result)
            if result.excluded and result.exclusion_reason:
                self._observability.record_exclusion(result.exclusion_reason.value)
            if result.baseline_decision:
                self._observability.record_decision("baseline", result.baseline_decision.decision.value)
            if result.enhanced_decision:
                self._observability.record_decision("enhanced", result.enhanced_decision.decision.value)
                shadow_records.append(
                    build_shadow_record(result.enhanced_decision, recorded_at=sample.as_of)
                )

        primary_horizon = self._config.outcome_horizons[0].horizon_id
        baseline_metrics = compute_policy_metrics(
            policy_id=baseline_policy.policy_id,
            policy_version=baseline_policy.version,
            classification=PolicyClassification.BASELINE_DETERMINISTIC,
            samples=sample_results,
            primary_horizon_id=primary_horizon,
            decisions_attr="baseline_decision",
            outcomes_attr="baseline_outcomes",
        )
        enhanced_metrics = compute_policy_metrics(
            policy_id=enhanced_policy.policy_id,
            policy_version=enhanced_policy.version,
            classification=PolicyClassification.AI_ENHANCED,
            samples=sample_results,
            primary_horizon_id=primary_horizon,
            decisions_attr="enhanced_decision",
            outcomes_attr="enhanced_outcomes",
        )
        delta = compute_ai_incremental_delta(baseline_metrics, enhanced_metrics)
        calibration = compute_calibration_report(sample_results, primary_horizon_id=primary_horizon)

        limitations = [
            "SOFTWARE_FIXTURE_ONLY — synthetic evaluation pack; not empirical alpha evidence",
            "MODEL_REPORTED_CONFIDENCE is empirical confidence analysis, not calibrated probability",
            "Subsequent returns measure association, not causal news attribution",
        ]
        if any(s.overlap_flags for s in sample_results):
            limitations.append("Overlapping outcome windows flagged — samples not statistically independent")
        if not self._config.oos_partition_start:
            limitations.append("Insufficient chronological partition for meaningful OOS — fixture sample only")

        run_body = {
            "run_id": run_id,
            "lane_id": pack.lane_id or self._config.lane_id,
            "instrument_universe": list(pack.instrument_universe),
            "eval_start": eval_start,
            "eval_end": eval_end,
            "baseline_policy_id": baseline_policy.policy_id,
            "baseline_policy_version": baseline_policy.version,
            "enhanced_policy_id": enhanced_policy.policy_id,
            "enhanced_policy_version": enhanced_policy.version,
            "config_hash": config_hash,
            "sample_count": len(sample_results),
        }
        run_record = EvaluationRunRecord(
            run_id=run_id,
            lane_id=pack.lane_id or self._config.lane_id,
            instrument_universe=pack.instrument_universe,
            eval_start=eval_start,
            eval_end=eval_end,
            baseline_policy_id=baseline_policy.policy_id,
            baseline_policy_version=baseline_policy.version,
            enhanced_policy_id=enhanced_policy.policy_id,
            enhanced_policy_version=enhanced_policy.version,
            outcome_horizons=self._config.outcome_horizons,
            config_hash=config_hash,
            run_hash=evaluation_run_hash(run_body),
            status="COMPLETE",
            news_policy_versions={
                "source_policy": pipeline_config.source_policy_version,
                "catalyst_registry": pipeline_config.catalyst_registry_version,
                "filter_chain": pipeline_config.filter_chain_version,
            },
            development_partition_end=self._config.development_partition_end,
            oos_partition_start=self._config.oos_partition_start,
        )

        report = EvaluationReport(
            run=run_record,
            sample_results=tuple(sample_results),
            baseline_metrics=baseline_metrics,
            enhanced_metrics=enhanced_metrics,
            ai_incremental_delta=delta,
            calibration=calibration,
            limitations=tuple(limitations),
            report_hash="",
        )
        report = EvaluationReport(
            run=report.run,
            sample_results=report.sample_results,
            baseline_metrics=report.baseline_metrics,
            enhanced_metrics=report.enhanced_metrics,
            ai_incremental_delta=report.ai_incremental_delta,
            calibration=report.calibration,
            limitations=report.limitations,
            report_hash=evaluation_report_hash(report),
        )
        self._repository.save_run(run_record)
        self._repository.save_report(report)
        self._observability.evaluated_count = baseline_metrics.evaluated_count
        self._observability.excluded_count = baseline_metrics.excluded_count
        self._observability.replay_duration_ms = int((time.perf_counter() - started) * 1000)
        self._shadow_records = tuple(shadow_records)
        return report

    @property
    def shadow_records(self) -> tuple[Any, ...]:
        return getattr(self, "_shadow_records", ())

    def _evaluate_sample(
        self,
        sample: EvaluationFixtureSample,
        *,
        run_id: str,
        config_hash: str,
        market_provider: FixtureMarketDataProvider,
        baseline_policy,
        enhanced_policy,
        naive_policy,
        news_replay,
        pipeline_config,
        seen_event_ids: set[str],
    ) -> EvaluationSampleResult:
        overlap_flags: list[str] = []
        if sample.overlap_with:
            overlap_flags.append("OVERLAPPING_EVENT_WINDOW")
            overlap_flags.extend(f"OVERLAP_WITH:{oid}" for oid in sample.overlap_with)

        try:
            as_of_ns = epoch_ns_from_iso(sample.as_of)
            if as_of_ns is None:
                raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, "invalid as_of")

            curated_events = []
            for event in sample.events:
                if not is_observable_at(event, as_of_ns):
                    if sample.expect_excluded:
                        return self._excluded_sample(
                            sample,
                            SampleExclusionReason.FUTURE_NEWS_NOT_OBSERVABLE,
                            overlap_flags,
                        )
                    raise EvaluationError(EvaluationErrorCode.FUTURE_NEWS_LEAK, event.event_id)

            replay = news_replay.replay(list(sample.events), as_of=sample.as_of, config=pipeline_config)
            curated_events = list(replay.accepted_events)
            if not curated_events and sample.events and not sample.expect_excluded:
                return self._excluded_sample(sample, SampleExclusionReason.STALE_EVENT_REJECTED, overlap_flags)
            if not curated_events and sample.expect_excluded:
                reason = SampleExclusionReason.STALE_EVENT_REJECTED
                if sample.exclusion_reason:
                    try:
                        reason = SampleExclusionReason(sample.exclusion_reason)
                    except ValueError:
                        pass
                return self._excluded_sample(sample, reason, overlap_flags)

            duplicate = any(e.event_id in seen_event_ids for e in curated_events)
            if duplicate:
                return self._excluded_sample(sample, SampleExclusionReason.DUPLICATE_EVENT_SAMPLE, overlap_flags)
            for event in curated_events:
                seen_event_ids.add(event.event_id)

            inference = sample.inference_record
            if inference and inference.result:
                completed_ns = epoch_ns_from_iso(inference.result.completed_time)
                if completed_ns is not None and completed_ns > as_of_ns:
                    return self._excluded_sample(
                        sample,
                        SampleExclusionReason.FUTURE_INFERENCE_NOT_OBSERVABLE,
                        overlap_flags,
                    )

            snapshot = build_feature_snapshot(
                as_of=sample.as_of,
                instrument_id=sample.instrument_id,
                asset_class=sample.asset_class,
                events=curated_events or list(sample.events),
                market_provider=market_provider,
                inference_record=inference,
                pipeline_results=list(replay.results),
                overlap_flags=tuple(overlap_flags),
            )

            baseline_decision = build_evaluation_decision(
                evaluation_run_id=run_id,
                sample_id=sample.sample_id,
                policy=baseline_policy,
                snapshot=snapshot,
                config_hash=config_hash,
                overlap_flags=tuple(overlap_flags),
            )
            enhanced_decision = build_evaluation_decision(
                evaluation_run_id=run_id,
                sample_id=sample.sample_id,
                policy=enhanced_policy,
                snapshot=snapshot,
                config_hash=config_hash,
                overlap_flags=tuple(overlap_flags),
            )
            naive_decision = build_evaluation_decision(
                evaluation_run_id=run_id,
                sample_id=sample.sample_id,
                policy=naive_policy,
                snapshot=snapshot,
                config_hash=config_hash,
                overlap_flags=tuple(overlap_flags),
            )

            baseline_outcomes = tuple(
                measure_outcome(
                    decision=baseline_decision,
                    horizon=horizon,
                    market_provider=market_provider,
                    flat_threshold_bps=self._config.directional_flat_threshold_bps,
                )
                for horizon in self._config.outcome_horizons
            )
            enhanced_outcomes = tuple(
                measure_outcome(
                    decision=enhanced_decision,
                    horizon=horizon,
                    market_provider=market_provider,
                    flat_threshold_bps=self._config.directional_flat_threshold_bps,
                )
                for horizon in self._config.outcome_horizons
            )

            return EvaluationSampleResult(
                sample_id=sample.sample_id,
                as_of=sample.as_of,
                instrument_id=sample.instrument_id,
                asset_class=sample.asset_class,
                excluded=False,
                exclusion_reason=None,
                feature_snapshot=snapshot,
                baseline_decision=baseline_decision,
                enhanced_decision=enhanced_decision,
                naive_decision=naive_decision,
                baseline_outcomes=baseline_outcomes,
                enhanced_outcomes=enhanced_outcomes,
                overlap_flags=tuple(overlap_flags),
            )
        except EvaluationError as exc:
            reason = SampleExclusionReason.CONFIG_INVALID
            if exc.code == EvaluationErrorCode.FUTURE_NEWS_LEAK:
                reason = SampleExclusionReason.FUTURE_NEWS_NOT_OBSERVABLE
            elif exc.code == EvaluationErrorCode.FUTURE_INFERENCE_LEAK:
                reason = SampleExclusionReason.FUTURE_INFERENCE_NOT_OBSERVABLE
            elif exc.code == EvaluationErrorCode.FUTURE_MARKET_LEAK:
                reason = SampleExclusionReason.FUTURE_MARKET_FEATURE
            elif exc.code == EvaluationErrorCode.MARKET_DATA_MISSING:
                reason = SampleExclusionReason.INCOMPLETE_OUTCOME_DATA
            if sample.expect_excluded:
                return self._excluded_sample(sample, reason, overlap_flags)
            raise

    def _excluded_sample(
        self,
        sample: EvaluationFixtureSample,
        reason: SampleExclusionReason,
        overlap_flags: list[str],
    ) -> EvaluationSampleResult:
        return EvaluationSampleResult(
            sample_id=sample.sample_id,
            as_of=sample.as_of,
            instrument_id=sample.instrument_id,
            asset_class=sample.asset_class,
            excluded=True,
            exclusion_reason=reason,
            feature_snapshot=None,
            baseline_decision=None,
            enhanced_decision=None,
            naive_decision=None,
            overlap_flags=tuple(overlap_flags),
            warnings=(reason.value,),
        )


__all__ = ["NewsStrategyEvaluator"]
