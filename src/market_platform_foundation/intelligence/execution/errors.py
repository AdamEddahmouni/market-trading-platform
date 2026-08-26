"""Execution-layer errors (BUILD 22)."""

from __future__ import annotations


class ExecutionError(Exception):
    """Base execution/risk error."""


class OpportunityGateError(ExecutionError):
    """Opportunity failed execution gate."""


class DirectForecastTradeForbidden(ExecutionError):
    """Forecast cannot bypass OpportunityV1."""


class LiveExecutionForbidden(ExecutionError):
    """Paper path cannot authorize live execution."""


__all__ = [
    "DirectForecastTradeForbidden",
    "ExecutionError",
    "LiveExecutionForbidden",
    "OpportunityGateError",
]
