from enum import StrEnum


class PercentageUnit(StrEnum):
    PERCENT_POINTS = "PERCENT_POINTS"
    DECIMAL_FRACTION = "DECIMAL_FRACTION"
    FORMATTED_PERCENT_STRING = "FORMATTED_PERCENT_STRING"


class DelayStatus(StrEnum):
    KNOWN_DELAYED = "KNOWN_DELAYED"
    NOT_DELAYED = "NOT_DELAYED"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


PROVIDER_SOURCE = "finviz-screener-snapshot"
SNAPSHOT_SCOPE = "candidate-universe descriptive market snapshot"
