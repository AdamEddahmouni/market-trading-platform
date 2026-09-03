"""Observation-only near-miss / shadow outcome tracker (no execution).

Why this exists
---------------
Most Path B / gated Path A candidates end as LOG (``low_confidence``,
``weak_lean``, ``liquidity_reject``, quote rejects, etc.). Without shadows we
cannot tell whether the gates were protective or over-filtering.

For each tracked LOG, this module looks up a would-be ATM contract, records the
entry mark, then checkpoints later (default 60m / 240m) and at EOD using the
*same* TP/SL/flatten rules as live exits — but never places an order.

Use EOD aggregates (``state/near_miss_eod_*.json``, Telegram section) to study
whether loosening a gate would have helped — especially when many rows die on
``no_listed_chain`` (shadow PnL is then uninformative by design).

State files: ``state/near_miss_tracker_{date}.json``, ``state/near_miss_eod_{date}.json``.

Merge notes: observation-only shadow PnL — reusable gate-tuning methodology;
option contract lookup is options-specific but the checkpoint/EOD simulation
pattern applies to any instrument with explicit exit rules.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.option_contracts import fetch_option_mark, lookup_atm_contract
from agent.portfolio import evaluate_option_exit_rule
from agent.quote_sanity import validate_entry_quote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"

DEFAULT_TRACK_REASON_CODES = frozenset(
    {
        "low_confidence",
        "weak_lean",
        "liquidity_reject",
        "options_not_clear",
        "stale_quote",
        "identical_quote_pause",
        "no_contract",
        "quote_rejected",
    }
)

DEFAULT_CONFIDENCE_BANDS: List[Tuple[int, int]] = [(60, 64), (45, 59), (0, 44)]

CHECKPOINT_OFFSETS_MIN = {"t60": 60, "t240": 240}


def _checkpoint_offsets(settings: Dict[str, Any]) -> Dict[str, int]:
    cfg = _tracker_cfg(settings)
    raw = cfg.get("checkpoint_offsets_min")
    if isinstance(raw, dict) and raw:
        out: Dict[str, int] = {}
        for key, val in raw.items():
            try:
                minutes = int(val)
            except (TypeError, ValueError):
                continue
            if minutes > 0:
                out[str(key)] = minutes
        if out:
            return out
    return dict(CHECKPOINT_OFFSETS_MIN)


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc)


def _session_date(now: Optional[datetime] = None) -> str:
    return (now or _now_et()).date().isoformat()


def _tracker_path(session_date: Optional[str] = None) -> Path:
    day = session_date or _session_date()
    return STATE_DIR / f"near_miss_tracker_{day}.json"


def _near_miss_eod_path(session_date: str) -> Path:
    return STATE_DIR / f"near_miss_eod_{session_date}.json"


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _load_tracker(session_date: Optional[str] = None) -> Dict[str, Any]:
    path = _tracker_path(session_date)
    try:
        if not path.exists():
            return {"session_date": session_date or _session_date(), "items": {}}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"session_date": session_date or _session_date(), "items": {}}
        data.setdefault("items", {})
        return data
    except Exception:
        return {"session_date": session_date or _session_date(), "items": {}}


def _save_tracker(data: Dict[str, Any], session_date: Optional[str] = None) -> Path:
    day = str(data.get("session_date") or session_date or _session_date())
    data["session_date"] = day
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _tracker_path(day)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(path)
    return path


def _tracker_cfg(settings: Dict[str, Any]) -> Dict[str, Any]:
    return dict(settings.get("near_miss_tracker") or {})


def _track_reason_codes(settings: Dict[str, Any]) -> frozenset:
    cfg = _tracker_cfg(settings)
    codes = cfg.get("track_reason_codes")
    if isinstance(codes, list) and codes:
        return frozenset(str(c) for c in codes)
    return DEFAULT_TRACK_REASON_CODES


def _confidence_bands(settings: Dict[str, Any]) -> List[Tuple[int, int]]:
    cfg = _tracker_cfg(settings)
    raw = cfg.get("confidence_bands")
    if isinstance(raw, list) and raw:
        bands: List[Tuple[int, int]] = []
        for row in raw:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                bands.append((int(row[0]), int(row[1])))
        if bands:
            return bands
    return list(DEFAULT_CONFIDENCE_BANDS)


def _threshold_pct(trade_entry: Dict[str, Any], settings: Dict[str, Any]) -> float:
    exec_cfg = settings.get("execution") or {}
    source = str(trade_entry.get("signal_source") or "").lower().strip()
    if source == "expiry":
        return float(exec_cfg.get("min_confidence_for_path_b", 65.0))
    return float(exec_cfg.get("min_confidence_for_action", 40.0))


def _confidence_pct(trade_entry: Dict[str, Any]) -> float:
    meta = trade_entry.get("decision_meta") or {}
    for key in ("confidence_pct",):
        val = meta.get(key)
        if val is not None:
            return float(val)
    if trade_entry.get("confidence_pct") is not None:
        return float(trade_entry["confidence_pct"])
    if trade_entry.get("lean_pct") is not None:
        return float(trade_entry["lean_pct"])
    return 0.0


def _is_options_shadow_candidate(trade_entry: Dict[str, Any]) -> bool:
    instrument = str(trade_entry.get("instrument_hint") or trade_entry.get("instrument") or "").lower()
    source = str(trade_entry.get("signal_source") or "").lower()
    if instrument == "option" or source == "expiry":
        return True
    if trade_entry.get("options_bias") is not None:
        return True
    return False


def _resolve_option_side(trade_entry: Dict[str, Any]) -> Optional[str]:
    lean = str(trade_entry.get("lean") or "").upper().strip()
    if lean == "BUY":
        return "call"
    if lean == "SELL":
        return "put"
    bias = str(trade_entry.get("options_bias") or "").lower().strip()
    if bias == "bullish":
        return "call"
    if bias == "bearish":
        return "put"
    decision = str(trade_entry.get("decision") or "").upper().strip()
    if decision == "BUY":
        return "call"
    if decision == "SELL":
        return "put"
    return None


def _pnl_pct(entry_premium: float, mark: float) -> Optional[float]:
    if entry_premium <= 0 or mark <= 0:
        return None
    return round((mark - entry_premium) / entry_premium * 100.0, 2)


def _eod_due_at(rejected_at: datetime, settings: Dict[str, Any]) -> datetime:
    trading = settings.get("trading") or {}
    exits = trading.get("options_exits") or {}
    text = str(exits.get("eod_flatten_et", "15:45")).strip()
    parts = text.split(":")
    hour = int(parts[0]) if parts else 15
    minute = int(parts[1]) if len(parts) > 1 else 45
    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:
        et = timezone.utc
    local = rejected_at.astimezone(et)
    due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due < local:
        due = local
    return due


def _build_checkpoints(rejected_at: datetime, settings: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    checkpoints: Dict[str, Dict[str, Any]] = {}
    for key, minutes in _checkpoint_offsets(settings).items():
        due = rejected_at + timedelta(minutes=minutes)
        checkpoints[key] = {
            "due_at": due.isoformat(),
            "status": "pending",
            "premium": None,
            "pnl_pct": None,
            "recorded_at": None,
        }

    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:
        et = timezone.utc
    local = rejected_at.astimezone(et)

    # Next regular session EOD mark (skip weekends).
    nxt = local + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt = nxt + timedelta(days=1)
    trading = settings.get("trading") or {}
    exits = trading.get("options_exits") or {}
    text = str(exits.get("eod_flatten_et", "15:45")).strip()
    parts = text.split(":")
    hour = int(parts[0]) if parts else 15
    minute = int(parts[1]) if len(parts) > 1 else 45
    next_day_eod = nxt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    checkpoints["next_day_eod"] = {
        "due_at": next_day_eod.isoformat(),
        "status": "pending",
        "premium": None,
        "pnl_pct": None,
        "recorded_at": None,
    }

    from agent.market_session import this_friday_date_et

    friday = this_friday_date_et(local)
    friday_close = datetime(
        friday.year, friday.month, friday.day, hour, minute, 0, 0, tzinfo=et
    )
    if friday_close < local:
        friday_close = local
    checkpoints["friday_close"] = {
        "due_at": friday_close.isoformat(),
        "status": "pending",
        "premium": None,
        "pnl_pct": None,
        "recorded_at": None,
    }

    # Keep same-day eod for compatibility when rejection is on Friday / same day.
    eod_due = _eod_due_at(rejected_at, settings)
    checkpoints["eod"] = {
        "due_at": eod_due.isoformat(),
        "status": "pending",
        "premium": None,
        "pnl_pct": None,
        "recorded_at": None,
    }
    return checkpoints


def _cooldown_blocked(
    data: Dict[str, Any],
    ticker: str,
    reason_code: str,
    rejected_at: datetime,
    cooldown_minutes: int,
) -> bool:
    if cooldown_minutes <= 0:
        return False
    items = data.get("items") or {}
    if not isinstance(items, dict):
        return False
    cutoff = rejected_at - timedelta(minutes=cooldown_minutes)
    key_ticker = ticker.upper().strip()
    for row in items.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("ticker", "")).upper() != key_ticker:
            continue
        if str(row.get("reason_code", "")) != reason_code:
            continue
        prev = _parse_ts(str(row.get("rejected_at", "")))
        if prev and prev >= cutoff:
            return True
    return False


def _shadow_outcome_from_rule(rule: str) -> str:
    if rule == "take_profit":
        return "would_have_won"
    if rule == "stop_loss":
        return "would_have_lost"
    if rule in {"eod_flatten", "deadline_flatten", "expired"}:
        return "would_have_flattened_flat"
    return "unknown"


def _band_label(confidence: float, bands: List[Tuple[int, int]]) -> str:
    score = int(round(confidence))
    for lo, hi in bands:
        if lo <= score <= hi:
            return f"{lo}-{hi}"
    return "other"


def maybe_record_near_miss(
    trade_entry: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Record one near-miss rejection with would-be contract and entry quote.

    Only LOG decisions with configured reason codes are tracked. Cooldown per
    ticker+reason avoids flooding the tracker when the agent re-evaluates the
    same name every cycle. Quote sanity failures still record the miss so we
    can count how often "would trade" dies on stale marks.
    """
    if not settings:
        return None
    cfg = _tracker_cfg(settings)
    if not bool(cfg.get("enabled", True)):
        return None
    if str(trade_entry.get("decision", "")).upper() != "LOG":
        return None
    if not _is_options_shadow_candidate(trade_entry):
        return None

    reason_code = str(
        trade_entry.get("decision_reason_code")
        or trade_entry.get("review_reason_code")
        or ""
    ).strip()
    if reason_code not in _track_reason_codes(settings):
        return None

    option_side = _resolve_option_side(trade_entry)
    if not option_side:
        return None

    ticker = str(trade_entry.get("ticker", "")).upper().strip()
    rejected_at = _parse_ts(str(trade_entry.get("timestamp", ""))) or datetime.now(timezone.utc)
    cooldown = int(cfg.get("cooldown_minutes", 60))

    data = _load_tracker(_session_date(rejected_at.astimezone(timezone.utc)))
    if _cooldown_blocked(data, ticker, reason_code, rejected_at, cooldown):
        return None

    threshold = _threshold_pct(trade_entry, settings)
    confidence = _confidence_pct(trade_entry)
    distance = round(confidence - threshold, 2)

    trading = settings.get("trading") or {}
    from agent.market_session import effective_options_max_dte

    max_dte = int(effective_options_max_dte(settings))
    spot = float(trade_entry.get("price_at_signal") or 0.0)

    contract_symbol = ""
    expiration = ""
    entry_premium = 0.0
    has_nbbo = False
    entry_quote_status = "skipped_no_contract"
    entry_quote_reject: Optional[str] = None
    contract_lookup_status = ""
    contract_lookup_detail = ""
    followup_status = "skipped"
    alpaca_error_kind: Optional[str] = None

    lookup = lookup_atm_contract(ticker, option_side, spot, max_dte=max_dte, settings=settings)
    contract = lookup.get("contract") if isinstance(lookup, dict) else None
    contract_lookup_status = str((lookup or {}).get("status") or "")
    contract_lookup_detail = str((lookup or {}).get("detail") or "")
    if isinstance(contract, dict):
        contract_symbol = str(contract.get("contract_symbol", ""))
        expiration = str(contract.get("expiration", ""))
        entry_premium = float(contract.get("premium") or 0.0)
        has_nbbo = bool(contract.get("has_nbbo"))
        quote_ok, quote_reason, _details = validate_entry_quote(
            ticker,
            contract_symbol,
            entry_premium,
            settings=settings,
            has_nbbo=has_nbbo,
            record=False,
        )
        if quote_ok:
            entry_quote_status = "ok"
            followup_status = "active"
        else:
            entry_quote_status = "skipped_stale_quote"
            entry_quote_reject = quote_reason
    else:
        # Distinguish confirmed misses from Alpaca provider failures / missing keys.
        if contract_lookup_status in {
            "no_0dte_chain_exists",
            "no_options_listed",
            "no_quoteable_premium",
            "contract_lookup_failed",
            "alpaca_confirmed_empty",
            "alpaca_error",
            "alpaca_no_credentials",
        }:
            entry_quote_status = contract_lookup_status
        else:
            entry_quote_status = "skipped_no_contract"
            contract_lookup_status = contract_lookup_status or "skipped_no_contract"
        entry_quote_reject = contract_lookup_detail or contract_lookup_status
        if contract_lookup_status == "alpaca_error":
            kind = (lookup or {}).get("alpaca_error_kind")
            alpaca_error_kind = str(kind) if kind else None

    item_id = f"{ticker}|{rejected_at.isoformat()}|{reason_code}"
    item = {
        "id": item_id,
        "ticker": ticker,
        "rejected_at": rejected_at.isoformat(),
        "signal_source": str(trade_entry.get("signal_source") or ""),
        "reason_code": reason_code,
        "confidence_pct": confidence,
        "threshold_pct": threshold,
        "distance_from_threshold": distance,
        "options_bias": trade_entry.get("options_bias"),
        "options_score": trade_entry.get("options_score"),
        "lean": trade_entry.get("lean"),
        "lean_pct": trade_entry.get("lean_pct"),
        "agreement_confidence": trade_entry.get("agreement_confidence")
        if trade_entry.get("agreement_confidence") is not None
        else (trade_entry.get("decision_meta") or {}).get("agreement_confidence"),
        "n_dir": trade_entry.get("n_dir")
        if trade_entry.get("n_dir") is not None
        else (trade_entry.get("decision_meta") or {}).get("n_dir"),
        "would_be_side": option_side,
        "contract_symbol": contract_symbol,
        "expiration": expiration,
        "entry_premium": entry_premium,
        "has_nbbo": has_nbbo,
        "entry_quote_status": entry_quote_status,
        "entry_quote_reject": entry_quote_reject,
        "contract_lookup_status": contract_lookup_status,
        "contract_lookup_detail": contract_lookup_detail,
        "contract_lookup_provider": (lookup or {}).get("provider"),
        "alpaca_error_kind": alpaca_error_kind,
        "nearest_listed_dte": (lookup or {}).get("nearest_listed_dte"),
        "followup_status": followup_status,
        "checkpoints": _build_checkpoints(rejected_at, settings),
        "first_exit_rule": None,
        "first_exit_at": None,
        "shadow_outcome": None,
    }

    items = data.setdefault("items", {})
    if not isinstance(items, dict):
        items = {}
        data["items"] = items
    items[item_id] = item
    _save_tracker(data)
    print(
        f"[near_miss] recorded {ticker} {reason_code} conf={confidence:.0f} "
        f"dist={distance:+.0f} followup={followup_status} quote={entry_quote_status}"
        + (f" ({contract_lookup_detail})" if contract_lookup_detail and entry_quote_status != "ok" else "")
    )
    return item


