from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from squeeze_core.contracts import EntitlementState, IngestionMethod, Observation
from squeeze_core.contracts.validation import require_aware_utc

from .diagnostics import DiagnosticCode, NormalizationDiagnostic


class AdapterContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ingested_at: datetime
    source_timezone: str | None
    provider: str
    adapter_version: str
    normalization_version: str
    entitlement_status: EntitlementState
    collection_method: IngestionMethod
    account_scope: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    expected_delay_ms: int | None = Field(default=None, ge=0)
    source_endpoint_name: str | None = None

    @field_validator("ingested_at")
    @classmethod
    def normalize_ingested_at(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class RejectedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: DiagnosticCode
    message: str
    raw_record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_id: str | None = None


class NormalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observations: tuple[Observation, ...] = ()
    diagnostics: tuple[NormalizationDiagnostic, ...] = ()
    rejection: RejectedRecord | None = None

    @computed_field
    @property
    def accepted(self) -> bool:
        return self.rejection is None

    @model_validator(mode="after")
    def rejection_excludes_observations(self) -> "NormalizationResult":
        if self.rejection is not None and self.observations:
            raise ValueError("rejected result cannot contain observations")
        return self
