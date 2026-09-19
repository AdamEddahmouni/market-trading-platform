"""Evidence context for IBP facts SUT from Lane B historical development fixtures."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from ...assistant.context_assembler import build_evidence_context
from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import sort_events
from ...market_data.historical_development import build_historical_rth_dataset
from ...market_data.historical_development.e2e_demo import normalized_bars_to_replay_events
from ...market_data.historical_development.provider import (
    FixtureHistoricalMarketDataProvider,
    load_fixture_rows_from_json,
)
from ...risk_simulation.evaluation import run_risk_simulation_evaluation
from ...strategy.evaluation import run_strategy_evaluation
from ...ui_api.store import ReplayStore

_INGEST_RUN_PREFIX = "IBP-FACTS-SUT"


def _fixture_session_params(rows_by_day: dict[str, tuple[dict[str, Any], ...]]) -> tuple[str, str, str]:
    days = sorted(rows_by_day.keys())
    if not days:
        raise ValueError("HISTORICAL_FIXTURE_EMPTY")
    first_row = rows_by_day[days[0]][0]
    code = str(first_row.get("code") or first_row.get("instrument_id") or "US.AAPL")
    instrument = code.split(".")[-1] if "." in code else code
    return instrument, days[0], days[-1]


def _normalized_bars_from_build(build: Any) -> list[dict[str, Any]]:
    normalized_path = build.paths.normalized_dir
    json_files = sorted(normalized_path.glob("*_normalized.json"))
    if not json_files:
        raise ValueError("NORMALIZED_ARTIFACT_MISSING")
    bars = json.loads(json_files[0].read_text(encoding="utf-8"))
    if not isinstance(bars, list) or not bars:
        raise ValueError("NORMALIZED_BARS_EMPTY")
    return [row for row in bars if isinstance(row, dict)]


def _decoded_replay_snapshot_from_bars(
    bars: list[dict[str, Any]],
    *,
    normalized_fingerprint: str,
) -> dict[str, Any]:
    ingest_run_id = f"{_INGEST_RUN_PREFIX}-{normalized_fingerprint[:12]}"
    events = sort_events(normalized_bars_to_replay_events(bars, ingest_run_id=ingest_run_id))
    if not events:
        raise ValueError("REPLAY_EVENTS_EMPTY")
    instrument_id = str(events[0]["instrument_id"])
    session_id = sha256_bytes(
        canonical_bytes(
            {
                "instrument_id": instrument_id,
                "ingest_run_id": ingest_run_id,
                "bar_count": len(events),
                "authority": "HISTORICAL_DEVELOPMENT",
            }
        )
    )
    return {
        "evaluation": run_risk_simulation_evaluation(events),
        "events": events,
        "instrument_id": instrument_id,
        "session_id": session_id,
        "strategy": run_strategy_evaluation(events),
    }


def _replay_store_for_fixture(repository_root: Path, fixture_path: Path) -> ReplayStore | None:
    try:
        rows_by_day = load_fixture_rows_from_json(fixture_path)
        instrument, start_date, end_date = _fixture_session_params(rows_by_day)
        provider = FixtureHistoricalMarketDataProvider(rows_by_day)
        with tempfile.TemporaryDirectory() as tmp:
            build = build_historical_rth_dataset(
                repository_root=repository_root,
                provider=provider,
                instrument=instrument,
                start_date=start_date,
                end_date=end_date,
                artifact_root=Path(tmp) / "corpus",
                fixture_only=True,
            )
            if not build.ok or not build.normalized_fingerprint:
                return None
            bars = _normalized_bars_from_build(build)
            decoded = _decoded_replay_snapshot_from_bars(
                bars,
                normalized_fingerprint=str(build.normalized_fingerprint),
            )
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    store = ReplayStore(collection_root=repository_root, data_mode="FIXTURE_REPLAY", mode="REPLAY")
    store.load_decoded_snapshot(decoded)
    return store


def build_historical_fixture_evidence_context(
    repository_root: Path,
    fixture_rel: str | None,
    *,
    selection_ref: str | None = "explain:quality:system",
) -> dict[str, Any] | None:
    """Assemble MRA-001-style evidence context from a historical development fixture path."""
    if not fixture_rel:
        return None
    fixture_path = repository_root / fixture_rel
    if not fixture_path.is_file():
        return None
    store = _replay_store_for_fixture(repository_root, fixture_path)
    if store is None:
        return None
    context = build_evidence_context(store, selection_ref=selection_ref)
    context["historical_fixture_path"] = fixture_rel
    context["evidence_authority"] = "HISTORICAL_DEVELOPMENT"
    return context


__all__ = ["build_historical_fixture_evidence_context"]
