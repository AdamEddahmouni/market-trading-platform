"""Official CFTC Public Reporting dataset identifiers and scope semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import CotPositionScope, CotReportFamily


class CotDataset(StrEnum):
    """Observed official Socrata dataset IDs — filtered views preferred over All."""

    LEGACY_FUTURES_ONLY = "6dca-aqww"
    LEGACY_COMBINED = "jun7-fc8e"
    DISAGGREGATED_FUTURES_ONLY = "72hh-3qpy"
    DISAGGREGATED_COMBINED = "kh3c-gbw2"
    TFF_FUTURES_ONLY = "gpe5-46if"
    TFF_COMBINED = "yw9f-hn96"
    SUPPLEMENTAL_CIT = "4zgm-a668"
    PRODUCT_HIERARCHY = "rj6x-va3z"


# Documented All datasets that contain BOTH scopes — mandatory filter required.
COT_ALL_DATASETS: frozenset[str] = frozenset(
    {
        "gpe5-46if",  # TFF_All equivalent warning in docs — filtered IDs used
    }
)


@dataclass(frozen=True, slots=True)
class CotDatasetSpec:
    dataset_id: str
    report_family: CotReportFamily
    position_scope: CotPositionScope
    label: str


DATASET_SPECS: dict[CotDataset, CotDatasetSpec] = {
    CotDataset.LEGACY_FUTURES_ONLY: CotDatasetSpec(
        dataset_id=CotDataset.LEGACY_FUTURES_ONLY.value,
        report_family=CotReportFamily.LEGACY,
        position_scope=CotPositionScope.FUTURES_ONLY,
        label="Legacy Futures Only",
    ),
    CotDataset.LEGACY_COMBINED: CotDatasetSpec(
        dataset_id=CotDataset.LEGACY_COMBINED.value,
        report_family=CotReportFamily.LEGACY,
        position_scope=CotPositionScope.FUTURES_AND_OPTIONS_COMBINED,
        label="Legacy Combined",
    ),
    CotDataset.DISAGGREGATED_FUTURES_ONLY: CotDatasetSpec(
        dataset_id=CotDataset.DISAGGREGATED_FUTURES_ONLY.value,
        report_family=CotReportFamily.DISAGGREGATED,
        position_scope=CotPositionScope.FUTURES_ONLY,
        label="Disaggregated Futures Only",
    ),
    CotDataset.DISAGGREGATED_COMBINED: CotDatasetSpec(
        dataset_id=CotDataset.DISAGGREGATED_COMBINED.value,
        report_family=CotReportFamily.DISAGGREGATED,
        position_scope=CotPositionScope.FUTURES_AND_OPTIONS_COMBINED,
        label="Disaggregated Combined",
    ),
    CotDataset.TFF_FUTURES_ONLY: CotDatasetSpec(
        dataset_id=CotDataset.TFF_FUTURES_ONLY.value,
        report_family=CotReportFamily.TFF,
        position_scope=CotPositionScope.FUTURES_ONLY,
        label="TFF Futures Only",
    ),
    CotDataset.TFF_COMBINED: CotDatasetSpec(
        dataset_id=CotDataset.TFF_COMBINED.value,
        report_family=CotReportFamily.TFF,
        position_scope=CotPositionScope.FUTURES_AND_OPTIONS_COMBINED,
        label="TFF Combined",
    ),
    CotDataset.SUPPLEMENTAL_CIT: CotDatasetSpec(
        dataset_id=CotDataset.SUPPLEMENTAL_CIT.value,
        report_family=CotReportFamily.SUPPLEMENTAL_CIT,
        position_scope=CotPositionScope.FUTURES_ONLY,
        label="Supplemental Commodity Index Trader",
    ),
}


def dataset_spec(dataset: CotDataset) -> CotDatasetSpec:
    return DATASET_SPECS[dataset]


def require_position_scope(
    scope: CotPositionScope | None,
    *,
    context: str = "",
) -> CotPositionScope:
    """Fail closed when scope is ambiguous — prevents All-dataset double counting."""
    if scope is None:
        raise ValueError(f"REPORT_SCOPE_AMBIGUOUS{': ' + context if context else ''}")
    return scope


__all__ = [
    "COT_ALL_DATASETS",
    "CotDataset",
    "CotDatasetSpec",
    "DATASET_SPECS",
    "dataset_spec",
    "require_position_scope",
]
