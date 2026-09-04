"""Deterministic project hook for dangerous shell-operation boundaries."""

from __future__ import annotations

import json
import re
import sys
from typing import Any


DENY_PATTERNS = (
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\b.*(?:-f|--force)", re.IGNORECASE),
    re.compile(r"\bgit\s+checkout\s+--\s+", re.IGNORECASE),
    re.compile(r"\bgit\s+restore\s+--source\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b.*(?:--force|-f\b)", re.IGNORECASE),
    re.compile(
        r"\bgit\s+push\b.*(?:^|\s|[:/])(?:origin/)?(?:main|master)(?:\s|$)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:remove-item|del|erase|rmdir)\b.*(?:-recurse|-force|/s|/q)", re.IGNORECASE),
)


def decision_for(command: str) -> str:
    return "deny" if any(pattern.search(command) for pattern in DENY_PATTERNS) else "allow"


def _command_from_payload(payload: dict[str, Any]) -> str:
    for key in ("command", "cmd"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        value = tool_input.get("command")
        if isinstance(value, str):
            return value
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(json.dumps({"permission": "deny", "user_message": "Invalid hook input; command blocked."}))
        return 2
    command = _command_from_payload(payload if isinstance(payload, dict) else {})
    if decision_for(command) == "deny":
        print(
            json.dumps(
                {
                    "permission": "deny",
                    "user_message": "Blocked destructive Git/filesystem operation or protected-branch push.",
                    "agent_message": "Use an explicit, reviewed workflow for destructive operations or protected branches.",
                }
            )
        )
        return 0
    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
