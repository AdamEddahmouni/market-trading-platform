import hashlib
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from squeeze_core.contracts import Observation, ReplayMode
from squeeze_core.serialization import canonical_json_bytes


class ReplayDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    original_observation_ids: tuple[str, ...] = ()
    normalized_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplayResult:
    mode: ReplayMode
    observations: tuple[Observation, ...]
    emitted_observation_ids: tuple[str, ...]
    clock_timestamps: tuple[datetime, ...]
    diagnostics: tuple[ReplayDiagnostic, ...]

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(
            {
                "clock_timestamps": self.clock_timestamps,
                "diagnostics": self.diagnostics,
                "emitted_observation_ids": self.emitted_observation_ids,
                "mode": self.mode,
                "observations": self.observations,
            }
        )

    @property
    def result_hash(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()

