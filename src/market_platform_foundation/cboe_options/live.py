"""Live Cboe public options statistics configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .transport import CboeOptionsTransport, USER_AGENT


def live_enabled(environ: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    return values.get("IMP_CBOE_OPTIONS_LIVE") == "1"


def transport_from_env(environ: Mapping[str, str] | None = None) -> CboeOptionsTransport:
    values = os.environ if environ is None else environ
    user_agent = values.get("IMP_CBOE_OPTIONS_USER_AGENT", USER_AGENT).strip() or USER_AGENT
    return CboeOptionsTransport(user_agent=user_agent)


__all__ = ["live_enabled", "transport_from_env"]
