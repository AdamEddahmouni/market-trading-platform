"""Versioned discovery screen library."""

from __future__ import annotations

from .models import ScreenDefinition

SCHEMA_VERSION = "discovery.screen/1.0.0"

SHORT_SQUEEZE_DISCOVERY = ScreenDefinition(
    screen_id="SHORT_SQUEEZE_DISCOVERY",
    version="1.0.0",
    description="Broad short-squeeze candidate discovery via Finviz Elite",
    filters="sh_float_u50,sh_price_u50,sh_short_o20,sh_relvol_o1.5",
    sort="sh_short",
    max_results=50,
    required_fields=("short_float_pct", "float_shares", "rel_volume"),
    reason="Identify elevated short-float names with unusual relative volume for canonical lane verification",
)

UNUSUAL_VOLUME_DISCOVERY = ScreenDefinition(
    screen_id="UNUSUAL_VOLUME_DISCOVERY",
    version="1.0.0",
    description="Relative volume spike discovery",
    filters="sh_relvol_o2",
    sort="sh_relvol",
    max_results=50,
    required_fields=("rel_volume", "volume"),
    reason="Surface unusual volume for operator inspection",
)

MOMENTUM_IGNITION_DISCOVERY = ScreenDefinition(
    screen_id="MOMENTUM_IGNITION_DISCOVERY",
    version="1.0.0",
    description="Momentum ignition with volume confirmation",
    filters="ta_change_u10,sh_relvol_o1.5",
    sort="ta_change",
    max_results=40,
    required_fields=("change_pct", "rel_volume"),
    reason="Momentum + volume combination for tape inspection",
)

GAP_CATALYST_DISCOVERY = ScreenDefinition(
    screen_id="GAP_CATALYST_DISCOVERY",
    version="1.0.0",
    description="Gap movers for catalyst follow-up",
    filters="ta_gap_u5",
    sort="ta_gap",
    max_results=40,
    required_fields=("change_pct"),
    reason="Gap discovery for catalyst lane enrichment",
)

EARNINGS_MOVER_DISCOVERY = ScreenDefinition(
    screen_id="EARNINGS_MOVER_DISCOVERY",
    version="1.0.0",
    description="Earnings-week movers",
    filters="earningsdate_thisweek",
    sort="sh_change",
    max_results=40,
    required_fields=("earnings_date", "change_pct"),
    reason="Earnings context discovery",
)

ANALYST_EVENT_DISCOVERY = ScreenDefinition(
    screen_id="ANALYST_EVENT_DISCOVERY",
    version="1.0.0",
    description="Analyst recommendation changes",
    filters="an_recom_buybetter",
    sort="sh_change",
    max_results=40,
    required_fields=("recommendation", "change_pct"),
    reason="Analyst event discovery — not a trade signal",
)

INSIDER_ACTIVITY_DISCOVERY = ScreenDefinition(
    screen_id="INSIDER_ACTIVITY_DISCOVERY",
    version="1.0.0",
    description="Insider buying activity screen",
    filters="sh_insidertrans_o10",
    sort="sh_insidertrans",
    max_results=40,
    required_fields=("change_pct"),
    reason="Insider discovery trigger — SEC filing authority retained",
)

TECHNICAL_BREAKOUT_DISCOVERY = ScreenDefinition(
    screen_id="TECHNICAL_BREAKOUT_DISCOVERY",
    version="1.0.0",
    description="Technical breakout candidates",
    filters="ta_highlow52w_nh",
    sort="sh_change",
    max_results=40,
    required_fields=("change_pct", "perf_week"),
    reason="Technical breakout discovery for workspace inspection",
)

SCREEN_LIBRARY: dict[str, ScreenDefinition] = {
    screen.screen_id: screen
    for screen in (
        SHORT_SQUEEZE_DISCOVERY,
        UNUSUAL_VOLUME_DISCOVERY,
        MOMENTUM_IGNITION_DISCOVERY,
        GAP_CATALYST_DISCOVERY,
        EARNINGS_MOVER_DISCOVERY,
        ANALYST_EVENT_DISCOVERY,
        INSIDER_ACTIVITY_DISCOVERY,
        TECHNICAL_BREAKOUT_DISCOVERY,
    )
}


def get_screen(screen_id: str) -> ScreenDefinition | None:
    return SCREEN_LIBRARY.get(screen_id.upper())


def list_screens() -> list[dict[str, object]]:
    return [screen.to_dict() for screen in SCREEN_LIBRARY.values()]
