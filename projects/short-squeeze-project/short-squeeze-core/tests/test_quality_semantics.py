from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.contracts import (
    BorrowFeePayload,
    Completeness,
    Quality,
    QualityState,
    SourceHealth,
)


def test_known_zero_borrow_fee_is_not_missing() -> None:
    payload = BorrowFeePayload(annualized_fee_percent=Decimal("0"), fee_type="indicative")
    quality = Quality(state=QualityState.KNOWN_VALUE)
    assert payload.annualized_fee_percent == Decimal("0")
    assert quality.state is QualityState.KNOWN_VALUE


def test_missing_borrow_fee_remains_null_and_explicit() -> None:
    payload = BorrowFeePayload(annualized_fee_percent=None, fee_type="indicative")
    quality = Quality(state=QualityState.MISSING, reasons=["field absent from source"])
    assert payload.annualized_fee_percent is None
    assert quality.state is QualityState.MISSING


@pytest.mark.parametrize(
    "state",
    [
        QualityState.MISSING,
        QualityState.UNAVAILABLE,
        QualityState.NOT_APPLICABLE,
        QualityState.STALE,
        QualityState.DELAYED,
        QualityState.INVALID,
        QualityState.CONFLICTED,
        QualityState.ESTIMATED,
    ],
)
def test_non_known_quality_states_require_reasons(state: QualityState) -> None:
    with pytest.raises(ValidationError, match="reason"):
        Quality(state=state)


def test_quality_object_preserves_optional_evaluation_context() -> None:
    evaluated_at = datetime(2026, 1, 2, tzinfo=UTC)
    quality = Quality(
        state=QualityState.STALE,
        reasons=["quote exceeds freshness threshold"],
        evaluated_at=evaluated_at,
        age_ms=61_000,
        expected_delay_ms=0,
        source_health=SourceHealth.DEGRADED,
        completeness=Completeness.PARTIAL,
        confidence=Decimal("0.75"),
    )
    assert quality.age_ms == 61_000
    assert quality.confidence == Decimal("0.75")


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Quality(state=QualityState.KNOWN_VALUE, confidence=Decimal("1.01"))

