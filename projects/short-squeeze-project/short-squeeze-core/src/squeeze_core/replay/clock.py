from datetime import datetime

from squeeze_core.contracts.validation import require_aware_utc


class ReplayValidationError(ValueError):
    """Raised when fixture or replay invariants are violated."""


class ReplayClock:
    def __init__(self) -> None:
        self._current: datetime | None = None
        self._history: list[datetime] = []

    @property
    def current(self) -> datetime | None:
        return self._current

    @property
    def history(self) -> tuple[datetime, ...]:
        return tuple(self._history)

    def advance_to(self, timestamp: datetime) -> datetime:
        target = require_aware_utc(timestamp)
        if self._current is not None and target < self._current:
            raise ReplayValidationError("simulated clock cannot move backward")
        self._current = target
        self._history.append(target)
        return target

