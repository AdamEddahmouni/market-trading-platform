"""Bounded decision-source snapshot for Paper simulated order intents."""

from __future__ import annotations

from typing import Any

SOURCE_TYPES: tuple[str, ...] = (
    "paper_command_attention",
    "workspace_lane",
)

MAX_HEADLINE_LENGTH = 240
MAX_REASON_COUNT = 5
MAX_REASON_CODE_LENGTH = 64
MAX_REASON_LABEL_LENGTH = 200
MAX_SOURCE_ID_LENGTH = 128
MAX_SOURCE_MODULE_LENGTH = 64

KNOWN_LANE_MODULES: frozenset[str] = frozenset(
    {
        "squeeze",
        "order-flow",
        "order-book",
        "catalyst",
        "options",
        "futures",
        "large-transactions",
        "disclosure",
        "institutional-flow",
        "fund-etf",
    }
)


def _clean_text(value: Any, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:max_length]


def _parse_reasons(value: Any) -> list[dict[str, str]] | None:
    if not isinstance(value, list):
        return None
    reasons: list[dict[str, str]] = []
    for item in value[:MAX_REASON_COUNT]:
        if not isinstance(item, dict):
            continue
        code = _clean_text(item.get("code"), max_length=MAX_REASON_CODE_LENGTH)
        label = _clean_text(item.get("label"), max_length=MAX_REASON_LABEL_LENGTH)
        if not code or not label:
            continue
        reasons.append({"code": code, "label": label})
    return reasons or None


def _parse_source_time(value: Any) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value <= 0:
        return None
    # Reject absurd values (well beyond plausible epoch ns/ms through ~2286).
    if value > 10_000_000_000_000_000_000:
        return None
    return value


def _parse_tier(value: Any) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value < 0:
        return None
    return value


def parse_decision_source_snapshot(value: Any) -> dict[str, Any] | None:
    """Parse and sanitize an optional decision-source snapshot from request JSON."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("DECISION_SOURCE_SNAPSHOT_INVALID")
    source_type = _clean_text(value.get("source_type"), max_length=64)
    if source_type not in SOURCE_TYPES:
        raise ValueError("DECISION_SOURCE_SNAPSHOT_TYPE_INVALID")
    source_id = _clean_text(value.get("source_id"), max_length=MAX_SOURCE_ID_LENGTH)
    if not source_id:
        raise ValueError("DECISION_SOURCE_SNAPSHOT_ID_REQUIRED")
    snapshot: dict[str, Any] = {
        "source_type": source_type,
        "source_id": source_id,
    }
    source_module = _clean_text(value.get("source_module"), max_length=MAX_SOURCE_MODULE_LENGTH)
    if source_module:
        snapshot["source_module"] = source_module
    headline = _clean_text(value.get("headline"), max_length=MAX_HEADLINE_LENGTH)
    if headline:
        snapshot["headline"] = headline
    tier = _parse_tier(value.get("tier"))
    if tier is not None:
        snapshot["tier"] = tier
    reasons = _parse_reasons(value.get("reasons"))
    if reasons:
        snapshot["reasons"] = reasons
    source_time = _parse_source_time(value.get("source_time"))
    if source_time is not None:
        snapshot["source_time"] = source_time
    return snapshot


def validate_snapshot_against_correlation(
    *,
    snapshot: dict[str, Any] | None,
    correlation_id: str | None,
) -> dict[str, Any] | None:
    """Reject snapshots whose source identity conflicts with correlation provenance."""
    if snapshot is None:
        return None
    if not correlation_id:
        raise ValueError("DECISION_SOURCE_SNAPSHOT_CORRELATION_REQUIRED")
    correlation = correlation_id.strip()
    source_type = snapshot["source_type"]
    source_id = snapshot["source_id"]
    if source_type == "workspace_lane":
        expected = f"lane:{source_id}"
        if correlation != expected:
            raise ValueError("DECISION_SOURCE_SNAPSHOT_CORRELATION_MISMATCH")
        module = snapshot.get("source_module") or source_id
        if module != source_id:
            raise ValueError("DECISION_SOURCE_SNAPSHOT_MODULE_MISMATCH")
        return snapshot
    if source_type == "paper_command_attention":
        if correlation.startswith("lane:"):
            raise ValueError("DECISION_SOURCE_SNAPSHOT_CORRELATION_MISMATCH")
        normalized_attention = source_id
        if correlation.startswith("attention:"):
            if correlation != f"attention:{normalized_attention}":
                raise ValueError("DECISION_SOURCE_SNAPSHOT_CORRELATION_MISMATCH")
        elif correlation != normalized_attention:
            raise ValueError("DECISION_SOURCE_SNAPSHOT_CORRELATION_MISMATCH")
        return snapshot
    raise ValueError("DECISION_SOURCE_SNAPSHOT_TYPE_INVALID")


def snapshot_matches_correlation(
    *,
    snapshot: dict[str, Any] | None,
    correlation_id: str | None,
) -> bool:
    if snapshot is None or not correlation_id:
        return snapshot is None
    try:
        validate_snapshot_against_correlation(snapshot=snapshot, correlation_id=correlation_id)
    except ValueError:
        return False
    return True
