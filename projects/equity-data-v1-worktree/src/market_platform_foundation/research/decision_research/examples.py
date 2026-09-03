"""PIT-gated decision-example builder (DECISION-RESEARCH-001 §4/§11).

Builds ``ResearchExample``-shaped rows deterministically from the admitted
fixture slices (no RNG, no provider I/O):

- one **base** example per usable BIYA 1-minute bar carrying a deterministic,
  PIT-safe ``SQUEEZE_STATE`` research proxy (``IMP_DERIVED``, fixture scope);
- donor lane evidence (NVDA order-flow CVD, BOXL catalyst, BOXL MC16
  market-context) is attached to the earliest base example at-or-after each
  donor row's event time on the same trading day, so evidence availability is
  strictly PIT (``available_time_ns <= decision_time_ns``) and each donor row
  adds at most one example — reproducing the measured OOS caps.

Mark-based outcomes use a declared horizon and a deterministic friction, both
stamped ``execution_book_aware_v1``. No fill is required and no retroactive
Finviz feature is ever synthesized (``DEC-FV-001``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...normalization.equity_bars import iso_to_epoch_ns
from .pit_gate import reject_historical_finviz_screen_without_capture, validate_temporal_example

BAR_SOURCE_RELATIVE = (
    "short-squeeze-project/short-squeeze-core/tests/fixtures/validation/"
    "outcome_amendment/biya_market_bars_intraday.jsonl"
)
NVDA_ORDER_FLOW_SOURCE = "tests/fixtures/providers/order_flow/nvda_order_flow_slice.json"
BOXL_CATALYST_SOURCE = "tests/fixtures/providers/catalyst/boxl_catalyst_slice.json"
MC16_SOURCE = "tests/fixtures/market_context/boxl_multidoc_synthesis_expected.json"

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_HORIZON_BARS = 30  # 30 minutes
EVENT_MATCH_MAX_GAP_NS = 3_600_000_000_000  # 1 hour, same trading day only

# Spec §4 declared-only families: no labelled adapter backed by fixture data
# exists, so no example may ever be constructed with them (fail closed, never
# coerced). See the finalized family mapping in the implementation plan.
DECLARED_ONLY_FAMILIES = frozenset(
    {"OPTIONS_DEALER", "ATTENTION", "PARTICIPANT_CROWDING", "FINVIZ_DISCOVERY"}
)


def _epoch_day(epoch_ns: int) -> str:
    return datetime.fromtimestamp(epoch_ns // 1_000_000_000, tz=timezone.utc).date().isoformat()


def load_biya_bars(bar_source: Path) -> list[dict[str, Any]]:
    """Load and time-sort the pinned BIYA 1-minute bar fixture."""
    rows: list[dict[str, Any]] = []
    for line in bar_source.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("event_type") != "BAR":
            continue
        metadata = (record.get("provenance") or {}).get("provider_metadata") or {}
        bar_end = metadata.get("bar_end")
        if not bar_end:
            continue
        payload = record.get("payload") or {}
        try:
            close = float(payload["close"])
            open_ = float(payload["open"])
            high = float(payload["high"])
            low = float(payload["low"])
            volume = float(payload.get("volume", 0))
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(
            {
                "end_ns": iso_to_epoch_ns(bar_end),
                "close": close,
                "open": open_,
                "high": high,
                "low": low,
                "volume": volume,
            }
        )
    rows.sort(key=lambda row: row["end_ns"])
    return rows


def squeeze_state_proxy(bars: list[dict[str, Any]], index: int) -> tuple[str, float]:
    """Deterministic PIT-safe squeeze-state research proxy (fixture scope only).

    Uses only bars ``[0..index]`` so nothing after the decision influences it.
    Purely a fixture-derived proxy for the short-squeeze lane; not the donor
    squeeze engine and not a trading signal.
    """
    window = bars[max(0, index - 19) : index + 1]
    prior = bars[max(0, index - 19) : index]
    sma20 = sum(b["close"] for b in window) / len(window)
    vol_avg = sum(b["volume"] for b in prior) / max(len(prior), 1) if prior else 0.0
    breakout_high = max(b["high"] for b in prior) if prior else bars[index]["high"]
    bar = bars[index]
    up_trend = bar["close"] > sma20
    surge = vol_avg > 0 and bar["volume"] > 1.5 * vol_avg
    breakout = bar["close"] >= breakout_high
    if up_trend and surge and breakout:
        state = "ACTIVE_SQUEEZE"
    elif up_trend and surge:
        state = "LIVE_CONFIRMATION"
    elif up_trend:
        state = "IGNITION_WATCH"
    elif surge and bar["close"] < sma20:
        state = "VULNERABLE"
    else:
        state = "NONE"
    fuel = 100.0 * max(0.0, min(1.0, (bar["close"] - sma20) / max(sma20, 1e-9) + 0.5))
    fuel = round(fuel, 1)
    return state, fuel


def _friction_costs_bps(bar: dict[str, Any]) -> float:
    """Deterministic friction floor derived from the bar's own range proxy."""
    spread_proxy = (bar["high"] - bar["low"]) / bar["close"] if bar["close"] else 0.0
    return round(0.5 * spread_proxy * 10_000 + 1.0, 1)


