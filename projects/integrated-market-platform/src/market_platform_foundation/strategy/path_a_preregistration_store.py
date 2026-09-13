"""Paper/Demo persist+load for Phase-6 Path A preregistration records.

Create is a separate operator step: ``persist_paper_demo_preregistration``
stamps ``registered_at`` via ``build_preregistration`` *before* any hop.
The Path A hop only *loads* a previously persisted record. Catalog evaluators
never call ``build_preregistration``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..canonical import load_json_strict, write_canonical_json
from ..normalization.equity_bars import iso_to_epoch_ns
from .preregistration import build_preregistration, verify_preregistration
from .strategy_spec import StrategyDefinition, coerce_strategy_spec


def persist_paper_demo_preregistration(
    strategy_spec: StrategyDefinition | Mapping[str, Any],
    *,
    registered_at: str,
    destination: str | Path,
    principal_id: str = "PROJECT-PRINCIPAL-001",
) -> dict[str, Any]:
    """Operator create: stamp ``registered_at`` and persist the Phase-6 record.

    Not a hop/eval authority. Must run before the quote ``event_time_ns`` that
    a later Paper/Demo load will compare against.
    """

    record = build_preregistration(
        strategy_spec,
        registered_at=registered_at,
        principal_id=principal_id,
    )
    dest = Path(destination)
    if dest.suffix.lower() == ".json":
        target = dest
    else:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / f"{record['strategy_identity_hash']}.json"
    write_canonical_json(target, record)
    return record


def load_paper_demo_preregistrations(source: str | Path) -> tuple[dict[str, Any], ...]:
    """Load previously persisted Phase-6 records. Fail closed on missing/corrupt."""

    path = Path(source)
    if not path.exists():
        return ()
    if path.is_dir():
        rows: list[dict[str, Any]] = []
        for child in sorted(path.glob("*.json")):
            rows.extend(_load_preregistration_payload(child))
        return tuple(rows)
    return tuple(_load_preregistration_payload(path))


def select_eligible_preregistration(
    strategy_spec: StrategyDefinition | Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
    *,
    quote_event_time_ns: int,
) -> dict[str, Any] | None:
    """Return a stored record only when identity verifies and it predates the quote."""

    if not isinstance(quote_event_time_ns, int):
        return None
    spec = coerce_strategy_spec(strategy_spec)
    expected_identity = str(spec["strategy_identity_hash"])
    eligible: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        payload = dict(record)
        if payload.get("strategy_identity_hash") != expected_identity:
            continue
        status, _reasons = verify_preregistration(payload, spec)
        if status != "PASS":
            continue
        registered_at_ns = _registered_at_ns(payload.get("registered_at"))
        if registered_at_ns is None:
            continue
        if registered_at_ns >= quote_event_time_ns:
            continue
        eligible.append(payload)
    if not eligible:
        return None
    eligible.sort(key=lambda row: str(row.get("preregistration_record_hash") or ""))
    return eligible[0]


def _load_preregistration_payload(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        payload = load_json_strict(path)
    except (OSError, TypeError, ValueError):
        return ()
    if isinstance(payload, Mapping):
        return (dict(payload),)
    if isinstance(payload, list):
        return tuple(dict(row) for row in payload if isinstance(row, Mapping))
    return ()


def _registered_at_ns(value: object) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return iso_to_epoch_ns(value)
    except (OSError, TypeError, ValueError):
        return None


__all__ = [
    "load_paper_demo_preregistrations",
    "persist_paper_demo_preregistration",
    "select_eligible_preregistration",
]
