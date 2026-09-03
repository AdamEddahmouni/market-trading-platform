from enum import StrEnum


class HaltLifecycleStatus(StrEnum):
    HALT_ANNOUNCED = "HALT_ANNOUNCED"
    HALT_ACTIVE = "HALT_ACTIVE"
    QUOTE_RESUMPTION_SCHEDULED = "QUOTE_RESUMPTION_SCHEDULED"
    QUOTE_RESUMED = "QUOTE_RESUMED"
    TRADE_RESUMPTION_SCHEDULED = "TRADE_RESUMPTION_SCHEDULED"
    TRADING_RESUMED = "TRADING_RESUMED"
    HALT_CANCELLED = "HALT_CANCELLED"
    HALT_UPDATED = "HALT_UPDATED"
    UNKNOWN = "UNKNOWN"


class HaltRevisionStatus(StrEnum):
    ORIGINAL = "ORIGINAL"
    UPDATED = "UPDATED"
    CORRECTED = "CORRECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


PROVIDER_SOURCE = "exchange-shaped-offline-trading-halts"

# This list classifies fixture codes only. It deliberately carries no reason mapping.
KNOWN_HALT_CODES = frozenset({"T1", "T2", "T5", "T6", "T12", "H10", "LUDP", "M"})
