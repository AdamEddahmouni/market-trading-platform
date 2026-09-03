from apps.research_screener.borrow_fee_live import (
    BorrowFeeProvider,
    NullBorrowFeeProvider,
)


def test_borrow_fee_status_does_not_claim_unverified_generic_tick_258() -> None:
    assert "258" not in str(BorrowFeeProvider().status()["detail"])
    assert "258" not in str(NullBorrowFeeProvider().status()["detail"])
