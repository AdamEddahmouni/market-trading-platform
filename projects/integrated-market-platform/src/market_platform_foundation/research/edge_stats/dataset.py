"""Admitted BIYA bar source resolution and byte verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...adapters.equity_intraday_jsonl import (
    COLLECTION_RELATIVE_PATH,
    PINNED_SHA256,
    SOURCE_OBJECT_ID,
    EquityIntradayJsonlAdapter,
)
from ..decision_research.examples import REPO_ROOT, load_biya_bars


@dataclass(frozen=True, slots=True)
class AdmittedBarDataset:
    source_object_id: str
    source_sha256: str
    collection_relative_path: str
    bar_count: int


def resolve_bar_source_path(repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    return root.parent / COLLECTION_RELATIVE_PATH


def verify_and_load_biya_bars(
    *,
    bar_source: Path | None = None,
    ingest_run_id: str = "edge-stats-offline",
) -> tuple[list[dict[str, Any]], AdmittedBarDataset]:
    path = bar_source or resolve_bar_source_path()
    adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
    reasons = adapter.verify_source_bytes(path)
    if reasons:
        raise ValueError(f"ADMITTED_SOURCE_VERIFICATION_FAILED:{','.join(reasons)}")
    bars = load_biya_bars(path)
    dataset = AdmittedBarDataset(
        source_object_id=SOURCE_OBJECT_ID,
        source_sha256=PINNED_SHA256,
        collection_relative_path=COLLECTION_RELATIVE_PATH,
        bar_count=len(bars),
    )
    return bars, dataset
