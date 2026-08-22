"""Source authority matrix for Finviz vs Moomoo vs SEC/FINRA."""

from __future__ import annotations

from typing import Any

AUTHORITY_MATRIX: dict[str, dict[str, str]] = {
    "broad_screening": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "candidate_discovery": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "fundamental_snapshot": {"authority": "FINVIZ_ELITE", "role": "CONTEXT"},
    "technical_screening": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "relative_volume": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "short_float_discovery": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "official_short_interest": {"authority": "FINRA", "role": "REGULATORY"},
    "threshold_status": {"authority": "OFFICIAL_REGSHO", "role": "REGULATORY"},
    "fail_to_deliver": {"authority": "SEC", "role": "REGULATORY"},
    "sec_filings": {"authority": "SEC_EDGAR", "role": "REGULATORY"},
    "filing_discovery_alert": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY_TRIGGER"},
    "news_discovery": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "original_news": {"authority": "ORIGINAL_PUBLISHER", "role": "EVIDENCE"},
    "insider_discovery": {"authority": "FINVIZ_ELITE", "role": "DISCOVERY"},
    "insider_filing_truth": {"authority": "SEC", "role": "REGULATORY"},
    "analyst_events": {"authority": "FINVIZ_ELITE", "role": "CONTEXT"},
    "sector_industry_breadth": {"authority": "FINVIZ_ELITE", "role": "CONTEXT"},
    "etf_holdings": {"authority": "FINVIZ_ELITE", "role": "CONTEXT"},
    "live_bbo": {"authority": "MOOMOO", "role": "MARKET_DATA"},
    "live_trades": {"authority": "MOOMOO", "role": "MARKET_DATA"},
    "l2_depth": {"authority": "MOOMOO", "role": "MARKET_DATA"},
    "cvd": {"authority": "IMP_DERIVED", "role": "DERIVED"},
    "internal_fill": {"authority": "EXECUTION_ADMITTED", "role": "EXECUTION_EVIDENCE"},
    "execution": {"authority": "INTERNAL", "role": "EXECUTION"},
}


def authority_for_field(field_family: str) -> dict[str, str]:
    return AUTHORITY_MATRIX.get(field_family, {"authority": "UNKNOWN", "role": "CONTEXT"})


def authority_matrix_payload() -> dict[str, Any]:
    return {"matrix": AUTHORITY_MATRIX, "finviz_execution_role": "NONE"}
