"""Deterministic evaluation replay harness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ...canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.news.timestamps import epoch_ns_from_iso, is_observable_at

from .config import EvaluationConfig
from .contracts import EvaluationReport
from .evaluator import NewsStrategyEvaluator
from .fixture_loader import DEFAULT_FIXTURE_PATH, EvaluationFixturePack, load_fixture_pack
from .decisions import build_evaluation_decision
from .features import build_feature_snapshot
from .market_data import FixtureMarketDataProvider
from .policies import PolicyRegistry
from .errors import EvaluationError


def _aware_ns(value: str) -> int | None:
    try:
        clock = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if clock.tzinfo is None:
            return None
        return epoch_ns_from_iso(value)
    except (ValueError, TypeError, AttributeError):
        return None


@dataclass(frozen=True, slots=True)
class EvaluationReplayResult:
    report: EvaluationReport
    replay_count: int
    report_hashes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "replay_count": self.replay_count,
            "report_hashes": list(self.report_hashes),
            "deterministic": len(set(self.report_hashes)) == 1,
        }


class EvaluationReplayHarness:
    """Replay fixture evaluation with stable hashes."""

    def __init__(
        self,
        *,
        config: EvaluationConfig | None = None,
        fixture_path: Path | None = None,
    ) -> None:
        self._config = config or EvaluationConfig()
        self._fixture_path = fixture_path or DEFAULT_FIXTURE_PATH

    def snapshot_at(self, *, replay_date: str, as_of: str,
                    pack: EvaluationFixturePack | None = None) -> dict[str, Any]:
        """Read-only selected-day view. Forward labels never enter this view.

        Uses the same existing feature builder and three registered strategies.
        Receipt-less legacy fixtures remain usable only with an explicit limitation.
        No provider, model executor, calibration or execution adapter is constructed.
        """
        clock = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        selected = date.fromisoformat(replay_date)
        if clock.tzinfo is None or clock.astimezone(ZoneInfo('America/New_York')).date() != selected:
            raise ValueError('REPLAY_DAY_OR_TIMEZONE_MISMATCH')
        cutoff = epoch_ns_from_iso(as_of)
        if cutoff is None:
            raise ValueError('REPLAY_CLOCK_INVALID')
        pack = pack or load_fixture_pack(self._fixture_path)
        provider = FixtureMarketDataProvider.from_fixture_payload(pack.raw_payload)
        registry = PolicyRegistry()
        pairs = ((self._config.baseline_policy_id, self._config.baseline_policy_version),
                 (self._config.enhanced_policy_id, self._config.enhanced_policy_version),
                 (self._config.naive_policy_id, self._config.naive_policy_version))
        policies = tuple(registry.get(*pair) for pair in pairs)
        decisions = []
        gaps = []
        withheld_news = withheld_inference = 0
        sample_count = 0
        legacy = any(bar.received_time is None for instrument in pack.instrument_universe
                     for bar in (provider.get_series(instrument).bars if provider.get_series(instrument) else ()))
        for sample in sorted(pack.samples, key=lambda s: (s.as_of, s.sample_id)):
            instant = datetime.fromisoformat(sample.as_of.replace('Z', '+00:00'))
            if instant.tzinfo is None:
                gaps.append({'sample_id': sample.sample_id, 'reason': 'UNKNOWN_SAMPLE_TIMEZONE'})
                continue
            if instant.astimezone(ZoneInfo('America/New_York')).date() != selected or (
                    epoch_ns_from_iso(sample.as_of) or 0) > cutoff:
                continue
            sample_count += 1
            decision_cutoff = epoch_ns_from_iso(sample.as_of)
            events = [e for e in sample.events if is_observable_at(e, decision_cutoff)]
            withheld_news += len(sample.events) - len(events)
            inference = sample.inference_record
            if inference is not None:
                times = (inference.result.completed_time, inference.result.as_of,
                         inference.input_packet.as_of) if inference.result is not None else ()
                visible_ids = {event.event_id for event in events}
                result = inference.result
                packet = inference.input_packet
                lineage_valid = (result is not None and result.input_id == packet.input_id
                    and result.input_hash == packet.input_hash and result.status.value == 'SUCCESS'
                    and sample.instrument_id in result.instrument_ids
                    and sample.instrument_id in packet.instrument_ids
                    and bool(result.source_event_ids) and set(result.source_event_ids) <= visible_ids)
                article_refs_valid = (bool(packet.articles) and
                    {article.event_id for article in packet.articles} == set(result.source_event_ids) if result else False)
                if article_refs_valid:
                    visible_events = {event.event_id: event for event in events}
                    article_refs_valid = all(
                        _aware_ns(article.retrieved_time) is not None
                        and _aware_ns(article.retrieved_time) <= decision_cutoff
                        and article.source_id == visible_events[article.event_id].source_id
                        and article.provider_id == visible_events[article.event_id].provider_id
                        and article.headline == visible_events[article.event_id].headline
                        and article.summary == visible_events[article.event_id].summary
                        and epoch_ns_from_iso(article.published_time) == epoch_ns_from_iso(visible_events[article.event_id].published_time)
                        for article in packet.articles if article.event_id in visible_events)
                # Source timestamps and lineage must survive the news cutoff together. A model
                # output cannot smuggle excluded evidence into the historical snapshot.
                if not lineage_valid or not article_refs_valid or not times or any(_aware_ns(t) is None or _aware_ns(t) > decision_cutoff for t in times):
                    withheld_inference += 1
                    inference = None
            try:
                snapshot = build_feature_snapshot(as_of=sample.as_of, instrument_id=sample.instrument_id,
                    asset_class=sample.asset_class, events=events, market_provider=provider,
                    inference_record=inference)
                policy_decisions = [build_evaluation_decision(evaluation_run_id='REPLAY-ASOF',
                    sample_id=sample.sample_id, policy=policy, snapshot=snapshot,
                    config_hash=self._config.config_hash()).to_dict() for policy in policies]
                decisions.append({'sample_id': sample.sample_id, 'as_of': sample.as_of,
                                  'snapshot': snapshot.to_dict(), 'policy_decisions': policy_decisions})
            except EvaluationError as exc:
                gaps.append({'sample_id': sample.sample_id, 'reason': exc.code.value})
        limitations = ['SOFTWARE_FIXTURE_ONLY', 'INCOMPLETE_CURATED_MARKET_COVERAGE',
                       'FIXTURE_INSTRUMENT_SELECTION_NOT_SURVIVORSHIP_CONTROLLED',
                       'NO_FILL_OR_COST_MODEL', 'NO_REALIZED_PNL_OR_STRATEGY_EDGE_CLAIM']
        if legacy:
            limitations.append('LEGACY_MARKET_RECEIPT_TIME_UNKNOWN')
        body = {'replay_date': replay_date, 'as_of': as_of, 'timezone': 'America/New_York',
                'market_data_ref': pack.market_data_ref, 'config_hash': self._config.config_hash(),
                'simulation_only': True, 'execution_authority': False,
                'coverage': {'eligible_samples': sample_count, 'decision_samples': len(decisions),
                             'withheld_news': withheld_news, 'withheld_inference': withheld_inference},
                'decisions': decisions, 'gaps': gaps, 'limitations': limitations}
        return {**body, 'snapshot_hash': sha256_bytes(canonical_bytes(body))}

    def replay(self, *, iterations: int = 2) -> EvaluationReplayResult:
        pack = load_fixture_pack(self._fixture_path)
        hashes: list[str] = []
        report: EvaluationReport | None = None
        for _ in range(max(1, iterations)):
            evaluator = NewsStrategyEvaluator(config=self._config)
            report = evaluator.evaluate_fixture_pack(pack)
            hashes.append(report.report_hash)
        assert report is not None
        return EvaluationReplayResult(
            report=report,
            replay_count=len(hashes),
            report_hashes=tuple(hashes),
        )


__all__ = ["EvaluationReplayHarness", "EvaluationReplayResult"]
