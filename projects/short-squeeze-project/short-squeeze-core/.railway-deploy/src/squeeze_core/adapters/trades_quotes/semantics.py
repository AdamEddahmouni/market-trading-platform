from decimal import Decimal

from .models import QuoteMarketState


def quote_market_state(
    bid_price: Decimal | None, ask_price: Decimal | None
) -> QuoteMarketState:
    if bid_price is None or ask_price is None:
        return QuoteMarketState.UNKNOWN
    if bid_price < ask_price:
        return QuoteMarketState.NORMAL
    if bid_price == ask_price:
        return QuoteMarketState.LOCKED
    return QuoteMarketState.CROSSED

