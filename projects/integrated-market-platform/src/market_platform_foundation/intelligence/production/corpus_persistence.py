"""Read-only loaders for governed intelligence persistence (Item 7 Lane D).

Hydrates an in-memory ``IntelligenceRepository`` from operator-local JSONL,
Path A forecast directories, and optional MongoDB. Never mutates source files.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..contracts.forecast import ForecastV1, forecast_v1_from_dict
from ..contracts.outcome import OutcomeV1, outcome_v1_from_dict
from ..contracts.signal import SignalV1, signal_v1_from_dict
from ..contracts.snapshot import SnapshotV1, snapshot_v1_from_dict
from ..contracts.prediction_ledger import (
    PredictionLedgerEntryV1,
    prediction_ledger_entry_v1_from_dict,
)
from ..persistence import InMemoryIntelligenceRepository
from ..persistence.repository import IntelligenceRepository

_RECORD_LOADERS: dict[str, Any] = {
    "forecast": (forecast_v1_from_dict, "put_forecast", "forecast_id"),
    "outcome": (outcome_v1_from_dict, "put_outcome", "outcome_id"),
    "snapshot": (snapshot_v1_from_dict, "put_snapshot", "snapshot_id"),
    "signal": (signal_v1_from_dict, "put_signal", "signal_id"),
    "prediction_ledger_entry": (
        prediction_ledger_entry_v1_from_dict,
        "put_prediction_ledger_entry",
        "ledger_entry_id",
    ),
}

DEFAULT_INTELLIGENCE_JSONL_RELATIVE = (
    "intelligence/intelligence_records.jsonl",
    "intelligence_records.jsonl",
    "path-a/intelligence_records.jsonl",
)

DEFAULT_FORECAST_DIR_RELATIVE = (
    "path-a/forecasts",
    "path-a/production/forecasts",
    "forecasts/path-a",
)


@dataclass(frozen=True, slots=True)
class GovernedPersistenceSource:
    """One governed persistence input (read-only)."""

    kind: str
    path: str
    records_loaded: int = 0
    parse_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "records_loaded": self.records_loaded,
            "parse_errors": self.parse_errors,
        }


@dataclass(frozen=True, slots=True)
class GovernedPersistenceLoadReport:
    persistence_root: str | None
    sources: tuple[GovernedPersistenceSource, ...] = ()
    forecasts: int = 0
    outcomes: int = 0
    snapshots: int = 0
    signals: int = 0
    prediction_ledger_entries: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": "item7_governed_persistence_load_report_v1",
            "persistence_root": self.persistence_root,
            "counts": {
                "forecasts": self.forecasts,
                "outcomes": self.outcomes,
                "snapshots": self.snapshots,
                "signals": self.signals,
                "prediction_ledger_entries": self.prediction_ledger_entries,
            },
            "sources": [source.to_dict() for source in self.sources],
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class GovernedPersistenceLoadOptions:
    persistence_root: Path | None = None
    intelligence_jsonl_paths: tuple[Path, ...] = ()
    forecast_dirs: tuple[Path, ...] = ()
    use_mongo_if_configured: bool = False


def resolve_persistence_root(explicit: Path | str | None = None) -> Path | None:
    if explicit is not None and str(explicit).strip():
        path = Path(explicit).expanduser().resolve()
        return path if path.is_dir() else None
    env = os.environ.get("IMP_STATE_DIR", "").strip()
    if env:
        path = Path(env).expanduser().resolve()
        return path if path.is_dir() else None
    return None


def discover_governed_persistence_paths(root: Path) -> GovernedPersistenceLoadOptions:
    jsonl_paths: list[Path] = []
    for relative in DEFAULT_INTELLIGENCE_JSONL_RELATIVE:
        candidate = root / relative
        if candidate.is_file():
            jsonl_paths.append(candidate.resolve())
    forecast_dirs: list[Path] = []
    for relative in DEFAULT_FORECAST_DIR_RELATIVE:
        candidate = root / relative
        if candidate.is_dir():
            forecast_dirs.append(candidate.resolve())
    return GovernedPersistenceLoadOptions(
        persistence_root=root.resolve(),
        intelligence_jsonl_paths=tuple(jsonl_paths),
        forecast_dirs=tuple(forecast_dirs),
    )


def _load_intelligence_jsonl(
    path: Path,
    repository: IntelligenceRepository,
    *,
    seen: dict[str, set[str]],
) -> GovernedPersistenceSource:
    loaded = 0
    errors = 0
    if not path.is_file():
        return GovernedPersistenceSource(kind="intelligence_jsonl", path=str(path))
    for line_index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        if not isinstance(row, dict):
            errors += 1
            continue
        record_type = str(row.get("record_type") or "")
        payload = row.get("payload")
        if not record_type or not isinstance(payload, dict):
            errors += 1
            continue
        spec = _RECORD_LOADERS.get(record_type)
        if spec is None:
            continue
        from_dict, put_name, id_field = spec
        try:
            record = from_dict(payload)
        except (TypeError, ValueError, KeyError):
            errors += 1
            continue
        record_id = str(getattr(record, id_field))
        bucket = seen.setdefault(record_type, set())
        if record_id in bucket:
            continue
        bucket.add(record_id)
        put = getattr(repository, put_name)
        put(record)
        loaded += 1
    return GovernedPersistenceSource(
        kind="intelligence_jsonl",
        path=str(path),
        records_loaded=loaded,
        parse_errors=errors,
    )


def _load_forecast_dir(path: Path, repository: IntelligenceRepository, *, seen: set[str]) -> GovernedPersistenceSource:
    from ...strategy.path_a_forecast_store import load_paper_demo_forecasts

    loaded = 0
    if not path.is_dir():
        return GovernedPersistenceSource(kind="forecast_dir", path=str(path))
    for forecast in load_paper_demo_forecasts(path):
        forecast_id = str(forecast.forecast_id)
        if forecast_id in seen:
            continue
        seen.add(forecast_id)
        repository.put_forecast(forecast)
        loaded += 1
    return GovernedPersistenceSource(kind="forecast_dir", path=str(path), records_loaded=loaded)


def _count_repository(repository: IntelligenceRepository) -> dict[str, int]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return {
            "forecasts": 0,
            "outcomes": 0,
            "snapshots": 0,
            "signals": 0,
            "prediction_ledger_entries": 0,
        }
    return {
        "forecasts": len(stores.get("forecasts") or {}),
        "outcomes": len(stores.get("outcomes") or {}),
        "snapshots": len(stores.get("snapshots") or {}),
        "signals": len(stores.get("signals") or {}),
        "prediction_ledger_entries": len(stores.get("prediction_ledger") or {}),
    }


def try_load_mongo_repository() -> IntelligenceRepository | None:
    uri = os.environ.get("IMP_MONGODB_URI", "").strip()
    if not uri:
        return None
    try:
        from ..persistence.mongo import MongoIntelligenceRepository, MongoRepositoryConfig

        config = MongoRepositoryConfig.from_env()
        return MongoIntelligenceRepository(config)
    except (ImportError, ValueError, OSError):
        return None


def load_governed_intelligence_repository(
    options: GovernedPersistenceLoadOptions | None = None,
    *,
    persistence_root: Path | None = None,
    intelligence_jsonl: Iterable[Path] = (),
    forecast_dir: Iterable[Path] = (),
    use_mongo_if_configured: bool = False,
) -> tuple[IntelligenceRepository, GovernedPersistenceLoadReport]:
    """Hydrate a repository for corpus collection (read-only on disk sources)."""

    if options is None:
        root = persistence_root or resolve_persistence_root()
        discovered = discover_governed_persistence_paths(root) if root is not None else GovernedPersistenceLoadOptions()
        jsonl_paths = tuple(intelligence_jsonl) or discovered.intelligence_jsonl_paths
        forecast_dirs = tuple(forecast_dir) or discovered.forecast_dirs
        options = GovernedPersistenceLoadOptions(
            persistence_root=root,
            intelligence_jsonl_paths=jsonl_paths,
            forecast_dirs=forecast_dirs,
            use_mongo_if_configured=use_mongo_if_configured,
        )

    notes: list[str] = []
    sources: list[GovernedPersistenceSource] = []
    if options.use_mongo_if_configured:
        mongo_repo = try_load_mongo_repository()
        if mongo_repo is not None:
            counts = _count_repository(mongo_repo)
            return mongo_repo, GovernedPersistenceLoadReport(
                persistence_root=str(options.persistence_root) if options.persistence_root else None,
                sources=(
                    GovernedPersistenceSource(
                        kind="mongodb",
                        path="IMP_MONGODB_URI",
                        records_loaded=sum(counts.values()),
                    ),
                ),
                forecasts=counts["forecasts"],
                outcomes=counts["outcomes"],
                snapshots=counts["snapshots"],
                signals=counts["signals"],
                prediction_ledger_entries=counts["prediction_ledger_entries"],
                notes=("MongoDB read-only query surface; source files not mutated.",),
            )
        notes.append("IMP_MONGODB_URI configured but Mongo repository unavailable.")

    repository: IntelligenceRepository = InMemoryIntelligenceRepository()
    seen_by_type: dict[str, set[str]] = {}
    forecast_seen: set[str] = set()
    for path in options.intelligence_jsonl_paths:
        sources.append(_load_intelligence_jsonl(path, repository, seen=seen_by_type))
    for path in options.forecast_dirs:
        sources.append(_load_forecast_dir(path, repository, seen=forecast_seen))

    counts = _count_repository(repository)
    if not sources and options.persistence_root is not None:
        notes.append("No governed intelligence JSONL or forecast directories discovered under persistence root.")
    if not sources and options.persistence_root is None:
        notes.append("No persistence root; repository remains empty unless caller supplies in-memory data.")

    return repository, GovernedPersistenceLoadReport(
        persistence_root=str(options.persistence_root) if options.persistence_root else None,
        sources=tuple(sources),
        forecasts=counts["forecasts"],
        outcomes=counts["outcomes"],
        snapshots=counts["snapshots"],
        signals=counts["signals"],
        prediction_ledger_entries=counts["prediction_ledger_entries"],
        notes=tuple(notes),
    )


__all__ = [
    "GovernedPersistenceLoadOptions",
    "GovernedPersistenceLoadReport",
    "GovernedPersistenceSource",
    "discover_governed_persistence_paths",
    "load_governed_intelligence_repository",
    "resolve_persistence_root",
    "try_load_mongo_repository",
]
