"""Shared LLM chat helper — OpenAI, Anthropic, or Gemini via settings.llm.provider.

Purpose
-------
Centralize provider selection, API key loading, JSON extraction, and billing
circuit integration for all sentiment modules.

Pipeline role
-------------
``chat_text`` / ``chat_json`` used by ``claude_scorer``, ``claude_action_advisor``,
``claude_trade_rationale``. Reads ``settings.json`` + ``.env`` keys.

Key outputs
-----------
``chat_json`` → ``(parsed_dict, provider_name)``; raises on disabled LLM or
empty/malformed JSON.

Handoff notes
-------------
**Fully reusable** — provider abstraction portable to any downstream agent.
Set ``settings.llm.provider`` to ``openai``, ``anthropic``, or ``gemini``.

**Options-only coupling:** None; Anthropic path hooks ``claude_circuit`` for
billing pause (equity/futures agents benefit equally).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from os import getenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "settings.json"


def load_llm_settings() -> Dict[str, Any]:
    """Load merged defaults + ``settings.json`` for LLM provider configuration."""
    defaults: Dict[str, Any] = {
        "llm": {
            "provider": "gemini",
            "enabled": True,
            "openai_model": "gpt-4o-mini",
            "anthropic_model": "claude-haiku-4-5-20251001",
            "gemini_model": "gemini-flash-lite-latest",
            "max_tokens": 300,
            "temperature": 0,
            "rationale_max_tokens": 700,
        },
        # Legacy Claude block kept for backward compatibility.
        "claude": {
            "enabled": True,
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "temperature": 0,
            "rationale_max_tokens": 700,
        },
    }
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if isinstance(data.get("llm"), dict):
                    defaults["llm"].update(data["llm"])
                if isinstance(data.get("claude"), dict):
                    defaults["claude"].update(data["claude"])
                    llm = defaults["llm"]
                    llm.setdefault("anthropic_model", data["claude"].get("model"))
                    if "max_tokens" not in (data.get("llm") or {}):
                        llm["max_tokens"] = int(data["claude"].get("max_tokens", llm["max_tokens"]))
                    if "temperature" not in (data.get("llm") or {}):
                        llm["temperature"] = float(data["claude"].get("temperature", llm["temperature"]))
                    if "rationale_max_tokens" not in (data.get("llm") or {}):
                        llm["rationale_max_tokens"] = int(
                            data["claude"].get("rationale_max_tokens", llm["rationale_max_tokens"])
                        )
                    if "enabled" not in (data.get("llm") or {}) and str(llm.get("provider", "")).lower() == "anthropic":
                        llm["enabled"] = bool(data["claude"].get("enabled", True))
    except Exception as error:
        print(f"[llm_client] Failed to load settings.json: {error}")
    return defaults


def resolve_provider(settings: Optional[Dict[str, Any]] = None) -> str:
    """Normalize ``settings.llm.provider`` to openai, anthropic, or gemini."""
    cfg = (settings or load_llm_settings()).get("llm") or {}
    provider = str(cfg.get("provider") or "gemini").strip().lower()
    if provider in {"openai", "gpt", "oai"}:
        return "openai"
    if provider in {"anthropic", "claude"}:
        return "anthropic"
    if provider in {"gemini", "google", "google_genai"}:
        return "gemini"
    return "gemini"


def llm_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """Return False when LLM calls are disabled in settings."""
    data = settings or load_llm_settings()
    llm = data.get("llm") or {}
    if "enabled" in llm:
        return bool(llm.get("enabled"))
    if resolve_provider(data) == "anthropic":
        return bool((data.get("claude") or {}).get("enabled", True))
    return True


def extract_json_object(text: str) -> Dict[str, Any]:
    """Parse first JSON object from model text, stripping markdown fences if present."""
    candidate = (text or "").strip()
    if not candidate:
        raise ValueError("Model returned empty text; expected JSON.")
    candidate = candidate.replace("```json", "").replace("```", "").strip()
    if not candidate.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", candidate)
        if not match:
            raise ValueError("No JSON object found in model output.")
        candidate = match.group(0)
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Model returned non-dictionary JSON.")
    return parsed


def _chat_openai(
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    from openai import OpenAI

    api_key = getenv("OPENAI_API_KEY", "").strip() or getenv("OPENAI_KEY", "").strip()
    if not api_key:
        raise RuntimeError("No valid OPENAI_API_KEY found in .env")
    client = OpenAI(api_key=api_key)
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    try:
        response = client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
    except TypeError:
        response = client.chat.completions.create(**kwargs, max_tokens=max_tokens)
    except Exception as error:
        if "max_completion_tokens" in str(error) or "max_tokens" in str(error).lower():
            response = client.chat.completions.create(**kwargs, max_tokens=max_tokens)
        else:
            raise
    choice = response.choices[0].message if response.choices else None
    return str(getattr(choice, "content", "") or "").strip()


def _chat_anthropic(
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    import anthropic

    api_key = getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        raise RuntimeError("No valid ANTHROPIC_API_KEY found in .env")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text_output = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_output += block.text
    return text_output.strip()


def _chat_gemini(
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    from google import genai
    from google.genai import types

    api_key = (
        getenv("GEMINI_API_KEY", "").strip()
        or getenv("GOOGLE_API_KEY", "").strip()
        or getenv("GOOGLE_GENAI_API_KEY", "").strip()
    )
    if not api_key:
        raise RuntimeError("No valid GEMINI_API_KEY found in .env")

    client = genai.Client(api_key=api_key)
    # Flash models sometimes spend budget on internal tokens; keep a floor.
    out_tokens = max(int(max_tokens), 256)
    config = types.GenerateContentConfig(
        temperature=float(temperature),
        max_output_tokens=out_tokens,
        system_instruction=system or None,
    )
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=config,
    )
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    parts: list[str] = []
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            piece = getattr(part, "text", None)
            if piece:
                parts.append(str(piece))
    joined = "\n".join(parts).strip()
    if not joined:
        finish = None
        if getattr(response, "candidates", None):
            finish = getattr(response.candidates[0], "finish_reason", None)
        raise RuntimeError(f"Gemini returned empty text (finish_reason={finish})")
    return joined


def chat_text(
    *,
    system: str,
    user: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    settings: Optional[Dict[str, Any]] = None,
    purpose: str = "chat",
) -> Tuple[str, str]:
    """
    Run one chat completion. Returns (text, provider_used).

    Raises RuntimeError / provider API errors for the caller to handle.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    data = settings or load_llm_settings()
    if not llm_enabled(data):
        raise RuntimeError("LLM disabled in settings (llm.enabled=false)")

    provider = resolve_provider(data)
    if provider == "anthropic":
        try:
            from sentiment.claude_circuit import is_claude_paused, pause_reason

            if is_claude_paused(data):
                raise RuntimeError(f"Claude paused ({pause_reason()})")
        except ImportError:
            pass

    llm = data.get("llm") or {}
    claude = data.get("claude") or {}
    temp = float(temperature if temperature is not None else llm.get("temperature", claude.get("temperature", 0)))
    tokens = int(
        max_tokens
        if max_tokens is not None
        else llm.get("max_tokens", claude.get("max_tokens", 300))
    )

    if provider == "openai":
        model = str(llm.get("openai_model") or llm.get("model") or "gpt-4o-mini")
        text = _chat_openai(system=system, user=user, model=model, max_tokens=tokens, temperature=temp)
        return text, "openai"

    if provider == "gemini":
        model = str(llm.get("gemini_model") or llm.get("model") or "gemini-flash-lite-latest")
        text = _chat_gemini(system=system, user=user, model=model, max_tokens=tokens, temperature=temp)
        return text, "gemini"

    model = str(llm.get("anthropic_model") or claude.get("model") or "claude-haiku-4-5-20251001")
    try:
        text = _chat_anthropic(system=system, user=user, model=model, max_tokens=tokens, temperature=temp)
        return text, "anthropic"
    except Exception as error:
        try:
            from sentiment.claude_circuit import mark_claude_unavailable

            mark_claude_unavailable(error, source=purpose)
        except Exception:
            pass
        raise


def chat_json(
    *,
    system: str,
    user: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    settings: Optional[Dict[str, Any]] = None,
    purpose: str = "chat",
) -> Tuple[Dict[str, Any], str]:
    """Run chat completion and parse JSON object from response text."""
    text, provider = chat_text(
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
        settings=settings,
        purpose=purpose,
    )
    return extract_json_object(text), provider
