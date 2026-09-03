"""Live CFTC transport factory and environment helpers."""

from __future__ import annotations

import os

from .transport import CotTransport


def transport_from_env() -> CotTransport:
    base_url = os.environ.get("CFTC_SODA_BASE_URL", "https://publicreporting.cftc.gov/resource")
    user_agent = os.environ.get("CFTC_USER_AGENT", CotTransport().user_agent)
    return CotTransport(base_url=base_url, user_agent=user_agent)


__all__ = ["transport_from_env"]
