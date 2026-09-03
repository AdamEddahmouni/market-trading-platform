"""Live SEC client. Opt-in only. Observations are never auto-admitted."""

from __future__ import annotations

import os
from urllib.parse import quote

from .filing import FilingEvent, submissions_to_filings
from .identity import pad_cik
from .transport import SecTransport
from .xbrl import XbrlFact, facts_as_of

DATA_HOST = "https://data.sec.gov"
WWW_HOST = "https://www.sec.gov"


def live_enabled() -> bool:
    return os.environ.get("SEC_LIVE_TESTS") == "1" or os.environ.get("IMP_EDGAR_LIVE") == "1"


def transport_from_env() -> SecTransport:
    return SecTransport(user_agent=os.environ.get("SEC_USER_AGENT", ""))


def fetch_submissions(transport: SecTransport, cik: str) -> tuple[FilingEvent, ...]:
    padded = pad_cik(cik)
    url = f"{DATA_HOST}/submissions/CIK{padded}.json"
    body = transport.get(url)
    from datetime import datetime, timezone

    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return submissions_to_filings(body.decode("utf-8"), observed_time=observed)


def fetch_companyfacts(transport: SecTransport, cik: str, *, as_of: str, tag: str) -> tuple[XbrlFact, ...]:
    padded = pad_cik(cik)
    url = f"{DATA_HOST}/api/xbrl/companyfacts/CIK{padded}.json"
    body = transport.get(url)
    return facts_as_of(body.decode("utf-8"), as_of=as_of, tag=tag)


def fetch_primary_document(transport: SecTransport, filing: FilingEvent) -> bytes:
    if not filing.primary_document:
        raise ValueError("PRIMARY_DOCUMENT_MISSING")
    compact = filing.normalized_accession.replace("-", "")
    path = f"/Archives/edgar/data/{int(filing.cik)}/{compact}/{quote(filing.primary_document)}"
    return transport.get(WWW_HOST + path, immutable=True)
