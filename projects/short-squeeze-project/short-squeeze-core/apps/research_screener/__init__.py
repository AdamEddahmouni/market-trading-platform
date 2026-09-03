"""Short Squeeze Research Screener — a read-only view/controller layer.

This package renders evidence that already exists. It contains no metric formula, no rule
logic, no score, no ranking model, and no order or account access. Everything it shows is
either read from a frozen canonical artifact or retrieved read-only from a local provider
and labelled as not admissibility-gated.
"""

from __future__ import annotations

APP_TITLE = "Short Squeeze Research Screener"
DISCLAIMER = "RESEARCH TOOL"
SCHEMA_VERSION = "1.0.0"

__all__ = ["APP_TITLE", "DISCLAIMER", "SCHEMA_VERSION"]
