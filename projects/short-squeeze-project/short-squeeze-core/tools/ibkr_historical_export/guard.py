"""Static safety guard: prove forbidden IBKR API methods are absent from the tool.

The exporter's session layer subclasses ``ibapi`` ``EClient``/``EWrapper``, which
*inherit* order/account/portfolio methods. "Absent from the exporter" therefore means
absent from *our* source: the tool never references, calls, or overrides any forbidden
method. :func:`scan_source_for_forbidden` enforces that by scanning the package's own
``.py`` files.
"""

from __future__ import annotations

import re
from pathlib import Path

# The only IBKR client/wrapper API surface the tool is permitted to reference.
ALLOWED_API_METHODS: frozenset[str] = frozenset({
    # client
    "connect", "eConnect", "disconnect", "eDisconnect", "isConnected", "run",
    "serverVersion", "reqCurrentTime", "reqContractDetails", "reqHistoricalData",
    "cancelHistoricalData",
    # wrapper callbacks
    "connectAck", "nextValidId", "managedAccounts", "error", "contractDetails",
    "contractDetailsEnd", "historicalData", "historicalDataEnd", "currentTime",
})

# Forbidden methods -- must never appear in tool source. Order/account/portfolio/
# execution/market-data-subscription/scanner surface.
FORBIDDEN_API_METHODS: frozenset[str] = frozenset({
    "placeOrder", "cancelOrder", "reqOpenOrders", "reqAllOpenOrders",
    "reqAutoOpenOrders", "reqGlobalCancel",
    "reqPositions", "reqPositionsMulti", "reqAccountSummary", "reqAccountUpdates",
    "reqAccountUpdatesMulti", "reqExecutions", "reqCompletedOrders",
    "reqPnL", "reqPnLSingle",
    "reqMarketDataType", "reqMktData", "reqRealTimeBars", "reqScannerSubscription",
    "reqScannerParameters", "reqNewsBulletins", "reqHistogramData",
})

# Order/trading object names that must never be imported or instantiated.
FORBIDDEN_OBJECT_NAMES: frozenset[str] = frozenset({
    "Order", "OrderState", "OrderCancel", "Execution", "ExecutionFilter",
})


def _iter_python_sources(package_dir: Path) -> list[Path]:
    return sorted(p for p in package_dir.rglob("*.py") if "__pycache__" not in p.parts)


def scan_source_for_forbidden(package_dir: Path) -> list[str]:
    """Return a list of violation strings (empty when the tool is clean).

    This module names the forbidden methods for documentation, so it excludes itself
    from the scan; the enforcement target is every *other* module in the package.
    """
    violations: list[str] = []
    self_name = Path(__file__).name
    for source in _iter_python_sources(package_dir):
        if source.name == self_name:
            continue
        text = source.read_text(encoding="utf-8")
        for method in FORBIDDEN_API_METHODS:
            if re.search(rf"\b{re.escape(method)}\b", text):
                violations.append(f"{source.name}: forbidden method reference {method!r}")
        for obj in FORBIDDEN_OBJECT_NAMES:
            # Match import/instantiation, not incidental substrings.
            if re.search(rf"\b{re.escape(obj)}\s*\(", text) or re.search(
                rf"\bimport\b[^\n]*\b{re.escape(obj)}\b", text
            ):
                violations.append(f"{source.name}: forbidden object reference {obj!r}")
    return violations


def package_dir() -> Path:
    return Path(__file__).resolve().parent


__all__ = [
    "ALLOWED_API_METHODS",
    "FORBIDDEN_API_METHODS",
    "FORBIDDEN_OBJECT_NAMES",
    "scan_source_for_forbidden",
    "package_dir",
]
