"""Label rows with horizon-bounded availability per ADR-PIT-001."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

DEFAULT_HORIZON_NS = 60_000_000_000  # one minute in nanoseconds for 1m bars


def build_target_rows(
    rows: list[dict[str, object]],
    *,
    horizon_ns: int = DEFAULT_HORIZON_NS,
) -> list[dict[str, object]]:
    by_instrument: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_instrument.setdefault(str(row["instrument_id"]), []).append(row)
    targets: list[dict[str, object]] = []
    for instrument_id, inst_rows in sorted(by_instrument.items()):
        ordered = sorted(inst_rows, key=lambda row: int(row["available_time"]))
        for index, row in enumerate(ordered[:-1]):
            future = ordered[index + 1]
            available_time = int(row["available_time"])
            future_time = int(future["available_time"])
            if future_time - available_time > horizon_ns * 2:
                continue
            current_px = Decimal(str(row["value"]))
            future_px = Decimal(str(future["value"]))
            forward_return = future_px - current_px
            targets.append(
                {
                    "forward_return": str(forward_return),
                    "horizon_ns": future_time - available_time,
                    "instrument_id": instrument_id,
                    "label_available_time": future_time,
                    "observation_time": available_time,
                    "prediction_cutoff": int(row["prediction_cutoff"]),
                }
            )
    return targets


def verify_label_availability(
    targets: list[dict[str, object]],
    *,
    horizon_ns: int = DEFAULT_HORIZON_NS,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for row in targets:
        cutoff = int(row["prediction_cutoff"])
        label_time = int(row["label_available_time"])
        obs_time = int(row["observation_time"])
        if label_time <= cutoff:
            reasons.append("PIT_LABEL_NOT_AFTER_CUTOFF")
        if label_time < obs_time + horizon_ns:
            reasons.append("PIT_LABEL_BEFORE_HORIZON")
    status = "PASS" if not reasons else "FAIL"
    return status, sorted(set(reasons))
