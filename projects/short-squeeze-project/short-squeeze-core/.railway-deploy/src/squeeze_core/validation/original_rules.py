"""The original platform's rules, as actually implemented at detection.

Reconstructed read-only from `ScreenerProject` commit `b016d92f` (2026-07-17T11:56:43
America/New_York) -- the last commit before the advisor meeting began at 12:46:15. The
archived working tree is a *later* commit that includes a Prime/Subprime redesign made
2h53m after the meeting; describing the original rules from it would attribute
`classify_tier()` to the BIYA event, and that function did not exist yet.

Everything here is descriptive evidence. Nothing is corrected, and where implementation
disagrees with documentation both are recorded (see docs/phase-2v-original-rule-
manifest.md for the full narrative and citations).
"""

from .models import OriginalRuleDefinition

DETECTION_COMMIT = "b016d92f"

RULE_PRIME_SUBPRIME = OriginalRuleDefinition(
    rule_id="RULE-001-PRIME-SUBPRIME",
    display_name="Prime Setup / Subprime Setup",
    implemented_formula=(
        "score = (2 <= price <= 20) + (change_percent >= 10) + (rel_volume >= 5) + "
        "(short_float_percent >= 5); Prime when score == 4, Subprime when score == 3, "
        "otherwise the row is dropped"
    ),
    intended_meaning="this ticker is set up for a short squeeze",
    actual_input_fields=("change_percent", "price", "rel_volume", "short_float_percent"),
    providers=("ibkr", "yfinance"),
    thresholds=("change_percent>=10", "price in [2,20]", "rel_volume>=5", "short_float>=5"),
    missing_value_behavior="upstream row construction supplies defaults, so every row is scored",
    original_output_field="tier",
    known_mislabeling=(
        "the label names a squeeze classification, but the rubric reads no squeeze mechanic: "
        "borrow fee, days to cover, and TTM Squeeze are computed and displayed yet never scored"
    ),
    source_file="core/scoring.py",
    source_lines_or_symbol="score_setup(); applied at core/ib_api.py:208 and core/filters.py:98",
    source_commit=DETECTION_COMMIT,
)

RULE_SHORT_INTEREST_LABEL = OriginalRuleDefinition(
    rule_id="RULE-002-SHORT-INTEREST-COLUMN",
    display_name="Short Interest (%)",
    implemented_formula="round((shares_short / float_shares) * 100, 2)",
    intended_meaning="the security's short interest",
    actual_input_fields=("float_shares", "shares_short"),
    providers=("yfinance",),
    missing_value_behavior=(
        "returns (None, reason); falls back to the provider's own shortPercentOfFloat with flag "
        "short_float_percent_provider_supplied; disagreement beyond 2.0 points raises "
        "short_float_percent_discrepancy"
    ),
    unit_behavior="percent of float, not an absolute share count",
    original_output_field="ShortFloat / short_float_percent",
    known_mislabeling=(
        "column renamed from 'Short Float %' to 'Short Interest %' at commit 05c81f85, 2h04m "
        "before the meeting; 'Short Interest' unqualified denotes an absolute share count, while "
        "the displayed value is a percentage of float"
    ),
    source_file="core/short_interest.py",
    source_lines_or_symbol="calculate_short_float_percent(); display in ui/view.py, static/index.html",
    source_commit=DETECTION_COMMIT,
)

RULE_DAYS_TO_COVER = OriginalRuleDefinition(
    rule_id="RULE-003-DAYS-TO-COVER",
    display_name="Days to Cover",
    implemented_formula="round(shares_short / average_daily_volume, 2)",
    intended_meaning="sessions required to repurchase the outstanding short position",
    actual_input_fields=("average_daily_volume", "shares_short"),
    providers=("ibkr", "yfinance"),
    missing_value_behavior="returns (None, reason) and flags days_to_cover_unavailable; never zero",
    timestamp_behavior=(
        "numerator derives from a twice-monthly FINRA filing but is displayed beside live price "
        "and volume with no delay indicator; denominator served from a cache with a 1-hour TTL "
        "at this commit"
    ),
    unit_behavior="days",
    original_output_field="DaysToCover",
    source_file="core/short_interest.py",
    source_lines_or_symbol=(
        "calculate_days_to_cover(); called at core/ib_api.py:517 with avg_volume from "
        "core/ib_api.py:609 (statistics.mean(volumes[:-1]), excluding the incomplete current bar)"
    ),
    source_commit=DETECTION_COMMIT,
)

RULE_NEWS = OriginalRuleDefinition(
    rule_id="RULE-004-NEWS-TIMESTAMP",
    display_name="Breaking News",
    implemented_formula=(
        'headline = content.get("title", "No title"); '
        'timestamp = content.get("pubDate", "Unknown time")'
    ),
    intended_meaning="the latest catalyst news for this ticker, with its publication time",
    actual_input_fields=("pubDate", "summary", "title"),
    providers=("newsapi", "yfinance"),
    missing_value_behavior=(
        'a missing publication time becomes the literal string "Unknown time" and a missing '
        'title becomes "No title", so absence is type-indistinguishable from a real value'
    ),
    timestamp_behavior=(
        "provider string passed through unparsed, with no timezone normalization and no "
        "distinction among publication, update, capture, and receipt time"
    ),
    original_output_field="Headline",
    known_mislabeling=(
        'the displayed time may read "Unknown time" while occupying a field presented as a '
        "publication timestamp"
    ),
    source_file="core/yfinance_news_api.py",
    source_lines_or_symbol="line 52; core/newsapi_news_api.py:65",
    source_commit=DETECTION_COMMIT,
)

