"""Surface QA gates — block Q inference when surface is unreliable (O2)."""

from __future__ import annotations

from typing import Any

from ..contracts.options_quality import OptionQualityFlag, quality_blocks_surface_fit


def evaluate_surface_qa(surface: dict[str, Any], *, min_points: int = 2) -> dict[str, Any]:
    points = surface.get("points", [])
    if not isinstance(points, list):
        points = []
    flags: list[str] = []
    if len(points) < min_points:
        flags.append(OptionQualityFlag.SURFACE_SPARSE.value)
    sigmas = [
        float(point.get("sigma", 0.0) or 0.0)
        for point in points
        if isinstance(point, dict) and point.get("sigma") is not None
    ]
    if sigmas and max(sigmas) - min(sigmas) > 2.0:
        flags.append(OptionQualityFlag.SURFACE_ARBITRAGE_VIOLATION.value)
    blocked = quality_blocks_surface_fit(tuple(flags))
    return {
        "blocked": blocked,
        "flags": flags,
        "point_count": len(points),
        "qa_version": "surface_qa_v1",
    }


__all__ = ["evaluate_surface_qa"]
