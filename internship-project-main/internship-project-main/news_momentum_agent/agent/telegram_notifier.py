"""Telegram push notifications, pending REVIEW approvals, and operator controls.

Pipeline role
-------------
Human-in-the-loop layer after ``paper_trader`` logs a decision:
  - ``send_signal_alert`` — BUY/SELL/REVIEW push with inline approve buttons.
  - ``poll_telegram_updates`` — processes callback buttons → ``apply_approval``
    → ``portfolio.execute_decision(force=True)``.
  - ``notify_option_exit`` — take-profit / stop-loss / EOD close alerts.
  - ``maybe_send_heartbeat`` — periodic alive ping.

State files
-----------
  - ``state/pending_reviews.json`` — open REVIEW rows awaiting approval.
  - ``state/telegram_cooldown.json`` — per-ticker notify deduplication.
  - ``state/telegram_heartbeat.json`` — last heartbeat timestamp.
  - ``state/telegram_offset.json`` — Bot API update offset for polling.

Credentials from ``.env``: ``TELEGRAM_BOT_TOKEN``, ``TELEGRAM_CHAT_ID``.

Merge notes for stocks/futures
------------------------------
  - **Fully reusable:** notify gating (``should_notify``), cooldown, heartbeat,
    generic ``send_text``, kill-switch via ``set_force_review_flag``.
  - **Options-specific UI:** inline keyboard offers call/put instrument choices;
    exit messages reference option contracts — adapt buttons for futures/stock only.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
PENDING_PATH = STATE_DIR / "pending_reviews.json"
COOLDOWN_PATH = STATE_DIR / "telegram_cooldown.json"
TELEGRAM_API = "https://api.telegram.org"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def load_pending() -> List[Dict[str, Any]]:
    """Load pending REVIEW rows from ``state/pending_reviews.json``."""
    try:
        if not PENDING_PATH.exists():
            return []
        data = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_pending(rows: List[Dict[str, Any]]) -> None:
    """Persist pending REVIEW rows to ``state/pending_reviews.json``."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = PENDING_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    temp.replace(PENDING_PATH)


def _credentials() -> tuple[Optional[str], Optional[str]]:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or None
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None
    return token, chat_id


