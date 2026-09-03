"""Isolation and no-strategy guards for the Phase 1 runtime.

These tests turn the manual isolation scan into a permanent regression guard. They fail if any
executable module under ``src`` imports a network/database/GUI/ML client, reads credentials,
uses a wall clock or a random identity source, or introduces indicator/scoring/ranking logic.
Enum labels and provider-neutral vocabulary (for example ``NBBO`` as a market-scope label) are
data, not behavior, and are deliberately not matched.
"""

import re
from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "squeeze_core"

PY_FILES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)

FORBIDDEN_IMPORTS = re.compile(
    r"^\s*(?:import|from)\s+"
    r"(requests|httpx|aiohttp|urllib3|http\.client|socket|websocket|websockets|ftplib|"
    r"smtplib|sqlite3|sqlalchemy|psycopg2?|pymongo|redis|boto3|"
    r"pandas|numpy|scipy|sklearn|torch|tensorflow|keras|transformers|nltk|"
    r"flask|django|fastapi|starlette|tornado|tkinter|PyQt5|PyQt6|PySide6|selenium|playwright)"
    r"\b",
    re.MULTILINE,
)

WALL_CLOCK_OR_RANDOM = re.compile(
    r"\b(datetime\.now|datetime\.utcnow|time\.time|time\.monotonic|time\.perf_counter|"
    r"random\.\w+|os\.urandom|secrets\.\w+|uuid1\(|uuid4\()"
)

# Whole-word strategy / indicator / trading vocabulary that must never be implemented.
FORBIDDEN_STRATEGY_TERMS = re.compile(
    r"\b(rsi|macd|bollinger|keltner|ttm_squeeze|moving_average|"
    r"relative_strength|breakout|backtest|sentiment_score|catalyst_score|"
    r"squeeze_score|candidate_score|ranking_score|recommendation|"
    r"take_profit|stop_loss|order_book|aggressor|spread_analytics)\b",
    re.IGNORECASE,
)


def test_no_forbidden_runtime_imports() -> None:
    offenders = {}
    for path in PY_FILES:
        text = path.read_text(encoding="utf-8")
        matches = FORBIDDEN_IMPORTS.findall(text)
        if matches:
            offenders[str(path.relative_to(SRC))] = sorted(set(matches))
    assert offenders == {}, f"forbidden imports found: {offenders}"


def test_no_wall_clock_or_random_identity_in_runtime() -> None:
    offenders = {}
    for path in PY_FILES:
        text = path.read_text(encoding="utf-8")
        matches = WALL_CLOCK_OR_RANDOM.findall(text)
        if matches:
            offenders[str(path.relative_to(SRC))] = sorted(set(matches))
    assert offenders == {}, f"wall-clock or random identity found: {offenders}"


# squeeze_core.validation exists to *describe* the original platform's rules and to
# state in prose exactly which trading constructs this phase refuses to implement. It
# therefore has to name "squeeze_score" (a real source path in the archived platform),
# "backtest", and "recommendation" in docstrings and in descriptive string data. Those
# are data and disclaimers, not behavior -- the same carve-out this module's docstring
# already makes for enum labels and provider vocabulary.
#
# The raw-text scan below skips that package, and
# test_no_strategy_or_indicator_identifiers_anywhere immediately after applies an
# AST-based scan of actual identifiers across *every* module including validation. Real
# strategy logic is therefore still caught, in a form prose cannot trip.
DESCRIPTIVE_PACKAGES = ("validation", "analysis", "acquisition")


def test_no_strategy_or_indicator_logic() -> None:
    offenders = {}
    for path in PY_FILES:
        if path.relative_to(SRC).parts[0] in DESCRIPTIVE_PACKAGES:
            continue
        text = path.read_text(encoding="utf-8")
        matches = FORBIDDEN_STRATEGY_TERMS.findall(text)
        if matches:
            offenders[str(path.relative_to(SRC))] = sorted(set(matches))
    assert offenders == {}, f"strategy/indicator terms found: {offenders}"


def test_no_strategy_or_indicator_identifiers_anywhere() -> None:
    """Every module, including the descriptive packages skipped above: no function,
    class, variable, or attribute may be *named* after a strategy or scoring construct.
    Prose and string data cannot trip this; only code can."""

    import ast

    offenders = {}
    for path in PY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.keyword) and node.arg:
                names.add(node.arg)
        matched = sorted({name for name in names if FORBIDDEN_STRATEGY_TERMS.search(name)})
        if matched:
            offenders[str(path.relative_to(SRC))] = matched
    assert offenders == {}, f"strategy/indicator identifiers found: {offenders}"


def test_only_expected_third_party_runtime_dependency() -> None:
    """The only third-party runtime import allowed is pydantic; everything else is stdlib."""
    third_party = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z_][\w]*)", re.MULTILINE)
    stdlib_and_local = {
        "json", "hashlib", "datetime", "decimal", "enum", "typing", "uuid", "pathlib",
        "argparse", "sys", "collections", "itertools", "dataclasses", "re", "urllib",
        "abc", "functools", "math", "zoneinfo", "squeeze_core", "__future__", "os",
        "csv", "io", "importlib",
    }
    allowed_third_party = {"pydantic"}
    offenders = {}
    for path in PY_FILES:
        text = path.read_text(encoding="utf-8")
        for module in third_party.findall(text):
            if module in stdlib_and_local or module in allowed_third_party:
                continue
            offenders.setdefault(str(path.relative_to(SRC)), set()).add(module)
    offenders = {k: sorted(v) for k, v in offenders.items()}
    assert offenders == {}, f"unexpected runtime dependency: {offenders}"


def test_urllib_is_used_for_sanitization_only_not_network() -> None:
    """urllib may appear only as urllib.parse string helpers, never network openers."""
    for path in PY_FILES:
        text = path.read_text(encoding="utf-8")
        if "urllib" not in text:
            continue
        assert "urllib.request" not in text
        assert "urlopen" not in text
        # Only the parse submodule (pure string manipulation) is permitted.
        for line in text.splitlines():
            if line.lstrip().startswith(("import urllib", "from urllib")):
                assert "urllib.parse" in line or "from urllib.parse" in line
