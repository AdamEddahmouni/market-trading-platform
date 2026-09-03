from enum import StrEnum


class DateOnlyAvailabilityPolicy(StrEnum):
    STRICT_REJECT = "STRICT_REJECT"
    END_OF_DATE = "END_OF_DATE"
    INGESTION_TIME_UNCERTAIN_PLACEHOLDER = "INGESTION_TIME_UNCERTAIN_PLACEHOLDER"


class FilingStatus(StrEnum):
    ORIGINAL = "ORIGINAL"
    AMENDED = "AMENDED"
    CORRECTED = "CORRECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


PROVIDER_SOURCE = "sec-shaped-offline-filings"
