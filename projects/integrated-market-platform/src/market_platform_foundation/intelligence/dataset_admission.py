"""Fail-closed admission boundary for live/unadmitted provider captures.

Live opt-in captures are observational and are not admitted research
datasets. They must not feed training, promotion, or ``OrderReadyV1``.
Missing admission metadata is treated as unadmitted when the payload is
explicitly marked as a live/provider capture; ordinary fixture experiments
without those markers remain eligible.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

UNADMITTED_CAPTURE_CODE = "UNADMITTED_CAPTURE_REJECTED"

UNADMITTED_STATUSES = frozenset(
    {
        "UNADMITTED",
        "NOT_ADMITTED",
        "LIVE_PROVIDER_CAPTURE",
        "OBSERVATIONAL_UNADMITTED",
    }
)

LIVE_CAPTURE_MARKERS = (
    "live_opt_in_capture",
    "live_provider_capture",
    "unadmitted_capture",
)


class UnadmittedCaptureError(ValueError):
    """An unadmitted capture was presented to a gated research/execution surface."""

    def __init__(self, code: str, *, surface: str, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.surface = surface
        self.details = details or {}
        super().__init__(f"{code}:{surface}")


def is_unadmitted_capture(metadata: Mapping[str, Any] | None) -> bool:
    if not metadata:
        return False
    admitted = metadata.get("admitted_research_dataset")
    if admitted is True:
        return False
    if admitted is False:
        return True
    status = str(
        metadata.get("dataset_admission")
        or metadata.get("admission_status")
        or ""
    ).strip().upper()
    if status in UNADMITTED_STATUSES:
        return True
    if any(bool(metadata.get(key)) for key in LIVE_CAPTURE_MARKERS):
        return True
    return False


def assert_admitted_for_surface(
    metadata: Mapping[str, Any] | None,
    *,
    surface: str,
) -> None:
    if is_unadmitted_capture(metadata):
        raise UnadmittedCaptureError(
            UNADMITTED_CAPTURE_CODE,
            surface=surface,
            details={"metadata_keys": sorted(str(key) for key in (metadata or {}))},
        )


def assert_admitted_for_training(metadata: Mapping[str, Any] | None) -> None:
    assert_admitted_for_surface(metadata, surface="training")


def assert_admitted_for_promotion(metadata: Mapping[str, Any] | None) -> None:
    assert_admitted_for_surface(metadata, surface="promotion")


def assert_admitted_for_order_ready(metadata: Mapping[str, Any] | None) -> None:
    assert_admitted_for_surface(metadata, surface="order_ready")
