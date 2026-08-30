"""Fixture-backed XA-03 CFTC positioning admission helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from market_platform_foundation.cftc.contracts import InstitutionalPositioningObservation
from market_platform_foundation.cftc.datasets import CotDataset, dataset_spec
from market_platform_foundation.cftc.mapping import CotProductMapper
from market_platform_foundation.cftc.normalize import normalize_api_rows
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

from .admission import admit_positioning_observation
from .catalog import lookup_admitted_market_by_code
from .errors import Xa03Error, Xa03ErrorCode
from .registry import PositioningAdmissionRegistry, get_registry


def _xa03_fixture_root() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "xa03"


def _cftc_fixture_root() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "cftc"


def load_fixture(name: str) -> dict[str, Any]:
    path = _xa03_fixture_root() / name
    if not path.is_file():
        path = _cftc_fixture_root() / name
    if not path.is_file():
        raise Xa03Error(
            Xa03ErrorCode.INVALID_FIXTURE,
            "fixture file not found",
            {"path": str(path)},
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset_for_payload(payload: dict[str, Any]) -> CotDataset:
    family = str(payload.get("report_family", "")).upper()
    scope = str(payload.get("position_scope", "FUTURES_ONLY")).upper()
    if family == "TFF" and scope == "FUTURES_ONLY":
        return CotDataset.TFF_FUTURES_ONLY
    if family == "TFF":
        return CotDataset.TFF_COMBINED
    if family == "DISAGGREGATED" and scope == "FUTURES_ONLY":
        return CotDataset.DISAGGREGATED_FUTURES_ONLY
    if family == "DISAGGREGATED":
        return CotDataset.DISAGGREGATED_COMBINED
    if family == "LEGACY":
        return CotDataset.LEGACY_FUTURES_ONLY
    raise Xa03Error(
        Xa03ErrorCode.INVALID_FIXTURE,
        "unsupported report family in fixture",
        {"report_family": family, "position_scope": scope},
    )


def positioning_observations_from_fixture(payload: dict[str, Any]) -> list[InstitutionalPositioningObservation]:
    retrieved_time = str(payload.get("retrieved_time", "2026-08-14T19:35:00Z"))
    observed_time = str(payload.get("observed_time", retrieved_time))
    mapper = CotProductMapper()
    result: list[InstitutionalPositioningObservation] = []
    blocks = payload.get("markets") or [payload]
    for block in blocks:
        dataset = _dataset_for_payload(block)
        spec = dataset_spec(dataset)
        rows = block.get("rows") or []
        result.extend(
            normalize_api_rows(
                rows,
                spec=spec,
                mapper=mapper,
                observed_time=observed_time,
                retrieved_time=retrieved_time,
            )
        )
    return result


def positioning_observations_from_revision_fixture(payload: dict[str, Any]) -> list[tuple[InstitutionalPositioningObservation, int]]:
    """Return observations with explicit revision numbers from source_revision fixture shape."""
    base = load_fixture("tff_futures_only_es.json")
    merged = {**base, **payload}
    position_date = str(payload.get("position_date", "2026-08-11"))
    retrieved_time = str(payload.get("retrieved_time", "2026-08-14T19:35:00Z"))
    mapper = CotProductMapper()
    spec = dataset_spec(_dataset_for_payload(base))
    observations: list[tuple[InstitutionalPositioningObservation, int]] = []
    for version in payload.get("versions", []):
        row = dict(base["rows"][0])
        row["report_date_as_yyyy_mm_dd"] = position_date[:10]
        for key, value in version.items():
            if key not in {"version", "observed_time", "note"}:
                row[key] = value
        version_observed = str(version.get("observed_time", retrieved_time))
        version_number = int(version.get("version", 1))
        normalized = normalize_api_rows(
            [row],
            spec=spec,
            mapper=mapper,
            observed_time=version_observed,
            retrieved_time=version_observed,
        )
        for item in normalized:
            content_hash = sha256_bytes(
                canonical_bytes(
                    {
                        "version": version_number,
                        "long": item.long_positions,
                        "short": item.short_positions,
                    }
                )
            )
            replaced = InstitutionalPositioningObservation(
                market_id=item.market_id,
                contract_family_id=item.contract_family_id,
                cftc_contract_market_code=item.cftc_contract_market_code,
                cftc_commodity_code=item.cftc_commodity_code,
                market_and_exchange_names=item.market_and_exchange_names,
                report_family=item.report_family,
                position_scope=item.position_scope,
                participant_category=item.participant_category,
                position_date=item.position_date,
                publication_time=item.publication_time,
                available_time=item.available_time,
                observed_time=item.observed_time,
                open_interest=item.open_interest,
                long_positions=item.long_positions,
                short_positions=item.short_positions,
                spreading_positions=item.spreading_positions,
                trader_count_long=item.trader_count_long,
                trader_count_short=item.trader_count_short,
                trader_count_spreading=item.trader_count_spreading,
                source=item.source,
                source_dataset=item.source_dataset,
                source_row_id=item.source_row_id,
                content_hash=content_hash,
                quality_flags=item.quality_flags,
                provenance_ref=f"cftc.revision:{version_number}:{content_hash[:16]}",
                lifecycle=item.lifecycle,
                predictive=item.predictive,
            )
            observations.append((replaced, version_number))
    return observations


def admit_fixture(
    *,
    fixture_name: str,
    registry: PositioningAdmissionRegistry | None = None,
) -> dict[str, Any]:
    store = registry or get_registry()
    store.bootstrap_catalog()
    payload = load_fixture(fixture_name)
    retrieved_time = str(payload.get("retrieved_time", "2026-08-14T19:35:00Z"))
    admitted_ids: list[str] = []
    markets: set[str] = set()
    if fixture_name == "source_revision.json" and "versions" in payload:
        for obs, revision_number in positioning_observations_from_revision_fixture(payload):
            envelope = admit_positioning_observation(obs, retrieved_time=retrieved_time, revision_number=revision_number)
            admitted_ids.append(store.admit_observation(envelope))
            markets.add(envelope.source_subject_id)
    else:
        for obs in positioning_observations_from_fixture(payload):
            definition = lookup_admitted_market_by_code(obs.cftc_contract_market_code)
            if definition is None:
                continue
            envelope = admit_positioning_observation(obs, retrieved_time=retrieved_time)
            admitted_ids.append(store.admit_observation(envelope))
            markets.add(envelope.source_subject_id)
    return {
        "fixture": fixture_name,
        "source_classification": str(payload.get("source_classification", "FIXTURE")),
        "observation_ids": admitted_ids,
        "observation_count": len(admitted_ids),
        "market_report_ids": sorted(markets),
    }
