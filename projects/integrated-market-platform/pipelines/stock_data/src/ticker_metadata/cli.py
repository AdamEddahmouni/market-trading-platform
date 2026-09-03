from __future__ import annotations

from pathlib import Path
import sys
import time

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.contract import REQUEST_CONTRACT_SHA256
from src.ticker_metadata.locking import MetadataRefreshLock
from src.ticker_metadata.models import CollectorProvenance
from src.ticker_metadata.provenance import collect_provenance
from src.ticker_metadata.provider import YFinanceMetadataAdapter
from src.ticker_metadata.runner import MetadataRunner
from src.ticker_metadata.storage import (
    MetadataBoundaryError,
    MetadataStore,
    resolve_existing_database,
)


REPORT_FIELDS = (
    "provider_symbol",
    "short_name",
    "long_name",
    "exchange_code",
    "exchange_name",
    "quote_type",
    "currency",
    "sector",
    "industry",
    "country",
    "market_cap",
)


def _failure_code(error: MetadataBoundaryError) -> int:
    if error.code == "metadata_refresh_locked":
        return 3
    if error.code == "metadata_schema_incompatible":
        return 4
    return 2


def _print_boundary_error(error: MetadataBoundaryError) -> int:
    print(f"ticker-metadata error={error.code}", file=sys.stderr)
    return _failure_code(error)


def run_refresh_ticker_metadata(
    *,
    database,
    filter_spec,
    limit: int | None,
    retry_errored: bool,
    adapter=None,
    provenance: CollectorProvenance | None = None,
    limiter=None,
) -> int:
    if database is None:
        return _print_boundary_error(
            MetadataBoundaryError(
                "database_required",
                "refresh-ticker-metadata requires --database",
            )
        )
    effective_limit = limit if limit is not None else filter_spec.limit
    if effective_limit is not None and effective_limit <= 0:
        return _print_boundary_error(
            MetadataBoundaryError("limit_invalid", "Metadata limit must be positive")
        )

    try:
        resolved = resolve_existing_database(database)
        preflight = MetadataStore.preflight(resolved)
    except MetadataBoundaryError as error:
        return _print_boundary_error(error)

    print(f"database={preflight.database_path}")
    print(
        "preflight.quick_check="
        f"{preflight.quick_check} preflight.tickers={preflight.ticker_count} "
        f"preflight.registry_columns={len(preflight.registry_columns)}"
    )
    started = time.monotonic()
    repository_root = Path(__file__).resolve().parents[4]
    run_provenance = provenance or collect_provenance(repository_root)

    try:
        with MetadataRefreshLock(resolved):
            store = MetadataStore(resolved)
            store.initialize_schema()
            selected = store.select_tickers(
                filter_spec,
                limit=effective_limit,
                retry_errored=retry_errored,
                contract_hash=REQUEST_CONTRACT_SHA256,
            )
            provider = adapter or YFinanceMetadataAdapter()
            runner = MetadataRunner(
                store,
                provider,
                run_provenance,
                limiter=limiter,
                workers=4,
            )
            report = runner.run(selected)
    except MetadataBoundaryError as error:
        return _print_boundary_error(error)

    elapsed = time.monotonic() - started
    print(f"contract_sha256={REQUEST_CONTRACT_SHA256}")
    print(
        f"collector_revision={run_provenance.collector_git_revision} "
        f"collector_dirty={str(run_provenance.collector_dirty).lower()} "
        f"provider_version={run_provenance.provider_library_version}"
    )
    print(f"filter={selected.filter_description}")
    print(
        f"selected_tickers={report.selected_tickers} skipped_tickers={report.skipped_tickers} "
        f"ticker_limit={effective_limit if effective_limit is not None else 'unbounded'} "
        "workers=4 rate_per_second=2 burst_capacity=1 max_call_ordinals=3 "
        "retry_delays_seconds=2,4"
    )
    print(
        f"calls={report.calls} retries={report.retries} "
        f"committed_attempts={report.committed_attempts} "
        f"committed_observations={report.committed_observations}"
    )
    for outcome in AcquisitionOutcome:
        print(f"outcome.{outcome.value}={report.outcome_counts.get(outcome.value, 0)}")
    for field in REPORT_FIELDS:
        present = report.field_presence_counts.get(field, 0)
        missing = report.committed_observations - present
        print(f"field.{field}.present={present} field.{field}.missing={missing}")
    print(f"circuit={report.circuit_reason or 'closed'}")
    earliest = (
        report.earliest_observation_at_utc.isoformat()
        if report.earliest_observation_at_utc
        else "none"
    )
    latest = (
        report.latest_observation_at_utc.isoformat()
        if report.latest_observation_at_utc
        else "none"
    )
    print(
        f"elapsed_seconds={elapsed:.3f} earliest_observation_at_utc={earliest} "
        f"latest_observation_at_utc={latest}"
    )
    return report.exit_code
