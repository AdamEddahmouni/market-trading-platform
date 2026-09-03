"""Live weather configuration; core NOAA/NWS/CPC access needs no secret."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .transport import DEFAULT_NWS_USER_AGENT, WeatherTransport, require_nws_user_agent


def load_nws_user_agent(environ: Mapping[str, str] | None = None) -> str:
    values = os.environ if environ is None else environ
    configured = values.get("IMP_NWS_USER_AGENT", "").strip()
    return require_nws_user_agent(configured or DEFAULT_NWS_USER_AGENT)


def live_enabled(environ: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    return values.get("IMP_WEATHER_LIVE") == "1"


def transport_from_env(environ: Mapping[str, str] | None = None) -> WeatherTransport:
    return WeatherTransport(user_agent=load_nws_user_agent(environ))


__all__ = ["live_enabled", "load_nws_user_agent", "transport_from_env"]