def build_short_squeeze_examples(
    bars: list[dict[str, Any]] | None = None,
    *,
    horizon_bars: int = DEFAULT_HORIZON_BARS,
    bar_source: Path | None = None,
) -> list[dict[str, Any]]:
    """Base SS examples: one per usable BIYA bar with SQUEEZE_STATE + outcome."""
    if bars is None:
        bars = load_biya_bars(bar_source or _default_bar_source())
    if horizon_bars < 1:
        raise ValueError("HORIZON_BARS_INVALID")
    examples: list[dict[str, Any]] = []
    for index in range(len(bars) - horizon_bars):
        bar = bars[index]
        state, fuel = squeeze_state_proxy(bars, index)
        next_bar = bars[index + horizon_bars]
        raw_bps = (next_bar["close"] / bar["close"] - 1.0) * 10_000 if bar["close"] else 0.0
        costs_bps = _friction_costs_bps(bar)
        forward_return_bps = round(raw_bps - costs_bps, 3)
        examples.append(
            {
                "example_id": f"ss-ex-{index:06d}",
                "instrument_id": "BIYA",
                "decision_time_ns": bar["end_ns"],
                "features": [
                    {
                        "evidence_family": "SQUEEZE_STATE",
                        "feature_source": "BIYA_MARKET_BARS_INTRADAY_FIXTURE",
                        "available_time_ns": bar["end_ns"] - 1,
                        "quality_flags": ["FIXTURE_SQUEEZE_PROXY"],
                        "freshness_ms": 1,
                        "authority": "IMP_DERIVED",
                        "value": {"state": state, "fuel_pct": fuel},
                    }
                ],
                "outcome_time_ns": next_bar["end_ns"],
                "outcome": {
                    "positive": forward_return_bps > 0,
                    "forward_return_bps": forward_return_bps,
                    "horizon_ns": horizon_bars * 60 * 1_000_000_000,
                    "costs_bps": costs_bps,
                    "cost_model_version": "execution_book_aware_v1",
                },
            }
        )
    return examples


def _default_bar_source() -> Path:
    return REPO_ROOT.parent / BAR_SOURCE_RELATIVE


