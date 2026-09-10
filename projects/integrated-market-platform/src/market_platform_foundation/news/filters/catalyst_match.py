"""Catalyst keyword relevance filter."""

from __future__ import annotations

from ..catalysts import CatalystRegistry
from ..contracts import FilterDecision, FilterStage, NewsArticleEvent, PipelineConfig


class CatalystKeywordFilter:
    STAGE = FilterStage.CATALYST_KEYWORD

    def __init__(self, registry: CatalystRegistry | None = None) -> None:
        self._registry = registry or CatalystRegistry()

    def evaluate(
        self,
        event: NewsArticleEvent,
        *,
        config: PipelineConfig,
    ) -> FilterDecision:
        asset_classes = tuple(
            dict.fromkeys(link.asset_class for link in event.instrument_linkages if link.asset_class)
        )
        text = " ".join([event.headline, event.summary]).strip()
        matched = self._registry.match(
            text,
            enabled_catalyst_ids=config.enabled_catalyst_ids,
            asset_classes=asset_classes,
        )
        if config.require_catalyst_match and not matched:
            return FilterDecision(
                stage=self.STAGE,
                accepted=False,
                reason_code="CATALYST_NO_MATCH",
                detail="No enabled catalyst keyword matched",
                policy_version=config.catalyst_registry_version,
            )
        return FilterDecision(
            stage=self.STAGE,
            accepted=True,
            reason_code="CATALYST_MATCHED",
            detail=",".join(matched),
            matched_catalyst_ids=matched,
            policy_version=config.catalyst_registry_version,
        )


__all__ = ["CatalystKeywordFilter"]
