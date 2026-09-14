"""Pinned upstream Market Trackers contract (preparation only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class UpstreamPin:
    """Frozen third-party contract reference for audit and parser drift detection."""

    parser_repository: str
    parser_commit: str
    data_repository: str
    data_commit: str
    dataset_id: str
    export_dir: str
    schema_version: int
    parser_license: str
    data_license: str
    primary_source_authority: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_commit": self.data_commit,
            "data_license": self.data_license,
            "data_repository": self.data_repository,
            "dataset_id": self.dataset_id,
            "export_dir": self.export_dir,
            "parser_commit": self.parser_commit,
            "parser_license": self.parser_license,
            "parser_repository": self.parser_repository,
            "primary_source_authority": self.primary_source_authority,
            "schema_version": self.schema_version,
        }


# Pinned at Lane H preparation time (2026-09-14). Bump when upstream published shape changes.
UPSTREAM_PIN = UpstreamPin(
    parser_repository="https://github.com/LuxAlgo/market-trackers",
    parser_commit="9bf1045b6953e42a56f112445481d411a92261c9",
    data_repository="https://github.com/LuxAlgo/market-trackers-data",
    data_commit="64891b082072f7707cd070bc4e6795b74e871e88",
    dataset_id="insider-transactions",
    export_dir="insider/transactions",
    schema_version=2,
    parser_license="MIT (LuxAlgo/market-trackers repository LICENSE)",
    data_license="CC0-1.0 (LuxAlgo/market-trackers-data data files; see repo LICENSE)",
    primary_source_authority="SEC EDGAR ownership XML (Forms 3/4/5); Market Trackers is not primary",
)

ADAPTER_PREP_VERSION = "market_trackers.sec_insider/0.1.0-prep"
