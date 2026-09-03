"""Frozen official-evidence inputs for IBKR historical-bar semantic resolution.

Every value here is a *documented fact* traceable to an exact official Interactive
Brokers source or the installed official ``ibapi`` contract, or an explicit
"absent"/"unresolved" marker where official evidence is silent. Nothing in this
module accesses the network, the Gateway, account data, or bar (OHLCV) values --
web research and local-config inspection are performed by evidence *tooling* and
their conclusions are frozen here as constants so the resolver stays pure and
deterministic.

The evidence classes are never blurred: an official documented fact, the installed
API contract, a local observation, and a project inference are distinct.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceClass(StrEnum):
    """Disjoint provenance classes; never blurred into one another."""

    OFFICIAL_DOC = "OFFICIAL_DOC"
    INSTALLED_API_CONTRACT = "INSTALLED_API_CONTRACT"
    LOCAL_BATCH05_OBSERVATION = "LOCAL_BATCH05_OBSERVATION"
    LOCAL_GATEWAY_CONFIG = "LOCAL_GATEWAY_CONFIG"
    PROJECT_INFERENCE = "PROJECT_INFERENCE"


class TimestampBoundaryDoc(StrEnum):
    """What official evidence establishes about intraday bar timestamp boundary."""

    START = "START"
    END = "END"
    ABSENT = "ABSENT"  # not established by official docs or the API contract


class VolumeUnitResolution(StrEnum):
    """Shares vs round lots, or an honest unresolved marker. Not a manifest field."""

    SHARES = "SHARES"
    ROUND_LOTS = "ROUND_LOTS"
    HISTORICAL_VOLUME_UNIT_UNRESOLVED = "HISTORICAL_VOLUME_UNIT_UNRESOLVED"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SemanticEvidenceCitation(_Frozen):
    """One traceable evidence statement supporting one resolved field."""

    supports_field: str = Field(min_length=1)
    evidence_class: EvidenceClass
    source: str = Field(min_length=1)  # canonical URL or sanitized path category
    section: str = ""
    paraphrase: str = Field(min_length=1)


class IbkrHistoricalSemanticEvidence(_Frozen):
    """Documented request parameters and official-fact flags for one collection.

    Boolean/enum flags reflect what official evidence *establishes*, not what the
    project assumes. ``*_documented`` flags being ``False`` means "official docs are
    silent", which yields ``UNKNOWN`` downstream -- never a fabricated value.
    """

    what_to_show: str = Field(min_length=1)
    format_date: int
    use_rth: int
    # Price corporate-action adjustment (official for TRADES).
    trades_split_adjusted: bool
    trades_dividend_adjusted: bool
    # Volume corporate-action adjustment: only resolvable if officially documented.
    volume_corporate_action_documented: bool
    volume_split_adjusted: bool  # meaningful only if volume_corporate_action_documented
    # Bar timestamp boundary as established by official docs / installed API.
    bar_timestamp_boundary: TimestampBoundaryDoc
    # formatDate=2 => "seconds since 1/1/1970 GMT" per installed ibapi contract.
    epoch_seconds_gmt: bool
    # Shares vs round lots; provenance only, never gates preflight.
    volume_unit: VolumeUnitResolution


# --- Frozen official evidence for the Batch 05 TRADES collection -------------------
#
# whatToShow=TRADES, formatDate=2, useRTH=0 (all captured in the Batch 05 request
# manifest). Split-adjusted-not-dividend is officially documented; volume
# corporate-action treatment and intraday bar start/end are officially ABSENT;
# volume unit is unresolved (see docs/batch-06-volume-unit-resolution.md).

OFFICIAL_TRADES_EVIDENCE = IbkrHistoricalSemanticEvidence(
    what_to_show="TRADES",
    format_date=2,
    use_rth=0,
    trades_split_adjusted=True,
    trades_dividend_adjusted=False,
    volume_corporate_action_documented=False,
    volume_split_adjusted=False,
    bar_timestamp_boundary=TimestampBoundaryDoc.ABSENT,
    epoch_seconds_gmt=True,
    volume_unit=VolumeUnitResolution.HISTORICAL_VOLUME_UNIT_UNRESOLVED,
)


OFFICIAL_CITATIONS: tuple[SemanticEvidenceCitation, ...] = (
    SemanticEvidenceCitation(
        supports_field="price_adjustment_semantics",
        evidence_class=EvidenceClass.OFFICIAL_DOC,
        source="https://interactivebrokers.github.io/tws-api/historical_bars.html",
        section="Historical Data Types",
        paraphrase="TRADES data is adjusted for splits, but not dividends.",
    ),
    SemanticEvidenceCitation(
        supports_field="corporate_action_handling",
        evidence_class=EvidenceClass.OFFICIAL_DOC,
        source="https://interactivebrokers.github.io/tws-api/historical_bars.html",
        section="Historical Data Types",
        paraphrase="Splits are applied to TRADES data, so an adjustment is applied.",
    ),
    SemanticEvidenceCitation(
        supports_field="volume_adjustment_semantics",
        evidence_class=EvidenceClass.OFFICIAL_DOC,
        source="https://interactivebrokers.github.io/tws-api/historical_bars.html",
        section="Historical Data Types",
        paraphrase=(
            "Official docs state split adjustment for TRADES price but are silent on "
            "volume corporate-action treatment; volume is therefore left UNKNOWN."
        ),
    ),
    SemanticEvidenceCitation(
        supports_field="event_timezone",
        evidence_class=EvidenceClass.INSTALLED_API_CONTRACT,
        source="C:/TWS API/source/pythonclient/ibapi/client.py::reqHistoricalData",
        section="formatDate docstring",
        paraphrase="formatDate=2 returns a long integer of seconds since 1/1/1970 GMT.",
    ),
    SemanticEvidenceCitation(
        supports_field="timestamp_semantics",
        evidence_class=EvidenceClass.OFFICIAL_DOC,
        source="https://interactivebrokers.github.io/tws-api/historical_bars.html",
        section="Historical Bar Data",
        paraphrase=(
            "Only the daily-bar close-date rule is documented; intraday bar start/end "
            "is absent, so timestamp_semantics stays UNKNOWN."
        ),
    ),
    SemanticEvidenceCitation(
        supports_field="session_coverage",
        evidence_class=EvidenceClass.INSTALLED_API_CONTRACT,
        source="C:/TWS API/source/pythonclient/ibapi/client.py::reqHistoricalData",
        section="useRTH docstring",
        paraphrase="useRTH=0 returns all data even where the market was outside RTH.",
    ),
    SemanticEvidenceCitation(
        supports_field="filtered_feed_disclosure",
        evidence_class=EvidenceClass.OFFICIAL_DOC,
        source="https://interactivebrokers.github.io/tws-api/historical_data.html",
        section="Historical Market Data",
        paraphrase=(
            "Historical data is filtered for trade types away from the NBBO; unfiltered "
            "real-time volume is generally larger than filtered historical volume."
        ),
    ),
    SemanticEvidenceCitation(
        supports_field="volume_unit",
        evidence_class=EvidenceClass.LOCAL_GATEWAY_CONFIG,
        source="C:/Jts/ibgateway/1045 (jts.ini plaintext; ibg.*.xml obfuscated binary)",
        section="API settings",
        paraphrase=(
            "The lots setting is not in Batch 05 capture and lives only in obfuscated "
            "binary config; volume unit is left HISTORICAL_VOLUME_UNIT_UNRESOLVED."
        ),
    ),
)


FILTERED_FEED_DISCLOSURE = (
    "IBKR historical trade data is provider-filtered (trade types away from the NBBO "
    "such as combo legs, block trades, and derivative trades are excluded) and may have "
    "lower volume than an unfiltered feed; it is not complete consolidated-market volume."
)


__all__ = [
    "EvidenceClass",
    "TimestampBoundaryDoc",
    "VolumeUnitResolution",
    "SemanticEvidenceCitation",
    "IbkrHistoricalSemanticEvidence",
    "OFFICIAL_TRADES_EVIDENCE",
    "OFFICIAL_CITATIONS",
    "FILTERED_FEED_DISCLOSURE",
]
