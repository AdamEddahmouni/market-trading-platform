from enum import StrEnum


class BarIntervalUnit(StrEnum):
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"


class BarIntervalKind(StrEnum):
    FIXED = "FIXED"
    SESSION_BASED = "SESSION_BASED"


class BarInterval(StrEnum):
    ONE_MINUTE = "1_MINUTE"
    FIVE_MINUTES = "5_MINUTES"
    FIFTEEN_MINUTES = "15_MINUTES"
    THIRTY_MINUTES = "30_MINUTES"
    ONE_HOUR = "1_HOUR"
    ONE_DAY = "1_DAY"

    @property
    def magnitude(self) -> int:
        return {
            BarInterval.ONE_MINUTE: 1,
            BarInterval.FIVE_MINUTES: 5,
            BarInterval.FIFTEEN_MINUTES: 15,
            BarInterval.THIRTY_MINUTES: 30,
            BarInterval.ONE_HOUR: 1,
            BarInterval.ONE_DAY: 1,
        }[self]

    @property
    def unit(self) -> BarIntervalUnit:
        if self is BarInterval.ONE_DAY:
            return BarIntervalUnit.DAY
        if self is BarInterval.ONE_HOUR:
            return BarIntervalUnit.HOUR
        return BarIntervalUnit.MINUTE

    @property
    def kind(self) -> BarIntervalKind:
        return (
            BarIntervalKind.SESSION_BASED
            if self is BarInterval.ONE_DAY
            else BarIntervalKind.FIXED
        )


class BarTimestampMeaning(StrEnum):
    START = "START"
    END = "END"
    LABEL = "LABEL"
    UNKNOWN = "UNKNOWN"


class BarCompletionStatus(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    CORRECTED = "CORRECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class BarSession(StrEnum):
    PREMARKET = "PREMARKET"
    REGULAR = "REGULAR"
    AFTER_HOURS = "AFTER_HOURS"
    OVERNIGHT = "OVERNIGHT"
    EXTENDED = "EXTENDED"
    CLOSED_SESSION = "CLOSED_SESSION"
    UNKNOWN = "UNKNOWN"


class BarVolumeUnit(StrEnum):
    SHARES = "SHARES"
    CONTRACTS = "CONTRACTS"
    UNITS = "UNITS"
    UNKNOWN = "UNKNOWN"


PROVIDER_SOURCE = "offline-market-bars"
