"""Fail-closed consumption rules for historical research splits."""

from __future__ import annotations

from .types import HistoricalResearchSplitName

HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED = "HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED"


class HistoricalResearchHoldoutConsumptionError(ValueError):
    """Raised when HISTORICAL_RESEARCH_TEST is used for training or selection."""


def assert_split_consumable_for_training_or_selection(
    split: HistoricalResearchSplitName,
    *,
    purpose: str,
) -> None:
    if split == HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST:
        raise HistoricalResearchHoldoutConsumptionError(
            f"{HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED}:{purpose}"
        )


__all__ = [
    "HISTORICAL_RESEARCH_TEST_HOLDOUT_REFUSED",
    "HistoricalResearchHoldoutConsumptionError",
    "assert_split_consumable_for_training_or_selection",
]