def load_donor_rows(family: str, repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Load donor rows as ``{event_ns, feature}`` dicts for a family."""
    if family in DECLARED_ONLY_FAMILIES:
        raise ValueError(f"DECLARED_ONLY_FAMILY_NOT_BUILDABLE:{family}")
    root = repo_root or REPO_ROOT
    rows: list[dict[str, Any]] = []
    if family == "ORDER_FLOW_CVD":
        payload = json.loads((root / NVDA_ORDER_FLOW_SOURCE).read_text(encoding="utf-8"))
        cvd_summary = payload.get("cvd_summary") or {}
        for bar in payload.get("bars") or []:
            event_ns = iso_to_epoch_ns(str(bar["date"]))
            rows.append(
                {
                    "event_ns": event_ns,
                    "feature": {
                        "evidence_family": "ORDER_FLOW_CVD",
                        "feature_source": "NVDA_ORDER_FLOW_SLICE",
                        "available_time_ns": event_ns,
                        "quality_flags": [],
                        "freshness_ms": 0,
                        "authority": "IMP_DERIVED",
                        "value": {
                            "session_cvd": bar.get("delta"),
                            "cvd_slope": cvd_summary.get("cvd_slope"),
                            "volume": bar.get("volume"),
                        },
                    },
                }
            )
    elif family == "CATALYST":
        payload = json.loads((root / BOXL_CATALYST_SOURCE).read_text(encoding="utf-8"))
        for row in payload.get("catalysts") or []:
            event_ns = iso_to_epoch_ns(str(row["event_time"]))
            rows.append(
                {
                    "event_ns": event_ns,
                    "feature": {
                        "evidence_family": "CATALYST",
                        "feature_source": "BOXL_CATALYST_SLICE",
                        "available_time_ns": event_ns,
                        "quality_flags": [],
                        "freshness_ms": 0,
                        "authority": "MODEL_OUTPUT",
                        "value": {
                            "catalyst_type": row.get("catalyst_type"),
                            "news_score": row.get("news_score"),
                            "headline": row.get("headline"),
                        },
                    },
                }
            )
    elif family == "MARKET_CONTEXT":
        payload = json.loads((root / MC16_SOURCE).read_text(encoding="utf-8"))
        for summary in payload.get("synthesis_summaries") or []:
            event_ns = iso_to_epoch_ns(str(summary["available_time"]))
            flags = list(summary.get("quality_flags") or [])
            rows.append(
                {
                    "event_ns": event_ns,
                    "feature": {
                        "evidence_family": "MARKET_CONTEXT",
                        "feature_source": "BOXL_MC16_EXPECTED",
                        "available_time_ns": event_ns,
                        "quality_flags": flags,
                        "freshness_ms": 0,
                        "authority": "MODEL_OUTPUT",
                        "value": {
                            "regime_label": "RISK_ON" if summary.get("theme_agreement_score") is not None and not summary.get("contradiction_detected") else None,
                            "theme_agreement_score": summary.get("theme_agreement_score"),
                            "contradiction_detected": summary.get("contradiction_detected"),
                            "consolidated_channels": summary.get("consolidated_channels"),
                        },
                    },
                }
            )
    rows.sort(key=lambda row: row["event_ns"])
    return rows


def attach_donor_evidence(
    examples: list[dict[str, Any]],
    family: str,
    donor_rows: list[dict[str, Any]],
    *,
    max_gap_ns: int = EVENT_MATCH_MAX_GAP_NS,
) -> list[dict[str, Any]]:
    """Attach each donor row to the earliest same-day base example at-or-after it.

    One donor row adds at most one example; features are only added when strictly
    PIT-valid, preserving every emitted example's temporal integrity.
    """
    by_day: dict[str, list[tuple[int, int]]] = {}
    for index, example in enumerate(examples):
        by_day.setdefault(_epoch_day(example["decision_time_ns"]), []).append(
            (example["decision_time_ns"], index)
        )
    used: set[int] = set()
    for row in donor_rows:
        day = _epoch_day(row["event_ns"])
        candidates = by_day.get(day) or []
        target = None
        for decision_ns, index in sorted(candidates):
            if index in used:
                continue
            if decision_ns >= row["event_ns"] and decision_ns - row["event_ns"] <= max_gap_ns:
                target = index
                break
        if target is None:
            continue
        used.add(target)
        examples[target]["features"].append(dict(row["feature"]))


def validate_examples(examples: list[dict[str, Any]]) -> list[str]:
    """Fail-closed PIT + Finviz-scope validation over every emitted example.

    Returns a flat list of every violation reason (empty == all valid). Raises
    nothing itself; callers choose to raise. Each feature also runs
    ``reject_historical_finviz_screen_without_capture`` so a retrospective
    Finviz screen without a captured snapshot is impossible (``DEC-FV-001``).
    """
    violations: list[str] = []
    for example in examples:
        ok, reasons = validate_temporal_example(example)
        if not ok:
            violations.extend(
                f"{example.get('example_id')}:{reason}" for reason in reasons
            )
        for feature in example.get("features") or []:
            ok, reason = reject_historical_finviz_screen_without_capture(
                feature_source=str(feature.get("feature_source") or ""),
                capture_present=bool(feature.get("capture_snapshot_id")),
            )
            if not ok:
                violations.append(
                    f"{example.get('example_id')}:{feature.get('evidence_family')}:{reason}"
                )
    return violations


def build_ss_family_examples(
    bars: list[dict[str, Any]] | None = None,
    *,
    horizon_bars: int = DEFAULT_HORIZON_BARS,
    bar_source: Path | None = None,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Full deterministic fixture: base BIYA examples + donor-lane evidence.

    Fails closed: any example that violates the PIT gate or a declared-only /
    Finviz-scope rule raises instead of silently emitting bad data.
    """
    examples = build_short_squeeze_examples(bars, horizon_bars=horizon_bars, bar_source=bar_source)
    for family in ("ORDER_FLOW_CVD", "CATALYST", "MARKET_CONTEXT"):
        attach_donor_evidence(examples, family, load_donor_rows(family, repo_root=repo_root))
    violations = validate_examples(examples)
    if violations:
        raise RuntimeError(
            "EXAMPLES_FAILED_VALIDATION:" + ";".join(sorted(set(violations)))
        )
    return examples


def examples_root_hash(examples: list[dict[str, Any]]) -> str:
    payload = [canonical_bytes(example) for example in examples]
    return sha256_bytes(b"".join(sorted(payload)))


__all__ = [
    "attach_donor_evidence",
    "build_short_squeeze_examples",
    "build_ss_family_examples",
    "examples_root_hash",
    "load_biya_bars",
    "load_donor_rows",
    "squeeze_state_proxy",
    "validate_examples",
]