def telegram_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when notifications allow Telegram and bot token + chat id are configured."""
    cfg = (settings or {}).get("notifications", {})
    if not bool(cfg.get("telegram_enabled", True)):
        return False
    token, chat_id = _credentials()
    return bool(token and chat_id)


def _api(token: str, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    response = requests.post(url, json=payload, timeout=15)
    try:
        data = response.json()
    except Exception:
        data = {}
    if response.status_code >= 400 or not data.get("ok", True):
        desc = data.get("description") if isinstance(data, dict) else None
        raise RuntimeError(desc or f"HTTP {response.status_code}")
    return data


def dequeue_pending(pending_id: str) -> None:
    """Remove a pending review row (e.g. after failed Telegram send)."""
    rows = load_pending()
    kept = [row for row in rows if str(row.get("id")) != str(pending_id)]
    if len(kept) != len(rows):
        save_pending(kept)


def _escape_md(value: Any) -> str:
    """Escape Telegram legacy-Markdown specials in free-form text."""
    text = str(value or "")
    # Order matters: escape backslash first.
    for ch in ("\\", "_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _probs_line(action_probs: Dict[str, Any]) -> str:
    return " | ".join(f"{k} {float(v)*100:.0f}%" for k, v in action_probs.items())


def build_alert_text(entry: Dict[str, Any]) -> str:
    """Format a Telegram Markdown alert body from a trade-log / decision entry dict."""
    probs = entry.get("action_probs") or {}
    expl = entry.get("decision_explanation") or {}
    conf = expl.get("confidence_label") or entry.get("confidence") or "?"
    conf_pct = expl.get("confidence_pct") or entry.get("confidence_pct") or entry.get("lean_pct") or 0
    why = expl.get("why") or entry.get("why") or entry.get("reasoning") or ""
    expect = expl.get("what_to_expect") or entry.get("what_to_expect") or entry.get("next_action") or ""
    exit_plan = expl.get("exit_plan") or entry.get("exit_plan") or ""
    instrument = expl.get("instrument") or entry.get("instrument_hint") or "stock"
    meta = entry.get("decision_meta") or expl.get("odte_factors") or {}
    if meta.get("equity_fallback_liquidity"):
        instrument = "stock (equity fallback — options illiquid)"
    gex = meta.get("gex_regime") or (meta.get("factor_snapshot") or {}).get("gex_regime")
    rationale = entry.get("in_depth_rationale") or expl.get("in_depth_rationale") or {}
    decision = str(entry.get("decision", "?")).upper()
    ticker = _escape_md(entry.get("ticker", "?"))
    lean = _escape_md(entry.get("lean", "?"))
    headline = _escape_md(str(entry.get("news_headline", "") or "")[:120])
    source = _escape_md(entry.get("signal_source", "news"))
    herd = _escape_md(entry.get("herd_stage", "?"))
    options_bias = _escape_md(entry.get("options_bias", "n/a"))
    gex_s = _escape_md(gex) if gex else ""
    lines = [
        f"*{decision}* `{entry.get('ticker', '?')}`",
        f"Instrument: `{instrument}`",
        f"Confidence: *{_escape_md(conf)}* ({conf_pct}%) · Lean: *{lean} {entry.get('lean_pct', 0)}%*",
        _probs_line(probs),
        f"Source: {source} | Herd: {herd}",
        f"Options: {options_bias} ({entry.get('options_score', 'n/a')})"
        + (f" | GEX: {gex_s}" if gex_s else ""),
        headline,
        f"*Why:* {_escape_md(str(why)[:320])}",
        f"*Expect:* {_escape_md(str(expect)[:240])}",
        f"*Exit:* {_escape_md(str(exit_plan)[:160])}",
    ]
    if decision == "REVIEW":
        lines.append(
            "*REVIEW gate:* reply approve/reject via buttons, or yes/no + ticker. "
            "Unanswered -> auto LOG (no trade)."
        )
        if rationale.get("reasoning"):
            lines.append(f"*Rationale:* {_escape_md(str(rationale['reasoning'])[:350])}")
    elif rationale.get("reasoning"):
        lines.append(f"*Rationale:* {_escape_md(str(rationale['reasoning'])[:280])}")
    return "\n".join(lines)


def _pending_confidence_pct(row: Dict[str, Any]) -> float:
    """Resolve the best available confidence percentage for a pending review."""
    for source in (row.get("in_depth_rationale") or {}, row.get("decision_meta") or {}, row):
        if not isinstance(source, dict):
            continue
        for key in ("confidence_pct", "agreement_confidence"):
            value = source.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        lean_pct = source.get("lean_pct")
        if lean_pct is not None:
            try:
                return float(lean_pct)
            except (TypeError, ValueError):
                pass
    return 0.0


def enqueue_pending_review(entry: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a pending review row for REVIEW (and optional confirm_auto_trades)."""
    cfg = (settings or {}).get("notifications", {})
    exec_cfg = (settings or {}).get("execution") or {}
    # Prefer shorter REVIEW TTL for near-expiry; fall back to notifications.pending_ttl_minutes.
    ttl_minutes = int(exec_cfg.get("review_ttl_minutes", cfg.get("pending_ttl_minutes", 8)))
    pending_id = str(uuid.uuid4())
    rationale = entry.get("in_depth_rationale") or {}
    row = {
        "id": pending_id,
        "ticker": entry.get("ticker"),
        "created_at": _now_iso(),
        "expires_at": (_now() + timedelta(minutes=ttl_minutes)).isoformat(),
        "status": "pending",
        "decision": entry.get("decision"),
        "action_probs": entry.get("action_probs") or {},
        "lean": entry.get("lean"),
        "lean_pct": entry.get("lean_pct"),
        "instrument_hint": entry.get("instrument_hint", "stock"),
        "price_at_signal": entry.get("price_at_signal"),
        "news_headline": entry.get("news_headline"),
        "options_bias": entry.get("options_bias"),
        "options_score": entry.get("options_score"),
        "signal_source": entry.get("signal_source"),
        "herd_stage": entry.get("herd_stage"),
        "next_action": entry.get("next_action"),
        "reasoning": entry.get("reasoning"),
        "why": entry.get("why"),
        "in_depth_rationale": rationale,
        "decision_meta": entry.get("decision_meta") or {},
        "confidence_pct": (
            (entry.get("in_depth_rationale") or {}).get("confidence_pct")
            or (entry.get("decision_meta") or {}).get("confidence_pct")
            or entry.get("confidence_pct")
            or entry.get("lean_pct")
        ),
        "expires_to": "LOG",
    }
    rows = load_pending()
    rows.append(row)
    save_pending(rows)
    return row


