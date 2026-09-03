"""Static read-only guard for the application package.

The application subclasses ``ibapi`` ``EClient``/``EWrapper``, which *inherit* order,
account and portfolio methods. "The application cannot trade" therefore means: no module
in this package references, calls or overrides any forbidden method, and no user-interface
element offers a trading action.

This is a wider allowance than ``tools/ibkr_historical_export/guard.py``, which stays
narrow: the research exporter still forbids scanner and market-data methods. The extra
surface is scoped to this application and enumerated below.
"""

from __future__ import annotations

import re
from pathlib import Path

#: The only IBKR client/wrapper API surface the application may reference.
ALLOWED_API_METHODS: frozenset[str] = frozenset({
    # client — connection
    "connect", "eConnect", "disconnect", "eDisconnect", "isConnected", "run",
    "serverVersion", "reqCurrentTime",
    # client — contracts and bars
    "reqContractDetails", "reqHistoricalData", "cancelHistoricalData",
    # client — scanner (read-only discovery)
    "reqScannerParameters", "reqScannerSubscription", "cancelScannerSubscription",
    # client — market data (read-only quotes)
    "reqMarketDataType", "reqMktData", "cancelMktData",
    # wrapper callbacks
    "connectAck", "nextValidId", "managedAccounts", "error", "currentTime",
    "contractDetails", "contractDetailsEnd", "historicalData", "historicalDataEnd",
    "scannerParameters", "scannerData", "scannerDataEnd",
    "marketDataType", "tickPrice", "tickSize", "tickGeneric", "tickString",
    "tickSnapshotEnd",
})

#: Forbidden methods — must never appear in application source. Order / account /
#: position / execution / PnL / portfolio surface.
FORBIDDEN_API_METHODS: frozenset[str] = frozenset({
    "placeOrder", "cancelOrder", "reqOpenOrders", "reqAllOpenOrders",
    "reqAutoOpenOrders", "reqGlobalCancel", "reqCompletedOrders",
    "reqPositions", "reqPositionsMulti", "reqAccountSummary", "cancelAccountSummary",
    "reqAccountUpdates", "reqAccountUpdatesMulti", "reqExecutions",
    "reqPnL", "reqPnLSingle", "cancelPnL", "cancelPnLSingle",
    "reqFamilyCodes", "reqManagedAccts",
})

#: Order/trading object names that must never be imported or instantiated.
FORBIDDEN_OBJECT_NAMES: frozenset[str] = frozenset({
    "Order", "OrderState", "OrderCancel", "Execution", "ExecutionFilter",
})

#: Trading actions that must never appear as a user-interface control.
FORBIDDEN_UI_ACTIONS: tuple[str, ...] = (
    "Buy", "Sell", "Trade Now", "Place Order", "Submit Order",
)

#: Interface files scanned for trading actions.
UI_SUFFIXES: tuple[str, ...] = (".html", ".js")

#: Matches an actionable control whose label is a trading verb — a button, a link, or an
#: option. Prose that merely mentions the word is not a control and is not a violation.
_UI_CONTROL_PATTERN = (
    r"<(?:button|a)\b[^>]*>\s*{action}\s*<|"
    r"<option\b[^>]*>\s*{action}\s*<|"
    r"(?:textContent|innerHTML|value)\s*=\s*['\"]{action}['\"]"
)


def _iter_python_sources(package_dir: Path) -> list[Path]:
    return sorted(p for p in package_dir.rglob("*.py") if "__pycache__" not in p.parts)


def _iter_ui_sources(package_dir: Path) -> list[Path]:
    return sorted(
        p for p in package_dir.rglob("*")
        if p.suffix in UI_SUFFIXES and "__pycache__" not in p.parts
    )


def scan_source_for_forbidden(package_dir: Path) -> list[str]:
    """Violations in the application's own Python source (empty when clean).

    This module names the forbidden methods for documentation, so it excludes itself from
    the scan; the enforcement target is every *other* module in the package.
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
            if re.search(rf"\b{re.escape(obj)}\s*\(", text) or re.search(
                rf"\bimport\b[^\n]*\b{re.escape(obj)}\b", text
            ):
                violations.append(f"{source.name}: forbidden object reference {obj!r}")
    return violations


def scan_ui_for_trading_actions(package_dir: Path) -> list[str]:
    """Violations in the application's interface files (empty when clean)."""
    violations: list[str] = []
    for source in _iter_ui_sources(package_dir):
        text = source.read_text(encoding="utf-8")
        for action in FORBIDDEN_UI_ACTIONS:
            pattern = _UI_CONTROL_PATTERN.format(action=re.escape(action))
            if re.search(pattern, text, flags=re.IGNORECASE):
                violations.append(
                    f"{source.name}: trading action control {action!r}"
                )
    return violations


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def verify() -> list[str]:
    """Every violation across source and interface. Empty means the guard passes."""
    root = package_dir()
    return scan_source_for_forbidden(root) + scan_ui_for_trading_actions(root)


__all__ = [
    "ALLOWED_API_METHODS",
    "FORBIDDEN_API_METHODS",
    "FORBIDDEN_OBJECT_NAMES",
    "FORBIDDEN_UI_ACTIONS",
    "package_dir",
    "scan_source_for_forbidden",
    "scan_ui_for_trading_actions",
    "verify",
]
