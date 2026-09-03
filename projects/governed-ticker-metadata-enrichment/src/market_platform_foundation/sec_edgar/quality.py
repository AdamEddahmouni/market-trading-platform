"""Quality mapping. Unreachable SEC is not 'no filings'."""

from __future__ import annotations


def quality_from_failure(exc: BaseException) -> tuple[str, ...]:
    text = str(exc)
    if "SEC_HTTP_404" in text:
        return ("CAPABILITY_UNAVAILABLE",)
    return ("SOURCE_UNAVAILABLE", "TEMPORARILY_UNAVAILABLE")
