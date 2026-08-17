"""Large-print normalization helpers (PORT_ADAPT; no donor code copy)."""

from __future__ import annotations


def size_ratio(print_size: float, reference_value: float) -> float:
    if reference_value <= 0:
        return 0.0
    return round(print_size / reference_value, 4)


def threshold_gate(size_ratio_value: float, *, min_ratio: float) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if size_ratio_value < min_ratio:
        reasons.append("BELOW_SIZE_THRESHOLD")
        return False, reasons
    return True, reasons


def direction_label(side: str, size_ratio_value: float, *, gate_ok: bool) -> str:
    if not gate_ok:
        return "neutral"
    normalized_side = side.lower()
    if normalized_side == "unknown":
        return "ambiguous"
    if normalized_side == "buy":
        return "supports_long"
    if normalized_side == "sell":
        return "supports_short"
    return "ambiguous"


__all__ = ["direction_label", "size_ratio", "threshold_gate"]
