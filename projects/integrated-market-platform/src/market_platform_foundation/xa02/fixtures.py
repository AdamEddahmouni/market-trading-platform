"""Fixture-backed XA-02 admission helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from market_platform_foundation.fred.normalize import normalize_v1_observation_row
from market_platform_foundation.fred.pit import observations_from_v1_realtime_rows
from market_platform_foundation.fred.registry import lookup_canonical

from .admission import admit_macro_observation
from .errors import Xa02Error, Xa02ErrorCode
from .registry import AdmissionRegistry, get_registry


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "xa02"


def load_fixture(name: str) -> dict[str, Any]:
    path = _fixture_root() / name
    if not path.is_file():
        raise Xa02Error(
            Xa02ErrorCode.INVALID_FIXTURE,
            "fixture file not found",
            {"path": str(path)},
        )
    return json.loads(path.read_text(encoding="utf-8"))


def macro_observations_from_fixture(payload: dict[str, Any]) -> list:
    retrieved_time = str(payload.get("retrieved_time", ""))
    observed_time = str(payload.get("observed_time", retrieved_time))
    result = []
    for block in payload.get("series", []):
        canonical_indicator_id = str(block["canonical_indicator_id"])
        entry = lookup_canonical(canonical_indicator_id)
        if entry is None:
            raise Xa02Error(
                Xa02ErrorCode.INVALID_FIXTURE,
                "unknown canonical indicator in fixture",
                {"canonical_indicator_id": canonical_indicator_id},
            )
        rows = block.get("rows") or block.get("observations") or []
        if block.get("mode") == "v1_realtime_sequence":
            result.extend(
                observations_from_v1_realtime_rows(
                    rows,
                    canonical_indicator_id=canonical_indicator_id,
                    series_id=entry.fred_series_id,
                    retrieved_time=retrieved_time,
                )
            )
            continue
        for row in rows:
            result.append(
                normalize_v1_observation_row(
                    row,
                    entry=entry,
                    retrieved_time=retrieved_time,
                    observed_time=str(row.get("provider_first_observed_time", observed_time)),
                )
            )
    return result


def admit_fixture(
    *,
    fixture_name: str,
    registry: AdmissionRegistry | None = None,
) -> dict[str, Any]:
    store = registry or get_registry()
    store.bootstrap_catalog()
    payload = load_fixture(fixture_name)
    macro_observations = macro_observations_from_fixture(payload)
    admitted_ids: list[str] = []
    for macro_obs in macro_observations:
        admitted = admit_macro_observation(macro_obs)
        admitted_ids.append(store.admit_observation(admitted))
    indicators = sorted({item.canonical_indicator_id for item in macro_observations})
    return {
        "fixture": fixture_name,
        "source_classification": str(payload.get("source_classification", "FIXTURE")),
        "observation_ids": admitted_ids,
        "observation_count": len(admitted_ids),
        "indicators": indicators,
    }
