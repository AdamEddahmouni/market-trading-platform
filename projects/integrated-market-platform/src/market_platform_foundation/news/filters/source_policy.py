"""Source-trust policy filter."""

from __future__ import annotations

from ..contracts import FilterDecision, FilterStage, NewsArticleEvent, PipelineConfig
from ..sources import SourceTrustCatalog


class SourcePolicyFilter:
    STAGE = FilterStage.SOURCE_POLICY

    def __init__(self, catalog: SourceTrustCatalog | None = None) -> None:
        self._catalog = catalog or SourceTrustCatalog()

    def evaluate(
        self,
        event: NewsArticleEvent,
        *,
        config: PipelineConfig,
    ) -> FilterDecision:
        entry = self._catalog.resolve_for_event(
            source_id=event.source_id,
            publisher_source=event.publisher_source,
        )
        trusted, reason = self._catalog.is_trusted(
            entry,
            enabled_source_ids=config.enabled_source_ids,
        )
        if not trusted:
            return FilterDecision(
                stage=self.STAGE,
                accepted=False,
                reason_code=reason,
                detail=f"source_id={event.source_id}",
                policy_version=config.source_policy_version,
            )
        return FilterDecision(
            stage=self.STAGE,
            accepted=True,
            reason_code="SOURCE_ACCEPTED",
            detail=entry.source_id if entry else "",
            policy_version=config.source_policy_version,
        )


__all__ = ["SourcePolicyFilter"]
