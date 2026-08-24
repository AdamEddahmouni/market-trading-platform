from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from src.acquisition import AcquisitionOutcome


@dataclass(frozen=True)
class TickerRef:
    raw_ticker_id: int
    requested_symbol: str


@dataclass(frozen=True)
class ClassifiedResult:
    outcome: AcquisitionOutcome
    reason_code: str
    detail: str | None = None
    projected: Mapping[str, str | int] = None  # type: ignore[assignment]
    observed_fields: tuple[str, ...] = ()
    observed_provider_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.projected is None:
            object.__setattr__(self, "projected", {})


@dataclass(frozen=True)
class PreflightSummary:
    database_path: Path
    quick_check: str
    ticker_count: int
    registry_columns: tuple[str, ...]


@dataclass(frozen=True)
class AttemptRecord:
    run_id: str
    raw_ticker_id: int
    requested_symbol: str
    provider: str
    method: str
    request_contract_json: str
    request_contract_version: str
    request_contract_sha256: str
    retry_ordinal: int
    started_at_utc: datetime
    completed_at_utc: datetime
    requested_fields: tuple[str, ...]
    observed_fields: tuple[str, ...]
    outcome: AcquisitionOutcome
    reason_code: str
    detail: str | None
    collector_git_revision: str
    collector_dirty: bool
    python_version: str
    provider_library_name: str
    provider_library_version: str


@dataclass(frozen=True)
class ObservationRecord:
    run_id: str
    raw_ticker_id: int
    requested_symbol: str
    provider: str
    method: str
    request_contract_json: str
    request_contract_version: str
    request_contract_sha256: str
    provider_observed_at_utc: datetime
    projected: Mapping[str, str | int]
    present_fields: tuple[str, ...]
    collector_git_revision: str
    collector_dirty: bool
    python_version: str
    provider_library_name: str
    provider_library_version: str


@dataclass(frozen=True)
class WriteReceipt:
    attempt_id: int
    observation_id: int | None


@dataclass(frozen=True)
class Selection:
    tickers: tuple[TickerRef, ...]
    skipped_terminal: int
    filter_description: str


@dataclass(frozen=True)
class ProviderCallResult:
    ordinal: int
    started_at_utc: datetime
    completed_at_utc: datetime
    classified: ClassifiedResult


@dataclass(frozen=True)
class CollectorProvenance:
    collector_git_revision: str
    collector_dirty: bool
    python_version: str
    provider_library_name: str
    provider_library_version: str


@dataclass(frozen=True)
class RunReport:
    run_id: str
    selected_tickers: int
    skipped_tickers: int
    calls: int
    retries: int
    committed_attempts: int
    committed_observations: int
    outcome_counts: Mapping[str, int]
    field_presence_counts: Mapping[str, int]
    earliest_observation_at_utc: datetime | None
    latest_observation_at_utc: datetime | None
    circuit_reason: str | None
    exit_code: int
