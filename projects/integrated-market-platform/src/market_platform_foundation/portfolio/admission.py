"""Portfolio position admission gate (G2).

Reference-only identities can never become canonical portfolio positions. The
gate reuses the XA-01 tradability contract (``xa01.tradability``) so the
portfolio and the execution boundary share one executable-vs-reference rule:

- admitted: tradable securities/ETFs, option contracts, specific future
  contracts, tradable crypto pairs;
- rejected: futures family/root, continuous futures series, economic
  commodities, commodity spot/reference identities, index benchmarks,
  currencies, FX pairs, sovereign securities, and reference-only bonds.

The gate fails closed: an unknown kind/tradability is rejected, and a
provider-supplied quantity for an ambiguous symbol never becomes a position.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..xa01.contracts import InstrumentRecord
from ..xa01.enums import InstrumentKind, Tradability, XaAssetClass
from ..xa01.tradability import (
    EXECUTABLE_KINDS,
    NON_EXECUTABLE_KINDS,
    default_tradability,
    is_executable,
)
from .canonical import PortfolioError, PortfolioErrorCode


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    REJECTED_NON_EXECUTABLE = "REJECTED_NON_EXECUTABLE"
    REJECTED_UNKNOWN = "REJECTED_UNKNOWN"
    REJECTED_ASSET_CLASS_MISMATCH = "REJECTED_ASSET_CLASS_MISMATCH"


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    status: AdmissionStatus
    instrument_kind: str
    asset_class: str
    tradability: str
    reason: str = ""

    @property
    def admitted(self) -> bool:
        return self.status == AdmissionStatus.ADMITTED


# Kinds whose only XA-01 asset class is not the default: guard against a kind
# being admitted under the wrong asset class (e.g. TRADABLE_SECURITY under
# CRYPTO). Equity/ETF securities are EQUITY/ETF_FUND; options are OPTION.
_ALLOWED_ASSET_CLASSES: dict[InstrumentKind, frozenset[XaAssetClass]] = {
    InstrumentKind.TRADABLE_SECURITY: frozenset(
        {XaAssetClass.EQUITY, XaAssetClass.ETF_FUND}
    ),
    InstrumentKind.OPTION_CONTRACT: frozenset({XaAssetClass.OPTION}),
    InstrumentKind.FUTURE_CONTRACT: frozenset({XaAssetClass.FUTURE}),
    InstrumentKind.CRYPTO_PAIR: frozenset({XaAssetClass.CRYPTO}),
}


def admission_result(
    *,
    instrument_kind: str,
    asset_class: str,
    tradability: str | None = None,
) -> AdmissionResult:
    """Deterministic admission classification for one identity.

    ``tradability`` may be omitted; it then defaults the same way XA-01
    defaults it (executable kinds default to TRADABLE, everything else to
    REFERENCE_ONLY / CONTINUOUS_SERIES).
    """
    try:
        kind = InstrumentKind(str(instrument_kind))
    except ValueError:
        return AdmissionResult(
            AdmissionStatus.REJECTED_UNKNOWN,
            str(instrument_kind),
            str(asset_class),
            tradability or "UNKNOWN",
            reason="UNKNOWN_INSTRUMENT_KIND",
        )
    try:
        asset = XaAssetClass(str(asset_class))
    except ValueError:
        return AdmissionResult(
            AdmissionStatus.REJECTED_UNKNOWN,
            kind.value,
            str(asset_class),
            tradability or default_tradability(kind).value,
            reason="UNKNOWN_ASSET_CLASS",
        )
    effective_tradability = (
        Tradability(str(tradability)) if tradability is not None else default_tradability(kind)
    )
    allowed = _ALLOWED_ASSET_CLASSES.get(kind)
    if allowed is not None and asset not in allowed:
        return AdmissionResult(
            AdmissionStatus.REJECTED_ASSET_CLASS_MISMATCH,
            kind.value,
            asset.value,
            effective_tradability.value,
            reason=f"ASSET_CLASS_MISMATCH_FOR_KIND:{kind.value}",
        )
    if not is_executable(instrument_kind=kind, tradability=effective_tradability):
        return AdmissionResult(
            AdmissionStatus.REJECTED_NON_EXECUTABLE,
            kind.value,
            asset.value,
            effective_tradability.value,
            reason=f"NON_EXECUTABLE:{kind.value}:{effective_tradability.value}",
        )
    return AdmissionResult(
        AdmissionStatus.ADMITTED,
        kind.value,
        asset.value,
        effective_tradability.value,
    )


def assert_position_admissible(
    *,
    instrument_kind: str,
    asset_class: str,
    tradability: str | None = None,
) -> AdmissionResult:
    """Raise ``PortfolioError(NON_EXECUTABLE_INSTRUMENT)`` for a non-admitted identity."""
    result = admission_result(
        instrument_kind=instrument_kind,
        asset_class=asset_class,
        tradability=tradability,
    )
    if result.admitted:
        return result
    raise PortfolioError(
        PortfolioErrorCode.NON_EXECUTABLE_INSTRUMENT,
        "identity is not admissible as a portfolio position (reference/synthetic identities cannot be held)",
        {
            "instrument_kind": result.instrument_kind,
            "asset_class": result.asset_class,
            "tradability": result.tradability,
            "reason": result.reason,
        },
    )


def assert_record_admissible(record: InstrumentRecord) -> AdmissionResult:
    """Admission against a canonical XA-01 record (registry-backed boundary)."""
    identity = record.descriptor.identity
    return assert_position_admissible(
        instrument_kind=identity.instrument_kind.value,
        asset_class=identity.asset_class.value,
        tradability=record.descriptor.tradability.value,
    )


ADMITTED_KINDS = frozenset(kind.value for kind in EXECUTABLE_KINDS)

__all__ = [
    "ADMITTED_KINDS",
    "AdmissionResult",
    "AdmissionStatus",
    "admission_result",
    "assert_position_admissible",
    "assert_record_admissible",
]