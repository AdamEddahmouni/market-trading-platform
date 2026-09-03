from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import Completeness, EntitlementState, IngestionMethod, ObservationKind


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    ingestion_method: IngestionMethod
    origin_kind: ObservationKind
    normalized: bool
    normalization_version: str | None = None
    upstream_observation_ids: tuple[str, ...] = ()
    completeness: Completeness | None = None
    units_modified: bool = False
    naming_modified: bool = False
    entitlement_state: EntitlementState = EntitlementState.UNKNOWN
    source_timezone: str | None = None
    source_timestamp_representation: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalized_data_has_version(self) -> "Provenance":
        if self.normalized and not self.normalization_version:
            raise ValueError("normalized provenance requires normalization_version")
        return self
