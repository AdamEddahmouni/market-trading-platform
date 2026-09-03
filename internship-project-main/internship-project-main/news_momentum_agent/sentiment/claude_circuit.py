"""Shared Claude/Anthropic pause + billing circuit breaker.

Purpose
-------
Thread-safe global pause when Anthropic returns billing/credit errors, preventing
runaway failed API calls across scorer, rationale, and advisor modules.

Pipeline role
-------------
``llm_client.chat_text`` checks ``is_claude_paused`` before Anthropic calls;
``mark_claude_unavailable`` trips on credit-balance errors.

Key outputs
-----------
Process-local pause flag + ``pause_reason()`` string for logs.

Handoff notes
-------------
**Fully reusable** for any Anthropic-backed agent; extend ``mark_claude_unavailable``
patterns for other providers if needed.

**Options-only coupling:** None.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


_LOCK = threading.Lock()
_PAUSED = False
_PAUSE_REASON = ""
_LAST_LOG_AT = 0.0


def _settings_claude_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    if settings is None:
        try:
            import json
            from pathlib import Path

            data = json.loads((Path(__file__).resolve().parents[1] / "settings.json").read_text(encoding="utf-8"))
            settings = data if isinstance(data, dict) else {}
        except Exception:
            return True
    claude = (settings or {}).get("claude") or {}
    return bool(claude.get("enabled", True))


def is_claude_paused(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when Anthropic is paused (billing) or ``claude.enabled`` is false."""
    if not _settings_claude_enabled(settings):
        return True
    with _LOCK:
        return _PAUSED


def pause_reason() -> str:
    """Human-readable reason for the current Claude pause state."""
    with _LOCK:
        if not _settings_claude_enabled():
            return "claude.enabled=false in settings"
        return _PAUSE_REASON or "claude paused"


def mark_claude_unavailable(error: Any, *, source: str = "claude") -> None:
    """Trip circuit on billing/credit failures; log once."""
    text = str(error or "")
    lower = text.lower()
    billing = (
        "credit balance" in lower
        or "too low to access" in lower
        or "billing" in lower
        or "payment" in lower
        or "plans & billing" in lower
    )
    if not billing:
        return
    global _PAUSED, _PAUSE_REASON, _LAST_LOG_AT
    with _LOCK:
        first = not _PAUSED
        _PAUSED = True
        _PAUSE_REASON = f"{source}: {text[:160]}"
        now = time.time()
        should_log = first or (now - _LAST_LOG_AT) > 1800
        if should_log:
            _LAST_LOG_AT = now
    if should_log:
        print(
            f"[claude] Anthropic credits/billing unavailable — pausing Claude API calls "
            f"({source}). Set claude.enabled=true after topping up. Detail: {text[:200]}"
        )


def reset_claude_circuit() -> None:
    """Clear billing pause (e.g. after topping up Anthropic credits)."""
    global _PAUSED, _PAUSE_REASON
    with _LOCK:
        _PAUSED = False
        _PAUSE_REASON = ""
