from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineRunConfig:
    limit: int | None = None
    retry_errored: bool = False
    aggregate: bool = False

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be positive")
