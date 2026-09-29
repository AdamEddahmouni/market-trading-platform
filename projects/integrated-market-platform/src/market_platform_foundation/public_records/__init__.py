"""Official U.S. government public-record sources (Screener S12).

Keyless, official, structured sources only: USAspending.gov (federal award
transactions) and the Lobbying Disclosure Act API (lda.gov). House Clerk
disclosures live in ``congressional_ptr.house``; CFTC positioning in ``cftc``;
SEC ownership in ``sec_edgar.ownership``.

Every adapter is opt-in (``IMP_PUBLIC_RECORDS_LIVE=1``), bounded (timeout, size
cap), and returns provider-neutral records; nothing here is a signal or a score.
"""

from .http import LIVE_ENV, PublicRecordsHttp, PublicRecordsError, live_state

__all__ = ["LIVE_ENV", "PublicRecordsError", "PublicRecordsHttp", "live_state"]
