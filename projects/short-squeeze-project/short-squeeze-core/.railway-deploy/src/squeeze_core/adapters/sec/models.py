from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .semantics import DateOnlyAvailabilityPolicy, FilingStatus


FixtureOrigin = Literal[
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
]


class SecFilingRecord(BaseModel):
    """Strict local-only shape for representative SEC filing metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    source_record_id: str = Field(min_length=1)
    provider_schema: Literal["SEC_FILING_V1"]
    record_type: Literal["SEC_FILING"]
    fixture_origin: FixtureOrigin
    symbol: str = Field(
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("symbol", "ticker"),
    )
    issuer_cik: str | None = Field(
        default=None,
        validation_alias=AliasChoices("issuer_cik", "cik"),
    )
    company_name: str | None = None
    form_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("form_type", "form"),
    )
    accession_number: str | None = None
    filed_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("filed_at", "filed_date", "filing_date"),
    )
    filed_timezone: str | None = None
    filed_date_only_policy: DateOnlyAvailabilityPolicy = (
        DateOnlyAvailabilityPolicy.INGESTION_TIME_UNCERTAIN_PLACEHOLDER
    )
    accepted_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("accepted_at", "acceptance_datetime"),
    )
    acceptance_timezone: str | None = None
    published_at: str | None = Field(
        default=None,
        validation_alias=AliasChoices("published_at", "publication_datetime"),
    )
    publication_timezone: str | None = None
    date_only_publication_policy: DateOnlyAvailabilityPolicy = (
        DateOnlyAvailabilityPolicy.STRICT_REJECT
    )
    period_of_report: str | None = None
    primary_document: str | None = None
    filing_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("filing_url", "filing_href"),
    )
    is_amendment: bool | None = None
    amends_accession_number: str | None = None
    document_count: Any = None
    file_number: str | None = None
    film_number: str | None = None
    fiscal_year_end: str | None = None
    provider_record_id: str | None = None
    capture_timestamp: str | None = None
    capture_timezone: str | None = None
    filing_status: FilingStatus = Field(
        default=FilingStatus.UNKNOWN,
        validation_alias=AliasChoices("filing_status", "record_status"),
    )

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized
