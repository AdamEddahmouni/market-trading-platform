"""Policy-driven recency filter."""

from __future__ import annotations

from ..contracts import FilterDecision, FilterStage, NewsArticleEvent, PipelineConfig, PublicationTimeQuality
from ..timestamps import age_seconds_at, epoch_ns_from_iso


class RecencyFilter:
    STAGE = FilterStage.RECENCY

    def evaluate(
        self,
        event: NewsArticleEvent,
        *,
        as_of_ns: int,
        config: PipelineConfig,
    ) -> FilterDecision:
        published_ns = epoch_ns_from_iso(event.published_time)
        if published_ns is not None and published_ns > as_of_ns + config.recency_reject_future_seconds * 1_000_000_000:
            return FilterDecision(
                stage=self.STAGE,
                accepted=False,
                reason_code="RECENCY_FUTURE_PUBLICATION",
                detail="Publication time is after evaluation time",
                policy_version=config.filter_chain_version,
            )
        if event.published_time_quality == PublicationTimeQuality.UNKNOWN:
            if config.recency_unknown_publication_policy == "REJECT":
                return FilterDecision(
                    stage=self.STAGE,
                    accepted=False,
                    reason_code="RECENCY_UNKNOWN_PUBLICATION",
                    detail="Publication time unknown and policy rejects",
                    policy_version=config.filter_chain_version,
                )
        age = age_seconds_at(event, as_of_ns)
        if age is None:
            return FilterDecision(
                stage=self.STAGE,
                accepted=False,
                reason_code="RECENCY_AGE_UNKNOWN",
                detail="Cannot compute event age",
                policy_version=config.filter_chain_version,
            )
        if age > config.recency_max_age_seconds:
            return FilterDecision(
                stage=self.STAGE,
                accepted=False,
                reason_code="RECENCY_EXCEEDS_TTL",
                detail=f"Age {age}s exceeds max {config.recency_max_age_seconds}s",
                policy_version=config.filter_chain_version,
                event_age_seconds=age,
            )
        basis = "PUBLISHED_TIME"
        if event.published_time_quality == PublicationTimeQuality.UNKNOWN:
            basis = "RETRIEVED_TIME_AGE_PROXY"
        return FilterDecision(
            stage=self.STAGE,
            accepted=True,
            reason_code="RECENCY_ACCEPTED",
            detail=f"Age computed from {basis}",
            policy_version=config.filter_chain_version,
            event_age_seconds=age,
        )


__all__ = ["RecencyFilter"]
