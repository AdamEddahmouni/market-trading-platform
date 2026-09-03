"""Read-only IBKR historical-bar collection tool (Phase 3D Batch 05).

This package is a *collection utility*, deliberately isolated from the
deterministic research runtime in ``src/squeeze_core``. The runtime never imports
it and never gains live IBKR reads. Only :mod:`tools.ibkr_historical_export.session`
imports ``ibapi``; every other module is ibapi-free and unit-testable without a live
Gateway.

The tool connects only to a local IB Gateway, requests contract details and
historical bars for the frozen Batch 01 cohort, and writes provider data solely to
the Git-ignored private intake area. It never places orders, never reads account or
portfolio data, never associates cases, and never computes outcomes.
"""

from .statuses import (
    CollectionStatus,
    ContractStatus,
    HistoricalStatus,
    PreflightStatus,
)

__all__ = [
    "CollectionStatus",
    "ContractStatus",
    "HistoricalStatus",
    "PreflightStatus",
]
