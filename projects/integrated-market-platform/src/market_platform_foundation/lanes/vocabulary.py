"""Single mapping table for the three lane vocabularies (hardening P1-4).

Vocabularies (never interchangeable):

1. **Discovery** — screener attention buckets ``MOMENTUM`` / ``SQUEEZE`` /
   ``CATALYST`` / ``SWING`` from ``discovery/mixed.py``.
2. **Workspace kebab** — UI module ids such as ``squeeze``, ``order-flow``,
   ``catalyst`` from ``WORKSPACE_LANE_REGISTRY``.
3. **Evidence ``LaneId``** — research-family publisher ids such as
   ``short_squeeze`` / ``market_context`` from ``cross_lane.evidence.LaneId``.

UI workstation envelopes also use UPPER_SNAKE tokens (``MARKET_CONTEXT``).
Those are listed separately and must agree with the TypeScript map in
``paperDecisionSemantics.ts``.

``LaneId.MARKET_CONTEXT`` is the information / catalyst / narrative family
(see ``MARKET_CONTEXT_GLOSSARY.md``). It maps to workspace ``catalyst``,
not ``order-book`` (L2 book UI) and not ``order-flow`` (microstructure).
"""

from __future__ import annotations

from typing import Mapping

# Discovery attention buckets produced by mixed-queue aggregation.
DISCOVERY_LANES: frozenset[str] = frozenset({"MOMENTUM", "SQUEEZE", "CATALYST", "SWING"})

# Screener-only buckets have no workspace page.
DISCOVERY_LANE_TO_WORKSPACE_MODULE: dict[str, str | None] = {
    "SQUEEZE": "squeeze",
    "CATALYST": "catalyst",
    "MOMENTUM": None,
    "SWING": None,
}

# cross_lane.evidence.LaneId values → workspace module (None = no page).
LANE_ID_TO_WORKSPACE_MODULE: dict[str, str | None] = {
    "short_squeeze": "squeeze",
    "order_flow": "order-flow",
    "market_context": "catalyst",
    "catalyst": "catalyst",
    "attention": "catalyst",
    "options": "options",
    "futures": "futures",
    "participant_intelligence": "institutional-flow",
    "crypto": None,
    "prediction_market": None,
}

# ui_api.workspace_evidence lane tokens → workspace module.
UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE: dict[str, str] = {
    "SHORT_SQUEEZE": "squeeze",
    "ORDER_FLOW": "order-flow",
    "MARKET_CONTEXT": "catalyst",
    "CATALYST": "catalyst",
    "OPTIONS": "options",
    "FUTURES": "futures",
    "SHORT_INTELLIGENCE": "disclosure",
    "WHALE_INSIDER": "institutional-flow",
}


def workspace_module_for_discovery_lane(lane: str) -> str | None:
    key = str(lane).strip().upper()
    if key not in DISCOVERY_LANES:
        raise KeyError(f"UNKNOWN_DISCOVERY_LANE:{lane}")
    return DISCOVERY_LANE_TO_WORKSPACE_MODULE[key]


def workspace_module_for_lane_id(lane_id: str) -> str | None:
    key = str(lane_id).strip().lower()
    if key not in LANE_ID_TO_WORKSPACE_MODULE:
        raise KeyError(f"UNKNOWN_EVIDENCE_LANE_ID:{lane_id}")
    return LANE_ID_TO_WORKSPACE_MODULE[key]


def workspace_module_for_ui_evidence_lane(lane: str) -> str | None:
    key = str(lane).strip().upper()
    return UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE.get(key)


def mapping_tables() -> Mapping[str, Mapping[str, str | None]]:
    return {
        "discovery": DISCOVERY_LANE_TO_WORKSPACE_MODULE,
        "lane_id": LANE_ID_TO_WORKSPACE_MODULE,
        "ui_evidence": UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE,
    }
