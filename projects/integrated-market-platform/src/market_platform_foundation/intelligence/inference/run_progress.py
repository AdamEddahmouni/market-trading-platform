"""Stage reporting for one bounded inference run.

A run announces the stage it is entering; whoever started the run may observe that. Reporting is
observation only: with no observer it does nothing, and an observer can never change or fail a run.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

StageObserver = Callable[[str, dict[str, Any]], None]

_OBSERVER: ContextVar[StageObserver | None] = ContextVar("imp_inference_stage_observer", default=None)


def report_stage(stage: str, **detail: Any) -> None:
    """Announce the stage this thread's run is entering, or add detail to the stage it is already in."""
    observer = _OBSERVER.get()
    if observer is None:
        return
    try:
        observer(stage, detail)
    except Exception:  # noqa: BLE001 - an observer is never allowed to change the outcome of a run
        pass


@contextmanager
def observing(observer: StageObserver) -> Iterator[None]:
    """Observe the stages reported by work done on this thread inside the block."""
    token = _OBSERVER.set(observer)
    try:
        yield
    finally:
        _OBSERVER.reset(token)


@contextmanager
def relabelled(stage: str, **fixed: Any) -> Iterator[None]:
    """Report every stage announced inside the block as ``stage``, carrying the inner stage as ``step``.

    A run made of many bounded calls shows which call it is on, not one line per inner stage of each call."""
    outer = _OBSERVER.get()
    if outer is None:
        yield
        return
    token = _OBSERVER.set(lambda inner, detail: outer(stage, {**fixed, **detail, "step": inner}))
    try:
        yield
    finally:
        _OBSERVER.reset(token)


__all__ = ["StageObserver", "observing", "relabelled", "report_stage"]
