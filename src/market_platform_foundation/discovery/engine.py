"""Discovery engine — Finviz screen → CandidateSet."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from ..finviz.fields import field_inventory_summary
from ..finviz.provider_role import PROVIDER_ID
from ..finviz.screener import FinvizScreenerClient, FinvizScreenerRow
from ..finviz.symbols import finviz_to_canonical
from .capture import persist_discovery_capture
from .models import CandidateSet, DiscoveryCandidate, ScreenDefinition
from .screens import SCHEMA_VERSION, get_screen
from .transitions import compute_transitions, load_previous_symbols


def _utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _match_reasons(row: FinvizScreenerRow, screen: ScreenDefinition) -> list[str]:
    reasons: list[str] = []
    if row.short_float_pct is not None and "short" in screen.filters:
        reasons.append(f"Short Float {row.short_float_pct:.1f}%")
    if row.rel_volume is not None:
        reasons.append(f"RVOL {row.rel_volume:.2f}")
    if row.change_pct is not None:
        reasons.append(f"{row.change_pct:+.1f}%")
    if row.recommendation:
        reasons.append(f"Analyst {row.recommendation}")
    if row.earnings_date:
        reasons.append(f"Earnings {row.earnings_date}")
    if not reasons:
        reasons.append(f"Matched screen {screen.screen_id}")
    return reasons


def _row_quality(row: FinvizScreenerRow, screen: ScreenDefinition) -> str:
    missing = [
        field
        for field in screen.required_fields
        if row.canonical_metrics().get(field) is None
    ]
    if missing:
        return "DEGRADED"
    return "PASS"


def _inspection_priority(row: FinvizScreenerRow, screen: ScreenDefinition, rank: int) -> int:
    score = 100 - rank
    if row.rel_volume is not None:
        score += int(min(row.rel_volume, 5) * 10)
    if row.short_float_pct is not None:
        score += int(min(row.short_float_pct, 50))
    if screen.screen_id == "SHORT_SQUEEZE_DISCOVERY" and row.short_float_pct:
        score += 5
    return score


def _rank_rows(rows: list[FinvizScreenerRow], screen: ScreenDefinition) -> list[FinvizScreenerRow]:
    if screen.sort == "sh_short":
        return sorted(rows, key=lambda r: -(r.short_float_pct or 0))
    if screen.sort == "sh_relvol":
        return sorted(rows, key=lambda r: -(r.rel_volume or 0))
    if screen.sort == "ta_change" or screen.sort == "sh_change":
        return sorted(rows, key=lambda r: -(abs(r.change_pct or 0)))
    return list(rows)


class DiscoveryEngine:
    def __init__(self, *, screener: FinvizScreenerClient | None = None) -> None:
        self._screener = screener or FinvizScreenerClient()

    def run_screen(
        self,
        screen_id: str,
        *,
        force: bool = False,
        previous_catalog: dict[str, Any] | None = None,
        persist: bool = True,
    ) -> CandidateSet:
        screen = get_screen(screen_id)
        if screen is None:
            raise ValueError(f"UNKNOWN_SCREEN:{screen_id}")
        requested_at = _utc_iso()
        export = self._screener.fetch_export(filter_expr=screen.filters, force=force)
        received_at = str(export.get("received_at") or _utc_iso())
        available_ns = int(export.get("available_time_ns") or 0)
        run_id = uuid.uuid4().hex
        quality = "PASS" if export.get("success") else "UNAVAILABLE"
        rows = export.get("rows") or []
        ranked = _rank_rows(rows, screen)[:screen.max_results]
        candidates: list[DiscoveryCandidate] = []
        for idx, row in enumerate(ranked):
            mapping = finviz_to_canonical(row.ticker)
            candidates.append(
                DiscoveryCandidate(
                    instrument_id=mapping.instrument_id,
                    provider_symbol=mapping.provider_symbol,
                    screen_id=screen.screen_id,
                    screen_version=screen.version,
                    discovered_at=received_at,
                    available_time_ns=available_ns,
                    matched_reasons=_match_reasons(row, screen),
                    metrics=row.canonical_metrics(),
                    inspection_priority=_inspection_priority(row, screen, idx),
                    quality=_row_quality(row, screen),
                    provenance={
                        "provider": PROVIDER_ID,
                        "screen_filters": screen.filters,
                        "field_inventory": field_inventory_summary(list(export.get("columns") or [])),
                    },
                    rank=idx + 1,
                )
            )
        previous = load_previous_symbols(previous_catalog)
        current = {c.instrument_id for c in candidates}
        reentered = previous - current  # simplified; true reentry needs history
        transitions = compute_transitions(
            previous_symbols=previous,
            current_symbols=current,
            reentered_symbols=reentered & current,
        )
        for candidate in candidates:
            match = next(
                (t for t in transitions if t["instrument_id"] == candidate.instrument_id),
                None,
            )
            if match:
                candidate.transition = match["transition"]
        candidate_set = CandidateSet(
            run_id=run_id,
            screen_id=screen.screen_id,
            screen_version=screen.version,
            screen_definition=screen.to_dict(),
            requested_at=requested_at,
            received_at=received_at,
            available_time_ns=available_ns,
            provider=PROVIDER_ID,
            schema_version=SCHEMA_VERSION,
            candidate_count=len(candidates),
            candidates=candidates,
            quality=quality if candidates else "UNAVAILABLE",
            raw_response_hash=export.get("raw_response_hash"),
            transitions=transitions,
        )
        if persist and export.get("success"):
            persist_discovery_capture(candidate_set)
        return candidate_set
