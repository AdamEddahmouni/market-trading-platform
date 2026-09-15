"""Known reference Pine fixtures (imported != approved; registry holds status)."""

from __future__ import annotations

from dataclasses import dataclass

FIXTURE_SMA_CROSSOVER = "imp.pinets.fixture.sma_crossover"
FIXTURE_RSI_THRESHOLD = "imp.pinets.fixture.rsi_threshold"
FIXTURE_SIMPLE_BREAKOUT = "imp.pinets.fixture.simple_breakout"


@dataclass(frozen=True, slots=True)
class PineFixtureDefinition:
    script_id: str
    title: str
    pine_source: str
    reference_parameters: dict[str, int | float]


SMA_CROSSOVER_FIXTURE = PineFixtureDefinition(
    script_id=FIXTURE_SMA_CROSSOVER,
    title="SMA crossover (fast/slow)",
    reference_parameters={"fast_length": 3, "slow_length": 5},
    pine_source="// Reference fixture — execute via isolated PineTS research bridge only.\n"
    "// @version=5\nindicator(\"IMP SMA Crossover Ref\", overlay=true)\n"
    "fastLen = input.int(3, \"Fast\")\n"
    "slowLen = input.int(5, \"Slow\")\n"
    "fast = ta.sma(close, fastLen)\n"
    "slow = ta.sma(close, slowLen)\n"
    "plot(fast, color=color.green)\n"
    "plot(slow, color=color.red)\n",
)

RSI_THRESHOLD_FIXTURE = PineFixtureDefinition(
    script_id=FIXTURE_RSI_THRESHOLD,
    title="RSI threshold",
    reference_parameters={"rsi_length": 3, "oversold": 30.0},
    pine_source="// Reference fixture — execute via isolated PineTS research bridge only.\n"
    "// @version=5\nindicator(\"IMP RSI Threshold Ref\")\n"
    "len = input.int(3, \"RSI Length\")\n"
    "level = input.float(30, \"Oversold\")\n"
    "r = ta.rsi(close, len)\n"
    "plot(r)\n"
    "hline(level)\n",
)

SIMPLE_BREAKOUT_FIXTURE = PineFixtureDefinition(
    script_id=FIXTURE_SIMPLE_BREAKOUT,
    title="Simple breakout",
    reference_parameters={"lookback": 4},
    pine_source="// Reference fixture — execute via isolated PineTS research bridge only.\n"
    "// @version=5\nindicator(\"IMP Breakout Ref\", overlay=true)\n"
    "lb = input.int(4, \"Lookback\")\n"
    "hh = ta.highest(high, lb)\n"
    "plot(hh)\n",
)

BUILTIN_PINETS_FIXTURES: tuple[PineFixtureDefinition, ...] = (
    SMA_CROSSOVER_FIXTURE,
    RSI_THRESHOLD_FIXTURE,
    SIMPLE_BREAKOUT_FIXTURE,
)
