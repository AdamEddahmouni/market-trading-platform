from enum import StrEnum


class EventType(StrEnum):
    TRADE = "TRADE"
    QUOTE = "QUOTE"
    BAR = "BAR"
    PUBLISHED_SHORT_INTEREST = "PUBLISHED_SHORT_INTEREST"
    BORROW_AVAILABILITY = "BORROW_AVAILABILITY"
    BORROW_FEE = "BORROW_FEE"
    NEWS_ITEM = "NEWS_ITEM"
    SEC_FILING = "SEC_FILING"
    TRADING_HALT = "TRADING_HALT"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    DERIVED_INDICATOR = "DERIVED_INDICATOR"
    SOURCE_STATUS = "SOURCE_STATUS"
    MARKET_SNAPSHOT = "MARKET_SNAPSHOT"


class PayloadType(StrEnum):
    TRADE = "trade"
    QUOTE = "quote"
    BAR = "bar"
    PUBLISHED_SHORT_INTEREST = "published_short_interest"
    BORROW_AVAILABILITY = "borrow_availability"
    BORROW_FEE = "borrow_fee"
    NEWS_ITEM = "news_item"
    SEC_FILING = "sec_filing"
    TRADING_HALT = "trading_halt"
    CORPORATE_ACTION = "corporate_action"
    DERIVED_INDICATOR = "derived_indicator"
    SOURCE_STATUS = "source_status"
    MARKET_SNAPSHOT = "market_snapshot"


class EarningsSession(StrEnum):
    BEFORE_MARKET = "BEFORE_MARKET"
    AFTER_MARKET = "AFTER_MARKET"
    DURING_MARKET = "DURING_MARKET"
    UNKNOWN = "UNKNOWN"


class AssetClass(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    UNKNOWN = "UNKNOWN"


class MarketSession(StrEnum):
    PRE_MARKET = "PRE_MARKET"
    REGULAR = "REGULAR"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class DataFreshness(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    HISTORICAL = "HISTORICAL"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


class ObservationKind(StrEnum):
    PROVIDER_PUBLISHED = "PROVIDER_PUBLISHED"
    MARKET_OBSERVED = "MARKET_OBSERVED"
    DERIVED = "DERIVED"
    HUMAN_ANNOTATION = "HUMAN_ANNOTATION"
    SYNTHETIC = "SYNTHETIC"


class QualityState(StrEnum):
    KNOWN_VALUE = "KNOWN_VALUE"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    STALE = "STALE"
    DELAYED = "DELAYED"
    INVALID = "INVALID"
    CONFLICTED = "CONFLICTED"
    ESTIMATED = "ESTIMATED"


class SourceHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class Completeness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class IngestionMethod(StrEnum):
    SCRAPED = "SCRAPED"
    POLLED = "POLLED"
    STREAMED = "STREAMED"
    DOWNLOADED = "DOWNLOADED"
    HUMAN_ENTERED = "HUMAN_ENTERED"
    CALCULATED = "CALCULATED"
    LOADED_FIXTURE = "LOADED_FIXTURE"


class EntitlementState(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReplayMode(StrEnum):
    STRICT = "STRICT"
    NORMALIZED = "NORMALIZED"
