from enum import StrEnum


class NewsSourceShape(StrEnum):
    FINVIZ = "FINVIZ"
    YAHOO = "YAHOO"
    NEWSAPI = "NEWSAPI"
    PROVIDER_NEUTRAL = "PROVIDER_NEUTRAL"


class NewsLifecycleStatus(StrEnum):
    ORIGINAL = "ORIGINAL"
    UPDATED = "UPDATED"
    CORRECTED = "CORRECTED"
    WITHDRAWN = "WITHDRAWN"
    DELETED = "DELETED"
    UNKNOWN = "UNKNOWN"


class NewsDateOnlyPolicy(StrEnum):
    STRICT = "STRICT"
    CONSERVATIVE_END_OF_DAY = "CONSERVATIVE_END_OF_DAY"
    UNCERTAIN_PLACEHOLDER = "UNCERTAIN_PLACEHOLDER"


PROVIDER_SOURCE = "offline-objective-news"
URL_POLICY_VERSION = "news-url-v1"
