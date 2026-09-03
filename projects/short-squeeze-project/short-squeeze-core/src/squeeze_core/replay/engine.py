from collections.abc import Callable, Iterable
from pathlib import Path

from squeeze_core.contracts import Observation, ReplayMode

from .clock import ReplayClock, ReplayValidationError
from .loader import load_fixture
from .result import ReplayDiagnostic, ReplayResult


ReplayConsumer = Callable[[Observation, ReplayClock], None]


def observation_order_key(observation: Observation) -> tuple[object, ...]:
    return (
        observation.effective_timestamp,
        observation.source_timestamp,
        observation.sequence_number is None,
        observation.sequence_number if observation.sequence_number is not None else 0,
        observation.observation_id,
    )


class ReplayEngine:
    def __init__(self, *, mode: ReplayMode) -> None:
        self.mode = mode
        self._consumers: list[ReplayConsumer] = []

    def register_consumer(self, consumer: ReplayConsumer) -> None:
        self._consumers.append(consumer)

    def replay_file(self, path: str | Path) -> ReplayResult:
        return self.replay(load_fixture(path))

    def replay(self, observations: Iterable[Observation]) -> ReplayResult:
        input_items = list(observations)
        self._reject_duplicate_ids(input_items)
        ordered = sorted(input_items, key=observation_order_key)
        diagnostics: list[ReplayDiagnostic] = []
        if input_items != ordered:
            if self.mode is ReplayMode.STRICT:
                raise ReplayValidationError("fixture observations are out of order")
            diagnostics.append(
                ReplayDiagnostic(
                    code="INPUT_ORDER_NORMALIZED",
                    message="Input observations were reordered using the canonical replay key.",
                    original_observation_ids=tuple(item.observation_id for item in input_items),
                    normalized_observation_ids=tuple(item.observation_id for item in ordered),
                )
            )

        clock = ReplayClock()
        emitted_ids: list[str] = []
        for observation in ordered:
            clock.advance_to(observation.effective_timestamp)
            for consumer in self._consumers:
                consumer(observation, clock)
            emitted_ids.append(observation.observation_id)

        return ReplayResult(
            mode=self.mode,
            observations=tuple(ordered),
            emitted_observation_ids=tuple(emitted_ids),
            clock_timestamps=clock.history,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _reject_duplicate_ids(observations: list[Observation]) -> None:
        seen: set[str] = set()
        for observation in observations:
            if observation.observation_id in seen:
                raise ReplayValidationError(
                    f"duplicate observation_id: {observation.observation_id}"
                )
            seen.add(observation.observation_id)

