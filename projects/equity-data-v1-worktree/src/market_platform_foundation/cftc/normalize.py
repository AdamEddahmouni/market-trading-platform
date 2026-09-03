"""Normalize CFTC COT rows into canonical institutional positioning observations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .contracts import CotParticipantCategory, CotPositionScope, CotReportFamily, InstitutionalPositioningObservation
from .datasets import CotDatasetSpec, require_position_scope
from .mapping import CotProductMapper
from .parser import CotParsedReport, parse_cot_row
from .quality import CotQualityFlag
from .release_schedule import publication_time_utc, release_for_position_date


def _position_date_iso(position_date: str) -> str:
    return f"{position_date[:10]}T00:00:00.000000000Z"


def resolve_publication_time(
    position_date: str,
    *,
    observed_time: str,
    historical_backfill: bool = False,
) -> tuple[str, tuple[str, ...]]:
    flags: list[str] = []
    try:
        pos = date.fromisoformat(position_date[:10])
    except ValueError:
        flags.append(CotQualityFlag.PUBLICATION_TIME_INFERRED.value)
        return observed_time, tuple(flags)

    release = release_for_position_date(pos)
    if release:
        return publication_time_utc(release.publication_date), tuple(flags)

    if historical_backfill:
        flags.append(CotQualityFlag.HISTORICAL_PUBLICATION_TIME_INFERRED.value)
        # Conservative: assume Friday 15:30 ET three days after Tuesday
        from datetime import timedelta

        pub = pos + timedelta(days=3)
        return publication_time_utc(pub), tuple(flags)

    flags.append(CotQualityFlag.PUBLICATION_TIME_INFERRED.value)
    return observed_time, tuple(flags)


def normalize_parsed_report(
    parsed: CotParsedReport,
    *,
    spec: CotDatasetSpec,
    mapper: CotProductMapper,
    observed_time: str,
    retrieved_time: str,
    historical_backfill: bool = False,
) -> tuple[InstitutionalPositioningObservation, ...]:
    scope = require_position_scope(spec.position_scope, context=spec.label)
    mapping = mapper.resolve(
        cftc_contract_market_code=parsed.cftc_contract_market_code,
        market_and_exchange_names=parsed.market_and_exchange_names,
    )
    quality: list[str] = []
    if not mapping.resolved:
        quality.append(CotQualityFlag.PRODUCT_MAPPING_UNRESOLVED.value)

    publication_time, pub_flags = resolve_publication_time(
        parsed.position_date,
        observed_time=observed_time,
        historical_backfill=historical_backfill,
    )
    quality.extend(pub_flags)
    available_time = publication_time
    market_id = f"cftc:{parsed.cftc_contract_market_code}:{parsed.position_date}"
    contract_family_id = mapping.contract_family_id or f"UNRESOLVED:{parsed.cftc_contract_market_code}"

    observations: list[InstitutionalPositioningObservation] = []
    for category_row in parsed.categories:
        content_hash = sha256_bytes(
            canonical_bytes(
                {
                    "position_date": parsed.position_date,
                    "code": parsed.cftc_contract_market_code,
                    "category": category_row.participant_category.value,
                    "scope": scope.value,
                    "family": spec.report_family.value,
                    "long": category_row.long_positions,
                    "short": category_row.short_positions,
                }
            )
        )
        observations.append(
            InstitutionalPositioningObservation(
                market_id=market_id,
                contract_family_id=contract_family_id,
                cftc_contract_market_code=parsed.cftc_contract_market_code,
                cftc_commodity_code=parsed.cftc_commodity_code,
                market_and_exchange_names=parsed.market_and_exchange_names,
                report_family=spec.report_family,
                position_scope=scope,
                participant_category=category_row.participant_category,
                position_date=_position_date_iso(parsed.position_date),
                publication_time=publication_time,
                available_time=available_time,
                observed_time=observed_time,
                open_interest=parsed.open_interest,
                long_positions=category_row.long_positions,
                short_positions=category_row.short_positions,
                spreading_positions=category_row.spreading_positions,
                trader_count_long=category_row.trader_count_long,
                trader_count_short=category_row.trader_count_short,
                trader_count_spreading=category_row.trader_count_spreading,
                source="cftc_cot",
                source_dataset=spec.dataset_id,
                source_row_id=parsed.source_row_id,
                content_hash=content_hash,
                quality_flags=tuple(dict.fromkeys(quality)),
                provenance_ref=f"cftc.observed:{content_hash[:16]}",
                lifecycle="OBSERVED",
                predictive=False,
            )
        )
    return tuple(observations)


def normalize_api_rows(
    rows: list[dict[str, Any]],
    *,
    spec: CotDatasetSpec,
    mapper: CotProductMapper,
    observed_time: str,
    retrieved_time: str,
    historical_backfill: bool = False,
) -> tuple[InstitutionalPositioningObservation, ...]:
    observations: list[InstitutionalPositioningObservation] = []
    for row in rows:
        parsed = parse_cot_row(row, spec=spec)
        observations.extend(
            normalize_parsed_report(
                parsed,
                spec=spec,
                mapper=mapper,
                observed_time=observed_time,
                retrieved_time=retrieved_time,
                historical_backfill=historical_backfill,
            )
        )
    return tuple(observations)


def to_futures_positioning_report(
    obs: InstitutionalPositioningObservation,
) -> dict[str, Any]:
    """Bridge to existing F4 positioning engine report shape."""
    net = None
    if obs.long_positions is not None and obs.short_positions is not None:
        net = obs.long_positions - obs.short_positions
    report_type = f"{obs.report_family.value.lower()}_{obs.position_scope.value.lower()}"
    return {
        "instrument_family": obs.contract_family_id,
        "contract_family_id": obs.contract_family_id,
        "market_id": obs.market_id,
        "report_type": report_type,
        "report_family": obs.report_family.value,
        "position_scope": obs.position_scope.value,
        "participant_category": obs.participant_category.value.lower(),
        "long_positions": obs.long_positions,
        "short_positions": obs.short_positions,
        "spreading": obs.spreading_positions,
        "net": net,
        "open_interest": obs.open_interest,
        "observation_time": obs.position_date,
        "publication_time": obs.publication_time,
        "available_time": obs.available_time,
        "observed_time": obs.observed_time,
        "quality_flags": list(obs.quality_flags),
        "provenance_ref": obs.provenance_ref,
        "source_dataset": obs.source_dataset,
        "predictive": False,
        "is_contract_family_level": True,
        "is_specific_expiration": False,
    }


def filter_scope_rows(
    rows: list[dict[str, Any]],
    required_scope: CotPositionScope,
) -> list[dict[str, Any]]:
    """Filter All-dataset rows to prevent futures-only + combined double counting."""
    from .parser import detect_scope_in_row

    filtered: list[dict[str, Any]] = []
    for row in rows:
        detected = detect_scope_in_row(row)
        if detected is None:
            filtered.append(row)
            continue
        normalized = detected.upper().replace(" ", "")
        if required_scope == CotPositionScope.FUTURES_ONLY and normalized in {"FUTONLY", "FUTURES_ONLY", "FO"}:
            filtered.append(row)
        elif required_scope == CotPositionScope.FUTURES_AND_OPTIONS_COMBINED and normalized in {
            "COMBINED",
            "FUTURES_AND_OPTIONS_COMBINED",
            "FC",
        }:
            filtered.append(row)
    return filtered


__all__ = [
    "filter_scope_rows",
    "normalize_api_rows",
    "normalize_parsed_report",
    "resolve_publication_time",
    "to_futures_positioning_report",
]