RULE_MARKET_DATA_FRESHNESS = OriginalRuleDefinition(
    rule_id="RULE-005-MARKET-DATA-FRESHNESS",
    display_name="Price / Change % / Relative Volume",
    implemented_formula="IB streaming market data, with fallback to delayed data on error 10089",
    intended_meaning="near-real-time market state, refreshed minute by minute",
    actual_input_fields=("change_percent", "price", "rel_volume"),
    providers=("ibkr",),
    missing_value_behavior="flags rel_volume_unavailable / historical_bars_unavailable",
    timestamp_behavior=(
        "the account lacked the required market-data subscription, so every symbol including "
        "BIYA fell back to delayed data; the interface carried no delayed-data indicator"
    ),
    original_output_field="Price / ChangePercent / RelVolume",
    known_mislabeling="delayed values presented in a screener described as near-real-time",
    source_file="core/ib_api.py",
    source_lines_or_symbol="market data subscription path; observed in logs/app.log as error 10089",
    source_commit=DETECTION_COMMIT,
)

RULE_CORROBORATION = OriginalRuleDefinition(
    rule_id="RULE-006-CROSS-PROVIDER-CORROBORATION",
    display_name="Cross-provider corroboration",
    implemented_formula="score_setup() reapplied to a second provider's numbers for the same ticker",
    intended_meaning="independent confirmation of a candidate from a second data source",
    actual_input_fields=("change_percent", "price", "rel_volume", "short_float_percent"),
    providers=("schwab",),
    missing_value_behavior="corroboration silently absent when the provider call fails",
    timestamp_behavior=(
        "every corroboration call during the observed run failed with DNS resolution errors on "
        "api.schwabapi.com, and the absence was not surfaced in the interface"
    ),
    original_output_field="corroboration_score / corroborated_by",
    known_mislabeling=(
        "reapplying the same rubric tests data agreement, not rule validity, so agreement is "
        "weaker evidence than the term 'corroboration' implies"
    ),
    source_file="core/schwab_api.py",
    source_lines_or_symbol="score_tickers_for_corroboration()",
    source_commit=DETECTION_COMMIT,
)

RULE_SQUEEZE_SCORE = OriginalRuleDefinition(
    rule_id="RULE-007-COMPOSITE-SQUEEZE-SCORE",
    display_name="Squeeze Score",
    implemented_formula=(
        "weighted mean of saturating-linear sub-scores: short_float 25/55, borrow_fee 20/55, "
        "days_to_cover 10/55; missing inputs excluded and remaining weights renormalized"
    ),
    intended_meaning="composite short-squeeze pressure from 0 to 100",
    actual_input_fields=("days_to_cover", "ib_borrow_fee_rate", "short_float_percent"),
    providers=("ibkr", "yfinance"),
    missing_value_behavior="None in, None out; excluded from the composite and never treated as zero",
    unit_behavior="unitless 0-100 composite",
    original_output_field="SqueezeScore",
    known_mislabeling=(
        "displayed as an independent column that did not gate Prime/Subprime at this commit, so a "
        "ticker could show a low composite score and still be labelled Prime"
    ),
    source_file="core/squeeze_score.py",
    source_lines_or_symbol="compute_squeeze_score(); classify_tier() did not exist at this commit",
    source_commit=DETECTION_COMMIT,
    implemented_but_not_documented=True,
)

ORIGINAL_RULES: tuple[OriginalRuleDefinition, ...] = tuple(
    sorted(
        (
            RULE_PRIME_SUBPRIME,
            RULE_SHORT_INTEREST_LABEL,
            RULE_DAYS_TO_COVER,
            RULE_NEWS,
            RULE_MARKET_DATA_FRESHNESS,
            RULE_CORROBORATION,
            RULE_SQUEEZE_SCORE,
        ),
        key=lambda item: item.rule_id,
    )
)


def lookup_rule(rule_id: str) -> OriginalRuleDefinition:
    for rule in ORIGINAL_RULES:
        if rule.rule_id == rule_id:
            return rule
    raise KeyError(f"unknown original rule: {rule_id}")


__all__ = [
    "DETECTION_COMMIT",
    "ORIGINAL_RULES",
    "RULE_CORROBORATION",
    "RULE_DAYS_TO_COVER",
    "RULE_MARKET_DATA_FRESHNESS",
    "RULE_NEWS",
    "RULE_PRIME_SUBPRIME",
    "RULE_SHORT_INTEREST_LABEL",
    "RULE_SQUEEZE_SCORE",
    "lookup_rule",
]
