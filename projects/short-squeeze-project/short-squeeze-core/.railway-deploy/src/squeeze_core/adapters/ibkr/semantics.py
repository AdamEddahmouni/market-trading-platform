from enum import StrEnum


class PercentUnit(StrEnum):
    PERCENT_POINTS = "PERCENT_POINTS"
    DECIMAL_FRACTION = "DECIMAL_FRACTION"


class DelayStatus(StrEnum):
    KNOWN_DELAYED = "KNOWN_DELAYED"
    NOT_DELAYED = "NOT_DELAYED"
    UNKNOWN = "UNKNOWN"


PROVIDER_SOURCE = "interactive-brokers-short-stock-file"
FEE_TYPE = "indicative_annualized_borrow_fee"
