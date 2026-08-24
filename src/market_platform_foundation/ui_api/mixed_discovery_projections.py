"""Stateful projections for the mixed semi-live discovery queue."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from ..clock import monotonic_wall_ns
from ..discovery import DiscoveryEngine, aggregate_candidate_sets
from ..discovery.live_enrichment import MoomooCandidateEnricher
from ..discovery.screens import SCREEN_LIBRARY
from ..market_data.live_runtime import get_live_runtime
from .discovery_projections import load_latest_capture_for_screen


def _utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        payload = converter()
        if isinstance(payload, dict):
            return payload
    raise TypeError("discovery result must be a dictionary or expose to_dict()")


class MixedDiscoveryService:
    """Coordinate expensive discovery refreshes separately from read-only live polls."""

    def __init__(
        self,
        *,
        engine_factory: Callable[[], Any] = DiscoveryEngine,
        capture_loader: Callable[[str], dict[str, Any] | None] = load_latest_capture_for_screen,
        runtime_getter: Callable[..., Any | None] = get_live_runtime,
        now_ns: Callable[[], int] = monotonic_wall_ns,
        generated_at: Callable[[], str] = _utc_iso,
    ) -> None:
        self._engine_factory = engine_factory
        self._capture_loader = capture_loader
        self._runtime_getter = runtime_getter
        self._now_ns = now_ns
        self._generated_at = generated_at
        self._candidate_sets: list[dict[str, Any]] = []
        self._screen_outcomes: list[dict[str, Any]] = []
        self._refresh_lock = threading.Lock()
        self._refresh_in_progress = False
        self._runtime: Any | None = None
        self._enricher: MoomooCandidateEnricher | None = None

    def _validate_screens(self, screen_ids: Sequence[str] | None) -> list[str]:
        selected = list(SCREEN_LIBRARY) if screen_ids is None else [str(item).upper() for item in screen_ids]
        if not selected:
            raise ValueError("screen_ids must contain at least one screen")
        unknown = [screen_id for screen_id in selected if screen_id not in SCREEN_LIBRARY]
        if unknown:
            raise ValueError(f"UNKNOWN_SCREEN:{','.join(unknown)}")
        return selected

    def _ensure_capture_snapshot(self) -> None:
        if self._candidate_sets:
            return
        candidate_sets: list[dict[str, Any]] = []
        outcomes: list[dict[str, Any]] = []
        for screen_id in SCREEN_LIBRARY:
            captured = self._capture_loader(screen_id)
            if captured is None:
                outcomes.append(
                    {
                        "screen_id": screen_id,
                        "status": "UNAVAILABLE",
                        "candidate_count": 0,
                        "reason": "NO_SAVED_CAPTURE",
                    }
                )
                continue
            candidate_sets.append(captured)
            outcomes.append(
                {
                    "screen_id": screen_id,
                    "status": "FALLBACK",
                    "candidate_count": len(captured.get("candidates") or []),
                    "reason": "LATEST_SAVED_CAPTURE",
                }
            )
        self._candidate_sets = candidate_sets
        self._screen_outcomes = outcomes

    def _set_runtime(self, runtime: Any | None) -> MoomooCandidateEnricher:
        if self._enricher is None or runtime is not self._runtime:
            self._runtime = runtime
            self._enricher = MoomooCandidateEnricher(runtime)
        return self._enricher

    def _project(self, *, refresh_in_progress: bool | None = None) -> dict[str, Any]:
        self._ensure_capture_snapshot()
        runtime = self._runtime_getter(create=False)
        enricher = self._set_runtime(runtime)
        preliminary = aggregate_candidate_sets(self._candidate_sets, now_ns=self._now_ns())
        market_by_symbol = enricher.enrich(preliminary)
        ranked = aggregate_candidate_sets(
            self._candidate_sets,
            now_ns=self._now_ns(),
            market_by_symbol=market_by_symbol,
        )
        candidate_payloads = [candidate.to_dict() for candidate in ranked]
        lane_counts = {
            lane: sum(1 for candidate in ranked if lane in candidate.lanes)
            for lane in ("MOMENTUM", "SQUEEZE", "CATALYST", "SWING")
        }
        discovery_times = [
            str(candidate_set.get("received_at") or "")
            for candidate_set in self._candidate_sets
            if candidate_set.get("received_at")
        ]
        finviz_states = {row["status"] for row in self._screen_outcomes}
        if "PASS" in finviz_states and finviz_states == {"PASS"}:
            finviz_connection = "HEALTHY"
        elif finviz_states.intersection({"PASS", "FALLBACK"}):
            finviz_connection = "DEGRADED"
        else:
            finviz_connection = "UNAVAILABLE"
        provider_health = [
            {
                "provider": "FINVIZ_ELITE",
                "connection": finviz_connection,
                "role": "DISCOVERY",
                "reason": None if finviz_connection == "HEALTHY" else "USING_PARTIAL_OR_SAVED_DISCOVERY",
                "setup_command": "python tools/finviz/auth.py status",
            },
            enricher.health(),
        ]
        return {
            "available": bool(candidate_payloads),
            "mode": "SEMI_LIVE",
            "candidate_role": "INVESTIGATE",
            "execution_authority": "NONE",
            "generated_at": self._generated_at(),
            "discovery_as_of": max(discovery_times) if discovery_times else None,
            "refresh_in_progress": self._refresh_in_progress
            if refresh_in_progress is None
            else refresh_in_progress,
            "refresh_interval_seconds": 120,
            "poll_interval_seconds": 3,
            "provider_health": provider_health,
            "lane_counts": lane_counts,
            "screen_outcomes": [dict(row) for row in self._screen_outcomes],
            "candidates": candidate_payloads,
        }

    def read(self) -> dict[str, Any]:
        """Read current admitted state without Finviz calls or subscription mutation."""

        return self._project()

    def refresh(self, screen_ids: Sequence[str] | None = None) -> dict[str, Any]:
        selected = self._validate_screens(screen_ids)
        if not self._refresh_lock.acquire(blocking=False):
            return self._project(refresh_in_progress=True)
        self._refresh_in_progress = True
        try:
            engine = self._engine_factory()
            candidate_sets: list[dict[str, Any]] = []
            outcomes: list[dict[str, Any]] = []
            for screen_id in selected:
                try:
                    result = _as_dict(engine.run_screen(screen_id, force=True, persist=True))
                except Exception as exc:  # Per-screen degradation is part of the API contract.
                    captured = self._capture_loader(screen_id)
                    if captured is None:
                        outcomes.append(
                            {
                                "screen_id": screen_id,
                                "status": "UNAVAILABLE",
                                "candidate_count": 0,
                                "reason": str(exc),
                            }
                        )
                        continue
                    candidate_sets.append(captured)
                    outcomes.append(
                        {
                            "screen_id": screen_id,
                            "status": "FALLBACK",
                            "candidate_count": len(captured.get("candidates") or []),
                            "reason": str(exc),
                        }
                    )
                    continue
                candidate_sets.append(result)
                status = "PASS" if result.get("quality") != "UNAVAILABLE" else "UNAVAILABLE"
                outcomes.append(
                    {
                        "screen_id": screen_id,
                        "status": status,
                        "candidate_count": len(result.get("candidates") or []),
                        "reason": None if status == "PASS" else "FINVIZ_SCREEN_UNAVAILABLE",
                    }
                )
            self._candidate_sets = candidate_sets
            self._screen_outcomes = outcomes
            preliminary = aggregate_candidate_sets(candidate_sets, now_ns=self._now_ns())
            runtime = self._runtime_getter(create=True)
            self._set_runtime(runtime).reconcile(preliminary)
        finally:
            self._refresh_in_progress = False
            self._refresh_lock.release()
        return self._project(refresh_in_progress=False)


_SERVICE = MixedDiscoveryService()


def build_mixed_discover_payload() -> dict[str, Any]:
    return _SERVICE.read()


def refresh_mixed_discovery(screen_ids: Sequence[str] | None = None) -> dict[str, Any]:
    return _SERVICE.refresh(screen_ids)