def _update_shadow_outcome(item: Dict[str, Any]) -> None:
    rule = item.get("first_exit_rule")
    if rule:
        item["shadow_outcome"] = _shadow_outcome_from_rule(str(rule))
        return
    eod = (item.get("checkpoints") or {}).get("eod") or {}
    if str(eod.get("status")) == "unknown":
        item["shadow_outcome"] = "unknown"
    elif item.get("followup_status") == "complete" and not rule:
        if eod.get("pnl_pct") is not None:
            item["shadow_outcome"] = "would_have_flattened_flat"
        else:
            item["shadow_outcome"] = "unknown"


def tick_pending_near_misses(
    settings: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> int:
    """
    Process due checkpoints and exit-rule checks for active near-misses.

    Call from the live loop periodically. Shadows use the same
    ``evaluate_option_exit_rule`` as real positions so “would have hit SL”
    is comparable to live COIN-style stops — still observation only.
    """
    cfg = _tracker_cfg(settings)
    if not bool(cfg.get("enabled", True)):
        return 0

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    # Cross-session: tick today's file plus recent active trackers (multi-day CPs).
    session_dates: List[str] = []
    today = _session_date(current.astimezone(timezone.utc))
    session_dates.append(today)
    for path in sorted(STATE_DIR.glob("near_miss_tracker_*.json"), reverse=True)[:10]:
        stem = path.stem  # near_miss_tracker_YYYY-MM-DD
        day = stem.replace("near_miss_tracker_", "")
        if len(day) == 10 and day not in session_dates:
            session_dates.append(day)

    total_updated = 0
    for day in session_dates:
        data = _load_tracker(day)
        items = data.get("items") or {}
        if not isinstance(items, dict) or not items:
            continue

        updated = 0
        for item in items.values():
            if not isinstance(item, dict):
                continue
            if str(item.get("followup_status")) != "active":
                continue
            if str(item.get("entry_quote_status")) != "ok":
                continue

            contract_symbol = str(item.get("contract_symbol") or "")
            entry_premium = float(item.get("entry_premium") or 0.0)
            expiration = str(item.get("expiration") or "")
            if not contract_symbol or entry_premium <= 0:
                continue

            try:
                from zoneinfo import ZoneInfo

                et = ZoneInfo("America/New_York")
            except Exception:
                et = timezone.utc
            now_et = current.astimezone(et)

            mark = fetch_option_mark(contract_symbol)
            changed = False

            if not item.get("first_exit_rule") and mark > 0:
                rule = evaluate_option_exit_rule(
                    entry=entry_premium,
                    mark=mark,
                    expiration=expiration,
                    settings=settings,
                    now_et=now_et,
                )
                if rule:
                    item["first_exit_rule"] = rule
                    item["first_exit_at"] = current.isoformat()
                    item["shadow_outcome"] = _shadow_outcome_from_rule(rule)
                    changed = True

            checkpoints = item.get("checkpoints") or {}
            for cp_key, cp in checkpoints.items():
                if not isinstance(cp, dict):
                    continue
                if str(cp.get("status")) != "pending":
                    continue
                due = _parse_ts(str(cp.get("due_at", "")))
                if not due or current < due:
                    continue
                cp_mark = fetch_option_mark(contract_symbol)
                if cp_mark <= 0:
                    cp["status"] = "unknown"
                else:
                    cp["status"] = "recorded"
                    cp["premium"] = round(cp_mark, 4)
                    pnl = _pnl_pct(entry_premium, cp_mark)
                    cp["pnl_pct"] = pnl
                cp["recorded_at"] = current.isoformat()
                changed = True

            terminal_keys = ("friday_close", "eod")
            terminal_done = False
            for key in terminal_keys:
                tcp = checkpoints.get(key) or {}
                if str(tcp.get("status")) in {"recorded", "unknown"}:
                    terminal_done = True
                    break

            if terminal_done:
                item["followup_status"] = "complete"
                _update_shadow_outcome(item)
                changed = True
            elif item.get("first_exit_rule"):
                all_due_done = True
                for cp_key, cp in checkpoints.items():
                    if not isinstance(cp, dict):
                        continue
                    due = _parse_ts(str(cp.get("due_at", "")))
                    if due and current >= due and str(cp.get("status")) == "pending":
                        all_due_done = False
                        break
                if all_due_done:
                    item["followup_status"] = "complete"
                    _update_shadow_outcome(item)
                    changed = True

            if changed:
                updated += 1

        if updated:
            _save_tracker(data, day)
            total_updated += updated
    return total_updated


def build_near_miss_eod_section(
    session_date: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate near-miss shadow outcomes for one session."""
    day = session_date or _session_date()
    data = _load_tracker(day)
    items = list((data.get("items") or {}).values())
    items = [r for r in items if isinstance(r, dict)]

    bands = _confidence_bands(settings or {})
    by_reason: Counter = Counter()
    low_conf_outcomes: Counter = Counter()
    band_stats: Dict[str, Dict[str, int]] = {}

    for lo, hi in bands:
        band_stats[f"{lo}-{hi}"] = {
            "count": 0,
            "would_have_won": 0,
            "would_have_lost": 0,
            "would_have_flattened_flat": 0,
            "unknown": 0,
            "hit_tp": 0,
        }

    active_followup = 0
    with_entry_quote = 0
    by_quote_status: Counter = Counter()
    no_0dte_n = 0
    lookup_failed_n = 0
    alpaca_error_n = 0
    alpaca_confirmed_empty_n = 0
    alpaca_no_credentials_n = 0
    by_alpaca_error_kind: Counter = Counter()

    for row in items:
        reason = str(row.get("reason_code") or "other")
        by_reason[reason] += 1
        quote_status = str(row.get("entry_quote_status") or "unknown")
        by_quote_status[quote_status] += 1
        if quote_status == "ok":
            with_entry_quote += 1
        if quote_status in {
            "no_0dte_chain_exists",
            "no_options_listed",
            "alpaca_confirmed_empty",
        }:
            no_0dte_n += 1
        if quote_status == "alpaca_confirmed_empty":
            alpaca_confirmed_empty_n += 1
        if quote_status == "alpaca_error":
            alpaca_error_n += 1
            kind = str(row.get("alpaca_error_kind") or "unknown")
            by_alpaca_error_kind[kind] += 1
        if quote_status == "alpaca_no_credentials":
            alpaca_no_credentials_n += 1
        if quote_status == "contract_lookup_failed":
            lookup_failed_n += 1
        if str(row.get("followup_status")) == "active":
            active_followup += 1

        if reason != "low_confidence":
            continue
        outcome = str(row.get("shadow_outcome") or "unknown")
        if outcome in {"would_have_won", "would_have_lost", "would_have_flattened_flat", "unknown"}:
            low_conf_outcomes[outcome] += 1

        conf = float(row.get("confidence_pct") or 0.0)
        label = _band_label(conf, bands)
        if label not in band_stats:
            band_stats[label] = {
                "count": 0,
                "would_have_won": 0,
                "would_have_lost": 0,
                "would_have_flattened_flat": 0,
                "unknown": 0,
                "hit_tp": 0,
            }
        band_stats[label]["count"] += 1
        if outcome in band_stats[label]:
            band_stats[label][outcome] += 1
        if str(row.get("first_exit_rule")) == "take_profit":
            band_stats[label]["hit_tp"] += 1

    total = len(items)
    low_n = int(by_reason.get("low_confidence", 0))
    liq_n = int(by_reason.get("liquidity_reject", 0))

    band_60_64 = band_stats.get("60-64", {})
    band_60_64_count = int(band_60_64.get("count", 0))
    band_60_64_tp = int(band_60_64.get("hit_tp", 0))

    headline_parts = [f"{total} near-misses"]
    if low_n or liq_n:
        headline_parts.append(f"({low_n} low_confidence, {liq_n} liquidity_reject)")
    headline_detail = ""
    if band_60_64_count:
        headline_detail = (
            f"Of the {band_60_64_count} that scored 60-64, {band_60_64_tp} would have hit TP."
        )
    no_0dte_note = ""
    skipped_legacy = int(by_quote_status.get("skipped_no_contract", 0))
    providers = Counter(
        str(r.get("contract_lookup_provider") or "unknown")
        for r in items
        if isinstance(r, dict)
    )
    yahoo_gap_caveat = ""
    alpaca_error_alert = ""
    # Provider failure must not look like a confirmed empty chain.
    if alpaca_error_n > 0:
        kind_bits = ", ".join(f"{k}={v}" for k, v in by_alpaca_error_kind.most_common(4))
        alpaca_error_alert = (
            f"ALERT: {alpaca_error_n}/{total} near-misses hit alpaca_error "
            f"({kind_bits or 'kind=unknown'}) — auth/rate-limit/network failure, "
            f"NOT confirmed missing near-expiry chain. Do not treat as no_0dte_chain_exists."
        )
    # Sessions recorded before Alpaca expiry fallback (or still yfinance-only misses)
    # can falsely label SPY/QQQ same-day expiry as missing when Yahoo omitted today's daily.
    if day == "2026-07-23" or (
        total > 0
        and with_entry_quote == 0
        and (no_0dte_n + skipped_legacy) >= max(1, int(0.8 * total))
        and int(providers.get("alpaca_fallback", 0)) == 0
        and alpaca_error_n == 0
    ):
        yahoo_gap_caveat = (
            "CAVEAT: near-miss chain classifications this session may be unreliable for "
            "daily-expiry ETFs (SPY/QQQ) — yfinance often omits the current day's expiry "
            "while the exchange/Alpaca still list it. Do not treat no_0dte_chain_exists as "
            "ground truth for those names until records show provider=alpaca_fallback or "
            "yfinance includes ET today."
        )
    if total > 0 and no_0dte_n == total and alpaca_error_n == 0:
        no_0dte_note = (
            "All near-misses lack a listed near-expiry contract — shadow PnL is not informative "
            "for the liquidity floor on this session (expected for many single-name equities; "
            "verify SPY/QQQ separately after Alpaca expiry fallback)."
        )
    elif total > 0 and no_0dte_n > 0 and with_entry_quote == 0 and alpaca_error_n == 0:
        empty_bits = []
        if alpaca_confirmed_empty_n:
            empty_bits.append(f"{alpaca_confirmed_empty_n} alpaca_confirmed_empty")
        if lookup_failed_n:
            empty_bits.append(f"{lookup_failed_n} contract_lookup_failed")
        if alpaca_no_credentials_n:
            empty_bits.append(f"{alpaca_no_credentials_n} alpaca_no_credentials")
        suffix = f" ({', '.join(empty_bits)})" if empty_bits else ""
        no_0dte_note = (
            f"{no_0dte_n}/{total} near-misses had no listed near-expiry chain{suffix} — "
            "limited liquidity-floor shadow data."
        )
    elif total > 0 and with_entry_quote == 0 and skipped_legacy == total:
        no_0dte_note = (
            "All near-misses are skipped_no_contract (pre-distinction records). "
            "Re-check with the Alpaca-backed expiry lookup before treating as ground truth."
        )
    if yahoo_gap_caveat:
        no_0dte_note = (no_0dte_note + " " + yahoo_gap_caveat).strip()
    if alpaca_error_alert:
        no_0dte_note = (alpaca_error_alert + (" " + no_0dte_note if no_0dte_note else "")).strip()

    return {
        "session_date": day,
        "total": total,
        "with_entry_quote": with_entry_quote,
        "active_followup": active_followup,
        "by_reason": dict(by_reason.most_common()),
        "by_entry_quote_status": dict(by_quote_status.most_common()),
        "no_0dte_chain_count": no_0dte_n,
        "contract_lookup_failed_count": lookup_failed_n,
        "alpaca_error_count": alpaca_error_n,
        "alpaca_confirmed_empty_count": alpaca_confirmed_empty_n,
        "alpaca_no_credentials_count": alpaca_no_credentials_n,
        "by_alpaca_error_kind": dict(by_alpaca_error_kind.most_common()),
        "alpaca_error_alert": alpaca_error_alert,
        "no_0dte_note": no_0dte_note,
        "yahoo_expiry_gap_caveat": bool(yahoo_gap_caveat),
        "by_lookup_provider": dict(providers.most_common()),
        "low_confidence_outcomes": dict(low_conf_outcomes),
        "confidence_bands": band_stats,
        "headline": " ".join(headline_parts),
        "headline_detail": headline_detail,
    }


def format_near_miss_telegram(section: Dict[str, Any]) -> str:
    """Format near-miss block for Telegram EOD message."""
    if not section or int(section.get("total", 0)) == 0:
        return "Near-misses: none tracked today."
    lines = [
        f"Near-misses: {section.get('headline', '')}",
    ]
    detail = str(section.get("headline_detail") or "").strip()
    if detail:
        lines.append(detail)
    note = str(section.get("no_0dte_note") or "").strip()
    if note:
        lines.append(note)
    alert = str(section.get("alpaca_error_alert") or "").strip()
    # Alert is already folded into no_0dte_note; keep explicit if present alone.
    if alert and alert not in note:
        lines.append(alert)
    quote_status = section.get("by_entry_quote_status") or {}
    if quote_status:
        bits = ", ".join(f"{k}={v}" for k, v in list(quote_status.items())[:6])
        lines.append(f"quote status: {bits}")
    outcomes = section.get("low_confidence_outcomes") or {}
    if outcomes:
        bits = ", ".join(f"{k}={v}" for k, v in sorted(outcomes.items()))
        lines.append(f"low_confidence outcomes: {bits}")
    bands = section.get("confidence_bands") or {}
    band_lines = []
    for label in ("60-64", "45-59", "0-44"):
        row = bands.get(label)
        if not row or not row.get("count"):
            continue
        band_lines.append(
            f"{label}: n={row['count']} TP={row.get('hit_tp', 0)} "
            f"win={row.get('would_have_won', 0)} loss={row.get('would_have_lost', 0)}"
        )
    if band_lines:
        lines.append("Bands: " + " | ".join(band_lines))
    return "\n".join(lines)


def save_near_miss_eod_section(section: Dict[str, Any]) -> Path:
    """Persist EOD near-miss aggregate to ``state/near_miss_eod_{date}.json``."""
    day = str(section.get("session_date") or _session_date())
    path = _near_miss_eod_path(day)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(section, indent=2), encoding="utf-8")
    temp.replace(path)
    return path