def _load_cooldown() -> Dict[str, str]:
    try:
        if not COOLDOWN_PATH.exists():
            return {}
        data = json.loads(COOLDOWN_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cooldown(data: Dict[str, str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = COOLDOWN_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(COOLDOWN_PATH)


def _cooldown_key(entry: Dict[str, Any]) -> str:
    ticker = str(entry.get("ticker", "")).upper()
    decision = str(entry.get("decision", "")).upper()
    lean = str(entry.get("lean", "")).upper()
    source = str(entry.get("signal_source", "")).lower()
    return f"{ticker}:{decision}:{lean}:{source}"


def in_notify_cooldown(entry: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> bool:
    """True if we already notified this ticker/decision recently."""
    cfg = (settings or {}).get("notifications", {})
    minutes = int(cfg.get("cooldown_minutes", 60))
    if minutes <= 0:
        return False
    key = _cooldown_key(entry)
    stamp = _load_cooldown().get(key)
    if not stamp:
        return False
    try:
        last = datetime.fromisoformat(stamp)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return _now() - last < timedelta(minutes=minutes)


def mark_notified(entry: Dict[str, Any]) -> None:
    """Record notify timestamp for this ticker/decision key in the cooldown file."""
    data = _load_cooldown()
    data[_cooldown_key(entry)] = _now_iso()
    # Keep file small.
    if len(data) > 300:
        items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:200]
        data = dict(items)
    _save_cooldown(data)


def should_notify(entry: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Gate noisy alerts.

    - Always allow BUY/SELL (unless cooldown).
    - REVIEW only when lean is BUY/SELL and lean_pct is high enough.
    - Skip quiet Path B WAIT spam (neutral options, no herd).
    """
    cfg = (settings or {}).get("notifications", {})
    notify_on = {str(x).upper() for x in cfg.get("notify_on", ["BUY", "SELL", "REVIEW"])}
    decision = str(entry.get("decision", "")).upper()
    if decision not in notify_on:
        return False

    lean = str(entry.get("lean", "WAIT")).upper()
    lean_pct = int(entry.get("lean_pct") or 0)
    herd = str(entry.get("herd_stage", "quiet")).lower()
    source = str(entry.get("signal_source", "news")).lower()
    options_bias = str(entry.get("options_bias", "no_data")).lower()
    options_score = float(entry.get("options_score") or 50.0)
    min_review_lean = int(cfg.get("min_review_lean_pct", 55))
    review_leans = {
        str(x).upper() for x in cfg.get("notify_review_leans", ["BUY", "SELL"])
    }

    if decision == "REVIEW":
        if lean not in review_leans:
            return False
        if lean_pct < min_review_lean:
            return False
        # Path B quiet neutrals are not phone-worthy.
        if source == "expiry" and herd in {"quiet", "coiled"} and options_bias == "neutral":
            return False
        if source == "expiry" and options_bias == "no_data":
            return False
        # Strong options alone can still notify on REVIEW if lean is directional.
        if source == "expiry" and lean == "BUY" and options_score < 65:
            return False
        if source == "expiry" and lean == "SELL" and options_score > 35:
            return False

    if in_notify_cooldown(entry, settings):
        return False
    return True


def send_signal_alert(entry: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> bool:
    """Push BUY/SELL/REVIEW alert to Telegram with approval buttons when needed."""
    if not should_notify(entry, settings):
        return False
    if not telegram_enabled(settings):
        return False

    cfg = (settings or {}).get("notifications", {})
    decision = str(entry.get("decision", "")).upper()

    token, chat_id = _credentials()
    assert token and chat_id

    needs_buttons = decision == "REVIEW" or bool(cfg.get("confirm_auto_trades", False))
    probs = entry.get("action_probs") or {}
    buy_pct = int(round(float(probs.get("BUY", 0)) * 100))
    sell_pct = int(round(float(probs.get("SELL", 0)) * 100))
    text = build_alert_text(entry)

    def _markup_for(pending_id: str) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": f"Buy stock ({buy_pct}%)", "callback_data": f"approve:{pending_id}:BUY:stock"},
                    {"text": f"Buy call ({buy_pct}%)", "callback_data": f"approve:{pending_id}:BUY:call"},
                ],
                [
                    {"text": f"Sell/put ({sell_pct}%)", "callback_data": f"approve:{pending_id}:SELL:put"},
                    {"text": "Skip", "callback_data": f"approve:{pending_id}:SKIP:none"},
                ],
            ]
        }

    pending = None
    if needs_buttons:
        pending = enqueue_pending_review(entry, settings)

    attempts = [
        {"parse_mode": "Markdown", "text": text},
        {"text": text.replace("\\", "")},  # plain fallback if Markdown entities fail
    ]
    last_error: Optional[Exception] = None
    for attempt in attempts:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "disable_web_page_preview": True,
            **attempt,
        }
        if pending:
            payload["reply_markup"] = _markup_for(str(pending["id"]))
        try:
            _api(token, "sendMessage", payload)
            mark_notified(entry)
            if attempt is attempts[1]:
                print("[telegram] fallback plain-text send ok")
            return True
        except Exception as error:
            last_error = error
            print(f"[telegram] send failed: {error}")

    if pending and pending.get("id"):
        try:
            dequeue_pending(str(pending["id"]))
        except Exception:
            pass
    if last_error:
        print(f"[telegram] alert dropped after retries: {last_error}")
    return False


def send_text(message: str, settings: Optional[Dict[str, Any]] = None) -> bool:
    """Send a plain-text Telegram message. Returns True on success."""
    if not telegram_enabled(settings):
        return False
    token, chat_id = _credentials()
    assert token and chat_id
    try:
        _api(token, "sendMessage", {"chat_id": chat_id, "text": message})
        return True
    except Exception as error:
        print(f"[telegram] text send failed: {error}")
        return False


def notify_option_exit(fill: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> bool:
    """Alert on option take-profit / stop-loss / EOD / signal-flip close."""
    if not telegram_enabled(settings):
        return False
    try:
        from agent.market_session import is_options_session_open

        if not is_options_session_open(settings):
            print("[telegram] skip option exit notify — options market closed")
            return False
    except Exception:
        pass
    action = str(fill.get("action", "")).lower()
    if action != "close":
        return False
    reason = str(fill.get("reason", "exit"))
    ticker = str(fill.get("ticker", "?"))
    contract = str(fill.get("contract_symbol", ""))
    side = str(fill.get("side", "call"))
    contracts = int(fill.get("contracts", 0) or 0)
    price = float(fill.get("price", 0.0) or 0.0)
    pnl = float(fill.get("realized_pnl", 0.0) or 0.0)
    try:
        from agent.market_session import options_horizon_label

        horizon = options_horizon_label(settings).upper()
    except Exception:
        horizon = "OPTIONS"
    message = (
        f"{horizon} EXIT ({reason})\n"
        f"{ticker} {side.upper()} `{contract}`\n"
        f"{contracts} contract(s) @ ${price:.2f}\n"
        f"Realized P&L: ${pnl:+.2f}"
    )
    return send_text(message, settings)


def expire_stale_pending() -> int:
    """Mark expired pending reviews as expired (auto → LOG / no trade)."""
    rows = load_pending()
    changed = 0
    now = _now()
    for row in rows:
        if row.get("status") != "pending":
            continue
        expires = str(row.get("expires_at", ""))
        try:
            exp_dt = datetime.fromisoformat(expires)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if now > exp_dt:
            row["status"] = "expired"
            row["resolved_as"] = row.get("expires_to") or "LOG"
            row["resolved_at"] = _now_iso()
            changed += 1
    if changed:
        save_pending(rows)
    return changed


def set_force_review_flag(settings: Dict[str, Any], enabled: bool) -> None:
    """Persist kill-switch into settings.json execution.force_review_all."""
    settings.setdefault("execution", {})["force_review_all"] = bool(enabled)
    settings.setdefault("risk", {})["force_review_all"] = bool(enabled)
    try:
        path = PROJECT_ROOT / "settings.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("execution", {})["force_review_all"] = bool(enabled)
        data.setdefault("risk", {})["force_review_all"] = bool(enabled)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(path)
    except Exception as error:
        print(f"[telegram] Could not persist force_review_all: {error}")


def _find_pending(pending_id: str) -> Optional[Dict[str, Any]]:
    for row in load_pending():
        if row.get("id") == pending_id:
            return row
    return None


def _update_pending(pending_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    rows = load_pending()
    updated = None
    for row in rows:
        if row.get("id") == pending_id:
            row.update(fields)
            updated = row
            break
    if updated is not None:
        save_pending(rows)
    return updated


def apply_approval(
    pending_id: str,
    action: str,
    instrument: str,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute an approved pending review as a paper trade."""
    row = _find_pending(pending_id)
    if not row:
        return {"ok": False, "message": "Unknown pending id"}
    if row.get("status") != "pending":
        return {"ok": False, "message": f"Already {row.get('status')}"}

    action_u = str(action).upper().strip()
    if action_u == "SKIP":
        _update_pending(pending_id, status="skipped", resolved_at=_now_iso())
        return {"ok": True, "message": f"Skipped {row.get('ticker')}"}

    if action_u not in {"BUY", "SELL"}:
        return {"ok": False, "message": f"Invalid action {action_u}"}

    exec_cfg = settings.get("execution") or {}
    min_conf = float(
        exec_cfg.get(
            "min_confidence_for_telegram_approve",
            exec_cfg.get("min_confidence_for_action", 40),
        )
    )
    conf = _pending_confidence_pct(row)
    if conf < min_conf:
        return {
            "ok": False,
            "message": (
                f"Approval blocked: confidence {conf:.0f}% is below the "
                f"{min_conf:.0f}% floor for {row.get('ticker')}"
            ),
        }

    instrument_hint = str(instrument or row.get("instrument_hint") or "stock").lower().strip()
    if instrument_hint not in {"stock", "call", "put"}:
        instrument_hint = "stock"

    ticker = str(row.get("ticker", "")).upper()
    price = float(row.get("price_at_signal") or 0.0)
    try:
        from agent.portfolio import execute_decision

        execution = execute_decision(
            ticker=ticker,
            decision=action_u,
            price=price,
            reason=f"Telegram approval {pending_id}",
            settings=settings,
            instrument_hint=instrument_hint,
            force=True,
            signal_confidence=_pending_confidence_pct(row),
        )
        _update_pending(
            pending_id,
            status="approved",
            resolved_at=_now_iso(),
            approved_action=action_u,
            approved_instrument=instrument_hint,
            execution=execution,
        )
        label = (execution or {}).get("contract_symbol") or ticker
        return {
            "ok": True,
            "message": f"Executed {action_u} {label} ({instrument_hint})",
            "execution": execution,
        }
    except Exception as error:
        return {"ok": False, "message": str(error)}


def poll_telegram_updates(settings: Dict[str, Any], offset_path: Optional[Path] = None) -> int:
    """Poll Telegram callbacks and apply approvals. Returns actions applied."""
    if not telegram_enabled(settings):
        return 0
    token, chat_id = _credentials()
    assert token and chat_id
    expire_stale_pending()

    offset_file = offset_path or (STATE_DIR / "telegram_offset.json")
    offset = 0
    try:
        if offset_file.exists():
            offset = int(json.loads(offset_file.read_text(encoding="utf-8")).get("offset", 0))
    except Exception:
        offset = 0

    try:
        data = _api(token, "getUpdates", {"offset": offset, "timeout": 0})
    except Exception as error:
        print(f"[telegram] poll failed: {error}")
        return 0

    applied = 0
    max_offset = offset
    for update in data.get("result", []):
        update_id = int(update.get("update_id", 0)) + 1
        max_offset = max(max_offset, update_id)

        # Text commands: /pause (kill switch) /resume
        message = update.get("message") or {}
        msg_chat = (message.get("chat") or {}).get("id")
        text = str(message.get("text") or "").strip().lower()
        if msg_chat is not None and str(msg_chat) == str(chat_id) and text in {"/pause", "pause"}:
            set_force_review_flag(settings, True)
            send_text("Kill switch ON — all BUY/SELL forced to REVIEW.", settings)
            applied += 1
            continue
        if msg_chat is not None and str(msg_chat) == str(chat_id) and text in {"/resume", "resume"}:
            set_force_review_flag(settings, False)
            send_text("Kill switch OFF — autonomous BUY/SELL restored.", settings)
            applied += 1
            continue

        callback = update.get("callback_query") or {}
        message_chat = ((callback.get("message") or {}).get("chat") or {}).get("id")
        if message_chat is not None and str(message_chat) != str(chat_id):
            continue
        callback_data = str(callback.get("data", ""))
        if not callback_data.startswith("approve:"):
            continue
        parts = callback_data.split(":")
        if len(parts) != 4:
            continue
        _, pending_id, action, instrument = parts
        result = apply_approval(pending_id, action, instrument, settings)
        applied += 1
        try:
            _api(
                token,
                "answerCallbackQuery",
                {"callback_query_id": callback.get("id"), "text": result.get("message", "")[:180]},
            )
            send_text(str(result.get("message", "")), settings)
        except Exception:
            pass

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        offset_file.write_text(json.dumps({"offset": max_offset}), encoding="utf-8")
    except Exception:
        pass
    return applied


def maybe_send_heartbeat(settings: Dict[str, Any], watchlist_count: int, pending_count: int) -> None:
    """Send occasional alive ping."""
    cfg = settings.get("notifications", {})
    minutes = int(cfg.get("heartbeat_minutes", 60))
    if minutes <= 0 or not telegram_enabled(settings):
        return
    marker = STATE_DIR / "telegram_heartbeat.json"
    now = _now()
    try:
        if marker.exists():
            last = datetime.fromisoformat(json.loads(marker.read_text(encoding="utf-8")).get("at"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if now - last < timedelta(minutes=minutes):
                return
    except Exception:
        pass
    send_text(
        f"Agent alive. watchlist={watchlist_count} pending_reviews={pending_count}",
        settings,
    )
    marker.write_text(json.dumps({"at": now.isoformat()}), encoding="utf-8")
