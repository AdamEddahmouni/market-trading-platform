"""Parity harness for PineTS vs Python reference (never P&L-only parity)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence


class ParityFailureCode(StrEnum):
    UNSUPPORTED_PINE_FEATURE = "UNSUPPORTED_PINE_FEATURE"
    NUMERICAL_MISMATCH = "NUMERICAL_MISMATCH"
    TIME_ALIGNMENT_MISMATCH = "TIME_ALIGNMENT_MISMATCH"
    WARMUP_MISMATCH = "WARMUP_MISMATCH"
    RUNTIME_ERROR = "RUNTIME_ERROR"


_NUMERIC_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class ParityCompareResult:
    ok: bool
    failure_codes: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    indicator_checks: int = 0
    signal_checks: int = 0

    @classmethod
    def success(cls, *, indicator_checks: int = 0, signal_checks: int = 0) -> ParityCompareResult:
        return cls(
            ok=True,
            indicator_checks=indicator_checks,
            signal_checks=signal_checks,
        )

    @classmethod
    def failure(
        cls,
        code: ParityFailureCode,
        detail: str,
        *,
        indicator_checks: int = 0,
        signal_checks: int = 0,
    ) -> ParityCompareResult:
        return cls(
            ok=False,
            failure_codes=(str(code),),
            details=(detail,),
            indicator_checks=indicator_checks,
            signal_checks=signal_checks,
        )


@dataclass(frozen=True, slots=True)
class ParitySide:
    indicators: Mapping[str, Sequence[float | None]] = field(default_factory=dict)
    signals: Sequence[Mapping[str, Any]] = ()
    warmup_bars: int = 0


def compare_parity(reference: ParitySide, challenger: ParitySide) -> ParityCompareResult:
    if reference.warmup_bars != challenger.warmup_bars:
        return ParityCompareResult.failure(
            ParityFailureCode.WARMUP_MISMATCH,
            f"warmup:{reference.warmup_bars}!={challenger.warmup_bars}",
        )

    indicator_checks = 0
    ref_keys = set(reference.indicators)
    chal_keys = set(challenger.indicators)
    if ref_keys != chal_keys:
        missing = sorted(ref_keys - chal_keys)
        extra = sorted(chal_keys - ref_keys)
        return ParityCompareResult.failure(
            ParityFailureCode.UNSUPPORTED_PINE_FEATURE,
            f"indicator_keys:missing={missing}:extra={extra}",
        )

    for key in sorted(ref_keys):
        ref_series = list(reference.indicators[key])
        chal_series = list(challenger.indicators[key])
        if len(ref_series) != len(chal_series):
            return ParityCompareResult.failure(
                ParityFailureCode.TIME_ALIGNMENT_MISMATCH,
                f"{key}:len:{len(ref_series)}!={len(chal_series)}",
            )
        for index, (left, right) in enumerate(zip(ref_series, chal_series, strict=False)):
            indicator_checks += 1
            if left is None and right is None:
                continue
            if left is None or right is None:
                return ParityCompareResult.failure(
                    ParityFailureCode.WARMUP_MISMATCH,
                    f"{key}[{index}]:na_mismatch",
                    indicator_checks=indicator_checks,
                )
            if abs(float(left) - float(right)) > _NUMERIC_TOLERANCE:
                return ParityCompareResult.failure(
                    ParityFailureCode.NUMERICAL_MISMATCH,
                    f"{key}[{index}]:{left}!={right}",
                    indicator_checks=indicator_checks,
                )

    ref_signal_times = [int(row.get("time", -1)) for row in reference.signals]
    chal_signal_times = [int(row.get("time", -1)) for row in challenger.signals]
    signal_checks = max(len(ref_signal_times), len(chal_signal_times))
    if ref_signal_times != chal_signal_times:
        return ParityCompareResult.failure(
            ParityFailureCode.TIME_ALIGNMENT_MISMATCH,
            f"signals:{ref_signal_times}!={chal_signal_times}",
            indicator_checks=indicator_checks,
            signal_checks=signal_checks,
        )

    return ParityCompareResult.success(
        indicator_checks=indicator_checks,
        signal_checks=signal_checks,
    )


def parity_side_from_reference_payload(payload: Mapping[str, Any]) -> ParitySide:
    indicators = payload.get("indicators") or {}
    if not isinstance(indicators, dict):
        indicators = {}
    return ParitySide(
        indicators={str(key): list(value) for key, value in indicators.items()},
        signals=tuple(dict(row) for row in payload.get("signals") or [] if isinstance(row, dict)),
        warmup_bars=int(payload.get("warmup_bars", 0)),
    )
