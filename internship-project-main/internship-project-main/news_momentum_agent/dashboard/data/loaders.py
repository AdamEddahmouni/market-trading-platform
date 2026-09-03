"""Cached, envelope-based state loaders for the dashboard (read-only)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from dashboard.data import paths as P


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        return 0.0


def _envelope(
    path: Path,
    data: Any,
    *,
    ok: bool,
    error: str = "",
    updated_at: Any = None,
) -> Dict[str, Any]:
    ts = _parse_iso(updated_at)
    if ts is None and path.exists():
        try:
            ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            ts = None
    age = (_now() - ts).total_seconds() if ts else None
    return {
        "ok": ok,
        "data": data,
        "path": str(path),
        "updated_at": ts.isoformat() if ts else None,
        "age_sec": age,
        "error": error,
        "exists": path.exists(),
    }


@st.cache_data(ttl=12, show_spinner=False)
def _read_json_cached(path_str: str, mtime: float) -> Tuple[bool, Any, str]:
    path = Path(path_str)
    if not path.exists():
        return False, None, "missing"
    try:
        raw = path.read_text(encoding="utf-8")
        return True, json.loads(raw), ""
    except json.JSONDecodeError as exc:
        return False, None, f"malformed JSON: {exc}"
    except OSError as exc:
        return False, None, str(exc)


def load_json(path: Path, default: Any = None) -> Dict[str, Any]:
    """Load JSON into a standard envelope."""
    ok, data, err = _read_json_cached(str(path), _mtime(path))
    if not ok:
        return _envelope(path, default if default is not None else {}, ok=False, error=err or "missing")
    updated = None
    if isinstance(data, dict):
        updated = data.get("updated_at") or data.get("generated_at") or (data.get("meta") or {}).get("updated_at")
    return _envelope(path, data, ok=True, updated_at=updated)


def clear_loader_cache() -> None:
    """Clear Streamlit cache for JSON loaders (manual refresh)."""
    _read_json_cached.clear()
    count_solicitation_skips.clear()


def load_settings() -> Dict[str, Any]:
    env = load_json(P.SETTINGS_PATH, {})
    return env["data"] if isinstance(env.get("data"), dict) else {}


def load_items_file(path: Path) -> Dict[str, Any]:
    """Normalize ``{items, meta}`` or bare list into envelope with items/meta."""
    env = load_json(path, {"items": [], "meta": {}})
    data = env.get("data")
    items: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {}
    if isinstance(data, dict):
        raw_items = data.get("items", [])
        items = raw_items if isinstance(raw_items, list) else []
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if not meta and data.get("updated_at"):
            meta = {"updated_at": data.get("updated_at")}
    elif isinstance(data, list):
        items = data
    env["items"] = [x for x in items if isinstance(x, dict)]
    env["meta"] = meta
    return env


def options_state_dir(settings: Dict[str, Any]) -> Path:
    engine = str((settings.get("options_confirmation") or {}).get("engine_path") or "").strip()
    if engine:
        return Path(engine).expanduser() / "state"
    return P.PROJECT_ROOT.parent / "options_confirmation_engine" / "state"


def load_options_signals(settings: Dict[str, Any]) -> Dict[str, Any]:
    path = options_state_dir(settings) / "signals.json"
    return load_items_file(path)


def load_options_health(settings: Dict[str, Any]) -> Dict[str, Any]:
    return load_json(options_state_dir(settings) / "health.json", {})


def load_latest_eod() -> Dict[str, Any]:
    path = P.latest_eod_summary_path()
    if path is None:
        return _envelope(P.STATE_DIR / "eod_summary_missing.json", {}, ok=False, error="no eod_summary files")
    return load_json(path, {})


def load_near_miss_eod(day: Optional[str] = None) -> Dict[str, Any]:
    env = load_json(P.near_miss_eod_path(day), {})
    if env["ok"]:
        return env
    # Fall back to embedded near_miss on latest EOD
    eod = load_latest_eod()
    if eod["ok"] and isinstance(eod.get("data"), dict) and isinstance(eod["data"].get("near_miss"), dict):
        return _envelope(
            Path(eod["path"]),
            eod["data"]["near_miss"],
            ok=True,
            updated_at=eod["data"].get("generated_at"),
        )
    return env


def is_process_running(pid: int) -> bool:
    """Return True if ``pid`` appears alive."""
    if pid <= 0:
        return False
    try:
        import os

        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def load_agent_pid() -> Dict[str, Any]:
    path = P.PID_PATH
    if not path.exists():
        return _envelope(path, {"pid": None, "running": False}, ok=False, error="missing")
    try:
        pid = int(path.read_text(encoding="utf-8").strip().split()[0])
    except Exception:
        return _envelope(path, {"pid": None, "running": False}, ok=False, error="unreadable pid")
    return _envelope(path, {"pid": pid, "running": is_process_running(pid)}, ok=True)


@st.cache_data(ttl=30, show_spinner=False)
def count_solicitation_skips(log_path: str, mtime: float, day: str) -> Dict[str, Any]:
    """Count solicitation-filter log lines for ``day`` (YYYY-MM-DD) — read-only."""
    path = Path(log_path)
    if not path.exists():
        return {"ok": False, "count": 0, "error": "log missing", "samples": []}
    patterns = (
        "skipped solicitation",
        "law-firm solicitation",
        "skipped law-firm solicitation",
    )
    count = 0
    samples: List[str] = []
    day_token = day  # ISO date appears in many log lines as prefix or timestamp
    try:
        # Tail-ish: read last ~4MB to keep refresh cheap
        size = path.stat().st_size
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            if size > 4_000_000:
                handle.seek(size - 4_000_000)
                handle.readline()
            for line in handle:
                if day_token not in line and f"{day_token}T" not in line:
                    # also accept lines without date if file is session-only — still count keywords
                    lower = line.lower()
                    if not any(p in lower for p in patterns):
                        continue
                lower = line.lower()
                if any(p in lower for p in patterns):
                    # Prefer same-day when timestamp present
                    if re.search(r"\d{4}-\d{2}-\d{2}", line) and day_token not in line:
                        continue
                    count += 1
                    if len(samples) < 8:
                        samples.append(line.strip()[:220])
    except OSError as exc:
        return {"ok": False, "count": 0, "error": str(exc), "samples": []}
    return {"ok": True, "count": count, "error": "", "samples": samples}


def solicitation_stats(day: Optional[str] = None) -> Dict[str, Any]:
    day = day or P.session_date_et()
    return count_solicitation_skips(str(P.AGENT_LOG_PATH), _mtime(P.AGENT_LOG_PATH), day)


def horizon_explainer(settings: Dict[str, Any]) -> Dict[str, str]:
    """Plain-English horizon mode for the header."""
    trading = settings.get("trading") or {}
    raw = str(trading.get("options_expiry_horizon") or "same_day").strip().lower()
    if raw in {"deadline", "through_friday", "this_friday", "friday"}:
        mode = "deadline"
    elif raw in {"range", "dte_range", "window"}:
        mode = "range"
    else:
        mode = "same_day"

    if mode == "range":
        dte = trading.get("options_dte_range") or [0, 30]
        try:
            lo, hi = int(dte[0]), int(dte[1])
        except Exception:
            lo, hi = 0, 30
        detail = (
            f"range mode: [{lo}, {hi}] DTE — no deadline flatten; "
            "exits via TP/SL; EOD flatten only if the contract expires today."
        )
    elif mode == "deadline":
        deadline = str(trading.get("deadline_date") or "this Friday (ET)")
        detail = (
            f"deadline mode: expiries on/before {deadline}; "
            "deadline-day flatten enabled; overnight holds allowed until then."
        )
    else:
        detail = "same_day (0DTE) mode: same-day expiry only; EOD flatten on expiry day."

    return {"mode": mode, "detail": detail, "raw": raw}


def gate_flags(settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Safety / path gates for the header chip row."""
    execution = settings.get("execution") or {}
    trading = settings.get("trading") or {}
    return [
        {"key": "market_hours_only", "on": bool(execution.get("market_hours_only", True))},
        {"key": "no_post_1545_opens", "on": bool(execution.get("no_post_1545_opens", True))},
        {"key": "path_b_auto_execute", "on": bool(execution.get("path_b_auto_execute", False))},
        {"key": "path_a2_auto_execute", "on": bool(execution.get("path_a2_auto_execute", False))},
        {"key": "exit_on_signal_flip", "on": bool(execution.get("exit_on_signal_flip", False))},
        {"key": "instrument", "on": True, "value": str(trading.get("instrument") or "stock")},
        {
            "key": "auto_execute",
            "on": bool(trading.get("auto_execute", False)),
            "value": "paper" if trading.get("auto_execute") else "off",
        },
    ]


def path_label(signal_source: Any) -> str:
    src = str(signal_source or "news").lower().strip()
    if src in {"news_catalyst", "path_a2", "a2"}:
        return "A.2"
    if src in {"expiry", "path_b", "both"}:
        return "B"
    return "A"


def freshness_text(age_sec: Optional[float]) -> str:
    if age_sec is None:
        return "unknown"
    if age_sec < 90:
        return f"{int(age_sec)}s ago"
    if age_sec < 5400:
        return f"{int(age_sec / 60)}m ago"
    return f"{age_sec / 3600:.1f}h ago"
