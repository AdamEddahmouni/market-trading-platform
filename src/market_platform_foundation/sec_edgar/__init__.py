"""Public SEC EDGAR regulatory evidence path (ADR-EDGAR-001).

Live observations are not admitted research datasets. Ordinary CI is fixture-only.
"""

from .dilution import DilutionEvidence, dilution_from_filing
from .filing import FilingEvent, submissions_to_filings
from .identity import EntityMap, normalize_accession, pad_cik
from .store import FilingStore
from .transport import SecTransport, require_user_agent

__all__ = [
    "DilutionEvidence",
    "EntityMap",
    "FilingEvent",
    "FilingStore",
    "SecTransport",
    "dilution_from_filing",
    "normalize_accession",
    "pad_cik",
    "require_user_agent",
    "submissions_to_filings",
]
