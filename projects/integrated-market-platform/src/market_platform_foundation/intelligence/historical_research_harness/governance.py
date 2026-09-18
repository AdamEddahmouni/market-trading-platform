"""Governance banners for historical research harness runs."""

from __future__ import annotations

from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT


def historical_research_governance_lines() -> tuple[str, ...]:
    return (
        f"AUTHORITY: {CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT}",
        "ITEM9_EFFECT: NONE",
        "ITEM7_EFFECT: NONE",
        "FTEP_EFFECT: NONE",
        "LIVE_AUTHORITY: NONE",
        "PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED",
        "CALIBRATION_STATE_CHANGED: NO",
    )


__all__ = ["historical_research_governance_lines"]
